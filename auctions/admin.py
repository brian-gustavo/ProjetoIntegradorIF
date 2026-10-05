from django.contrib import admin

from .models import Auction, AuctionWatch, Bid, SecondChanceOffer

class BidInline(admin.TabularInline):
    model = Bid
    extra = 0
    raw_id_fields = ('bidder',)

@admin.register(Auction)
class AuctionAdmin(admin.ModelAdmin):
    list_display = ('product', 'status', 'start_price', 'current_price', 'bid_count', 'reserve_price', 'buy_now_price', 'ends_at')
    list_filter = ('status', 'duration_days', 'bought_now', 'ended_early')
    search_fields = ('product__title', 'product__seller__username')
    raw_id_fields = ('product', 'leader', 'winner', 'order', 'relisted_as')
    inlines = (BidInline,)

@admin.register(Bid)
class BidAdmin(admin.ModelAdmin):
    list_display = ('auction', 'bidder', 'amount', 'is_auto', 'created_at', 'retracted_at')
    list_filter = ('is_auto', 'retraction_reason')
    search_fields = ('auction__product__title', 'bidder__username')
    raw_id_fields = ('auction', 'bidder')

@admin.register(SecondChanceOffer)
class SecondChanceOfferAdmin(admin.ModelAdmin):
    list_display = ('auction', 'bidder', 'price', 'status', 'created_at', 'expires_at')
    list_filter = ('status',)
    search_fields = ('auction__product__title', 'bidder__username')
    raw_id_fields = ('auction', 'bidder', 'order')

@admin.register(AuctionWatch)
class AuctionWatchAdmin(admin.ModelAdmin):
    list_display = ('auction', 'user', 'created_at')
    search_fields = ('auction__product__title', 'user__username')
    raw_id_fields = ('auction', 'user')