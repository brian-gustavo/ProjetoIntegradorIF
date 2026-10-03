from decimal import Decimal, ROUND_DOWN
from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from catalog.templatetags.catalog_extras import brl
from orders.models import Order, PlatformConfig
from rewards.services import checkout_preview
from .models import Coupon, CouponRedemption, SavedCoupon

AUTO = 'auto'
CENT = Decimal('0.01')

def _floor(valor):
    return valor.quantize(CENT, rounding=ROUND_DOWN)

def normalize_code(code):
    return ''.join((code or '').split()).upper()

def active_redemptions():
    pedidos = Order.objects.filter(
        Q(seller_coupon=OuterRef('pk')) | Q(platform_coupon=OuterRef('pk'))
    ).exclude(status='CANCELLED')
    return CouponRedemption.objects.filter(Exists(pedidos))

def visible_coupons(user):
    return Coupon.objects.filter(Q(is_public=True) | Q(saves__user=user)).distinct()

def valid_now(qs, agora=None):
    agora = agora or timezone.now()
    return qs.filter(active=True, starts_at__lte=agora).filter(Q(ends_at__isnull=True) | Q(ends_at__gt=agora))

def annotate_usage(coupons, user=None):
    ids = [c.pk for c in coupons]
    usos = active_redemptions().filter(coupon_id__in=ids)
    total = dict(usos.values('coupon_id').annotate(n=Count('id')).values_list('coupon_id', 'n'))
    do_usuario = dict(
        usos.filter(user=user).values('coupon_id').annotate(n=Count('id')).values_list('coupon_id', 'n')
    ) if user else {}
    for c in coupons:
        c.used_total = total.get(c.pk, 0)
        c.used_by_user = do_usuario.get(c.pk, 0)
    return coupons

def purchased_sellers(user):
    compras = Order.objects.filter(buyer=user).exclude(status__in=('PENDING', 'CANCELLED'))
    return set(compras.values_list('product__seller_id', flat=True))

def blocking_reason(coupon, user, compras, agora=None):
    agora = agora or timezone.now()
    if not coupon.active:
        return 'Cupom encerrado'
    if coupon.starts_at > agora:
        return f'Válido a partir de {timezone.localtime(coupon.starts_at):%d/%m às %H:%M}'
    if coupon.ends_at and coupon.ends_at <= agora:
        return 'Cupom expirado'
    if coupon.seller_id == user.pk:
        return 'Este cupom é da sua própria loja'
    if coupon.usage_limit is not None and coupon.used_total >= coupon.usage_limit:
        return 'Cupom esgotado'
    if coupon.used_by_user >= coupon.per_user_limit:
        return 'Você já usou este cupom' if coupon.per_user_limit == 1 else 'Você atingiu o limite de usos deste cupom'
    if coupon.first_purchase_only:
        if coupon.is_platform and compras:
            return 'Exclusivo para a primeira compra na MegaGame'
        if not coupon.is_platform and coupon.seller_id in compras:
            return 'Exclusivo para a primeira compra na loja'
    return None

def coupon_status(coupon, agora=None):
    agora = agora or timezone.now()
    if not coupon.active:
        return 'Encerrado', 'badge-cancelled'
    if coupon.ends_at and coupon.ends_at <= agora:
        return 'Expirado', 'badge-default'
    if coupon.usage_limit is not None and coupon.used_total >= coupon.usage_limit:
        return 'Esgotado', 'badge-default'
    if coupon.starts_at > agora:
        return 'Agendado', 'badge-pending'
    return 'Ativo', 'badge-paid'

def available_coupons(user, sellers=None):
    agora = timezone.now()
    qs = valid_now(visible_coupons(user), agora).select_related('seller', 'category')
    if sellers is not None:
        qs = qs.filter(Q(seller__isnull=True) | Q(seller_id__in=sellers))
    cupons = annotate_usage(list(qs), user)
    compras = purchased_sellers(user)
    return [c for c in cupons if blocking_reason(c, user, compras, agora) is None]

def store_coupons(seller):
    cupons = annotate_usage(list(valid_now(seller.coupons.filter(is_public=True)).select_related('category')))
    return [c for c in cupons if c.usage_limit is None or c.used_total < c.usage_limit]

