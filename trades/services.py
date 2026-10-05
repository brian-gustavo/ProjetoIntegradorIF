from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from catalog.models import Product, ProductVariant
from catalog.templatetags.catalog_extras import brl
from orders.models import Commission, Order, PlatformConfig
from .models import OWNER, PROPOSER, TradeEvent, TradeItem, TradeProposal

MAX_ITEMS = 5
MESSAGE_MAX_LENGTH = 500
RESERVING_STATUSES = ('PAID', 'CONFIRMED', 'PREPARING', 'SHIPPED', 'READY_PICKUP')
CANCELLABLE_STATUSES = ('PENDING', 'PAID', 'CONFIRMED', 'PREPARING')
FINISHED_STATUSES = ('DELIVERED', 'RETURN_WINDOW', 'COMPLETED')
AFTER_SALE_STATUSES = ('RETURN_REQUESTED', 'RETURN_ACCEPTED', 'DISPUTE_OPEN', 'RETURNED', 'CANCELLED_NO_RETURN')

def other(lado):
    return OWNER if lado == PROPOSER else PROPOSER

def _deadline(agora):
    return agora + timedelta(days=PlatformConfig.load().trade_response_days)

def _reserved_units(variant_ids):
    return dict(
        Order.objects.filter(variant_id__in=variant_ids)
        .filter(Q(status__in=RESERVING_STATUSES) | Q(status='PENDING', trade__isnull=False))
        .values('variant').annotate(n=Sum('quantity')).values_list('variant', 'n')
    )

def annotate_available(variants):
    variants = list(variants)
    reservados = _reserved_units([v.pk for v in variants])
    for variant in variants:
        variant.available = variant.quantity - reservados.get(variant.pk, 0)
    return variants

def tradeable_variants(user):
    qs = ProductVariant.objects.filter(
        product__seller=user, product__published=True, product__deleted=False,
        product__auction__isnull=True, quantity__gt=0,
    ).select_related('product').prefetch_related('product__images').order_by('product__title', 'name')
    return [v for v in annotate_available(qs) if v.available > 0]

def target_variants(product):
    return [v for v in annotate_available(product.variants.order_by('price', 'name')) if v.available > 0]

def open_proposal(product, user):
    return TradeProposal.objects.filter(
        product=product, proposer=user, status='PENDING', expires_at__gt=timezone.now(),
    ).first()

def accepts_trades(product):
    return product.accepts_trade and product.published and not product.deleted and not hasattr(product, 'auction')

def propose_blocker(product, user):
    if user.is_staff:
        return 'Contas da equipe MegaGame não podem propor trocas.'
    if product.seller_id == user.pk:
        return 'Você não pode propor uma troca no seu próprio anúncio.'
    if not accepts_trades(product):
        return 'Este anúncio não aceita propostas de troca.'
    if open_proposal(product, user):
        return 'Você já tem uma proposta em negociação para este anúncio.'
    if not target_variants(product):
        return 'Este anúncio está sem estoque disponível.'
    return None

def _clean_terms(variant, proposer, item_ids, cash_amount, cash_payer):
    item_ids = list(dict.fromkeys(item_ids))
    if not item_ids:
        return None, 'Escolha pelo menos um item para oferecer.'
    if len(item_ids) > MAX_ITEMS:
        return None, f'Escolha no máximo {MAX_ITEMS} itens.'

    disponiveis = {v.pk: v for v in tradeable_variants(proposer)}
    if any(pk not in disponiveis for pk in item_ids):
        return None, 'Um dos itens escolhidos não está mais disponível para troca.'
    itens = [disponiveis[pk] for pk in item_ids]

    if not cash_amount:
        cash_amount, cash_payer = Decimal('0.00'), ''
    elif cash_payer not in (PROPOSER, OWNER):
        return None, 'Escolha quem paga a volta.'
    elif cash_amount < 0:
        return None, 'Informe um valor de volta válido.'

    if cash_payer == PROPOSER and cash_amount >= variant.price:
        return None, f'A volta precisa ser menor que o valor do anúncio (R$ {brl(variant.price)}). Para pagar o valor cheio, compre o item.'
    valor_itens = sum((v.price for v in itens), Decimal('0.00'))
    if cash_payer == OWNER and cash_amount >= valor_itens:
        return None, f'A volta precisa ser menor que o valor de referência dos itens oferecidos (R$ {brl(valor_itens)}).'

    return {'itens': itens, 'cash_amount': cash_amount, 'cash_payer': cash_payer}, None

