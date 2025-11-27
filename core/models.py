from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models, transaction
from django.utils import timezone


class User(AbstractUser):
    ROLE_STAFF = "staff"
    ROLE_APPROVER_L1 = "approver_l1"
    ROLE_APPROVER_L2 = "approver_l2"
    ROLE_FINANCE = "finance"

    ROLE_CHOICES = [
        (ROLE_STAFF, "Staff"),
        (ROLE_APPROVER_L1, "Approver L1"),
        (ROLE_APPROVER_L2, "Approver L2"),
        (ROLE_FINANCE, "Finance"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_STAFF)


class PurchaseOrder(models.Model):
    number = models.CharField(max_length=64, unique=True)
    vendor = models.CharField(max_length=255, blank=True)
    terms = models.TextField(blank=True)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    document = models.FileField(upload_to="purchase_orders/", blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self) -> str:
        return self.number


class PurchaseRequest(models.Model):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="requests")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    proforma = models.FileField(upload_to="proformas/", blank=True, null=True)
    receipt = models.FileField(upload_to="receipts/", blank=True, null=True)

    purchase_order = models.OneToOneField(
        PurchaseOrder, on_delete=models.SET_NULL, blank=True, null=True, related_name="request"
    )

    def __str__(self) -> str:
        return f"#{self.pk} {self.title} ({self.status})"

    @transaction.atomic
    def approve(self, user: User) -> None:
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be approved.")
        if user.role not in (User.ROLE_APPROVER_L1, User.ROLE_APPROVER_L2):
            raise PermissionError("User not allowed to approve.")

        # Lock row to prevent races
        locked = (
            PurchaseRequest.objects.select_for_update()
            .filter(pk=self.pk)
            .get()
        )

        # Prevent duplicate approvals per level
        existing = self.approvals.filter(level=Approval.level_for_role(user.role), status=Approval.STATUS_APPROVED)
        if existing.exists():
            return

        Approval.objects.create(
            request=self,
            approver=user,
            level=Approval.level_for_role(user.role),
            status=Approval.STATUS_APPROVED,
        )

        # If all required levels approved, mark approved and generate PO
        levels_required = {1, 2}
        approved_levels = set(
            self.approvals.filter(status=Approval.STATUS_APPROVED).values_list("level", flat=True)
        )
        if levels_required.issubset(approved_levels):
            self.status = self.STATUS_APPROVED
            self.save(update_fields=["status"])

    @transaction.atomic
    def reject(self, user: User, reason: str = "") -> None:
        if self.status != self.STATUS_PENDING:
            raise ValueError("Only pending requests can be rejected.")
        if user.role not in (User.ROLE_APPROVER_L1, User.ROLE_APPROVER_L2):
            raise PermissionError("User not allowed to reject.")

        locked = (
            PurchaseRequest.objects.select_for_update()
            .filter(pk=self.pk)
            .get()
        )

        Approval.objects.create(
            request=self,
            approver=user,
            level=Approval.level_for_role(user.role),
            status=Approval.STATUS_REJECTED,
            comment=reason,
        )

        self.status = self.STATUS_REJECTED
        self.save(update_fields=["status"])


class RequestItem(models.Model):
    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    vendor = models.CharField(max_length=255, blank=True)

    @property
    def total_price(self):
        return self.quantity * self.unit_price


class Approval(models.Model):
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"

    STATUS_CHOICES = [
        (STATUS_APPROVED, "Approved"),
        (STATUS_REJECTED, "Rejected"),
    ]

    request = models.ForeignKey(PurchaseRequest, on_delete=models.CASCADE, related_name="approvals")
    approver = models.ForeignKey(User, on_delete=models.PROTECT, related_name="approvals")
    level = models.PositiveSmallIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    @staticmethod
    def level_for_role(role: str) -> int:
        return 1 if role == User.ROLE_APPROVER_L1 else 2

    def __str__(self) -> str:
        return f"Req {self.request_id} L{self.level} {self.status} by {self.approver_id}"