from rest_framework.permissions import BasePermission
from .models import User, PurchaseRequest


class IsStaffCanEditPending(BasePermission):
    def has_object_permission(self, request, view, obj: PurchaseRequest):
        if request.method in ("PUT", "PATCH"):
            return obj.status == PurchaseRequest.STATUS_PENDING and request.user == obj.created_by and request.user.role == User.ROLE_STAFF
        return True


class RolePermission(BasePermission):
    allowed_roles = None

    def has_permission(self, request, view):
        if self.allowed_roles is None:
            return True
        return getattr(request.user, "role", None) in self.allowed_roles


class IsApprover(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) in (User.ROLE_APPROVER_L1, User.ROLE_APPROVER_L2)


class IsFinance(BasePermission):
    def has_permission(self, request, view):
        return getattr(request.user, "role", None) == User.ROLE_FINANCE