from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from . import services
from .forms import TradeTermsForm
from .models import PROPOSER, TradeProposal
from catalog.models import Product
from catalog.views import _annotate_products, _apply_sort, _build_filter_context

def _deadline_text(proposal):
    return f'{timezone.localtime(proposal.expires_at):%d/%m às %H:%M}'

def trade_list(request):
    base_qs = _annotate_products(
        Product.objects.filter(published=True, deleted=False, accepts_trade=True, auction__isnull=True)
    ).select_related('seller__profile', 'auction').prefetch_related('images', 'variants')

    produtos_qs, filtros = _build_filter_context(request, base_qs)
    produtos_qs, ordenacao = _apply_sort(request, produtos_qs)

    return render(request, 'trades/trade_list.html', {
        'produtos': Paginator(produtos_qs, 24).get_page(request.GET.get('page')),
        'filtros': filtros,
        'ordenacao': ordenacao,
    })

@login_required
def propose_trade(request, product_id):
    product = get_object_or_404(Product.objects.select_related('seller__profile', 'category'), pk=product_id, deleted=False)
    erro = services.propose_blocker(product, request.user)
    if erro:
        existente = services.open_proposal(product, request.user)
        if existente:
            messages.info(request, erro)
            return redirect('trade_detail', trade_id=existente.pk)
        messages.error(request, erro)
        return redirect('product_detail', product_id=product.pk)

    inventario = services.tradeable_variants(request.user)
    variantes = services.target_variants(product)
    if request.method == 'POST':
        form = TradeTermsForm(request.POST, inventory=inventario, variants=variantes)
        if form.is_valid():
            itens, valor, pagador = form.terms(PROPOSER)
            proposal, erro = services.propose(
                product.pk, request.user, form.cleaned_data['variant'], itens, valor, pagador, form.cleaned_data['message'],
            )
            if proposal:
                messages.success(request, f'Proposta enviada! {product.seller.username} tem até {_deadline_text(proposal)} para responder.')
                return redirect('trade_detail', trade_id=proposal.pk)
            form.add_error(None, erro)
    else:
        form = TradeTermsForm(inventory=inventario, variants=variantes, initial={'variant': variantes[0].pk})

    return render(request, 'trades/trade_form.html', {
        'form': form,
        'product': product,
        'inventario': inventario,
        'variantes': variantes,
        'contraparte': product.seller,
        'sou_proponente': True,
        'max_itens': services.MAX_ITEMS,
        **services.fee_context(),
    })

@login_required
def counter_trade(request, trade_id):
    services.expire_trades()
    proposal = get_object_or_404(TradeProposal.objects.select_related('product__seller', 'variant', 'proposer', 'owner'), pk=trade_id)
    lado = proposal.party(request.user)
    if lado is None or not proposal.is_open or proposal.awaiting != lado:
        messages.error(request, 'Esta proposta não está aguardando a sua resposta.')
        return redirect('trade_detail', trade_id=proposal.pk)

    atuais = {item.variant_id for item in proposal.items.all()}
    inventario = services.tradeable_variants(proposal.proposer)
    disponiveis = {v.pk for v in inventario}
    if request.method == 'POST':
        form = TradeTermsForm(request.POST, inventory=inventario)
        if form.is_valid():
            itens, valor, pagador = form.terms(lado)
            resultado, erro = services.counter(proposal.pk, request.user, itens, valor, pagador, form.cleaned_data['message'])
            if resultado:
                messages.success(request, f'Contraproposta enviada! {resultado.awaiting_user.username} tem até {_deadline_text(resultado)} para responder.')
                return redirect('trade_detail', trade_id=proposal.pk)
            form.add_error(None, erro)
    else:
        form = TradeTermsForm(inventory=inventario, initial=TradeTermsForm.initial_for(proposal, lado))

    return render(request, 'trades/trade_form.html', {
        'form': form,
        'proposal': proposal,
        'product': proposal.product,
        'inventario': inventario,
        'alvo': proposal.variant,
        'contraparte': proposal.user_for(services.other(lado)),
        'sou_proponente': lado == PROPOSER,
        'max_itens': services.MAX_ITEMS,
        'itens_indisponiveis': atuais - disponiveis,
        'termos_atuais': services.describe(proposal),
        **services.fee_context(),
    })

@login_required
def my_trades(request):
    if request.user.is_staff:
        return redirect('trade_list')

    dados = services.inbox(request.user)
    abas = [
        ('sua_vez', 'Aguardando você'),
        ('aguardando', 'Aguardando a outra parte'),
        ('andamento', 'Trocas em andamento'),
        ('encerradas', 'Encerradas'),
    ]
    aba = request.GET.get('aba')
    if aba not in dict(abas):
        aba = 'sua_vez' if dados['sua_vez'] or not dados['aguardando'] else 'aguardando'

    return render(request, 'trades/my_trades.html', {
        'aba': aba,
        'abas': [{'chave': chave, 'titulo': titulo, 'total': len(dados[chave])} for chave, titulo in abas],
        'propostas': dados[aba],
    })

@login_required
def trade_detail(request, trade_id):
    services.expire_trades()
    proposal = get_object_or_404(
        TradeProposal.objects.select_related('product__seller', 'variant', 'proposer', 'owner'), pk=trade_id,
    )
    if proposal.party(request.user) is None and not request.user.is_staff:
        return redirect('home')

    pedidos = list(proposal.orders.select_related('product', 'variant', 'buyer', 'product__seller').order_by('pk'))
    services.annotate_for([proposal], request.user)
    pendentes = [p for p in pedidos if services.awaiting_payment(p)]
    for pedido in pedidos:
        pedido.aguardando_pagamento = pedido in pendentes

    return render(request, 'trades/trade_detail.html', {
        'proposal': proposal,
        'lados': services.sides(proposal, request.user),
        'eventos': proposal.events.select_related('author'),
        'pedidos': pedidos,
        'pode_cancelar': proposal.my_side is not None and services.can_cancel(proposal, pedidos),
        'meu_pagamento': next((p for p in pendentes if p.buyer_id == request.user.pk), None),
        'pagamentos_pendentes': [p for p in pendentes if p.buyer_id != request.user.pk],
        **services.fee_context(),
    })

@login_required
def trade_action(request, trade_id):
    proposal = get_object_or_404(TradeProposal, pk=trade_id)
    if request.method != 'POST':
        return redirect('trade_detail', trade_id=proposal.pk)

    acao = request.POST.get('acao')
    if acao == 'aceitar':
        resultado, erro = services.accept(proposal.pk, request.user)
        sucesso = 'Troca fechada! Os pedidos de envio foram criados para os dois lados.'
        if resultado and resultado.orders.filter(status='PENDING').exists():
            sucesso = 'Troca fechada! Assim que os dois lados concluírem os pagamentos, os envios são liberados.'
    elif acao == 'recusar':
        resultado, erro = services.decline(proposal.pk, request.user, request.POST.get('message'))
        sucesso = 'Proposta recusada.'
    elif acao == 'retirar':
        resultado, erro = services.withdraw(proposal.pk, request.user)
        sucesso = 'Proposta retirada.'
    elif acao == 'cancelar':
        resultado, erro = services.cancel(proposal.pk, request.user)
        sucesso = 'Troca cancelada. Os pedidos ligados a ela também foram cancelados.'
    else:
        return redirect('trade_detail', trade_id=proposal.pk)

    if erro:
        messages.error(request, erro)
    else:
        messages.success(request, sucesso)
    return redirect('trade_detail', trade_id=proposal.pk)