def redeem_code(user, code):
    code = normalize_code(code)
    if not code:
        return None, 'Digite o código do cupom'

    coupon = Coupon.objects.filter(code=code).select_related('seller').first()
    if not coupon:
        return None, 'Cupom não encontrado. Confira o código digitado.'
    if coupon.seller_id == user.pk:
        return None, 'Você não pode usar cupons da sua própria loja'

    agora = timezone.now()
    if not coupon.active or (coupon.ends_at and coupon.ends_at <= agora):
        return None, 'Este cupom não está mais disponível'

    SavedCoupon.objects.get_or_create(user=user, coupon=coupon)
    return coupon, None

def _distribuir(total, bases, tetos):
    soma = sum(bases)
    partes = [min(_floor(total * b / soma), t) for b, t in zip(bases, tetos)]
    resto = total - sum(partes)
    for i in sorted(range(len(partes)), key=lambda i: bases[i], reverse=True):
        if resto <= 0:
            break
        extra = min(resto, tetos[i] - partes[i])
        partes[i] += extra
        resto -= extra
    return partes

def _opcao(coupon, user, pedidos, compras, agora, base_de, teto_de):
    opcao = {'cupom': coupon, 'desconto': Decimal('0'), 'motivo': None, 'pedidos': [], 'limitado': False}

    motivo = blocking_reason(coupon, user, compras, agora)
    elegiveis = [p for p in pedidos if coupon.category_id is None or p.product.category_id == coupon.category_id]
    if not motivo and not elegiveis:
        motivo = f'Válido apenas para {coupon.category.name}'
    base = sum((base_de(p) for p in elegiveis), Decimal('0'))
    if not motivo and base < coupon.min_order_value:
        motivo = f'Faltam R$ {brl(coupon.min_order_value - base)} para usar este cupom'
    if motivo:
        opcao['motivo'] = motivo
        return opcao

    desconto = coupon.discount_for(base)
    teto = sum((teto_de(p) for p in elegiveis), Decimal('0'))
    if desconto > teto:
        desconto, opcao['limitado'] = teto, True

    opcao['desconto'] = desconto
    opcao['pedidos'] = elegiveis
    return opcao

def _escolher(opcoes, escolha):
    usaveis = [o for o in opcoes if not o['motivo'] and o['desconto'] > 0]
    if escolha == AUTO:
        return max(usaveis, key=lambda o: o['desconto'], default=None)
    return next((o for o in usaveis if o['cupom'].pk == escolha), None)

def _ordenar(opcoes):
    return sorted(opcoes, key=lambda o: (o['motivo'] is not None, -o['desconto'], o['cupom'].code))

def _aplicar(opcao, campo, base_de, teto_de):
    pedidos = opcao['pedidos']
    partes = _distribuir(opcao['desconto'], [base_de(p) for p in pedidos], [teto_de(p) for p in pedidos])
    for pedido, parte in zip(pedidos, partes):
        setattr(pedido, campo, parte)

def parse_choice(valor):
    if valor is None or valor == AUTO:
        return AUTO
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None

