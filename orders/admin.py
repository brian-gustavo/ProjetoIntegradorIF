from django.contrib import admin

from .models import Order, Cart, CartItem, PlatformConfig, Commission, Dispute, DisputeMessage

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'product', 'buyer', 'quantity', 'total_price', 'status', 'created_at')
    list_filter = ('status',)
    search_fields = ('product__title', 'buyer__username')

@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')

@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ('cart', 'product', 'quantity')

@admin.register(PlatformConfig)
class PlatformConfigAdmin(admin.ModelAdmin):
    list_display = ('commission_rate',)

    def has_add_permission(self, request):
        return not PlatformConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = ('order', 'rate', 'gross_amount', 'commission_amount', 'net_amount', 'created_at')
    readonly_fields = ('order', 'rate', 'gross_amount', 'commission_amount', 'net_amount', 'created_at')

@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('order', 'opened_by', 'status', 'created_at', 'resolved_by')
    list_filter = ('status',)

@admin.register(DisputeMessage)
class DisputeMessageAdmin(admin.ModelAdmin):
    list_display = ('dispute', 'author', 'created_at')