from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from .models import Permission, Role, RolePermission, UserRole

User = get_user_model()


class PermissionSerializer(serializers.ModelSerializer):
    module = serializers.SerializerMethodField()
    action = serializers.SerializerMethodField()

    class Meta:
        model = Permission
        fields = ("id", "name", "description", "module", "action")
        read_only_fields = fields

    def get_module(self, permission):
        return permission.name.split(".", 1)[0]

    def get_action(self, permission):
        return permission.name.split(".", 1)[1] if "." in permission.name else "manage"


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Permission.objects.all(),
        required=False,
        write_only=True,
    )
    permission_details = serializers.SerializerMethodField()
    permission_ids = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ("id", "name", "display_name", "description", "is_system", "permissions", "permission_ids", "permission_details")
        read_only_fields = ("id", "is_system", "permission_ids", "permission_details")

    def get_permission_ids(self, role):
        return list(role.role_permissions.filter(allow=True).values_list("permission_id", flat=True))

    def get_permission_details(self, role):
        permissions = Permission.objects.filter(
            id__in=RolePermission.objects.filter(role=role, allow=True).values("permission_id")
        )
        return PermissionSerializer(permissions, many=True).data

    def validate_name(self, value):
        normalized = value.strip().lower().replace(" ", "_")
        if not normalized:
            raise serializers.ValidationError("El nombre del rol es obligatorio.")
        queryset = Role.objects.filter(name=normalized)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Ya existe un rol con ese nombre.")
        return normalized

    def validate(self, attrs):
        if self.instance and self.instance.is_system:
            if attrs.get("name", self.instance.name) != self.instance.name:
                raise serializers.ValidationError({"name": "Los roles predefinidos no se pueden renombrar."})
        if self.instance and self.instance.name == "super_admin" and "permissions" in attrs:
            required = Permission.objects.filter(name="admin.manage").first()
            if required and required not in attrs["permissions"]:
                raise serializers.ValidationError({"permissions": "Super-Admin debe conservar admin.manage."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        permissions = validated_data.pop("permissions", [])
        role = super().create(validated_data)
        self._set_permissions(role, permissions)
        return role

    @transaction.atomic
    def update(self, instance, validated_data):
        permissions = validated_data.pop("permissions", serializers.empty)
        role = super().update(instance, validated_data)
        if permissions is not serializers.empty:
            self._set_permissions(role, permissions)
        return role

    @staticmethod
    def _set_permissions(role, permissions):
        RolePermission.objects.filter(role=role).delete()
        RolePermission.objects.bulk_create([
            RolePermission(role=role, permission=permission, allow=True)
            for permission in permissions
        ])


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)
    role_display_name = serializers.CharField(source="role.display_name", read_only=True)

    class Meta:
        model = UserRole
        fields = ("id", "user", "role", "role_name", "role_display_name", "resource_type", "resource_id", "expires_at", "assigned_at", "assigned_by")
        read_only_fields = ("id", "assigned_at", "assigned_by", "role_name", "role_display_name")

    def validate(self, attrs):
        attrs.setdefault("resource_type", None)
        attrs.setdefault("resource_id", None)
        queryset = UserRole.objects.filter(
            user=attrs.get("user", getattr(self.instance, "user", None)),
            role=attrs.get("role", getattr(self.instance, "role", None)),
            resource_type=attrs["resource_type"],
            resource_id=attrs["resource_id"],
        )
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("Esta asignación de rol ya existe.")
        return attrs

    def create(self, validated_data):
        validated_data["assigned_by"] = self.context["request"].user
        return super().create(validated_data)


class UserSummarySerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "auth_uid", "nombre", "apellidos", "email", "tipo_usuario", "estado", "is_active", "roles")
        read_only_fields = fields

    def get_roles(self, user):
        return list(user.user_roles.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).values_list("role__id", flat=True))
