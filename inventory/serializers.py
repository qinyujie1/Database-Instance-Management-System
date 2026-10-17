from rest_framework import serializers
from .crypto import encrypt
from .models import Department, Cluster, Instance, InstanceSnapshot, PasswordRotation

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "description"]

class ClusterSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source="department.name", read_only=True)
    class Meta:
        model = Cluster
        fields = ["id", "name", "department", "department_name", "description"]

class InstanceSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=12, max_length=256, trim_whitespace=False)
    cluster_name = serializers.CharField(source="cluster.name", read_only=True)
    department_name = serializers.CharField(source="cluster.department.name", read_only=True)
    department = serializers.IntegerField(source="cluster.department_id", read_only=True)
    rotation_pending = serializers.SerializerMethodField()
    def get_rotation_pending(self, obj):
        return bool(obj.pending_password_encrypted)
    def create(self, validated_data):
        validated_data["password_encrypted"] = encrypt(validated_data.pop("password"))
        return super().create(validated_data)
    def update(self, instance, validated_data):
        if "password" in validated_data:
            validated_data["password_encrypted"] = encrypt(validated_data.pop("password"))
        return super().update(instance, validated_data)
    class Meta:
        model = Instance
        fields = ["id", "name", "cluster", "cluster_name", "department", "department_name", "host", "port", "engine", "database", "username", "password", "last_rotated_at", "created_at", "rotation_pending"]
        read_only_fields = ["last_rotated_at", "created_at"]

class SnapshotSerializer(serializers.ModelSerializer):
    class Meta:
        model = InstanceSnapshot
        fields = "__all__"

class RotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = PasswordRotation
        fields = ["id", "instance", "created_at", "success", "error_code"]
