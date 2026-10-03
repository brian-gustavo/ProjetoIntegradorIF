from django.contrib import admin

from .models import CoinTransaction

@admin.register(CoinTransaction)
class CoinTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'kind', 'amount', 'description', 'order', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__username', 'description')
    raw_id_fields = ('user', 'order')