def build_quote(user, items, escolhas=None, pickups=None):
    escolhas = escolhas or {}
    pickups = pickups or {}
    config = PlatformConfig.load()
    agora = timezone.now()

    pedidos = []
    lojas = {}
    for item in items:
        pedido = Order(
            buyer=user, product=item.product, variant=item.variant, quantity=item.quantity,
            total_price=item.subtotal, pickup=pickups.get(item.pk, False) and item.product.accepts_pickup,
        )
        pedido.cart_item = item
        pedidos.append(pedido)
        loja = lojas.setdefault(item.product.seller_id, {'vendedor': item.product.seller, 'pedidos': []})
        loja['pedidos'].append(pedido)

    candidatos = annotate_usage(list(
        valid_now(visible_coupons(user), agora)
        .filter(Q(seller__isnull=True) | Q(seller_id__in=lojas))
        .select_related('seller', 'category')
    ), user)
    compras = purchased_sellers(user)

    valor_cheio = lambda p: p.total_price
    valor_venda = lambda p: p.sale_amount
    teto_plataforma = lambda p: _floor(p.sale_amount * config.commission_rate / Decimal('100'))

    for seller_id, loja in lojas.items():
        opcoes = [
            _opcao(c, user, loja['pedidos'], compras, agora, valor_cheio, valor_cheio)
            for c in candidatos if c.seller_id == seller_id
        ]
        escolhida = _escolher(opcoes, escolhas.get(f'cupom_loja_{seller_id}', AUTO))
        if escolhida:
            _aplicar(escolhida, 'seller_coupon_discount', valor_cheio, valor_cheio)
        loja['opcoes'] = _ordenar(opcoes)
        loja['escolhida'] = escolhida
        loja['usaveis'] = sum(1 for o in opcoes if not o['motivo'])
        loja['subtotal'] = sum(p.total_price for p in loja['pedidos'])
        loja['campo'] = f'cupom_loja_{seller_id}'

    opcoes = [
        _opcao(c, user, pedidos, compras, agora, valor_venda, teto_plataforma)
        for c in candidatos if c.is_platform
    ]
    escolhida = _escolher(opcoes, escolhas.get('cupom_plataforma', AUTO))
    if escolhida:
        _aplicar(escolhida, 'platform_coupon_discount', valor_venda, teto_plataforma)

    subtotal = sum((p.total_price for p in pedidos), Decimal('0'))
    desconto_lojas = sum((p.seller_coupon_discount for p in pedidos), Decimal('0'))
    desconto_plataforma = sum((p.platform_coupon_discount for p in pedidos), Decimal('0'))
    moedas = checkout_preview(user, pedidos)

    return {
        'pedidos': pedidos,
        'lojas': list(lojas.values()),
        'plataforma': {
            'opcoes': _ordenar(opcoes),
            'escolhida': escolhida,
            'usaveis': sum(1 for o in opcoes if not o['motivo']),
        },
        'subtotal': subtotal,
        'desconto_lojas': desconto_lojas,
        'desconto_plataforma': desconto_plataforma,
        'desconto_cupons': desconto_lojas + desconto_plataforma,
        'total': subtotal - desconto_lojas - desconto_plataforma,
        'economia_com_moedas': desconto_lojas + desconto_plataforma + moedas['desconto'],
        'moedas': moedas,
    }

def selected_ids(quote):
    ids = {loja['campo']: loja['escolhida']['cupom'].pk if loja['escolhida'] else None for loja in quote['lojas']}
    escolhida = quote['plataforma']['escolhida']
    ids['cupom_plataforma'] = escolhida['cupom'].pk if escolhida else None
    return ids

def save_redemptions(user, quote):
    usos = [(loja['escolhida'], 'seller_coupon') for loja in quote['lojas'] if loja['escolhida']]
    if quote['plataforma']['escolhida']:
        usos.append((quote['plataforma']['escolhida'], 'platform_coupon'))

    for opcao, campo in usos:
        uso = CouponRedemption.objects.create(coupon=opcao['cupom'], user=user, discount=opcao['desconto'])
        for pedido in opcao['pedidos']:
            setattr(pedido, campo, uso)

def coupon_stats(coupons):
    ids = [c.pk for c in coupons]
    pedidos = Order.objects.exclude(status='CANCELLED')
    linhas = {}
    for prefixo in ('seller_coupon', 'platform_coupon'):
        for linha in (
            pedidos.filter(**{f'{prefixo}__coupon_id__in': ids})
            .values(f'{prefixo}__coupon_id')
            .annotate(desconto=Sum(f'{prefixo}_discount'), vendas=Sum('total_price'), pedidos=Count('id'))
        ):
            linhas[linha[f'{prefixo}__coupon_id']] = linha

    annotate_usage(coupons)
    usados = set(CouponRedemption.objects.filter(coupon_id__in=ids).values_list('coupon_id', flat=True))
    agora = timezone.now()
    for c in coupons:
        c.ever_used = c.pk in usados
        linha = linhas.get(c.pk, {})
        c.discount_total = linha.get('desconto') or Decimal('0')
        c.sales_total = linha.get('vendas') or Decimal('0')
        c.orders_total = linha.get('pedidos') or 0
        c.status_label, c.status_class = coupon_status(c, agora)
    return coupons