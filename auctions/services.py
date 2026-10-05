from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.db import transaction
from django.db.models import Max, Q
from django.utils import timezone

from catalog.models import Product, ProductImage, ProductVariant
from catalog.templatetags.catalog_extras import brl
from orders.models import Order, PlatformConfig
from .models import Auction, AuctionWatch, Bid, SecondChanceOffer

VARIANT_NAME = 'Leilão'
EARLY_END_MIN_HOURS = 12
BUY_NOW_MIN_MARKUP = Decimal('1.30')

INCREMENTS = [
    (Decimal('1.00'), Decimal('0.05')),
    (Decimal('5.00'), Decimal('0.25')),
    (Decimal('25.00'), Decimal('0.50')),
    (Decimal('100.00'), Decimal('1.00')),
    (Decimal('250.00'), Decimal('2.50')),
    (Decimal('500.00'), Decimal('5.00')),
    (Decimal('1000.00'), Decimal('10.00')),
    (Decimal('2500.00'), Decimal('25.00')),
    (Decimal('5000.00'), Decimal('50.00')),
    (None, Decimal('100.00')),
]

def increment_for(price):
    return next(passo for limite, passo in INCREMENTS if limite is None or price < limite)

def increment_table():
    linhas, inicio = [], Decimal('0.00')
    for limite, passo in INCREMENTS:
        linhas.append({'de': inicio, 'ate': limite - Decimal('0.01') if limite else None, 'incremento': passo})
        inicio = limite
    return linhas

def parse_amount(valor):
    valor = (valor or '').strip().replace('R$', '').replace(' ', '')
    if ',' in valor:
        valor = valor.replace('.', '').replace(',', '.')
    try:
        quantia = Decimal(valor)
    except InvalidOperation:
        return None
    if not quantia.is_finite() or quantia <= 0:
        return None
    return quantia.quantize(Decimal('0.01'))

def mask_username(username):
    if len(username) <= 2:
        return f'{username[0]}***'
    return f'{username[0]}***{username[-1]}'

def _active_bids(auction):
    return auction.bids.filter(retracted_at__isnull=True)

def _rank(melhores):
    return sorted(melhores.values(), key=lambda b: (-b.amount, b.created_at, b.pk))

def _keep_best(melhores, bid):
    atual = melhores.get(bid.bidder_id)
    if atual is None or bid.amount > atual.amount:
        melhores[bid.bidder_id] = bid

def _ranking(auction):
    melhores = {}
    for bid in _active_bids(auction).filter(is_auto=False).select_related('bidder').order_by('created_at', 'pk'):
        _keep_best(melhores, bid)
    return _rank(melhores)

def _price_for(auction, ranking):
    if not ranking:
        return auction.start_price
    lider = ranking[0]
    if len(ranking) == 1:
        preco = auction.start_price
    else:
        segundo = ranking[1].amount
        preco = min(lider.amount, segundo + increment_for(segundo))
    if auction.has_reserve and lider.amount >= auction.reserve_price and preco < auction.reserve_price:
        preco = auction.reserve_price
    return preco

def minimum_bid(auction):
    if auction.bid_count == 0:
        return auction.start_price
    return auction.current_price + increment_for(auction.current_price)

def user_max(auction, user):
    return _active_bids(auction).filter(bidder=user, is_auto=False).aggregate(m=Max('amount'))['m']

def _sync_variant_price(auction, preco):
    ProductVariant.objects.filter(product_id=auction.product_id).update(price=preco)

def apply_bid(auction, user, amount, agora):
    era_lider = auction.leader_id == user.pk
    Bid.objects.create(auction=auction, bidder=user, amount=amount, created_at=agora)

    ranking = _ranking(auction)
    preco = _price_for(auction, ranking)
    lider = ranking[0]
    if lider.bidder_id != user.pk:
        Bid.objects.create(auction=auction, bidder_id=lider.bidder_id, amount=preco, is_auto=True, created_at=agora)

    _save_state(auction, preco, lider.bidder_id)
    return {'lider': lider.bidder_id == user.pk, 'aumentou': era_lider, 'preco': preco}

