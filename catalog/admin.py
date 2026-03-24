from django.contrib import admin
from .models import Category, Product, ProductImage

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)} # Gera a URL (slug) automaticamente quando o nome é digitado

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'seller', 'price', 'condition', 'created_at')
    list_filter = ('category', 'condition')
    search_fields = ('title', 'description')
    inlines = [ProductImageInline]