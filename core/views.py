from django.db import transaction
from django.utils import timezone
from django.conf import settings
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser

from .models import PurchaseRequest, RequestItem, Approval, PurchaseOrder, User
from .serializers import (
    PurchaseRequestSerializer,
    RequestItemSerializer,
    ApprovalSerializer,
    PurchaseOrderSerializer,
)
from .permissions import IsApprover, IsFinance, IsStaffCanEditPending
from .services.doc_processing import extract_proforma_metadata, generate_po_document, validate_receipt_against_po


class PurchaseRequestViewSet(viewsets.ModelViewSet):
    queryset = PurchaseRequest.objects.select_related("created_by", "purchase_order").prefetch_related("items", "approvals")
    serializer_class = PurchaseRequestSerializer
    permission_classes = [IsAuthenticated, IsStaffCanEditPending]
    parser_classes = [MultiPartParser, FormParser]

    def get_queryset(self):
        user = self.request.user
        qs = super().get_queryset()
        if user.role == User.ROLE_STAFF:
            return qs.filter(created_by=user)
        if user.role in (User.ROLE_APPROVER_L1, User.ROLE_APPROVER_L2):
            # Pending requests or ones they've reviewed
            level = 1 if user.role == User.ROLE_APPROVER_L1 else 2
            reviewed = qs.filter(approvals__approver=user)
            pending = qs.filter(status=PurchaseRequest.STATUS_PENDING).exclude(approvals__level=level, approvals__status=Approval.STATUS_APPROVED)
            return (pending | reviewed).distinct()
        if user.role == User.ROLE_FINANCE:
            return qs
        return qs.none()

    def perform_create(self, serializer):
        serializer.save()
        instance: PurchaseRequest = serializer.instance
        # If proforma uploaded, extract metadata to populate items/vendor
        if instance.proforma:
            meta = extract_proforma_metadata(instance.proforma.path)
            if meta.get("vendor"):
                # add vendor and items if not provided
                for item in meta.get("items", []):
                    RequestItem.objects.create(
                        request=instance,
                        name=item.get("name", "Item"),
                        quantity=item.get("quantity", 1),
                        unit_price=item.get("unit_price", 0),
                        vendor=meta.get("vendor", ""),
                    )
                instance.amount = sum(i.total_price for i in instance.items.all())
                instance.save(update_fields=["amount"])

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsApprover])
    def approve(self, request, pk=None):
        pr = self.get_object()
        try:
            with transaction.atomic():
                pr.approve(request.user)
                # If approved overall and no PO yet, generate PO
                if pr.status == PurchaseRequest.STATUS_APPROVED and not pr.purchase_order:
                    # naive PO number
                    po_number = f"PO-{pr.pk}-{int(timezone.now().timestamp())}"
                    data = {
                        "vendor": pr.items.first().vendor if pr.items.exists() else "",
                        "items": [
                            {"name": i.name, "quantity": i.quantity, "unit_price": float(i.unit_price)} for i in pr.items.all()
                        ],
                        "total": float(pr.amount),
                        "terms": "Net 30",
                    }
                    doc_path = generate_po_document(po_number, data, settings.MEDIA_ROOT / "purchase_orders")
                    po = PurchaseOrder.objects.create(number=po_number, vendor=data["vendor"], terms=data["terms"], total_amount=pr.amount)
                    # attach file path
                    relative = doc_path.relative_to(settings.MEDIA_ROOT)
                    po.document.name = str(relative)
                    po.save()
                    pr.purchase_order = po
                    pr.save(update_fields=["purchase_order"])
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(self.get_serializer(pr).data)

    @action(detail=True, methods=["patch"], permission_classes=[IsAuthenticated, IsApprover])
    def reject(self, request, pk=None):
        pr = self.get_object()
        reason = request.data.get("reason", "")
        try:
            with transaction.atomic():
                pr.reject(request.user, reason)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(pr).data)

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated], parser_classes=[MultiPartParser, FormParser])
    def submit_receipt(self, request, pk=None):
        pr = self.get_object()
        if pr.created_by != request.user:
            return Response({"detail": "Only the creator can submit a receipt."}, status=status.HTTP_403_FORBIDDEN)
        file = request.data.get("receipt")
        if not file:
            return Response({"detail": "No receipt file provided."}, status=status.HTTP_400_BAD_REQUEST)
        pr.receipt = file
        pr.save(update_fields=["receipt"])
        validation = {}
        if pr.purchase_order:
            po_data = {
                "vendor": pr.purchase_order.vendor,
                "total": float(pr.purchase_order.total_amount),
            }
            validation = validate_receipt_against_po(pr.receipt.path, po_data)
        return Response({"request": self.get_serializer(pr).data, "validation": validation})