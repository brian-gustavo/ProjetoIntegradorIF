from django.contrib import admin

from .models import Category, Product, ProductImage, Stock, ProductReview

# As classes inline facilitam a inserção de informações referentes às classes alheias ao produto em si (colocando-as na mesma página que todo o resto)
class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

class StockInline(admin.TabularInline):
    model = Stock
    extra = 0

class ProductReviewInline(admin.TabularInline):
    model = ProductReview
    extra = 0

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)} # Gera a URL automaticamente quando o nome é digitado

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'seller', 'price', 'condition', 'created_at')
    list_filter = ('category', 'condition')
    search_fields = ('title', 'description')
    inlines = [ProductImageInline, StockInline]

@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'reviewer', 'rating', 'created_at')
    list_filter = ('rating',)
    search_fields = ('product__title', 'reviewer__username')