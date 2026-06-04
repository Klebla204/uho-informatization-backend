from django.contrib import admin
from .models import Role, Permission, RolePermission, UserRole, RoleHierarchy


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'display_name', 'is_system')


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('name',)


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    list_display = ('role', 'permission', 'resource_type', 'resource_id', 'allow')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'resource_type', 'resource_id')


@admin.register(RoleHierarchy)
class RoleHierarchyAdmin(admin.ModelAdmin):
    list_display = ('parent', 'child')
