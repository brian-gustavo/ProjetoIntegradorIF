from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from orders.models import Order, PlatformConfig
from .models import CoinTransaction

COIN_VALUE = Decimal('0.01')
CHECKIN_REWARDS = [5, 5, 10, 10, 15, 15, 50]
LEVEL_WINDOW_DAYS = 365
LEVELS = [
    {'nome': 'Bronze', 'minimo': Decimal('0'), 'multiplicador': Decimal('1')},
    {'nome': 'Prata', 'minimo': Decimal('500'), 'multiplicador': Decimal('1.25')},
    {'nome': 'Ouro', 'minimo': Decimal('1500'), 'multiplicador': Decimal('1.5')},
    {'nome': 'Diamante', 'minimo': Decimal('4000'), 'multiplicador': Decimal('2')},
]
EXPECTED_CASHBACK_STATUSES = ('PAID', 'CONFIRMED', 'PREPARING', 'SHIPPED', 'READY_PICKUP', 'DELIVERED', 'RETURN_WINDOW')

def _to_coins(valor):
    return int((valor / COIN_VALUE).to_integral_value(rounding=ROUND_DOWN))

def coins_to_brl(coins):
    return (Decimal(coins) * COIN_VALUE).quantize(Decimal('0.01'))

def balance(user):
    return CoinTransaction.objects.filter(user=user).aggregate(total=Sum('amount'))['total'] or 0

def level_info(user):
    desde = timezone.now() - timedelta(days=LEVEL_WINDOW_DAYS)
    totais = Order.objects.filter(
        buyer=user, coin_transactions__kind='PURCHASE', coin_transactions__created_at__gte=desde,
    ).aggregate(bruto=Sum('total_price'), desconto=Sum('coins_discount'))
    gasto = (totais['bruto'] or Decimal('0')) - (totais['desconto'] or Decimal('0'))

    indice = max(i for i, nivel in enumerate(LEVELS) if gasto >= nivel['minimo'])
    atual = LEVELS[indice]
    proximo = LEVELS[indice + 1] if indice + 1 < len(LEVELS) else None

    progresso, faltam = 100, Decimal('0')
    if proximo:
        faixa = proximo['minimo'] - atual['minimo']
        progresso = int((gasto - atual['minimo']) / faixa * 100)
        faltam = proximo['minimo'] - gasto

    return {
        'atual': atual,
        'proximo': proximo,
        'indice': indice,
        'gasto': gasto,
        'faltam': faltam,
        'progresso': progresso,
        'niveis': LEVELS,
    }

def cashback_for(valor_pago, config, multiplicador):
    return _to_coins(valor_pago * config.coins_cashback_rate / Decimal('100') * multiplicador)

def redeem_rate(config):
    return min(config.coins_max_redeem_rate, config.commission_rate)

def redeemable_cap(valor, config):
    return _to_coins(valor * redeem_rate(config) / Decimal('100'))

def _cashback_pending_orders(user, config, agora):
    fim_devolucao = agora - timedelta(days=config.return_window_days)
    return Order.objects.filter(buyer=user).filter(
        Q(status='COMPLETED') | Q(status__in=('DELIVERED', 'RETURN_WINDOW'), updated_at__lte=fim_devolucao)
    ).exclude(coin_transactions__kind='PURCHASE').select_related('product')

def _refund_pending_orders(user, config, agora):
    fim_contestacao = agora - timedelta(days=config.dispute_window_days)
    return Order.objects.filter(buyer=user, coins_used__gt=0).filter(
        Q(status__in=('CANCELLED', 'RETURNED'))
        | Q(status='CANCELLED_NO_RETURN', dispute__status='RESOLVED_BUYER_REFUND')
        | Q(status='CANCELLED_NO_RETURN', dispute__isnull=True, updated_at__lte=fim_contestacao)
    ).exclude(coin_transactions__kind='REFUND').select_related('product')

def sync_wallet(user):
    config = PlatformConfig.load()
    agora = timezone.now()
    multiplicador = level_info(user)['atual']['multiplicador']

    for order in _cashback_pending_orders(user, config, agora):
        CoinTransaction.objects.get_or_create(
            order=order, kind='PURCHASE',
            defaults={
                'user': user,
                'amount': cashback_for(order.total_price - order.coins_discount, config, multiplicador),
                'description': f'Cashback · {order.product.title}',
            },
        )

    for order in _refund_pending_orders(user, config, agora):
        CoinTransaction.objects.get_or_create(
            order=order, kind='REFUND',
            defaults={
                'user': user,
                'amount': order.coins_used,
                'description': f'Moedas devolvidas · {order.product.title}',
            },
        )

