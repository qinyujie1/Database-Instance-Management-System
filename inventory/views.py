from django.contrib.admin.views.decorators import staff_member_required
from django.db import transaction
from django.db.models import ProtectedError
from django.shortcuts import render
from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from .models import Department, Cluster, Instance, InstanceSnapshot, PasswordRotation
from .serializers import DepartmentSerializer, ClusterSerializer, InstanceSerializer, SnapshotSerializer, RotationSerializer
from .services import probe

class Conflict(APIException):
    status_code = 409
    default_detail = "对象存在关联记录，或凭据正在轮换，请稍后再试。"

class ProtectedViewSet(viewsets.ModelViewSet):
    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise Conflict("请先删除或迁移关联实例/集群。")

class DepartmentViewSet(ProtectedViewSet):
    queryset = Department.objects.order_by("id")
    serializer_class = DepartmentSerializer

class ClusterViewSet(ProtectedViewSet):
    queryset = Cluster.objects.select_related("department").order_by("id")
    serializer_class = ClusterSerializer

class ProbeThrottle(UserRateThrottle):
    scope = "probe"

class InstanceViewSet(ProtectedViewSet):
    queryset = Instance.objects.select_related("cluster__department").order_by("id")
    serializer_class = InstanceSerializer
    def get_queryset(self):
        queryset = super().get_queryset()
        for field, lookup in [("department", "cluster__department_id"), ("cluster", "cluster_id")]:
            value = self.request.query_params.get(field)
            if value:
                if not value.isdecimal():
                    raise ValidationError({field: "必须是整数 ID"})
                queryset = queryset.filter(**{lookup: int(value)})
        return queryset
    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = Instance.objects.select_for_update().get(pk=self.get_object().pk)
            if instance.rotation_token or instance.pending_password_encrypted:
                raise Conflict()
            return super().update(request, *args, **kwargs)
    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = Instance.objects.select_for_update().get(pk=self.get_object().pk)
            if instance.rotation_token or instance.pending_password_encrypted:
                raise Conflict()
            return super().destroy(request, *args, **kwargs)
    @action(detail=True, methods=["post"], throttle_classes=[ProbeThrottle])
    def probe(self, request, pk=None):
        try:
            return Response(probe(self.get_object()))
        except ValueError:
            return Response({"detail": "目标地址不在允许探测的网段内。"}, status=status.HTTP_400_BAD_REQUEST)

class SnapshotViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InstanceSnapshot.objects.all()
    serializer_class = SnapshotSerializer
    def get_queryset(self):
        qs = super().get_queryset()
        dimension = self.request.query_params.get("dimension")
        if dimension:
            qs = qs.filter(dimension=dimension)
        date = self.request.query_params.get("date")
        if date:
            from datetime import date as date_type
            try:
                date_type.fromisoformat(date)
            except ValueError:
                raise ValidationError({"date": "请使用 YYYY-MM-DD"})
            qs = qs.filter(date=date)
        return qs

class RotationViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PasswordRotation.objects.order_by("-created_at")
    serializer_class = RotationSerializer

@staff_member_required
def dashboard(request):
    from django.contrib import admin
    return admin.site.index(request)
