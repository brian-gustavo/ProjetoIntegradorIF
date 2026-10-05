from django.urls import path

from . import views

urlpatterns = [
    path('trocas/', views.trade_list, name='trade_list'),
    path('trocas/minhas/', views.my_trades, name='my_trades'),
    path('trocas/<int:trade_id>/', views.trade_detail, name='trade_detail'),
    path('trocas/<int:trade_id>/contraproposta/', views.counter_trade, name='counter_trade'),
    path('trocas/<int:trade_id>/responder/', views.trade_action, name='trade_action'),
    path('anuncios/<int:product_id>/propor-troca/', views.propose_trade, name='propose_trade'),
]
