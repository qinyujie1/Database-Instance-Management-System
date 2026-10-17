from datetime import timedelta
from django.contrib.admin import AdminSite
from django.db.models import Avg, Max
from django.utils import timezone


class ConsoleAdminSite(AdminSite):
    site_header = "数据库实例管理系统"
    site_title = "数据库管理工作台"
    index_title = "数据库资源总览"
    index_template = "admin/console_index.html"

    def index(self, request, extra_context=None):
        from .models import Department, Cluster, Instance, PasswordRotation, InstanceSnapshot, RequestMetric, ProbeRecord
        recent_requests = RequestMetric.objects.filter(created_at__gte=timezone.now()-timedelta(days=1))
        metrics = recent_requests.aggregate(average=Avg("duration_ms"), maximum=Max("duration_ms"))
        context = {
            "department_count": Department.objects.count(),
            "cluster_count": Cluster.objects.count(),
            "instance_count": Instance.objects.count(),
            "rotation_count": PasswordRotation.objects.filter(success=True).count(),
            "rotation_failures": PasswordRotation.objects.filter(success=False).count(),
            "snapshot_count": InstanceSnapshot.objects.filter(date=timezone.localdate()).count(),
            "request_count": recent_requests.count(),
            "slow_count": recent_requests.filter(duration_ms__gte=1000).count(),
            "metrics": metrics,
            "recent_instances": Instance.objects.select_related("cluster__department").order_by("id")[:8],
            "recent_rotations": PasswordRotation.objects.select_related("instance").order_by("-id")[:5],
            "recent_requests": recent_requests[:6],
            "recent_probes": ProbeRecord.objects.select_related("instance")[:5],
            "today_snapshots": InstanceSnapshot.objects.filter(date=timezone.localdate(), dimension="department"),
            "latest_snapshot": InstanceSnapshot.objects.order_by("-captured_at").first(),
            "today": timezone.localdate(),
        }
        context.update(extra_context or {})
        return super().index(request, extra_context=context)
