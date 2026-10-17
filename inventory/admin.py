from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponseNotAllowed
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from .crypto import encrypt
from .models import Department, Cluster, Instance, PasswordRotation, InstanceSnapshot, RequestMetric, ProbeRecord
from .services import probe


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ["name", "description", "cluster_total"]
    search_fields = ["name"]
    @admin.display(description="集群数量")
    def cluster_total(self, obj):
        return obj.clusters.count()


@admin.register(Cluster)
class ClusterAdmin(admin.ModelAdmin):
    list_display = ["name", "department", "description", "instance_total"]
    list_filter = ["department"]
    search_fields = ["name"]
    list_select_related = ["department"]
    @admin.display(description="实例数量")
    def instance_total(self, obj):
        return obj.instances.count()


class InstanceForm(forms.ModelForm):
    password = forms.CharField(label="数据库密码", required=False, min_length=12, max_length=256, strip=False, widget=forms.PasswordInput(render_value=False), help_text="新增时必填，至少 12 个字符；编辑时留空保留原密码。这里只登记连接凭据，自动轮换会修改远端账号密码。")
    class Meta:
        model = Instance
        fields = ["name", "cluster", "host", "port", "engine", "database", "username", "password"]
    def clean(self):
        data = super().clean()
        if not self.instance.pk and not data.get("password"):
            self.add_error("password", "新增实例时必须填写数据库密码。")
        if self.instance.pk and (self.instance.rotation_token or self.instance.pending_password_encrypted):
            raise forms.ValidationError("凭据正在轮换或等待恢复，暂时不能修改。")
        return data


@admin.register(Instance)
class InstanceAdmin(admin.ModelAdmin):
    form = InstanceForm
    actions = None
    list_display = ["name", "department_name", "cluster", "host", "port", "engine", "username", "last_rotated_at", "credential_state", "operations"]
    list_filter = ["engine", "cluster__department", "cluster"]
    list_select_related = ["cluster__department"]
    search_fields = ["name", "host", "username"]
    readonly_fields = ["last_rotated_at", "credential_state"]
    fields = ["name", "cluster", "host", "port", "engine", "database", "username", "password", "last_rotated_at", "credential_state"]
    list_per_page = 25

    def get_object(self, request, object_id, from_field=None):
        obj = super().get_object(request, object_id, from_field)
        if obj and request.method == "POST" and transaction.get_connection().in_atomic_block:
            obj = Instance.objects.select_for_update().get(pk=obj.pk)
        return obj

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get("password"):
            obj.password_encrypted = encrypt(form.cleaned_data["password"])
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and (obj.rotation_token or obj.pending_password_encrypted))

    @admin.display(description="所属部门")
    def department_name(self, obj):
        return obj.cluster.department.name

    @admin.display(description="凭据状态")
    def credential_state(self, obj):
        if obj.rotation_token:
            return "正在轮换"
        return "等待重试恢复" if obj.pending_password_encrypted else "已加密保存"

    @admin.display(description="功能操作")
    def operations(self, obj):
        return format_html('<a href="{}">TCP 探测 / 密码轮换 →</a>', reverse("admin:inventory_instance_tools", args=[obj.pk]))

    def get_urls(self):
        return [path("<int:object_id>/tools/", self.admin_site.admin_view(self.tools_view), name="inventory_instance_tools")] + super().get_urls()

    def tools_view(self, request, object_id):
        from .tasks import rotate_one_password
        from .views import ProbeThrottle
        if request.method not in ["GET", "POST"]:
            return HttpResponseNotAllowed(["GET", "POST"])
        instance = self.get_object(request, str(object_id))
        if instance is None:
            raise Http404
        if not self.has_view_permission(request, instance):
            raise PermissionDenied
        result = None
        error = None
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "probe":
                if not ProbeThrottle().allow_request(request, self):
                    error = "探测过于频繁，请稍后再试（每分钟最多 30 次）。"
                else:
                    try:
                        result = probe(instance)
                    except ValueError:
                        error = "目标 IP 不在允许探测的网段内。"
            elif action == "rotate":
                if not self.has_change_permission(request, instance):
                    raise PermissionDenied
                try:
                    task = rotate_one_password.delay(instance.pk, timezone.now().isoformat())
                    self.message_user(request, f"密码轮换任务已提交：{task.id}。这不代表轮换已完成，请稍后查看轮换记录。", messages.SUCCESS)
                    return redirect("admin:inventory_passwordrotation_changelist")
                except Exception:
                    error = "任务提交失败，请检查消息队列和 Worker。"
            else:
                error = "未知操作。"
        context = {**self.admin_site.each_context(request), "title": "TCP 探测与密码轮换", "instance": instance, "result": result, "error": error, "opts": self.model._meta, "recent_probes": ProbeRecord.objects.filter(instance=instance)[:8], "can_rotate": self.has_change_permission(request, instance)}
        return TemplateResponse(request, "admin/instance_tools.html", context)


class ReadOnlyAdmin(admin.ModelAdmin):
    actions = None
    def has_add_permission(self, request):
        return False
    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PasswordRotation)
class RotationAdmin(ReadOnlyAdmin):
    list_display = ["instance", "created_at", "success", "error_code", "encrypted_status"]
    list_filter = ["success", "created_at"]
    search_fields = ["instance__name"]
    exclude = ["password_encrypted"]
    list_select_related = ["instance"]
    @admin.display(description="密码记录")
    def encrypted_status(self, obj):
        return "已加密归档" if obj.password_encrypted else "未修改当前密码"


@admin.register(InstanceSnapshot)
class SnapshotAdmin(ReadOnlyAdmin):
    list_display = ["date", "dimension", "object_name", "instance_count", "captured_at"]
    list_filter = ["date", "dimension"]
    search_fields = ["object_name"]
    date_hierarchy = "date"
    change_list_template = "admin/snapshot_list.html"
    def get_urls(self):
        return [path("capture/", self.admin_site.admin_view(self.capture), name="inventory_snapshot_capture")] + super().get_urls()
    def capture(self, request):
        from .tasks import snapshot_instances
        if request.method != "POST":
            return HttpResponseNotAllowed(["POST"])
        if not request.user.is_superuser:
            raise PermissionDenied
        try:
            task = snapshot_instances.delay()
            self.message_user(request, f"统计任务已提交：{task.id}。当日已有快照不会被覆盖，请稍后刷新查看。", messages.SUCCESS)
        except Exception:
            self.message_user(request, "统计任务提交失败，请检查队列连接。", messages.ERROR)
        return redirect("admin:inventory_instancesnapshot_changelist")


@admin.register(RequestMetric)
class RequestMetricAdmin(ReadOnlyAdmin):
    list_display = ["created_at", "method", "route", "status_code", "elapsed", "speed"]
    list_filter = ["method", "status_code"]
    search_fields = ["route"]
    list_per_page = 30
    @admin.display(description="耗时（毫秒）", ordering="duration_ms")
    def elapsed(self, obj):
        return f"{obj.duration_ms:.2f} ms"
    @admin.display(description="耗时分级")
    def speed(self, obj):
        return "慢请求 ≥ 1000 ms" if obj.duration_ms >= 1000 else "正常"


@admin.register(ProbeRecord)
class ProbeRecordAdmin(ReadOnlyAdmin):
    list_display = ["instance", "reachable", "latency_ms", "error", "created_at"]
    list_filter = ["reachable", "created_at"]
    search_fields = ["instance__name"]
    list_select_related = ["instance"]