def _clean_message(message):
    return (message or '').strip()[:MESSAGE_MAX_LENGTH]

def describe(proposal):
    itens = ' + '.join(f'{i.product.title} ({i.variant.name})' for i in proposal.items.select_related('product', 'variant'))
    texto = f'{itens} por {proposal.product.title} ({proposal.variant.name})'
    if proposal.cash_amount:
        texto += f', com volta de R$ {brl(proposal.cash_amount)} paga por {proposal.cash_payer_user.username}'
    return texto

def _log(proposal, author, kind, agora, message='', summary=True):
    TradeEvent.objects.create(
        proposal=proposal, author=author, kind=kind, created_at=agora,
        message=_clean_message(message), summary=describe(proposal) if summary else '',
    )

def _set_items(proposal, itens):
    proposal.items.all().delete()
    TradeItem.objects.bulk_create([TradeItem(proposal=proposal, product=v.product, variant=v) for v in itens])

def propose(product_id, user, variant_id, item_ids, cash_amount, cash_payer, message=''):
    with transaction.atomic():
        product = Product.objects.select_for_update().get(pk=product_id)
        erro = propose_blocker(product, user)
        if erro:
            return None, erro
        variant = next((v for v in target_variants(product) if v.pk == variant_id), None)
        if variant is None:
            return None, 'Escolha uma variação disponível do anúncio.'
        termos, erro = _clean_terms(variant, user, item_ids, cash_amount, cash_payer)
        if erro:
            return None, erro

        agora = timezone.now()
        proposal = TradeProposal.objects.create(
            product=product, variant=variant, proposer=user, owner=product.seller,
            cash_amount=termos['cash_amount'], cash_payer=termos['cash_payer'],
            awaiting=OWNER, expires_at=_deadline(agora), created_at=agora,
        )
        _set_items(proposal, termos['itens'])
        _log(proposal, user, 'PROPOSED', agora, message)
        return proposal, None

def _locked(proposal_id):
    return TradeProposal.objects.select_for_update().select_related('product', 'variant', 'proposer', 'owner').get(pk=proposal_id)

def _turn_blocker(proposal, user):
    lado = proposal.party(user)
    if lado is None or not proposal.is_open or proposal.awaiting != lado:
        return lado, 'Esta proposta não está aguardando a sua resposta.'
    return lado, None

def counter(proposal_id, user, item_ids, cash_amount, cash_payer, message=''):
    with transaction.atomic():
        proposal = _locked(proposal_id)
        lado, erro = _turn_blocker(proposal, user)
        if erro:
            return None, erro
        termos, erro = _clean_terms(proposal.variant, proposal.proposer, item_ids, cash_amount, cash_payer)
        if erro:
            return None, erro

        atuais = set(proposal.items.values_list('variant_id', flat=True))
        novos = {v.pk for v in termos['itens']}
        if atuais == novos and termos['cash_amount'] == proposal.cash_amount and termos['cash_payer'] == proposal.cash_payer:
            return None, 'A contraproposta precisa mudar os itens ou a volta. Para concordar com os termos atuais, aceite a proposta.'

        agora = timezone.now()
        proposal.cash_amount = termos['cash_amount']
        proposal.cash_payer = termos['cash_payer']
        proposal.awaiting = other(lado)
        proposal.rounds += 1
        proposal.expires_at = _deadline(agora)
        proposal.save()
        _set_items(proposal, termos['itens'])
        _log(proposal, user, 'COUNTERED', agora, message)
        return proposal, None

