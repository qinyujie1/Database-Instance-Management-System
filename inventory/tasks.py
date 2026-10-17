from celery import shared_task
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from .models import Department, Cluster, Instance, InstanceSnapshot
from .services import rotate_instance

@shared_task(bind=True, max_retries=3)
def rotate_passwords(self):
    local = timezone.localtime()
    cutoff = local.replace(hour=(local.hour // 12) * 12, minute=0, second=0, microsecond=0)
    results = {"rotated": 0, "failed": 0, "skipped": 0}
    for pk in Instance.objects.values_list("pk", flat=True).iterator():
        results[rotate_instance(pk, cutoff)] += 1
    if results["failed"]:
        raise self.retry(exc=RuntimeError("Some password rotations failed; inspect audit records"), countdown=300)
    return results

@shared_task
def snapshot_instances():
    today = timezone.localdate()
    with transaction.atomic():
        rows = []
        for dimension, queryset in [("department", Department.objects.annotate(total=Count("clusters__instances"))), ("cluster", Cluster.objects.annotate(total=Count("instances")))]:
            for obj in queryset:
                rows.append(InstanceSnapshot(date=today, dimension=dimension, object_id=obj.pk, object_name=obj.name, instance_count=obj.total))
        # First successful execution per day is immutable; retries cannot alter
        # the midnight snapshot if instances are edited later in the day.
        InstanceSnapshot.objects.bulk_create(rows, ignore_conflicts=True)
    return {"date": today.isoformat(), "rows": len(rows)}


@shared_task(bind=True, max_retries=3)
def rotate_one_password(self, instance_id, requested_at):
    from datetime import datetime
    result = rotate_instance(instance_id, cutoff=datetime.fromisoformat(requested_at))
    if result == "failed":
        raise self.retry(exc=RuntimeError("Rotation failed; inspect audit records"), countdown=300)
    return result
