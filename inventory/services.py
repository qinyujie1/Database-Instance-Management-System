import ipaddress
import socket
import uuid
from datetime import timedelta
from time import perf_counter
from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from .crypto import decrypt, encrypt, new_password
from .models import Instance, PasswordRotation

def validate_target(host):
    address = ipaddress.ip_address(host)
    if not any(address in ipaddress.ip_network(network.strip()) for network in settings.PROBE_ALLOWED_NETWORKS):
        raise ValueError("TargetNotAllowed")

def probe(instance):
    validate_target(instance.host)
    start = perf_counter()
    reachable, error = False, ""
    try:
        with socket.create_connection((instance.host, instance.port), timeout=3):
            reachable = True
    except OSError as exc:
        error = type(exc).__name__
    return {"instance_id": instance.pk, "reachable": reachable, "latency_ms": round((perf_counter() - start) * 1000, 3), "error": error}

def apply_remote_password(instance, candidate):
    if instance.engine == "mock":
        return
    validate_target(instance.host)
    import psycopg
    from psycopg import sql
    # After a crash between remote ALTER ROLE and local commit, the pending
    # credential may already be active. Retrying the same candidate reconciles it.
    connection = None
    for password in dict.fromkeys([decrypt(instance.password_encrypted), candidate]):
        try:
            connection = psycopg.connect(host=instance.host, port=instance.port, dbname=instance.database, user=instance.username, password=password, connect_timeout=5, sslmode="require", options="-c statement_timeout=5000")
            break
        except psycopg.OperationalError:
            continue
    if connection is None:
        raise ConnectionError("DatabaseConnectionFailed")
    with connection:
        with connection.cursor() as cursor:
            cursor.execute(sql.SQL("ALTER ROLE {} PASSWORD {}").format(sql.Identifier(instance.username), sql.Literal(candidate)))

def rotate_instance(instance_id, cutoff=None):
    now = timezone.now()
    token = str(uuid.uuid4())
    eligible = Instance.objects.filter(pk=instance_id).filter(Q(rotation_token="") | Q(rotation_started_at__lt=now - timedelta(minutes=10)))
    if cutoff:
        eligible = eligible.filter(Q(last_rotated_at__lt=cutoff) | ~Q(pending_password_encrypted=""))
    if not eligible.update(rotation_token=token, rotation_started_at=now):
        return "skipped"
    try:
        instance = Instance.objects.get(pk=instance_id)
        candidate_encrypted = instance.pending_password_encrypted or encrypt(new_password())
        Instance.objects.filter(pk=instance_id, rotation_token=token).update(pending_password_encrypted=candidate_encrypted)
        apply_remote_password(instance, decrypt(candidate_encrypted))
        with transaction.atomic():
            updated = Instance.objects.filter(pk=instance_id, rotation_token=token).update(password_encrypted=candidate_encrypted, pending_password_encrypted="", last_rotated_at=timezone.now(), rotation_token="", rotation_started_at=None)
            if not updated:
                raise RuntimeError("RotationLeaseLost")
            PasswordRotation.objects.create(instance_id=instance_id, success=True, password_encrypted=candidate_encrypted)
        return "rotated"
    except Exception as exc:
        # Never persist exception text: database exceptions may contain secrets.
        PasswordRotation.objects.create(instance_id=instance_id, success=False, error_code=type(exc).__name__)
        Instance.objects.filter(pk=instance_id, rotation_token=token).update(rotation_token="", rotation_started_at=None)
        return "failed"
