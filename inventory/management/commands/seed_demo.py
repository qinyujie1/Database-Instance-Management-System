import secrets
from datetime import timedelta
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from rest_framework.authtoken.models import Token
from inventory.crypto import encrypt, new_password
from inventory.models import Department, Cluster, Instance
from inventory.services import rotate_instance
from inventory.tasks import snapshot_instances

class Command(BaseCommand):
    help = "幂等创建模拟部门、集群、实例及本地管理员；不覆盖已有实例或用户密码。"
    def add_arguments(self, parser):
        parser.add_argument("--instances", type=int, default=120)
    def handle(self, *args, **options):
        count = options["instances"]
        if not 1 <= count <= 10000:
            from django.core.management.base import CommandError
            raise CommandError("instances 必须介于 1 和 10000")
        with transaction.atomic():
            departments = [Department.objects.get_or_create(name=name)[0] for name in ["研发中心", "数据平台", "财务部", "运营部", "客户服务", "基础设施"]]
            clusters = [Cluster.objects.get_or_create(name=f"demo-cluster-{i+1:02}", defaults={"department": departments[i // 2]})[0] for i in range(12)]
            created_ids = []
            for i in range(count):
                instance, created = Instance.objects.get_or_create(name=f"demo-db-{i+1:03}", defaults={"cluster": clusters[i % 12], "host": "127.0.0.1", "port": 8010 if i % 3 == 0 else 65000, "engine": "mock", "username": f"demo_user_{i+1:03}", "password_encrypted": encrypt(new_password()), "last_rotated_at": timezone.now() - timedelta(hours=13)})
                if created:
                    created_ids.append(instance.pk)
            user, created = get_user_model().objects.get_or_create(username="admin", defaults={"is_staff": True, "is_superuser": True})
            if created:
                password = "123456" if settings.DEMO_MODE else secrets.token_urlsafe(18)
                user.set_password(password)
                user.save()
                token = Token.objects.create(user=user)
                (settings.BASE_DIR / ".local-credentials.txt").write_text(f"URL: http://127.0.0.1:8010/\nUsername: admin\nPassword: {password}\nAPI Token: {token.key}\n", encoding="utf-8")
        for pk in created_ids:
            rotate_instance(pk)
        snapshot_instances()
        self.stdout.write(self.style.SUCCESS(f"新增 {len(created_ids)} 个模拟实例；共 {Instance.objects.count()} 个实例。登录信息在 .local-credentials.txt（不会提交）。"))
