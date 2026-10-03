from django.urls import path

from . import views

urlpatterns = [
    path('cupons/', views.my_coupons, name='my_coupons'),
    path('cupons/gerenciar/', views.manage_coupons, name='manage_coupons'),
    path('cupons/gerenciar/novo/', views.create_coupon, name='create_coupon'),
    path('cupons/gerenciar/<int:coupon_id>/editar/', views.edit_coupon, name='edit_coupon'),
    path('cupons/gerenciar/<int:coupon_id>/ativacao/', views.toggle_coupon, name='toggle_coupon'),
    path('cupons/gerenciar/<int:coupon_id>/excluir/', views.delete_coupon, name='delete_coupon'),
]