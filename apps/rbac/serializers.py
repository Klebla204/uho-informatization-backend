from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework import serializers

from apps.catalogo.models import Biblioteca

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
    biblioteca = serializers.PrimaryKeyRelatedField(
        queryset=Biblioteca.objects.filter(activa=True),
        required=False,
        write_only=True,
    )

    class Meta:
        model = UserRole
        fields = ("id", "user", "role", "role_name", "role_display_name", "resource_type", "resource_id", "biblioteca", "expires_at", "assigned_at", "assigned_by")
        read_only_fields = ("id", "assigned_at", "assigned_by", "role_name", "role_display_name")

    def validate(self, attrs):
        user = attrs.get("user", getattr(self.instance, "user", None))
        role = attrs.get("role", getattr(self.instance, "role", None))
        if role and user:
            if user.tipo_usuario == "SUPER_ADMIN" and role.name != "super_admin":
                raise serializers.ValidationError({"role": "Una cuenta Super-Admin solo puede tener el rol Super-Admin."})
            if role.name == "super_admin" and user.tipo_usuario != "SUPER_ADMIN":
                raise serializers.ValidationError({"user": "El rol Super-Admin solo puede asignarse a una cuenta Super-Admin."})
            can_promote_student = role.name == "bibliotecario" and user.tipo_usuario == "ESTUDIANTE"
            can_change_staff_role = role.name in {"bibliotecario", "administrador_biblioteca"} and user.tipo_usuario in {"BIBLIOTECARIO", "ADMINISTRADOR"}
            can_return_to_student = role.name == "estudiante" and user.tipo_usuario == "BIBLIOTECARIO"
            if role.name in {"bibliotecario", "administrador_biblioteca"} and not (can_change_staff_role or can_promote_student):
                raise serializers.ValidationError({"user": "Este rol solo puede asignarse a bibliotecarios o administradores."})
            if role.name == "estudiante" and user.tipo_usuario not in {"ESTUDIANTE", "BIBLIOTECARIO"}:
                raise serializers.ValidationError({"user": "Solo un estudiante o bibliotecario puede tener el rol estudiante."})
            requires_library = user.tipo_usuario in {"BIBLIOTECARIO", "ADMINISTRADOR"} and role.name in {"bibliotecario", "administrador_biblioteca"}
            if requires_library:
                if role.name == "super_admin":
                    raise serializers.ValidationError({"role": "Un usuario vinculado a sede no puede tener alcance Super-Admin."})
                if attrs.get("resource_type") not in (None, "biblioteca"):
                    raise serializers.ValidationError({"resource_type": "El rol debe limitarse a una biblioteca."})
                requested_library = attrs.get("biblioteca")
                if requested_library:
                    resource_id = attrs.get("resource_id")
                    if resource_id and resource_id != str(requested_library.id):
                        raise serializers.ValidationError({"resource_id": "El alcance debe coincidir con la sede seleccionada."})
                    attrs["resource_type"] = "biblioteca"
                    attrs["resource_id"] = str(requested_library.id)
                elif user.biblioteca_id:
                    attrs["resource_type"] = "biblioteca"
                    attrs["resource_id"] = str(user.biblioteca_id)
                else:
                    attrs["resource_type"] = None
                    attrs["resource_id"] = None
            else:
                attrs.pop("biblioteca", None)
                attrs["resource_type"] = None
                attrs["resource_id"] = None
            if can_return_to_student:
                attrs["resource_type"] = None
                attrs["resource_id"] = None
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
            has_other_roles = UserRole.objects.filter(user=user).exclude(role=role).exists()
            target_type = user.tipo_usuario
            if role.name == "bibliotecario" and user.tipo_usuario in {"ESTUDIANTE", "ADMINISTRADOR"}:
                target_type = "BIBLIOTECARIO"
            elif role.name == "administrador_biblioteca" and user.tipo_usuario == "BIBLIOTECARIO":
                target_type = "ADMINISTRADOR"
            elif role.name == "estudiante" and user.tipo_usuario == "BIBLIOTECARIO":
                target_type = "ESTUDIANTE"
            if target_type == user.tipo_usuario and not has_other_roles:
                raise serializers.ValidationError("Esta asignación de rol ya existe.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        library = validated_data.pop("biblioteca", None)
        user = validated_data["user"]
        role = validated_data["role"]
        existing_assignment = UserRole.objects.filter(
            user=user,
            role=role,
            resource_type=validated_data.get("resource_type"),
            resource_id=validated_data.get("resource_id"),
        ).first()
        current_type = user.tipo_usuario
        target_type = current_type
        if role.name == "bibliotecario" and current_type in {"ESTUDIANTE", "ADMINISTRADOR"}:
            target_type = "BIBLIOTECARIO"
        elif role.name == "administrador_biblioteca" and current_type == "BIBLIOTECARIO":
            target_type = "ADMINISTRADOR"
        elif role.name == "estudiante" and current_type == "BIBLIOTECARIO":
            target_type = "ESTUDIANTE"

        if target_type != current_type:
            if target_type == "ESTUDIANTE":
                UserRole.objects.filter(user=user, resource_type="biblioteca").delete()
                user.tipo_usuario = target_type
                user.biblioteca = None
                user.save(update_fields=["tipo_usuario", "biblioteca"])
            else:
                user.tipo_usuario = target_type
                user.save(update_fields=["tipo_usuario"])
        previous_assignments = UserRole.objects.filter(user=user)
        if existing_assignment:
            previous_assignments.exclude(role=role).delete()
            return existing_assignment
        previous_assignments.exclude(role=role).delete()
        if library:
            UserRole.objects.filter(
                user=user,
                role=validated_data["role"],
                resource_type__isnull=True,
                resource_id__isnull=True,
            ).delete()
            if user.biblioteca_id and user.biblioteca_id != library.id:
                UserRole.objects.filter(
                    user=user,
                    resource_type="biblioteca",
                    resource_id=str(user.biblioteca_id),
                ).delete()
            user.biblioteca = library
            user.save(update_fields=["biblioteca"])
        validated_data["assigned_by"] = self.context["request"].user
        return super().create(validated_data)

    @transaction.atomic
    def update(self, instance, validated_data):
        library = validated_data.pop("biblioteca", None)
        if library:
            instance.user.biblioteca = library
            instance.user.save(update_fields=["biblioteca"])
        assignment = super().update(instance, validated_data)
        UserRole.objects.filter(user=assignment.user).exclude(role=assignment.role).delete()
        return assignment


class UserSummarySerializer(serializers.ModelSerializer):
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "auth_uid", "nombre", "apellidos", "email", "tipo_usuario", "biblioteca", "estado", "is_active", "roles")
        read_only_fields = fields

    def get_roles(self, user):
        return list(user.user_roles.filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).values_list("role__id", flat=True))
