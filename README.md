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

## 首次克隆与运行（Windows）

适用于其他人第一次下载本仓库并在自己的电脑运行。请使用 PowerShell，依次执行以下步骤；某一步报错时先解决错误，再继续。

### 1. 准备环境

- 安装 Git 和 Python 3.12，安装 Python 时勾选加入 PATH。
- 本地演示使用 SQLite 和 Celery 文件队列，无需另外安装 MySQL、PostgreSQL、Redis 或 Docker。
- 如果仓库是私有仓库，需要仓库所有者先授予访问权限，并使用有权限的 GitHub 账号认证。

检查安装结果：

```powershell
git --version
python --version
```

### 2. 克隆仓库

在你希望存放项目的目录打开 PowerShell：

```powershell
git clone https://github.com/qinyujie1/Database-Instance-Management-System.git
cd Database-Instance-Management-System
```

后续所有命令均在这个项目目录执行，不要进入其他项目目录。

### 3. 创建虚拟环境并安装依赖

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

这里直接调用虚拟环境中的 Python，不需要另外激活虚拟环境。

### 4. 生成本地配置和加密密钥

```powershell
.\.venv\Scripts\python.exe scripts/bootstrap.py
```

该命令生成本机 `.env`，包含独立的 Django 密钥、凭据加密密钥、调试和演示模式配置。已有 `.env` 会保留，不会覆盖。首次运行不需要复制仓库所有者的密钥或登录信息。

`.env` 和本地数据库不会提交到 GitHub。初始化后应保留 `.env`；丢失其中的 `CREDENTIAL_KEY` 将无法解密已有实例密码。

### 5. 创建数据库并导入模拟数据

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --instances 120
```

会创建本地 `db.sqlite3`，导入 **6 个部门、12 个集群、120 个模拟实例**，执行一次模拟密码轮换并生成当天统计快照，同时创建演示管理员。

`seed_demo` 可重复执行，不覆盖已有实例，也不重置已有管理员密码。模拟实例是管理记录，不会实际启动 120 个数据库服务。

### 6. 启动服务

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

脚本在后台启动三个进程：

| 进程 | 作用 |
| --- | --- |
| Django Web | 提供页面和 REST API，监听 `127.0.0.1:8010` |
| Celery Worker | 执行密码轮换、统计等后台任务 |
| Celery Beat | 按计划投递每天 00:00 / 12:00 的任务 |

日志和进程记录位于 `.runtime/`。自动任务需要 Worker 和 Beat 持续运行，电脑关机后不会执行；重新开机需再次启动服务。

### 7. 打开页面并登录

- 中文管理工作台：http://127.0.0.1:8010/admin/
- 首页：http://127.0.0.1:8010/
- 可交互 API：http://127.0.0.1:8010/api/
- **演示用户名：`admin`**
- **初始密码：`123456`**

上述账号适用于默认 `DEMO_MODE=1` 配置下首次运行 `seed_demo` 的情况。登录页会显示演示账号提示。API Token 和初始化登录信息保存在本机 `.local-credentials.txt`；如果后来修改密码，该文件不会自动更新。

关闭演示模式时，新建管理员使用随机密码，请查看本机 `.local-credentials.txt`。已有管理员密码不会因重复导入数据而重置。对外部署前应更换演示密码并关闭演示模式。

### 8. 验证功能

- 在工作台查看部门、集群和实例数量，并进入列表新增、编辑或删除记录。
- 选择 `demo-db-001` 点击「TCP 探测 / 密码轮换」：它指向本机 `8010` 端口，网站运行时可演示端口可达。
- 选择 `demo-db-120` 探测：它指向本机 `65000` 端口，若没有服务监听，会显示连接被拒绝及中文排查建议。
- 提交模拟实例的密码轮换后，稍后查看「密码轮换记录」确认实际结果；任务提交成功不等于已执行成功。
- 查看「每日统计快照」和「请求耗时监控」，验证统计与请求记录。

也可以运行项目检查和自动化测试：

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test
```

### 9. 停止或再次启动