def unavailable_items(proposal):
    alvo = annotate_available([proposal.variant])[0]
    itens = annotate_available([i.variant for i in proposal.items.select_related('variant__product')])
    faltando = []
    if proposal.product.deleted or alvo.available < 1:
        faltando.append(alvo)
    faltando += [v for v in itens if v.product.deleted or v.available < 1]
    return faltando

def fee_shares(taxa=None):
    taxa = PlatformConfig.load().trade_fee if taxa is None else taxa
    metade = (taxa / 2).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    return {'total': taxa, PROPOSER: taxa - metade, OWNER: metade}

def fee_context():
    taxas = fee_shares()
    return {'taxa_total': taxas['total'], 'taxa_proponente': taxas[PROPOSER], 'taxa_anunciante': taxas[OWNER]}

def _create_orders(proposal):
    taxas = fee_shares()
    status = 'PENDING' if proposal.cash_amount or taxas['total'] else 'PAID'
    zero = Decimal('0.00')

    def volta(lado):
        return proposal.cash_amount if proposal.cash_payer == lado else zero

    pedidos = [Order(
        buyer=proposal.proposer, product=proposal.product, variant=proposal.variant, quantity=1,
        total_price=volta(PROPOSER), trade_fee=taxas[PROPOSER], status=status, trade=proposal,
    )]
    for indice, item in enumerate(proposal.items.select_related('product', 'variant')):
        primeiro = indice == 0
        pedidos.append(Order(
            buyer=proposal.owner, product=item.product, variant=item.variant, quantity=1,
            total_price=volta(OWNER) if primeiro else zero, trade_fee=taxas[OWNER] if primeiro else zero,
            status=status, trade=proposal,
        ))
    for pedido in pedidos:
        pedido.save()
    return pedidos

def accept(proposal_id, user):
    with transaction.atomic():
        proposal = _locked(proposal_id)
        _, erro = _turn_blocker(proposal, user)
        if erro:
            return None, erro
        faltando = unavailable_items(proposal)
        if faltando:
            nomes = ', '.join(f'"{v.product.title} ({v.name})"' for v in faltando)
            return None, f'Não é possível aceitar agora: {nomes} não está mais disponível. Faça uma contraproposta ou recuse.'

        agora = timezone.now()
        _create_orders(proposal)
        proposal.status = 'ACCEPTED'
        proposal.closed_at = agora
        proposal.save()
        _log(proposal, user, 'ACCEPTED', agora, summary=False)
        return proposal, None

def decline(proposal_id, user, message=''):
    with transaction.atomic():
        proposal = _locked(proposal_id)
        _, erro = _turn_blocker(proposal, user)
        if erro:
            return None, erro
        return _close(proposal, user, 'DECLINED', message), None

def withdraw(proposal_id, user):
    with transaction.atomic():
        proposal = _locked(proposal_id)
        lado = proposal.party(user)
        if lado is None or not proposal.is_open or proposal.awaiting == lado:
            return None, 'Esta proposta não pode mais ser retirada.'
        return _close(proposal, user, 'WITHDRAWN'), None

def _close(proposal, user, status, message=''):
    agora = timezone.now()
    proposal.status = status
    proposal.closed_at = agora
    proposal.save()
    _log(proposal, user, status, agora, message, summary=False)
    return proposal

def can_cancel(proposal, pedidos=None):
    if proposal.status != 'ACCEPTED':
        return False
    pedidos = proposal.orders.all() if pedidos is None else pedidos
    return all(p.status in CANCELLABLE_STATUSES for p in pedidos)

def cancel(proposal_id, user):
    with transaction.atomic():
        proposal = _locked(proposal_id)
        if proposal.party(user) is None:
            return None, 'Você não participa desta troca.'
        pedidos = list(proposal.orders.select_for_update())
        if not can_cancel(proposal, pedidos):
            return None, 'A troca não pode mais ser cancelada, porque um dos itens já foi enviado ou entregue.'
        Order.objects.filter(pk__in=[p.pk for p in pedidos]).update(status='CANCELLED', updated_at=timezone.now())
        return _close(proposal, user, 'CANCELLED'), None

def awaiting_payment(pedido):
    return pedido.status == 'PENDING' and not pedido.trade_paid and pedido.amount_charged > 0

