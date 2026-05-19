from django.urls import path

from . import views

urlpatterns = [
    path('pedidos/', views.my_orders, name='my_orders'),
    path('pedidos/<int:order_id>/pagar/', views.simulate_payment, name='simulate_payment'),
    path('pedidos/<int:order_id>/cancelar/', views.cancel_order_buyer, name='cancel_order_buyer'),
    path('pedidos/<int:order_id>/entregar/', views.confirm_delivery, name='confirm_delivery'),
    path('vendas/', views.seller_dashboard, name='seller_dashboard'),
    path('vendas/pedidos/', views.seller_orders, name='seller_orders'),
    path('vendas/<int:order_id>/confirmar/', views.confirm_order, name='confirm_order'),
    path('vendas/<int:order_id>/preparar/', views.mark_preparing, name='mark_preparing'),
    path('vendas/<int:order_id>/enviar/', views.mark_shipped, name='mark_shipped'),
    path('vendas/<int:order_id>/cancelar/', views.cancel_order_seller, name='cancel_order_seller'),
    path('carrinho/', views.cart_detail, name='cart_detail'),
    path('carrinho/adicionar/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('carrinho/remover/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('carrinho/finalizar/', views.checkout, name='checkout'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]