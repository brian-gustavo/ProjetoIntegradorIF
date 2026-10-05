from django.urls import path

from . import views

urlpatterns = [
    path('leiloes/', views.auction_list, name='auction_list'),
    path('leiloes/meus-lances/', views.my_bids, name='my_bids'),
    path('anuncios/<int:product_id>/leilao/', views.setup_auction, name='setup_auction'),
    path('anuncios/<int:product_id>/lances/', views.bid_history, name='bid_history'),
    path('anuncios/<int:product_id>/lances/novo/', views.place_bid, name='place_bid'),
    path('anuncios/<int:product_id>/comprar-agora/', views.buy_now, name='buy_now'),
    path('anuncios/<int:product_id>/acompanhar/', views.toggle_watch, name='toggle_watch'),
    path('anuncios/<int:product_id>/leilao/encerrar/', views.end_auction, name='end_auction'),
    path('anuncios/<int:product_id>/leilao/cancelar-venda/', views.cancel_unpaid, name='cancel_unpaid'),
    path('anuncios/<int:product_id>/leilao/relistar/', views.relist_auction, name='relist_auction'),
    path('anuncios/<int:product_id>/leilao/segunda-chance/', views.second_chance, name='second_chance'),
    path('anuncios/<int:product_id>/lances/retirar/', views.retract_bid, name='retract_bid'),
    path('leiloes/ofertas/<int:offer_id>/responder/', views.respond_offer, name='respond_offer'),
]