def _save_state(auction, preco, lider_id):
    auction.current_price = preco
    auction.leader_id = lider_id
    auction.bid_count = _active_bids(auction).count()
    auction.save(update_fields=['current_price', 'leader', 'bid_count'])
    _sync_variant_price(auction, preco)

def rebuild_bids(auction):
    auction.bids.filter(is_auto=True).delete()
    melhores = {}
    for bid in list(_active_bids(auction).filter(is_auto=False).order_by('created_at', 'pk')):
        _keep_best(melhores, bid)
        ranking = _rank(melhores)
        if ranking[0].bidder_id != bid.bidder_id:
            Bid.objects.create(
                auction=auction, bidder_id=ranking[0].bidder_id, amount=_price_for(auction, ranking),
                is_auto=True, created_at=bid.created_at,
            )
    ranking = _rank(melhores)
    _save_state(auction, _price_for(auction, ranking), ranking[0].bidder_id if ranking else None)

LATE_RETRACTION_HOURS = 12
LATE_RETRACTION_WINDOW = timedelta(hours=1)

def retractable_bids(auction, user, agora=None):
    agora = agora or timezone.now()
    if not auction.is_open:
        return []
    ativos = _active_bids(auction).filter(bidder=user, is_auto=False).order_by('-created_at', '-pk')
    if auction.ends_at - agora >= timedelta(hours=LATE_RETRACTION_HOURS):
        return list(ativos)
    ultimo = ativos.first()
    return [ultimo] if ultimo and ultimo.created_at >= agora - LATE_RETRACTION_WINDOW else []

def retract_bids(auction_id, user, motivo):
    if motivo not in dict(Bid.RETRACTION_CHOICES):
        return None, 'Escolha o motivo da retirada.'
    with transaction.atomic():
        auction = Auction.objects.select_for_update().select_related('product').get(pk=auction_id)
        agora = timezone.now()
        lances = retractable_bids(auction, user, agora)
        if not lances:
            return None, 'Você não tem lances que possam ser retirados neste leilão.'
        Bid.objects.filter(pk__in=[b.pk for b in lances]).update(retracted_at=agora, retraction_reason=motivo)
        rebuild_bids(auction)
        return {'quantidade': len(lances), 'preco': auction.current_price}, None

def _bid_blocker(auction, user):
    if not auction.is_open:
        return 'Este leilão já foi encerrado.'
    if user.is_staff:
        return 'Contas da equipe MegaGame não podem participar de leilões.'
    if auction.product.seller_id == user.pk:
        return 'Você não pode participar do seu próprio leilão.'
    return None

def place_bid(auction_id, user, amount):
    with transaction.atomic():
        auction = Auction.objects.select_for_update().select_related('product').get(pk=auction_id)
        erro = _bid_blocker(auction, user)
        if erro:
            return None, erro
        if amount is None:
            return None, 'Informe um valor de lance válido.'

        if auction.leader_id == user.pk:
            maximo = user_max(auction, user)
            if amount <= maximo:
                return None, f'Seu lance máximo atual é R$ {brl(maximo)}. Para aumentá-lo, informe um valor maior.'
        else:
            minimo = minimum_bid(auction)
            if amount < minimo:
                return None, f'Informe R$ {brl(minimo)} ou mais.'

        return apply_bid(auction, user, amount, timezone.now()), None

def _create_order(auction, buyer, preco):
    _sync_variant_price(auction, preco)
    return Order.objects.create(
        buyer=buyer,
        product=auction.product,
        variant=auction.product.variants.first(),
        quantity=1,
        total_price=preco,
        status='PENDING',
    )

def _finish(auction, agora, vencedor=None, preco=None):
    if vencedor:
        auction.status = 'SOLD'
        auction.winner = vencedor
        auction.current_price = preco
        auction.order = _create_order(auction, vencedor, preco)
        auction.payment_due_at = agora + timedelta(days=PlatformConfig.load().auction_payment_days)
    else:
        auction.status = 'UNSOLD'
    auction.closed_at = agora
    auction.save()
    Product.objects.filter(pk=auction.product_id).update(published=False, updated_at=agora)

