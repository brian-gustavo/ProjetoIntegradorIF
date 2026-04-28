from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from catalog.views import home, create_product, product_detail, category_detail
from accounts.views import register

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),
    path('accounts/register/', register, name='register'),
    path('', home, name='home'),
    path('anuncios/novo/', create_product, name='create_product'),
    path('anuncios/<int:product_id>/', product_detail, name='product_detail'),
    path('', include('orders.urls')),
    path('categorias/<slug:slug>/', category_detail, name='category_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)