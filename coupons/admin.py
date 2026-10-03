from django.contrib import admin

from .models import Coupon, CouponRedemption, SavedCoupon

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'seller', 'kind', 'value', 'min_order_value', 'starts_at', 'ends_at', 'is_public', 'active')
    list_filter = ('kind', 'is_public', 'active', 'first_purchase_only')
    search_fields = ('code', 'seller__username')
    raw_id_fields = ('seller',)

@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'discount', 'created_at')
    search_fields = ('coupon__code', 'user__username')
    raw_id_fields = ('coupon', 'user')

@admin.register(SavedCoupon)
class SavedCouponAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'user', 'created_at')
    search_fields = ('coupon__code', 'user__username')
    raw_id_fields = ('coupon', 'user')