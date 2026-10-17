# 数据库实例管理系统

基于 **Python 3.12 / Django 5.2 / Django REST Framework / Celery 5.6** 的笔试项目，包含管理看板、REST API、加密凭据、定时任务、请求计时和自动化测试。

## 题目与实现

| 要求 | 实现 |
| --- | --- |
| 实例、集群、部门模型 | Department → Cluster → Instance；部门由集群确定，避免双重归属冲突；删除父对象采用 PROTECT |
| 增删改查 | `/api/departments/`、`/api/clusters/`、`/api/instances/`，支持 GET/POST/PUT/PATCH/DELETE |
| TCP 探测 | `POST /api/instances/{id}/probe/`，3 秒超时、网段白名单、管理员鉴权、30 次/分钟限流 |
| 12 小时密码轮换 | Celery Beat 每天上海时间 00:00、12:00 执行；随机密码、Fernet 认证加密、加密历史记录 |
| 每日数量统计 | 每天 00:00 保存部门与集群两个维度的快照，包含零实例分组；唯一约束防止重复写入 |
| 请求耗时 | `perf_counter()` 计时，结构化日志及 `X-Request-Duration-Ms` 响应头 |

## Windows 本地启动

在项目目录执行（Python 3.12+）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts/bootstrap.py
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --instances 120
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

- 管理看板：http://127.0.0.1:8010/
- Django 管理后台：http://127.0.0.1:8010/admin/
- 可交互 API：http://127.0.0.1:8010/api/
- 用户名：`admin`；**随机密码和 API Token 在本地 `.local-credentials.txt` 中**。
- `seed_demo` 可重复运行，不会覆盖已有实例或重置管理员密码。演示数据为 6 个部门、12 个集群、120 个模拟实例，并实际执行一次模拟凭据轮换、生成当天快照。
- 每三个模拟实例有一个指向本地 Web 端口 8010，便于演示 TCP 可达；其余指向 65000（若此端口有其他服务监听，也可能可达）。TCP 可达仅代表端口开放，不代表数据库可正常认证。
- 后台运行三个进程：Django Web、Celery solo worker、Celery Beat。日志和进程记录位于 `.runtime/`。

