from django.contrib import admin
from .models import Department, Cluster, Instance, PasswordRotation, InstanceSnapshot
admin.site.site_header = "数据库实例管理系统"
admin.site.site_title = "DB Instance Manager"
admin.site.register(Department)
admin.site.register(Cluster)

@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    list_display = ["name", "cluster", "host", "port", "engine", "username", "last_rotated_at"]
    list_filter = ["engine", "cluster__department", "cluster"]
    search_fields = ["name", "host", "username"]
    exclude = ["password_encrypted", "pending_password_encrypted", "rotation_token", "rotation_started_at"]
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(PasswordRotation)
class RotationAdmin(admin.ModelAdmin):
    list_display = ["instance", "created_at", "success", "error_code"]
    exclude = ["password_encrypted"]
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(InstanceSnapshot)
class SnapshotAdmin(admin.ModelAdmin):
    list_display = ["date", "dimension", "object_name", "instance_count"]
    list_filter = ["date", "dimension"]
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False
