from django.contrib import admin

from .models import TradeEvent, TradeItem, TradeProposal

class TradeItemInline(admin.TabularInline):
    model = TradeItem
    extra = 0
    raw_id_fields = ('product', 'variant')

class TradeEventInline(admin.TabularInline):
    model = TradeEvent
    extra = 0
    raw_id_fields = ('author',)

@admin.register(TradeProposal)
class TradeProposalAdmin(admin.ModelAdmin):
    list_display = ('pk', 'product', 'proposer', 'owner', 'status', 'awaiting', 'cash_amount', 'cash_payer', 'rounds', 'expires_at')
    list_filter = ('status', 'awaiting', 'cash_payer')
    search_fields = ('product__title', 'proposer__username', 'owner__username')
    raw_id_fields = ('product', 'variant', 'proposer', 'owner')
    inlines = (TradeItemInline, TradeEventInline)