停止：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
```

本地使用 SQLite + Celery filesystem transport，无需安装 Redis。**该组合用于单 worker 演示**，不是生产部署。Celery 官方不支持 Windows；此处使用 solo 模式验证本机运行，正式环境使用 Linux + PostgreSQL + Redis。

## API 使用

所有业务接口要求管理员（`is_staff=True`），支持 Session + CSRF 或 Token Authentication。先通过 `/admin/` 登录，即可在浏览器中查看和编辑 API。接口不会返回明文密码或密文。

PowerShell 示例（读取本机 Token，不要把该文件上传）：

```powershell
$line = Get-Content .local-credentials.txt | Where-Object { $_ -like 'API Token:*' }
$token = $line.Substring(11).Trim()
$headers = @{ Authorization = "Token $token" }
Invoke-RestMethod http://127.0.0.1:8010/api/instances/ -Headers $headers
Invoke-RestMethod http://127.0.0.1:8010/api/instances/1/probe/ -Method Post -Headers $headers
```

| 路径 | 方法 | 用途 |
| --- | --- | --- |
| `/api/departments/`、`/api/clusters/`、`/api/instances/` | GET、POST | 分页列表、新建 |
| 上述路径 + `{id}/` | GET、PUT、PATCH、DELETE | 查询、替换、更新、删除 |
| `/api/instances/{id}/probe/` | POST | 返回 reachable、latency_ms、error |
| `/api/snapshots/?date=2026-10-17&dimension=department` | GET | 只读统计记录 |
| `/api/rotations/` | GET | 只读轮换审计，不暴露密码 |

实例列表支持 `?department=1&cluster=1&page=2`。每页 25 条。

新建实例 JSON 示例（需先创建对应集群）：

```json
{
  "name": "example-db",
  "cluster": 1,
  "host": "127.0.0.1",
  "port": 5432,
  "engine": "mock",
  "database": "postgres",
  "username": "app_user",
  "password": "replace-with-a-strong-password"
}
```

`host` 必须为 IP，避免 DNS 重绑定；端口范围 1–65535。密码必填且至少 12 字符，PATCH 时可省略。更新 `password` 表示登记已知凭据，**不会立即修改远程数据库密码**。父对象仍有关联时删除返回 409；凭据轮换中或等待恢复时禁止修改/删除该实例。

## 凭据与真实数据库改密

- 使用 `secrets` 生成随机密码，Fernet 认证加密保存当前密码、待确认密码和成功轮换历史；密钥由环境变量 `CREDENTIAL_KEY` 提供。
- `.env`、本地凭据、SQLite 文件、日志、虚拟环境均被 Git 忽略。妥善备份加密密钥，丢失后无法恢复既有凭据；生产环境应使用密钥管理服务。历史密文同样依赖该密钥。
- `engine=mock`：仅更新系统管理的模拟凭据，不连接真实数据库。
- `engine=postgresql`：用当前账号连接目标数据库，执行 `ALTER ROLE` 修改该账号真实密码，必须允许 SSL 连接（当前 `sslmode=require`）、允许账号自行改密且凭据正确；数据库密码策略也必须允许所生成的随机密码。部署时可进一步按企业证书策略改为 `verify-full`。
- 真实 PostgreSQL 改密驱动已实现并做隔离单元测试，但本地没有真实 PostgreSQL 服务，因此未完成真实数据库集成测试。MySQL 等其他引擎未冒充支持，需另写适配器。
- 改密前先持久化候选密码。若远端成功、本地提交前进程中断，下次用旧密码或候选密码重连，并重复应用相同候选值完成恢复。
- 原子认领及 10 分钟租约避免重复执行；每个 12 小时周期跳过已成功实例。单实例失败记录异常类别，不写入原始异常内容；整批失败项最多延迟 5 分钟重试 3 次。失败后保留候选密文，下一调度周期仍可恢复。
- 生产必须只运行一个 Beat。首次任务触发发生在下一个 00:00 / 12:00，服务停机期间不承诺准点执行。任务恢复后按当前周期补做；历史午夜库存无法在停机后准确重建。
- 更改共享账号密码可能影响业务连接，真实接入前需要业务系统同步取用最新密码。此项目没有提供明文密码读取 API。

## 每日统计口径

统计的是 **任务实际执行时** 的存量数量，按 Asia/Shanghai 当前日期写入，不是前一日新增量。分别按部门、集群聚合，包含空部门/空集群；历史记录保留对象名称和 ID，不随对象删除消失。同一日期同一维度同一对象已有快照时不覆盖。`captured_at` 记录真实采集时间；首次初始化的当日快照属于初始化时采样，不伪装成午夜历史数据。

## 请求耗时与网络边界

计时中间件位于最外层，覆盖正常响应、404 和异常路径；仅记录 HTTP 方法、路由模板、状态码及耗时，不记录查询参数、请求体或凭据。耗时不包含流式响应内容发送完毕和客户端接收时间。

`PROBE_ALLOWED_NETWORKS` 默认包含环回和 RFC1918 私网，可通过 `.env` 配置 CIDR 列表。探测与真实改密均应用该白名单。管理员仍应只登记获授权的企业实例。

## Linux / Docker Compose

安装 Docker Compose 后，先按前面步骤生成 `.env`，另在其中设置强随机 `POSTGRES_PASSWORD`：

```bash
docker compose up --build -d
docker compose exec web python manage.py createsuperuser
# 可选导入模拟数据
docker compose exec web python manage.py seed_demo --instances 120
```

该配置使用持久化 PostgreSQL、Redis、Web、Worker、Beat。容器内模拟实例的 `127.0.0.1:8010` 并非 Windows Web 端口，TCP 结果会与本机不同。Compose 仍使用 Django 开发服务器供验题；生产需要 WSGI 服务器、HTTPS、`DEBUG=0`、严格 `ALLOWED_HOSTS`、密钥托管和备份，不应直接用 runserver 对外服务。

## 测试与手动任务

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
# 向真实队列提交，不使用 eager 模式
.\.venv\Scripts\python.exe manage.py shell -c "from inventory.tasks import snapshot_instances; print(snapshot_instances.delay().id)"
```

测试覆盖三类模型 CRUD、鉴权、密文保护、端口校验、关联删除、TCP 成功/超时/白名单、改密成功与失败恢复、租约、重复调度、统计幂等与空分组、计时及看板。GitHub Actions 自动运行检查和测试。

## 目录

```text
config/                     Django / Celery 配置
inventory/models.py         业务模型
inventory/serializers.py     输入验证及敏感字段控制
inventory/views.py          REST API 和看板
inventory/services.py       TCP 探测、远端改密及恢复
inventory/tasks.py          Celery 定时任务
inventory/middleware.py     请求耗时
inventory/tests.py          自动化测试
inventory/management/       模拟数据命令
scripts/                    密钥生成及本地启停
templates/                  看板
compose.yaml                PostgreSQL + Redis 运行方案
```

参考：[Celery 定时任务](https://docs.celeryq.dev/en/stable/userguide/periodic-tasks.html)、[Celery Windows 支持说明](https://docs.celeryq.dev/en/stable/faq.html#does-celery-support-windows)、[Django 部署检查清单](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/)。
