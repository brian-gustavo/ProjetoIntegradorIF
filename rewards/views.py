from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect

from orders.models import PlatformConfig
from .services import balance, checkin_status, coins_to_brl, do_checkin, expected_cashback, level_info, redeem_rate, sync_wallet

@login_required
def wallet(request):
    if request.user.is_staff:
        return redirect('home')

    sync_wallet(request.user)
    saldo = balance(request.user)
    config = PlatformConfig.load()
    historico = request.user.coin_transactions.exclude(amount=0).select_related('order')

    return render(request, 'rewards/wallet.html', {
        'saldo': saldo,
        'saldo_brl': coins_to_brl(saldo),
        'previstas': expected_cashback(request.user),
        'nivel': level_info(request.user),
        'checkin': checkin_status(request.user),
        'config': config,
        'taxa_resgate': redeem_rate(config),
        'historico': Paginator(historico, 15).get_page(request.GET.get('page')),
    })

@login_required
def checkin(request):
    if request.method == 'POST' and not request.user.is_staff:
        moedas = do_checkin(request.user)
        if moedas:
            messages.success(request, f'Check-in feito! Você ganhou {moedas} MegaCoins.')
        else:
            messages.info(request, 'Você já fez o check-in hoje. Volte amanhã para manter a sequência!')
    return redirect('wallet')