def close_auction(auction, agora=None, antecipado=False):
    agora = agora or timezone.now()
    if antecipado:
        auction.ended_early = True
        auction.ends_at = agora
    vencedor = auction.leader if auction.leader_id and auction.reserve_met else None
    _finish(auction, agora, vencedor, auction.current_price)

def close_expired_auctions():
    agora = timezone.now()
    for pk in Auction.objects.filter(status='ACTIVE', ends_at__lte=agora).values_list('pk', flat=True):
        with transaction.atomic():
            auction = Auction.objects.select_for_update().select_related('product', 'leader').get(pk=pk)
            if auction.status == 'ACTIVE' and auction.ends_at <= agora:
                close_auction(auction, agora)
    SecondChanceOffer.objects.filter(status='PENDING', expires_at__lte=agora).update(status='EXPIRED')

def buy_now(auction_id, user):
    with transaction.atomic():
        auction = Auction.objects.select_for_update().select_related('product').get(pk=auction_id)
        erro = _bid_blocker(auction, user)
        if erro:
            return None, erro
        if not auction.buy_now_available:
            return None, 'A opção Comprar agora não está mais disponível para este leilão.'

        agora = timezone.now()
        auction.bought_now = True
        auction.ends_at = agora
        _finish(auction, agora, user, auction.buy_now_price)
        return auction.order, None

def end_early(auction_id, user):
    with transaction.atomic():
        auction = Auction.objects.select_for_update().select_related('product', 'leader').get(pk=auction_id, product__seller=user)
        if not auction.is_open:
            return None, 'Este leilão já foi encerrado.'
        restante = auction.ends_at - timezone.now()
        if auction.bid_count and restante < timedelta(hours=EARLY_END_MIN_HOURS):
            return None, f'Leilões com lances não podem ser encerrados nas últimas {EARLY_END_MIN_HOURS} horas.'
        close_auction(auction, antecipado=True)
        return auction, None

def can_cancel_unpaid(auction):
    return (
        auction.status == 'SOLD'
        and auction.order is not None
        and auction.order.status == 'PENDING'
        and auction.payment_due_at is not None
        and timezone.now() >= auction.payment_due_at
    )

def cancel_unpaid(auction):
    if not can_cancel_unpaid(auction):
        return 'O prazo de pagamento deste leilão ainda não terminou.'
    auction.order.status = 'CANCELLED'
    auction.order.save()
    return None

def _sale_in_progress(auction):
    return auction.status == 'SOLD' and auction.order is not None and auction.order.status != 'CANCELLED'

def _pending_offer(auction):
    return auction.second_chance_offers.filter(status='PENDING', expires_at__gt=timezone.now()).first()

def can_relist(auction):
    if auction.relisted_as_id or auction.product.deleted or auction.status == 'ACTIVE':
        return False
    return not _sale_in_progress(auction) and _pending_offer(auction) is None

def second_chance_window_days():
    return PlatformConfig.load().second_chance_window_days

def second_chance_blocker(auction):
    if auction.status == 'ACTIVE':
        return 'O leilão ainda está em andamento.'
    if auction.relisted_as_id or auction.product.deleted:
        return 'Este item já foi relistado ou excluído.'
    janela = second_chance_window_days()
    if timezone.now() > auction.closed_at + timedelta(days=janela):
        return f'Ofertas de segunda chance só podem ser enviadas até {janela} dias após o fim do leilão.'
    if _sale_in_progress(auction):
        return 'O item já tem uma venda em andamento.'
    if _pending_offer(auction):
        return 'Já existe uma oferta de segunda chance aguardando resposta.'
    return None

def second_chance_candidates(auction):
    excluidos = set(auction.second_chance_offers.values_list('bidder_id', flat=True))
    excluidos |= set(Order.objects.filter(product_id=auction.product_id).values_list('buyer_id', flat=True))
    return [
        {'bidder': bid.bidder, 'preco': bid.amount, 'abaixo_da_reserva': auction.has_reserve and bid.amount < auction.reserve_price}
        for bid in _ranking(auction) if bid.bidder_id not in excluidos
    ]

