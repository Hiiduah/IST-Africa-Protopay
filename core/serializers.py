from rest_framework import serializers
from .models import User, PurchaseRequest, RequestItem, Approval, PurchaseOrder


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "role"]


class RequestItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RequestItem
        fields = ["id", "name", "quantity", "unit_price", "vendor", "total_price"]
        read_only_fields = ["total_price"]


class PurchaseOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PurchaseOrder
        fields = ["id", "number", "vendor", "terms", "total_amount", "document", "created_at"]


class ApprovalSerializer(serializers.ModelSerializer):
    approver = UserSerializer(read_only=True)

    class Meta:
        model = Approval
        fields = ["id", "level", "status", "comment", "created_at", "approver"]


class PurchaseRequestSerializer(serializers.ModelSerializer):
    created_by = UserSerializer(read_only=True)
    items = RequestItemSerializer(many=True, required=False)
    approvals = ApprovalSerializer(many=True, read_only=True)
    purchase_order = PurchaseOrderSerializer(read_only=True)

    class Meta:
        model = PurchaseRequest
        fields = [
            "id",
            "title",
            "description",
            "amount",
            "status",
            "created_by",
            "created_at",
            "updated_at",
            "proforma",
            "receipt",
            "items",
            "approvals",
            "purchase_order",
        ]
        read_only_fields = ["status", "created_by", "created_at", "updated_at", "approvals", "purchase_order"]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        request = PurchaseRequest.objects.create(created_by=self.context["request"].user, **validated_data)
        for item in items_data:
            RequestItem.objects.create(request=request, **item)
        return request

    def update(self, instance, validated_data):
        if instance.status != PurchaseRequest.STATUS_PENDING:
            raise serializers.ValidationError("Only pending requests can be updated.")
        items_data = validated_data.pop("items", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        if items_data is not None:
            instance.items.all().delete()
            for item in items_data:
                RequestItem.objects.create(request=instance, **item)
        return instance