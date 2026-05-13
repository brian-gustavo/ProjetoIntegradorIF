from django.urls import path

from . import views

urlpatterns = [
    path('pedidos/', views.my_orders, name='my_orders'),
    path('pedidos/<int:order_id>/pagar/', views.simulate_payment, name='simulate_payment'),
    path('vendas/', views.seller_dashboard, name='seller_dashboard'),
    path('vendas/pedidos/', views.seller_orders, name='seller_orders'),
    path('vendas/<int:order_id>/entregar/', views.confirm_delivery, name='confirm_delivery'),
    path('carrinho/', views.cart_detail, name='cart_detail'),
    path('carrinho/adicionar/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('carrinho/remover/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('carrinho/finalizar/', views.checkout, name='checkout'),
]