使用完毕后，在项目目录停止后台服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
```

下次使用时，只需进入项目目录并执行启动脚本，不必重新克隆、生成密钥或导入数据：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

## 已有项目如何更新代码

在已有项目目录执行。先检查本地修改；如有自己修改的文件，应先提交或妥善保存，避免与拉取的更新冲突。

```powershell
git status
powershell -ExecutionPolicy Bypass -File scripts/stop.ps1
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py check
powershell -ExecutionPolicy Bypass -File scripts/start.ps1
```

各步成功后再继续；如果 `git pull --ff-only` 提示分支分叉，应先处理分支差异。拉取后要执行迁移，因为新版本可能新增表或字段。更新时保留原有 `.env`、`db.sqlite3` 和 `.local-credentials.txt`，不需要重新执行 `seed_demo`。页面更新后按 **Ctrl + F5** 刷新。

## 本地启动常见问题

| 现象 | 处理方式 |
| --- | --- |
| 找不到 `git` 或 `python` | 确认已安装并加入 PATH，然后重新打开 PowerShell |
| 提示缺少 Django 等依赖 | 在项目目录使用 `.venv\Scripts\python.exe`，并执行依赖安装命令 |
| 提示缺少配置或密钥 | 首次运行先执行 `scripts/bootstrap.py`；已有数据时应恢复原有 `.env` |
| 提示数据库表不存在 | 执行 `manage.py migrate` 后再启动 |
| 提示已有服务在运行 | 先运行 `scripts/stop.ps1`，再运行启动脚本 |
| 8010 端口被占用 | 确认是否已运行本项目或其他服务，停止对应服务后再启动 |
| 网页打不开或任务一直不执行 | 检查 `.runtime/web.err.log`、`.runtime/worker.err.log`、`.runtime/beat.err.log`；启动脚本的提示不替代日志检查 |
| `admin / 123456` 无法登录 | 确认已导入模拟数据、首次创建账号时启用了演示模式，且密码没有后来被修改 |
| 探测 65000 端口不可达 | 若该端口没有服务监听，这是正常检测结果；可用指向 8010 的模拟实例对比测试 |

本地 SQLite + Celery filesystem transport 组合用于单 worker 演示。Celery 官方不支持 Windows，本项目在本机通过 solo 模式验证运行；Linux / Docker 环境请参阅下方部署章节。

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

该配置使用持久化 PostgreSQL、Redis、Web、Worker、Beat。容器内模拟实例的 `127.0.0.1:8010` 并非 Windows Web 端口，TCP 结果会与本机不同。Compose 仍使用 Django 开发服务器供验题；生产需要 WSGI 服务器、HTTPS、`DJANGO_DEBUG=0`、`DEMO_MODE=0`、严格 `ALLOWED_HOSTS`、密钥托管和备份，不应直接用 runserver 对外服务。

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

登录页采用响应式双栏设计，支持密码显隐、键盘操作和中文错误提示。调试开关使用 `DJANGO_DEBUG`，避免与操作系统已有的通用 `DEBUG` 环境变量冲突。


## 中文功能工作台

登录后 `/` 与 `/admin/` 均展示统一工作台，首页直接列出五项需求和操作入口。

- **资源管理**：中文部门、集群与实例列表；实例支持页面新增、编辑、删除，新增密码加密入库，编辑时留空保留密码；轮换中禁止修改和删除。
- **TCP 探测**：实例列表的「TCP 探测 / 密码轮换」进入操作页，点击后展示可达性与耗时，并保存探测历史；原 REST API 同样记录结果。
- **密码轮换**：首页显示最近成功/失败记录与调度规则；单实例可手动提交 Celery 任务，提交提示不代表执行成功，实际结果在轮换记录中查看。
- **每日统计**：首页展示今日部门分布；统计列表可按日期和维度筛选，管理员可手动提交当日补采任务。
- **请求耗时**：中间件额外保存最近 1000 条业务请求的路由模板、方法、状态码和耗时，首页显示保留记录中最近 24 小时的平均耗时及慢请求数量。统计不含请求体、密码、查询参数或静态文件。监控写入失败只记日志，不阻断业务。

首页显示的是已记录的执行结果和调度配置，不将进程状态伪装成“运行正常”。SQLite 请求监控适合本地演示，高流量环境应改用异步监控采集。新增界面依然遵循 Django 模型权限和 CSRF 校验。

实例列表支持显式升降序选择、当前排序提示及可点击表头，默认按实例编号升序。探测接口返回 `reason`、`suggestion` 和 `error_number`，页面与历史记录同步显示中文原因及排查建议；错误原因属于基于连接结果的判断，不能代替服务器日志诊断。