def mark_paid(order_ids):
    pagos = Order.objects.filter(pk__in=order_ids, trade__isnull=False, status='PENDING')
    trocas = set(pagos.values_list('trade', flat=True))
    pagos.update(trade_paid=True)
    for trade_id in trocas:
        pendentes = list(Order.objects.filter(trade_id=trade_id, status='PENDING'))
        if not any(awaiting_payment(p) for p in pendentes):
            Order.objects.filter(pk__in=[p.pk for p in pendentes]).update(status='PAID', updated_at=timezone.now())

def expire_trades():
    agora = timezone.now()
    vencidas = list(TradeProposal.objects.filter(status='PENDING', expires_at__lte=agora))
    if not vencidas:
        return
    TradeEvent.objects.bulk_create([TradeEvent(proposal=p, kind='EXPIRED', created_at=p.expires_at) for p in vencidas])
    TradeProposal.objects.filter(pk__in=[p.pk for p in vencidas], status='PENDING').update(status='EXPIRED', closed_at=F('expires_at'))

STAGES = {
    'pagamento': 'Aguardando pagamentos',
    'envio': 'Envios em andamento',
    'pos_venda': 'Com devolução ou disputa',
    'concluida': 'Troca concluída',
}

def stage(proposal, pedidos=None):
    if proposal.status != 'ACCEPTED':
        return None
    pedidos = list(proposal.orders.all()) if pedidos is None else pedidos
    status = {p.status for p in pedidos}
    if 'PENDING' in status:
        chave = 'pagamento'
    elif status & set(AFTER_SALE_STATUSES):
        chave = 'pos_venda'
    elif status <= set(FINISHED_STATUSES):
        chave = 'concluida'
    else:
        chave = 'envio'
    return {'chave': chave, 'rotulo': STAGES[chave]}

def sides(proposal, viewer):
    itens = list(proposal.items.select_related('product', 'variant').prefetch_related('product__images'))
    faltando = {v.pk for v in unavailable_items(proposal)} if proposal.is_open else set()

    def linha(product, variant):
        return {'product': product, 'variant': variant, 'indisponivel': variant.pk in faltando}

    def volta(lado):
        return proposal.cash_amount if proposal.cash_payer == lado else None

    proponente = {
        'lado': PROPOSER, 'user': proposal.proposer,
        'itens': [linha(i.product, i.variant) for i in itens],
        'valor': sum((i.variant.price for i in itens), Decimal('0.00')),
        'volta': volta(PROPOSER),
    }
    anunciante = {
        'lado': OWNER, 'user': proposal.owner,
        'itens': [linha(proposal.product, proposal.variant)],
        'valor': proposal.variant.price,
        'volta': volta(OWNER),
    }
    for lado in (proponente, anunciante):
        lado['total'] = lado['valor'] + (lado['volta'] or Decimal('0.00'))
    return [anunciante, proponente] if proposal.party(viewer) == OWNER else [proponente, anunciante]

def annotate_for(proposals, user):
    for proposal in proposals:
        proposal.my_side = proposal.party(user)
        proposal.counterpart = proposal.user_for(other(proposal.my_side)) if proposal.my_side else None
        proposal.my_turn = proposal.is_open and proposal.awaiting == proposal.my_side
        proposal.stage = stage(proposal, list(proposal.orders.all()))
    return proposals

def inbox(user):
    expire_trades()
    propostas = annotate_for(list(
        TradeProposal.objects.filter(Q(proposer=user) | Q(owner=user))
        .select_related('product', 'variant', 'proposer', 'owner')
        .prefetch_related('product__images', 'items__product__images', 'items__variant', 'orders')
    ), user)
    return {
        'sua_vez': [p for p in propostas if p.my_turn],
        'aguardando': [p for p in propostas if p.is_open and not p.my_turn],
        'andamento': [p for p in propostas if p.stage and p.stage['chave'] != 'concluida'],
        'encerradas': [p for p in propostas if not p.is_open and (not p.stage or p.stage['chave'] == 'concluida')],
    }

