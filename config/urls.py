from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from inventory import views
router = DefaultRouter()
router.register("departments", views.DepartmentViewSet)
router.register("clusters", views.ClusterViewSet)
router.register("instances", views.InstanceViewSet)
router.register("snapshots", views.SnapshotViewSet)
router.register("rotations", views.RotationViewSet)
urlpatterns = [path("", views.dashboard), path("admin/", admin.site.urls), path("api/", include(router.urls)), path("api-auth/", include("rest_framework.urls"))]