def can_send_second_chance(auction):
    return second_chance_blocker(auction) is None and bool(second_chance_candidates(auction))

def send_second_chance(auction_id, seller, bidder_id, duracao):
    with transaction.atomic():
        auction = Auction.objects.select_for_update().select_related('product', 'order').get(pk=auction_id, product__seller=seller)
        erro = second_chance_blocker(auction)
        if erro:
            return None, erro
        if duracao not in dict(SecondChanceOffer.DURATION_CHOICES):
            return None, 'Escolha a validade da oferta.'
        candidato = next((c for c in second_chance_candidates(auction) if c['bidder'].pk == bidder_id), None)
        if not candidato:
            return None, 'Escolha um participante válido.'

        agora = timezone.now()
        return SecondChanceOffer.objects.create(
            auction=auction, bidder=candidato['bidder'], price=candidato['preco'], duration_days=duracao,
            created_at=agora, expires_at=agora + timedelta(days=duracao),
        ), None

def respond_second_chance(offer_id, user, aceitar):
    with transaction.atomic():
        offer = SecondChanceOffer.objects.select_for_update().get(pk=offer_id, bidder=user)
        auction = Auction.objects.select_for_update().select_related('product', 'order').get(pk=offer.auction_id)
        if not offer.is_pending:
            return None, 'Esta oferta não está mais disponível.'

        agora = timezone.now()
        offer.responded_at = agora
        if not aceitar:
            offer.status = 'DECLINED'
            offer.save()
            return offer, None

        if auction.relisted_as_id or auction.product.deleted or _sale_in_progress(auction):
            offer.status = 'EXPIRED'
            offer.save()
            return None, 'O item não está mais disponível.'

        auction.status = 'SOLD'
        auction.winner = user
        auction.current_price = offer.price
        auction.order = _create_order(auction, user, offer.price)
        auction.payment_due_at = agora + timedelta(days=PlatformConfig.load().auction_payment_days)
        auction.save()
        offer.status = 'ACCEPTED'
        offer.order = auction.order
        offer.save()
        return offer, None

def publish(product, auction, agora=None):
    agora = agora or timezone.now()
    ProductVariant.objects.create(product=product, name=VARIANT_NAME, price=auction.start_price, quantity=1)
    auction.product = product
    auction.starts_at = agora
    auction.ends_at = agora + timedelta(days=auction.duration_days)
    auction.current_price = auction.start_price
    auction.save()
    product.published = True
    product.save()
    return auction

def relist(auction):
    with transaction.atomic():
        antigo = auction.product
        novo = Product.objects.create(
            category=antigo.category,
            seller=antigo.seller,
            title=antigo.title,
            description=antigo.description,
            condition=antigo.condition,
            accepts_pickup=antigo.accepts_pickup,
        )
        ProductImage.objects.bulk_create([ProductImage(product=novo, image=img.image.name) for img in antigo.images.all()])
        novo_leilao = publish(novo, Auction(
            start_price=auction.start_price,
            reserve_price=auction.reserve_price,
            buy_now_price=auction.buy_now_price,
            duration_days=auction.duration_days,
        ))
        auction.relisted_as = novo_leilao
        auction.save(update_fields=['relisted_as'])
        return novo

def apply_edit(auction):
    auction.ends_at = auction.starts_at + timedelta(days=auction.duration_days)
    auction.current_price = auction.start_price
    auction.save()
    _sync_variant_price(auction, auction.start_price)

def close_for_deletion(auction):
    if auction.is_open and auction.bid_count:
        return 'Leilões com lances não podem ser excluídos. Encerre o leilão primeiro.'
    if auction.status == 'ACTIVE':
        close_auction(auction, antecipado=True)
    return None

