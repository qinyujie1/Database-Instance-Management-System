from django.apps import AppConfig
from django.contrib.admin.apps import AdminConfig


class InventoryConfig(AppConfig):
    name = "inventory"
    verbose_name = "数据库管理"


class ConsoleAdminConfig(AdminConfig):
    default_site = "inventory.sites.ConsoleAdminSite"
