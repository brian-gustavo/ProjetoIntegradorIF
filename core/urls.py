from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from accounts.views import register, profile_settings, review_seller
from catalog.views import home, create_product, product_detail, category_detail, category_list, my_products, autocomplete, review_product, manage_variants, unpublish_product
from orders.views import admin_dashboard

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', register, name='register'),
    path('', home, name='home'),
    path('anuncios/novo/', create_product, name='create_product'),
    path('anuncios/<int:product_id>/', product_detail, name='product_detail'),
    path('', include('orders.urls')),
    path('categorias/<slug:slug>/', category_detail, name='category_detail'),
    path('categorias/', category_list, name='category_list'),
    path('accounts/profile/', profile_settings, name='profile_settings'),
    path('anuncios/', my_products, name='my_products'),
    path('vendedor/<int:seller_id>/avaliar/', review_seller, name='review_seller'),
    path('autocomplete/', autocomplete, name='autocomplete'),
    path('anuncios/<int:product_id>/avaliar/', review_product, name='review_product'),
    path('anuncios/<int:product_id>/', product_detail, name='product_detail'),
    path('anuncios/<int:product_id>/variacoes/', manage_variants, name='manage_variants'),
    path('anuncios/<int:product_id>/retirar/', unpublish_product, name='unpublish_product'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)