def bid_history(auction, viewer=None):
    linhas = []
    retirados = []
    for bid in auction.bids.select_related('bidder'):
        proprio = viewer is not None and bid.bidder_id == viewer.pk
        linha = {
            'participante': 'Você' if proprio else mask_username(bid.bidder.username),
            'proprio': proprio,
            'valor': bid.amount if bid.is_auto else min(bid.amount, auction.current_price),
            'automatico': bid.is_auto,
            'momento': bid.created_at,
            'ordem': bid.pk,
            'retirado_em': bid.retracted_at,
            'motivo_retirada': bid.get_retraction_reason_display(),
        }
        (retirados if bid.retracted_at else linhas).append(linha)
    linhas.sort(key=lambda l: (-l['valor'], l['momento'], l['ordem']))
    retirados.sort(key=lambda l: l['retirado_em'], reverse=True)
    return linhas, retirados

def bidder_count(auction):
    return _active_bids(auction).values('bidder').distinct().count()

def suggested_bids(minimo):
    passo = increment_for(minimo)
    return [minimo, minimo + passo * 2, minimo + passo * 5]

def detail_context(auction, user):
    contexto = {
        'auction': auction,
        'minimum_bid': minimum_bid(auction),
        'watchers': auction.watches.count(),
        'bidders': bidder_count(auction),
        'early_end_hours': EARLY_END_MIN_HOURS,
        'can_end_early': auction.is_open and (
            not auction.bid_count or auction.ends_at - timezone.now() >= timedelta(hours=EARLY_END_MIN_HOURS)
        ),
        'can_relist': can_relist(auction),
        'can_cancel_unpaid': can_cancel_unpaid(auction),
    }
    if user.is_authenticated and user.pk == auction.product.seller_id and auction.status != 'ACTIVE':
        contexto.update({
            'can_second_chance': can_send_second_chance(auction),
            'second_chance_offers': auction.second_chance_offers.select_related('bidder'),
        })
    if user.is_authenticated:
        maximo = user_max(auction, user)
        contexto.update({
            'watching': auction.watches.filter(user=user).exists(),
            'my_max': maximo,
            'is_leader': auction.leader_id == user.pk,
            'is_winner': auction.winner_id == user.pk,
            'can_bid': _bid_blocker(auction, user) is None,
            'can_retract': bool(retractable_bids(auction, user)),
            'my_offer': auction.second_chance_offers.filter(bidder=user).first(),
        })
        if maximo and auction.leader_id == user.pk:
            contexto['suggested'] = []
        else:
            contexto['suggested'] = suggested_bids(contexto['minimum_bid'])
    return contexto

def toggle_watch(auction, user):
    watch, criado = AuctionWatch.objects.get_or_create(user=user, auction=auction)
    if not criado:
        watch.delete()
    return criado

def my_bids(user):
    leiloes = list(
        Auction.objects.filter(Q(bids__bidder=user, bids__retracted_at__isnull=True) | Q(winner=user)).distinct()
        .select_related('product', 'order', 'winner').prefetch_related('product__images')
        .order_by('ends_at')
    )
    acompanhados = list(
        Auction.objects.filter(watches__user=user)
        .select_related('product', 'order').prefetch_related('product__images')
        .order_by('status', 'ends_at')
    )
    maximos = dict(
        Bid.objects.filter(bidder=user, is_auto=False, retracted_at__isnull=True)
        .values('auction').annotate(m=Max('amount')).values_list('auction', 'm')
    )
    for leilao in leiloes + acompanhados:
        leilao.my_max = maximos.get(leilao.pk)
        leilao.is_leader = leilao.leader_id == user.pk

    ofertas = list(
        user.second_chance_offers.select_related('auction__product', 'order')
        .prefetch_related('auction__product__images')
    )
    ofertas.sort(key=lambda o: (not o.is_pending, -o.created_at.timestamp()))

    return {
        'ativos': [l for l in leiloes if l.status == 'ACTIVE'],
        'vencidos': sorted([l for l in leiloes if l.winner_id == user.pk], key=lambda l: l.closed_at, reverse=True),
        'perdidos': sorted([l for l in leiloes if l.status != 'ACTIVE' and l.winner_id != user.pk], key=lambda l: l.closed_at, reverse=True),
        'acompanhando': acompanhados,
        'ofertas': ofertas,
    }