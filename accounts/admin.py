from django.contrib import admin

from .models import Profile, SellerReview

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'city', 'uf')

@admin.register(SellerReview)
class SellerReviewAdmin(admin.ModelAdmin):
    list_display = ('seller', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating',)