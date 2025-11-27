from django.contrib import admin
from .models import User, PurchaseRequest, RequestItem, Approval, PurchaseOrder


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "role", "is_superuser")
    list_filter = ("role",)
    search_fields = ("username", "email")


class RequestItemInline(admin.TabularInline):
    model = RequestItem
    extra = 0


class ApprovalInline(admin.TabularInline):
    model = Approval
    extra = 0


@admin.register(PurchaseRequest)
class PurchaseRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "status", "amount", "created_by", "created_at")
    list_filter = ("status",)
    search_fields = ("title", "description")
    inlines = [RequestItemInline, ApprovalInline]


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "number", "vendor", "total_amount", "created_at")
    search_fields = ("number", "vendor")