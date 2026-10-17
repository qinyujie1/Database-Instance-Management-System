from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Department(models.Model):
    class Meta:
        verbose_name = "部门管理"
        verbose_name_plural = verbose_name

    name = models.CharField(verbose_name="名称", max_length=100, unique=True)
    description = models.TextField(verbose_name="说明", blank=True)
    def __str__(self):
        return self.name

class Cluster(models.Model):
    class Meta:
        verbose_name = "集群管理"
        verbose_name_plural = verbose_name

    name = models.CharField(verbose_name="名称", max_length=100, unique=True)
    department = models.ForeignKey(Department, verbose_name="所属部门", on_delete=models.PROTECT, related_name="clusters")
    description = models.TextField(verbose_name="说明", blank=True)
    def __str__(self):
        return self.name

class Instance(models.Model):
    class Meta:
        verbose_name = "实例管理"
        verbose_name_plural = verbose_name

    name = models.CharField(verbose_name="名称", max_length=100, unique=True)
    cluster = models.ForeignKey(Cluster, verbose_name="所属集群", on_delete=models.PROTECT, related_name="instances")
    host = models.GenericIPAddressField(verbose_name="IP 地址", )
    port = models.PositiveIntegerField(verbose_name="TCP 端口", validators=[MinValueValidator(1), MaxValueValidator(65535)])
    engine = models.CharField(verbose_name="数据库类型", max_length=20, choices=[("mock", "模拟实例"), ("postgresql", "PostgreSQL")], default="mock")
    database = models.CharField(verbose_name="数据库名称", max_length=100, default="postgres")
    username = models.CharField(verbose_name="数据库账号", max_length=100)
    password_encrypted = models.TextField(editable=False)
    pending_password_encrypted = models.TextField(blank=True, editable=False)
    rotation_token = models.CharField(max_length=36, blank=True, editable=False)
    rotation_started_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_rotated_at = models.DateTimeField(verbose_name="最近轮换时间", default=timezone.now)
    created_at = models.DateTimeField(verbose_name="记录时间", auto_now_add=True)
    def __str__(self):
        return self.name

class PasswordRotation(models.Model):
    class Meta:
        verbose_name = "密码轮换记录"
        verbose_name_plural = verbose_name

    instance = models.ForeignKey(Instance, verbose_name="数据库实例", on_delete=models.CASCADE, related_name="rotations")
    created_at = models.DateTimeField(verbose_name="记录时间", auto_now_add=True)
    success = models.BooleanField(verbose_name="是否成功", )
    password_encrypted = models.TextField(blank=True, editable=False)
    error_code = models.CharField(verbose_name="错误类型", max_length=100, blank=True)

class InstanceSnapshot(models.Model):
    date = models.DateField(verbose_name="统计日期", )
    dimension = models.CharField(verbose_name="统计维度", max_length=20, choices=[("department", "部门"), ("cluster", "集群")])
    object_id = models.PositiveBigIntegerField(verbose_name="对象 ID", )
    object_name = models.CharField(verbose_name="对象名称", max_length=100)
    instance_count = models.PositiveIntegerField(verbose_name="实例数量", )
    captured_at = models.DateTimeField(verbose_name="采集时间", auto_now=True)
    class Meta:
        verbose_name = "每日统计快照"
        verbose_name_plural = verbose_name
        constraints = [models.UniqueConstraint(fields=["date", "dimension", "object_id"], name="unique_daily_dimension")]
        ordering = ["-date", "dimension", "object_id"]


class RequestMetric(models.Model):
    method = models.CharField("请求方法", max_length=12)
    route = models.CharField("请求路由", max_length=255)
    status_code = models.PositiveIntegerField("响应状态码")
    duration_ms = models.FloatField("耗时（毫秒）")
    created_at = models.DateTimeField("请求时间", auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "请求耗时监控"
        verbose_name_plural = verbose_name
        ordering = ["-id"]


class ProbeRecord(models.Model):
    instance = models.ForeignKey(Instance, verbose_name="数据库实例", on_delete=models.CASCADE)
    reachable = models.BooleanField("端口可达")
    latency_ms = models.FloatField("探测耗时（毫秒）")
    error = models.CharField("错误类型", max_length=100, blank=True)
    created_at = models.DateTimeField("探测时间", auto_now_add=True)

    class Meta:
        verbose_name = "TCP 探测记录"
        verbose_name_plural = verbose_name
        ordering = ["-id"]
