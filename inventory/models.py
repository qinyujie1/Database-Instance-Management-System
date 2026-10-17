from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    def __str__(self):
        return self.name

class Cluster(models.Model):
    name = models.CharField(max_length=100, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name="clusters")
    description = models.TextField(blank=True)
    def __str__(self):
        return self.name

class Instance(models.Model):
    name = models.CharField(max_length=100, unique=True)
    cluster = models.ForeignKey(Cluster, on_delete=models.PROTECT, related_name="instances")
    host = models.GenericIPAddressField()
    port = models.PositiveIntegerField(validators=[MinValueValidator(1), MaxValueValidator(65535)])
    engine = models.CharField(max_length=20, choices=[("mock", "模拟实例"), ("postgresql", "PostgreSQL")], default="mock")
    database = models.CharField(max_length=100, default="postgres")
    username = models.CharField(max_length=100)
    password_encrypted = models.TextField(editable=False)
    pending_password_encrypted = models.TextField(blank=True, editable=False)
    rotation_token = models.CharField(max_length=36, blank=True, editable=False)
    rotation_started_at = models.DateTimeField(null=True, blank=True, editable=False)
    last_rotated_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return self.name

class PasswordRotation(models.Model):
    instance = models.ForeignKey(Instance, on_delete=models.CASCADE, related_name="rotations")
    created_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField()
    password_encrypted = models.TextField(blank=True, editable=False)
    error_code = models.CharField(max_length=100, blank=True)

class InstanceSnapshot(models.Model):
    date = models.DateField()
    dimension = models.CharField(max_length=20, choices=[("department", "部门"), ("cluster", "集群")])
    object_id = models.PositiveBigIntegerField()
    object_name = models.CharField(max_length=100)
    instance_count = models.PositiveIntegerField()
    captured_at = models.DateTimeField(auto_now=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["date", "dimension", "object_id"], name="unique_daily_dimension")]
        ordering = ["-date", "dimension", "object_id"]
