from django.contrib import admin

from .models import Profile, SellerReview, MercadoPagoAccount

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'uf')

@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ('seller', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating',)

@admin.register(MercadoPagoAccount)
class MercadoPagoAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'mp_user_id', 'connected_at')