def expected_cashback(user):
    config = PlatformConfig.load()
    multiplicador = level_info(user)['atual']['multiplicador']
    pedidos = Order.objects.filter(buyer=user, status__in=EXPECTED_CASHBACK_STATUSES).exclude(coin_transactions__kind='PURCHASE')
    return sum(cashback_for(o.total_price - o.coins_discount, config, multiplicador) for o in pedidos)

def annotate_orders(user, orders):
    config = PlatformConfig.load()
    multiplicador = level_info(user)['atual']['multiplicador']
    creditados = dict(
        CoinTransaction.objects.filter(order__in=orders, kind='PURCHASE').values_list('order_id', 'amount')
    )
    for order in orders:
        order.coins_earned = creditados.get(order.pk)
        order.coins_expected = None
        if order.coins_earned is None and order.status in EXPECTED_CASHBACK_STATUSES:
            order.coins_expected = cashback_for(order.total_price - order.coins_discount, config, multiplicador)

def checkout_preview(user, total, subtotais):
    config = PlatformConfig.load()
    saldo = balance(user)
    usaveis = min(saldo, sum(redeemable_cap(s, config) for s in subtotais))
    desconto = coins_to_brl(usaveis)
    multiplicador = level_info(user)['atual']['multiplicador']
    return {
        'saldo': saldo,
        'usaveis': usaveis,
        'desconto': desconto,
        'total_com_moedas': total - desconto,
        'cashback_previsto': cashback_for(total, config, multiplicador),
        'taxa_resgate': redeem_rate(config),
    }

def apply_redemption(user, orders):
    config = PlatformConfig.load()
    with transaction.atomic():
        disponivel = balance(user)
        for order in orders:
            coins = min(disponivel, redeemable_cap(order.total_price, config))
            if coins <= 0:
                continue
            order.coins_used = coins
            order.coins_discount = coins_to_brl(coins)
            order.save(update_fields=['coins_used', 'coins_discount'])
            CoinTransaction.objects.create(
                user=user, order=order, kind='REDEEM', amount=-coins,
                description=f'Desconto · {order.product.title}',
            )
            disponivel -= coins

def _checkin_dates(user):
    referencias = CoinTransaction.objects.filter(
        user=user, kind='CHECKIN', created_at__gte=timezone.now() - timedelta(days=60)
    ).values_list('reference', flat=True)
    return {date.fromisoformat(r.removeprefix('checkin:')) for r in referencias}

def checkin_status(user):
    hoje = timezone.localdate()
    datas = _checkin_dates(user)
    feito_hoje = hoje in datas

    dia = hoje if feito_hoje else hoje - timedelta(days=1)
    sequencia = 0
    while dia in datas:
        sequencia += 1
        dia -= timedelta(days=1)

    ciclo = len(CHECKIN_REWARDS)
    concluidos = ((sequencia - 1) % ciclo) + 1 if feito_hoje else sequencia % ciclo
    proximo = concluidos - 1 if feito_hoje else concluidos

    return {
        'feito_hoje': feito_hoje,
        'sequencia': sequencia,
        'recompensa': CHECKIN_REWARDS[proximo],
        'total_semana': sum(CHECKIN_REWARDS),
        'dias': [
            {'numero': i + 1, 'moedas': moedas, 'feito': i < concluidos, 'hoje': i == proximo}
            for i, moedas in enumerate(CHECKIN_REWARDS)
        ],
    }

def do_checkin(user):
    status = checkin_status(user)
    if status['feito_hoje']:
        return None

    dia = next(d for d in status['dias'] if d['hoje'])
    _, criado = CoinTransaction.objects.get_or_create(
        user=user, kind='CHECKIN', reference=f'checkin:{timezone.localdate().isoformat()}',
        defaults={'amount': dia['moedas'], 'description': f'Check-in diário · dia {dia["numero"]}'},
    )
    return dia['moedas'] if criado else None

def credit_review(user, reference, description):
    moedas = PlatformConfig.load().coins_review_reward
    if not moedas:
        return
    CoinTransaction.objects.get_or_create(
        user=user, kind='REVIEW', reference=reference,
        defaults={'amount': moedas, 'description': description},
    )