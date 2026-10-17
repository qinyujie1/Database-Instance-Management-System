from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse
from django.utils import timezone
from rest_framework.test import APIClient
from .crypto import encrypt, decrypt
from .models import Department, Cluster, Instance, InstanceSnapshot, PasswordRotation
from .services import rotate_instance
from .tasks import snapshot_instances, rotate_passwords
from .middleware import RequestTimingMiddleware

class SystemTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("tester", password="test-Only-password", is_staff=True)
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.department = Department.objects.create(name="研发")
        self.cluster = Cluster.objects.create(name="cluster-a", department=self.department)
        self.instance = Instance.objects.create(name="db-a", cluster=self.cluster, host="127.0.0.1", port=5432, username="dbuser", password_encrypted=encrypt("initial-password"))
    def test_api_requires_staff(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/instances/").status_code, 401)
        self.user.is_staff = False
        self.user.save()
        self.client.force_authenticate(self.user)
        self.assertEqual(self.client.get("/api/instances/").status_code, 403)
    def test_crud_and_secret_redaction(self):
        response = self.client.post("/api/instances/", {"name": "db-b", "cluster": self.cluster.pk, "host": "127.0.0.1", "port": 5432, "username": "dbuser", "password": "created-password"}, format="json")
        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        self.assertNotIn("password_encrypted", response.data)
        obj = Instance.objects.get(pk=response.data["id"])
        self.assertEqual(decrypt(obj.password_encrypted), "created-password")
        url = f"/api/instances/{obj.pk}/"
        self.assertEqual(self.client.patch(url, {"name": "updated"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)
    def test_department_and_cluster_crud(self):
        department = self.client.post("/api/departments/", {"name": "new"}, format="json")
        self.assertEqual(department.status_code, 201)
        department_url = f'/api/departments/{department.data["id"]}/'
        self.assertEqual(self.client.patch(department_url, {"description": "edited"}, format="json").status_code, 200)
        cluster = self.client.post("/api/clusters/", {"name": "new-cluster", "department": department.data["id"]}, format="json")
        self.assertEqual(cluster.status_code, 201)
        cluster_url = f'/api/clusters/{cluster.data["id"]}/'
        self.assertEqual(self.client.get(cluster_url).status_code, 200)
        self.assertEqual(self.client.put(cluster_url, {"name": "updated-cluster", "department": department.data["id"]}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(cluster_url).status_code, 204)
        self.assertEqual(self.client.delete(department_url).status_code, 204)
    def test_invalid_port(self):
        self.assertEqual(self.client.patch(f"/api/instances/{self.instance.pk}/", {"port": 70000}, format="json").status_code, 400)
    def test_protected_delete(self):
        self.assertEqual(self.client.delete(f"/api/clusters/{self.cluster.pk}/").status_code, 409)
        self.assertEqual(self.client.delete(f"/api/departments/{self.department.pk}/").status_code, 409)
    @patch("inventory.services.socket.create_connection")
    def test_probe_reachable(self, connection):
        response = self.client.post(f"/api/instances/{self.instance.pk}/probe/")
        self.assertTrue(response.data["reachable"])
        connection.assert_called_once_with(("127.0.0.1", 5432), timeout=3)
    @patch("inventory.services.socket.create_connection", side_effect=TimeoutError)
    def test_probe_timeout(self, connection):
        response = self.client.post(f"/api/instances/{self.instance.pk}/probe/")
        self.assertFalse(response.data["reachable"])
        self.assertEqual(response.data["error"], "TimeoutError")
    def test_probe_blocks_unapproved_address(self):
        self.instance.host = "169.254.169.254"
        self.instance.save()
        self.assertEqual(self.client.post(f"/api/instances/{self.instance.pk}/probe/").status_code, 400)
    def test_rotation_encrypted_audit(self):
        before = self.instance.password_encrypted
        self.assertEqual(rotate_instance(self.instance.pk), "rotated")
        self.instance.refresh_from_db()
        self.assertNotEqual(before, self.instance.password_encrypted)
        audit = PasswordRotation.objects.get()
        self.assertTrue(audit.success)
        self.assertEqual(audit.password_encrypted, self.instance.password_encrypted)
        self.assertNotIn(decrypt(audit.password_encrypted), str(self.client.get("/api/rotations/").data))
    @patch("inventory.services.apply_remote_password", side_effect=ConnectionError("sensitive-password"))
    def test_failed_rotation_preserves_current_secret(self, remote):
        before = self.instance.password_encrypted
        self.assertEqual(rotate_instance(self.instance.pk), "failed")
        self.instance.refresh_from_db()
        self.assertEqual(before, self.instance.password_encrypted)
        candidate = self.instance.pending_password_encrypted
        self.assertTrue(candidate)
        self.assertEqual(PasswordRotation.objects.get().error_code, "ConnectionError")
        remote.side_effect = None
        self.assertEqual(rotate_instance(self.instance.pk), "rotated")
        self.instance.refresh_from_db()
        self.assertEqual(candidate, self.instance.password_encrypted)
    def test_lock_prevents_duplicate_rotation_and_edits(self):
        self.instance.rotation_token = "busy"
        self.instance.rotation_started_at = timezone.now()
        self.instance.save()
        self.assertEqual(rotate_instance(self.instance.pk), "skipped")
        self.assertEqual(self.client.patch(f"/api/instances/{self.instance.pk}/", {"name": "new"}, format="json").status_code, 409)
    def test_expired_lock_can_recover(self):
        self.instance.rotation_token = "stale"
        self.instance.rotation_started_at = timezone.now() - timedelta(minutes=11)
        self.instance.save()
        self.assertEqual(rotate_instance(self.instance.pk), "rotated")
    def test_scheduled_rotation_is_idempotent(self):
        Instance.objects.update(last_rotated_at=timezone.now() - timedelta(days=1))
        self.assertEqual(rotate_passwords()["rotated"], 1)
        self.assertEqual(rotate_passwords()["skipped"], 1)
    def test_snapshot_counts_zeros_and_is_idempotent(self):
        empty = Department.objects.create(name="空部门")
        snapshot_instances()
        snapshot_instances()
        self.assertEqual(InstanceSnapshot.objects.count(), 3)
        self.assertEqual(InstanceSnapshot.objects.get(dimension="department", object_id=empty.pk).instance_count, 0)
        self.assertEqual(InstanceSnapshot.objects.get(dimension="cluster").instance_count, 1)
        self.instance.delete()
        snapshot_instances()
        self.assertEqual(InstanceSnapshot.objects.get(dimension="cluster").instance_count, 1)
    def test_timing_header_on_success_and_404(self):
        self.assertGreaterEqual(float(self.client.get("/api/instances/")["X-Request-Duration-Ms"]), 0)
        self.assertIn("X-Request-Duration-Ms", self.client.get("/missing/"))
    def test_timing_logs_on_exception(self):
        def failing(request):
            raise RuntimeError("test")
        with self.assertLogs("inventory.requests", level="INFO") as logs:
            with self.assertRaises(RuntimeError):
                RequestTimingMiddleware(failing)(RequestFactory().get("/"))
        self.assertIn("status=500", logs.output[0])
    def test_dashboard(self):
        self.client.force_login(self.user)
        self.assertContains(self.client.get("/"), "数据库资源总览")

    @patch("psycopg.connect")
    def test_postgresql_driver_changes_role(self, connect):
        from .services import apply_remote_password
        self.instance.engine = "postgresql"
        apply_remote_password(self.instance, "candidate-password")
        self.assertEqual(connect.call_args.kwargs["password"], "initial-password")
        self.assertEqual(connect.call_args.kwargs["sslmode"], "require")
        cursor = connect.return_value.cursor.return_value.__enter__.return_value
        statement = cursor.execute.call_args.args[0].as_string()
        self.assertIn('ALTER ROLE "dbuser"', statement)
        self.assertIn("candidate-password", statement)
    @patch("psycopg.connect")
    def test_postgresql_recovers_using_pending_password(self, connect):
        import psycopg
        from unittest.mock import MagicMock
        from .services import apply_remote_password
        self.instance.engine = "postgresql"
        connection = MagicMock()
        connect.side_effect = [psycopg.OperationalError("auth failed"), connection]
        apply_remote_password(self.instance, "pending-password")
        self.assertEqual(connect.call_count, 2)
        self.assertEqual(connect.call_args.kwargs["password"], "pending-password")
    def test_pending_rotation_blocks_api_changes(self):
        self.instance.pending_password_encrypted = encrypt("pending-password")
        self.instance.save()
        url = f"/api/instances/{self.instance.pk}/"
        self.assertEqual(self.client.delete(url).status_code, 409)
        self.assertEqual(self.client.patch(url, {"password": "overwritten-secret"}, format="json").status_code, 409)
