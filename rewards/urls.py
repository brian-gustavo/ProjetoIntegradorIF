from django.urls import path

from . import views

urlpatterns = [
    path('moedas/', views.wallet, name='wallet'),
    path('moedas/check-in/', views.checkin, name='coin_checkin'),
]