def awaiting_count(user):
    return TradeProposal.objects.filter(status='PENDING', expires_at__gt=timezone.now()).filter(
        Q(owner=user, awaiting=OWNER) | Q(proposer=user, awaiting=PROPOSER)
    ).count()

def product_context(product, user):
    if not product.accepts_trade or hasattr(product, 'auction'):
        return {}
    contexto = {'aceita_troca': accepts_trades(product)}
    if not user.is_authenticated:
        return contexto
    if user.pk == product.seller_id:
        contexto['propostas_recebidas'] = TradeProposal.objects.filter(
            product=product, status='PENDING', expires_at__gt=timezone.now(), awaiting=OWNER,
        ).count()
    else:
        contexto['minha_proposta'] = open_proposal(product, user)
        contexto['pode_propor'] = propose_blocker(product, user) is None
    return contexto

def _pct(parte, total):
    return float(parte / total * 100) if total else 0.0

def _variacao(atual, anterior):
    return float((atual - anterior) / anterior * 100) if anterior else None

OUTCOMES = [
    ('ACCEPTED', 'Aceitas'),
    ('CANCELLED', 'Aceitas e canceladas antes do envio'),
    ('DECLINED', 'Recusadas'),
    ('EXPIRED', 'Expiradas sem resposta'),
    ('WITHDRAWN', 'Retiradas pelo autor'),
]

def report(periodo):
    expire_trades()
    inicio, fim = periodo['inicio'], periodo['fim']

    def criadas(de, ate):
        return TradeProposal.objects.filter(created_at__date__gte=de, created_at__date__lte=ate).count()

    encerradas = list(
        TradeProposal.objects.filter(closed_at__date__gte=inicio, closed_at__date__lte=fim)
        .select_related('variant').prefetch_related('items__variant')
    )
    contagem = {chave: 0 for chave, _ in OUTCOMES}
    for proposta in encerradas:
        contagem[proposta.status] += 1
    aceitas = [p for p in encerradas if p.status in ('ACCEPTED', 'CANCELLED')]
    efetivadas = [p for p in encerradas if p.status == 'ACCEPTED']

    comissoes = Commission.objects.filter(
        created_at__date__gte=inicio, created_at__date__lte=fim, order__trade__isnull=False,
    ).aggregate(volta=Sum('gross_amount'), comissao=Sum('commission_amount'))

    propostas = criadas(inicio, fim)
    return {
        'propostas': propostas,
        'propostas_variacao': _variacao(propostas, criadas(periodo['inicio_anterior'], periodo['fim_anterior'])),
        'encerradas': len(encerradas),
        'aceitas': len(aceitas),
        'taxa_aceite': _pct(len(aceitas), len(encerradas)),
        'com_contraproposta': _pct(sum(1 for p in encerradas if p.rounds > 1), len(encerradas)),
        'rodadas_media': sum(p.rounds for p in encerradas) / len(encerradas) if encerradas else None,
        'com_volta': sum(1 for p in efetivadas if p.cash_amount),
        'volta_total': sum((p.cash_amount for p in efetivadas), Decimal('0.00')),
        'valor_referencia': sum((p.variant.price + p.offered_value for p in efetivadas), Decimal('0.00')),
        'taxas': Order.objects.filter(
            trade__in=[p.pk for p in efetivadas], trade_paid=True,
        ).aggregate(total=Sum('trade_fee'))['total'] or Decimal('0.00'),
        'volta_concluida': comissoes['volta'] or Decimal('0.00'),
        'comissao': comissoes['comissao'] or Decimal('0.00'),
        'desfechos': [
            {'desfecho': rotulo, 'propostas': contagem[chave], 'participacao': _pct(contagem[chave], len(encerradas))}
            for chave, rotulo in OUTCOMES if contagem[chave]
        ],
        'anuncios_agora': Product.objects.filter(
            accepts_trade=True, published=True, deleted=False, auction__isnull=True,
        ).count(),
        'negociando_agora': TradeProposal.objects.filter(status='PENDING', expires_at__gt=timezone.now()).count(),
    }
