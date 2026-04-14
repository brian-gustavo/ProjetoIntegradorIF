from django.urls import path
from . import views

urlpatterns = [
    path('pedidos/', views.my_orders, name='my_orders'),
    path('pedidos/novo/<int:product_id>/', views.create_order, name='create_order'),
    path('pedidos/<int:order_id>/pagar/', views.simulate_payment, name='simulate_payment'),
    path('vendas/', views.seller_orders, name='seller_orders'),
    path('vendas/<int:order_id>/entregar/', views.confirm_delivery, name='confirm_delivery'),
]