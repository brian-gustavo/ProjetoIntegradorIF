import json, math, requests
from datetime import timedelta, date
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Min, Q, Sum
from django.db.models.functions import TruncDate, TruncMonth
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .forms import DisputeForm, DisputeMessageForm, DisputeResolutionForm, PlatformConfigForm
from .models import Order, Cart, CartItem, generate_tracking_code, PlatformConfig, Commission, Dispute, DisputeMessage
from .reports import build_admin_report_pdf
from accounts.models import MercadoPagoAccount
from catalog.models import Product, ProductVariant

@login_required
def add_to_cart(request, product_id):
    if request.user.is_staff:
        return redirect('home')

    product = get_object_or_404(Product, pk=product_id)

    if product.seller == request.user:
        return redirect('home')

    if request.method == 'POST':
        variant_id = request.POST.get('variant_id')
        variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
        quantity = int(request.POST.get('quantity', 1))

        if quantity > variant.quantity:
            return render(request, 'orders/add_to_cart.html', {
                'product': product,
                'error': 'Quantidade indisponível em estoque',
            })

        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            variant=variant,
            defaults={'product': product, 'quantity': quantity},
        )
        if not created:
            new_quantity = item.quantity + quantity
            if new_quantity > variant.quantity:
                return render(request, 'orders/add_to_cart.html', {
                    'product': product,
                    'error': 'Quantidade indisponível em estoque',
                })
            item.quantity = new_quantity
            item.save()

        messages.success(request, f'"{product.title} — {variant.name}" adicionado ao carrinho')
        return redirect('cart_detail')

    return render(request, 'orders/add_to_cart.html', {'product': product})

@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product', 'variant').all()
    total = sum(item.subtotal for item in items)
    return render(request, 'orders/cart.html', {'cart': cart, 'items': items, 'total': total})

@login_required
def remove_from_cart(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)
    item.delete()
    return redirect('cart_detail')

@login_required
def checkout(request):
    cart = get_object_or_404(Cart, user=request.user)
    items = cart.items.select_related('product', 'variant').all()

    if not items:
        return redirect('cart_detail')

    out_of_stock = [item for item in items if item.quantity > item.variant.quantity]
    if out_of_stock:
        for item in out_of_stock:
            messages.error(request, f'"{item.product.title} — {item.variant.name}" não tem estoque suficiente')
        return redirect('cart_detail')

    if request.method == 'POST':
        new_orders = []
        for item in items:
            pickup = request.POST.get(f'pickup_{item.pk}') == '1'
            if pickup and not item.product.accepts_pickup:
                pickup = False
            order = Order.objects.create(
                buyer=request.user,
                product=item.product,
                variant=item.variant,
                quantity=item.quantity,
                total_price=item.subtotal,
                pickup=pickup,
            )
            new_orders.append(order)
        cart.items.all().delete()
        request.session['mp_pending_orders'] = [o.pk for o in new_orders]
        return redirect('mp_pay_next')

    pickup_items = [item for item in items if item.product.accepts_pickup]
    return render(request, 'orders/checkout.html', {
        'items': items,
        'total': sum(item.subtotal for item in items),
        'pickup_items': pickup_items,
    })

@login_required
def my_orders(request):
    from accounts.models import SellerReview
    from catalog.models import ProductReview

    orders = Order.objects.filter(buyer=request.user).order_by('-created_at')

    reviewed_sellers = set(
        SellerReview.objects.filter(reviewer=request.user).values_list('seller_id', flat=True)
    )
    edited_seller_reviews = set(
        SellerReview.objects.filter(reviewer=request.user, edited=True).values_list('seller_id', flat=True)
    )
    reviewed_products = set(
        ProductReview.objects.filter(reviewer=request.user).values_list('product_id', flat=True)
    )
    edited_product_reviews = set(
        ProductReview.objects.filter(reviewer=request.user, edited=True).values_list('product_id', flat=True)
    )

    config = PlatformConfig.load()
    dispute_window = timedelta(days=config.dispute_window_days)
    return_window = timedelta(days=config.return_window_days)

    for order in orders:
        order.seller_reviewed = order.product.seller.pk in reviewed_sellers
        order.seller_review_edited = order.product.seller.pk in edited_seller_reviews
        order.product_reviewed = order.product.pk in reviewed_products
        order.product_review_edited = order.product.pk in edited_product_reviews
        order.can_contest = (
            order.status == 'CANCELLED_NO_RETURN'
            and not hasattr(order, 'dispute')
            and timezone.now() - order.updated_at <= dispute_window
        )
        order.can_request_return = (
            order.status in ('DELIVERED', 'RETURN_WINDOW')
            and timezone.now() - order.updated_at <= return_window
        )

    return render(request, 'orders/my_orders.html', {'orders': orders})

@login_required
def resume_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status != 'PENDING':
        return redirect('my_orders')

    request.session['mp_pending_orders'] = [order.pk]
    return redirect('mp_pay_next')

@login_required
def cancel_order_buyer(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status in ('PENDING', 'PAID'):
        order.status = 'CANCELLED'
        order.save()

    return redirect('my_orders')

@login_required
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status in ('SHIPPED', 'READY_PICKUP'):
        _finalize_delivery(order)

    return redirect('my_orders')

@login_required
def confirm_delivery_seller(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status in ('SHIPPED', 'READY_PICKUP'):
        _finalize_delivery(order)

    return redirect('seller_orders')

def _finalize_delivery(order):
    variant = order.variant
    variant.quantity -= order.quantity
    variant.save()

    rate = PlatformConfig.get_commission_rate()
    gross = order.total_price
    commission_amount = (gross * rate / Decimal('100')).quantize(Decimal('0.01'))
    net = gross - commission_amount

    Commission.objects.get_or_create(
        order=order,
        defaults={
            'rate': rate,
            'gross_amount': gross,
            'commission_amount': commission_amount,
            'net_amount': net,
        }
    )

    order.status = 'DELIVERED'
    order.save()

@login_required
def request_return(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status in ('DELIVERED', 'RETURN_WINDOW'):
        if timezone.now() - order.updated_at > timedelta(days=PlatformConfig.load().return_window_days):
            messages.error(request, 'O prazo para solicitar devolução deste pedido já passou.')
            return redirect('my_orders')
        order.status = 'RETURN_REQUESTED'
        order.save()
        messages.success(request, 'Solicitação de devolução enviada ao vendedor')

    return redirect('my_orders')

@login_required
def accept_return(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'RETURN_REQUESTED':
        order.status = 'RETURN_ACCEPTED'
        order.save()
        messages.success(request, 'Devolução aceita. Aguardando recebimento do produto.')

    return redirect('seller_orders')

@login_required
def accept_no_return(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'RETURN_REQUESTED':
        if hasattr(order, 'commission'):
            order.commission.delete()

        order.status = 'CANCELLED_NO_RETURN'
        order.save()
        messages.success(request, 'Cancelamento sem devolução registrado')

    return redirect('seller_orders')

@login_required
def confirm_return_received(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'RETURN_ACCEPTED':
        variant = order.variant
        variant.quantity += order.quantity
        variant.save()

        if hasattr(order, 'commission'):
            order.commission.delete()

        order.status = 'RETURNED'
        order.save()
        messages.success(request, 'Devolução concluída. Estoque restaurado.')

    return redirect('seller_orders')

@login_required
def complete_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status in ('DELIVERED', 'RETURN_WINDOW'):
        order.status = 'COMPLETED'
        order.save()

    return redirect('my_orders')

@login_required
def seller_orders(request):
    orders = Order.objects.filter(product__seller=request.user).order_by('-created_at')
    return render(request, 'orders/seller_orders.html', {'orders': orders})

@login_required
def confirm_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'PAID':
        order.status = 'CONFIRMED'
        order.save()

    return redirect('seller_orders')

@login_required
def mark_preparing(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'CONFIRMED':
        order.status = 'PREPARING'
        order.save()

    return redirect('seller_orders')

@login_required
def mark_shipped(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'PREPARING' and not order.pickup:
        tracking_code = request.POST.get('tracking_code', '').strip()
        order.tracking_code = tracking_code if tracking_code else generate_tracking_code()
        order.status = 'SHIPPED'
        order.save()

    return redirect('seller_orders')

@login_required
def mark_ready_pickup(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'PREPARING' and order.pickup:
        order.status = 'READY_PICKUP'
        order.save()

    return redirect('seller_orders')

@login_required
def cancel_order_seller(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status in ('PAID', 'CONFIRMED', 'PREPARING'):
        order.status = 'CANCELLED'
        order.save()

    return redirect('seller_orders')

@login_required
def seller_dashboard(request):
    orders = Order.objects.filter(product__seller=request.user)
    delivered_orders = orders.filter(status__in=['DELIVERED', 'RETURN_WINDOW', 'COMPLETED'])

    total_vendas = delivered_orders.aggregate(total=Sum('quantity'))['total'] or 0

    total_bruto = delivered_orders.aggregate(
        total=Sum('total_price')
    )['total'] or Decimal('0')

    total_comissao = Commission.objects.filter(
        order__product__seller=request.user
    ).aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')

    total_liquido = total_bruto - total_comissao

    pendentes = orders.filter(status__in=['PAID', 'CONFIRMED', 'PREPARING']).count()

    produto_mais_vendido = (
        delivered_orders
        .values('product__title')
        .annotate(total=Sum('quantity'))
        .order_by('-total')
        .first()
    )

    return render(request, 'orders/seller_dashboard.html', {
        'total_vendas': total_vendas,
        'total_bruto': total_bruto,
        'total_comissao': total_comissao,
        'total_liquido': total_liquido,
        'pendentes': pendentes,
        'produto_mais_vendido': produto_mais_vendido,
        'mp_connected': hasattr(request.user, 'mp_account'),
    })

def _get_period_range(request):
    preset = request.GET.get('periodo', '30d')
    hoje = timezone.now().date()

    if preset == '7d':
        inicio, fim = hoje - timedelta(days=6), hoje
    elif preset == 'mes':
        inicio, fim = hoje.replace(day=1), hoje
    elif preset == 'ano':
        inicio, fim = hoje.replace(month=1, day=1), hoje
    elif preset == 'personalizado':
        try:
            inicio = date.fromisoformat(request.GET.get('inicio', ''))
            fim = date.fromisoformat(request.GET.get('fim', ''))
        except ValueError:
            preset = '30d'
            inicio, fim = hoje - timedelta(days=29), hoje
    else:
        preset = '30d'
        inicio, fim = hoje - timedelta(days=29), hoje

    dias = (fim - inicio).days + 1
    inicio_anterior = inicio - timedelta(days=dias)
    fim_anterior = inicio - timedelta(days=1)

    return {
        'preset': preset,
        'inicio': inicio, 'fim': fim,
        'inicio_anterior': inicio_anterior, 'fim_anterior': fim_anterior,
        'dias': dias,
    }

def _variacao(atual, anterior):
    if not anterior:
        return None
    return float((atual - anterior) / anterior * 100)

def _diferenca_pp(atual, anterior, base_anterior):
    if not base_anterior:
        return None
    return atual - anterior

def _pct(parte, total):
    return float(parte / total * 100) if total else 0.0

PERIODO_OPCOES = [('7d', '7 dias'), ('30d', '30 dias'), ('mes', 'Este mês'), ('ano', 'Este ano')]
RETURN_FLOW_STATUSES = ['RETURN_REQUESTED', 'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'DISPUTE_OPEN']

def _commissions_between(inicio, fim):
    return Commission.objects.filter(created_at__date__gte=inicio, created_at__date__lte=fim)

def _concentracao(linhas, total):
    ativos = len(linhas)
    if not ativos:
        return None

    pareto_n = max(1, math.ceil(ativos * 0.2))
    hhi = sum(l['participacao'] ** 2 for l in linhas)

    if hhi < 1500:
        nivel = 'baixa'
    elif hhi <= 2500:
        nivel = 'moderada'
    else:
        nivel = 'alta'

    return {
        'ativos': ativos,
        'top1': linhas[0]['participacao'],
        'top5': sum(l['participacao'] for l in linhas[:5]),
        'pareto_n': pareto_n,
        'pareto': sum(l['participacao'] for l in linhas[:pareto_n]),
        'hhi': hhi,
        'nivel': nivel,
    }

def _ranking_vendedores(commissions, limite):
    linhas = list(
        commissions
        .values('order__product__seller__username')
        .annotate(gmv=Sum('gross_amount'), comissao=Sum('commission_amount'), pedidos=Count('id'))
        .order_by('-gmv')
    )
    total = sum((l['gmv'] for l in linhas), Decimal('0'))

    acumulado = Decimal('0')
    for posicao, linha in enumerate(linhas, 1):
        acumulado += linha['gmv']
        linha['posicao'] = posicao
        linha['vendedor'] = linha.pop('order__product__seller__username')
        linha['ticket_medio'] = linha['gmv'] / linha['pedidos']
        linha['participacao'] = _pct(linha['gmv'], total)
        linha['acumulado'] = _pct(acumulado, total)

    demais = linhas[limite:]
    demais_resumo = None
    if demais:
        gmv_demais = sum((l['gmv'] for l in demais), Decimal('0'))
        demais_resumo = {
            'quantidade': len(demais),
            'gmv': gmv_demais,
            'comissao': sum((l['comissao'] for l in demais), Decimal('0')),
            'pedidos': sum(l['pedidos'] for l in demais),
            'participacao': _pct(gmv_demais, total),
        }

    return {
        'linhas': linhas[:limite],
        'demais': demais_resumo,
        'concentracao': _concentracao(linhas, total),
    }

def _vendas_por_categoria(commissions, commissions_anterior):
    def agrupar(qs):
        return {
            r['order__product__category__name']: r
            for r in qs.values('order__product__category__name')
            .annotate(gmv=Sum('gross_amount'), pedidos=Count('id'))
        }

    atual, anterior = agrupar(commissions), agrupar(commissions_anterior)
    total = sum((r['gmv'] for r in atual.values()), Decimal('0'))

    linhas = []
    for nome in set(atual) | set(anterior):
        gmv = atual[nome]['gmv'] if nome in atual else Decimal('0')
        pedidos = atual[nome]['pedidos'] if nome in atual else 0
        linhas.append({
            'categoria': nome,
            'gmv': gmv,
            'pedidos': pedidos,
            'ticket_medio': gmv / pedidos if pedidos else Decimal('0'),
            'participacao': _pct(gmv, total),
            'variacao': _variacao(gmv, anterior[nome]['gmv'] if nome in anterior else None),
        })

    linhas.sort(key=lambda l: l['gmv'], reverse=True)
    return linhas

def _saude_operacional(inicio, fim):
    pedidos = Order.objects.filter(
        created_at__date__gte=inicio, created_at__date__lte=fim
    ).exclude(status='PENDING')

    total = pedidos.count()
    cancelados = pedidos.filter(status='CANCELLED').count()
    devolucoes = pedidos.filter(Q(status__in=RETURN_FLOW_STATUSES) | Q(dispute__isnull=False)).count()
    disputas = pedidos.filter(dispute__isnull=False).count()

    resolvidas = list(
        Dispute.objects.filter(resolved_at__date__gte=inicio, resolved_at__date__lte=fim)
        .values_list('status', 'created_at', 'resolved_at')
    )
    tempos = [(resolvido - criado).total_seconds() / 86400 for _, criado, resolvido in resolvidas]
    favor_comprador = sum(1 for status, _, _ in resolvidas if status != 'RESOLVED_SELLER')

    abertas_periodo = Dispute.objects.filter(created_at__date__gte=inicio, created_at__date__lte=fim)
    total_abertas = abertas_periodo.count()
    motivos = [
        {
            'motivo': m['reason_category'] or 'Não informado',
            'disputas': m['disputas'],
            'participacao': _pct(m['disputas'], total_abertas),
        }
        for m in abertas_periodo.values('reason_category').annotate(disputas=Count('id')).order_by('-disputas')
    ]

    return {
        'pedidos': total,
        'cancelados': cancelados,
        'taxa_cancelamento': _pct(cancelados, total),
        'devolucoes': devolucoes,
        'taxa_devolucao': _pct(devolucoes, total),
        'disputas': disputas,
        'taxa_disputa': _pct(disputas, total),
        'disputas_resolvidas': len(resolvidas),
        'tempo_medio_resolucao': sum(tempos) / len(tempos) if tempos else None,
        'favor_comprador': favor_comprador,
        'favor_vendedor': len(resolvidas) - favor_comprador,
        'pct_favor_comprador': _pct(favor_comprador, len(resolvidas)),
        'motivos': motivos,
    }

def _compradores(commissions, inicio, primeiras_compras):
    novos = {'compradores': 0, 'gmv': Decimal('0'), 'pedidos': 0}
    recorrentes = {'compradores': 0, 'gmv': Decimal('0'), 'pedidos': 0}

    for r in commissions.values('order__buyer').annotate(gmv=Sum('gross_amount'), pedidos=Count('id')):
        grupo = novos if timezone.localtime(primeiras_compras[r['order__buyer']]).date() >= inicio else recorrentes
        grupo['compradores'] += 1
        grupo['gmv'] += r['gmv']
        grupo['pedidos'] += r['pedidos']

    for grupo in (novos, recorrentes):
        grupo['gmv_por_comprador'] = grupo['gmv'] / grupo['compradores'] if grupo['compradores'] else Decimal('0')

    ativos = novos['compradores'] + recorrentes['compradores']
    gmv_total = novos['gmv'] + recorrentes['gmv']
    return {
        'ativos': ativos,
        'novos': novos,
        'recorrentes': recorrentes,
        'pct_recorrentes': _pct(recorrentes['compradores'], ativos),
        'pct_gmv_recorrentes': _pct(recorrentes['gmv'], gmv_total),
    }

def _build_report_data(periodo):
    total_vendas = Order.objects.filter(
        status__in=['DELIVERED', 'RETURN_WINDOW', 'COMPLETED']
    ).aggregate(total=Sum('quantity'))['total'] or 0

    total_transacionado = Order.objects.filter(
        status__in=['DELIVERED', 'RETURN_WINDOW', 'COMPLETED']
    ).aggregate(total=Sum('total_price'))['total'] or Decimal('0')

    total_comissao = Commission.objects.aggregate(
        total=Sum('commission_amount')
    )['total'] or Decimal('0')

    taxa_atual = PlatformConfig.get_commission_rate()

    commissions_periodo = _commissions_between(periodo['inicio'], periodo['fim'])
    commissions_anterior = _commissions_between(periodo['inicio_anterior'], periodo['fim_anterior'])

    gmv_atual = commissions_periodo.aggregate(total=Sum('gross_amount'))['total'] or Decimal('0')
    gmv_anterior = commissions_anterior.aggregate(total=Sum('gross_amount'))['total'] or Decimal('0')

    comissao_periodo = commissions_periodo.aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')
    comissao_periodo_anterior = commissions_anterior.aggregate(total=Sum('commission_amount'))['total'] or Decimal('0')

    pedidos_periodo = commissions_periodo.count()
    pedidos_periodo_anterior = commissions_anterior.count()

    ticket_medio = (gmv_atual / pedidos_periodo) if pedidos_periodo else Decimal('0')
    ticket_medio_anterior = (gmv_anterior / pedidos_periodo_anterior) if pedidos_periodo_anterior else Decimal('0')

    trunc_fn = TruncMonth if periodo['dias'] > 62 else TruncDate
    serie = list(
        commissions_periodo
        .annotate(bucket=trunc_fn('created_at'))
        .values('bucket')
        .annotate(total=Sum('gross_amount'))
        .order_by('bucket')
    )
    fmt = '%m/%Y' if trunc_fn is TruncMonth else '%d/%m'
    serie_labels = [item['bucket'].strftime(fmt) for item in serie]
    serie_valores = [float(item['total']) for item in serie]

    config = PlatformConfig.load()
    ranking = _ranking_vendedores(commissions_periodo, config.ranking_size)
    ranking_anterior = _ranking_vendedores(commissions_anterior, config.ranking_size)
    concentracao = ranking['concentracao']
    concentracao_anterior = ranking_anterior['concentracao']
    if concentracao:
        tem_anterior = concentracao_anterior is not None
        concentracao['top5_diferenca'] = concentracao['top5'] - concentracao_anterior['top5'] if tem_anterior else None
        concentracao['pareto_diferenca'] = concentracao['pareto'] - concentracao_anterior['pareto'] if tem_anterior else None
        concentracao['hhi_anterior'] = concentracao_anterior['hhi'] if tem_anterior else None

    categorias = _vendas_por_categoria(commissions_periodo, commissions_anterior)

    saude = _saude_operacional(periodo['inicio'], periodo['fim'])
    saude_anterior = _saude_operacional(periodo['inicio_anterior'], periodo['fim_anterior'])
    for chave in ('taxa_cancelamento', 'taxa_devolucao', 'taxa_disputa'):
        saude[f'{chave}_diferenca'] = _diferenca_pp(saude[chave], saude_anterior[chave], saude_anterior['pedidos'])

    primeiras_compras = dict(
        Commission.objects.values('order__buyer')
        .annotate(primeira=Min('created_at'))
        .values_list('order__buyer', 'primeira')
    )
    compradores = _compradores(commissions_periodo, periodo['inicio'], primeiras_compras)
    compradores_anterior = _compradores(commissions_anterior, periodo['inicio_anterior'], primeiras_compras)
    compradores['novos_variacao'] = _variacao(compradores['novos']['compradores'], compradores_anterior['novos']['compradores'])
    compradores['recorrentes_variacao'] = _variacao(compradores['recorrentes']['compradores'], compradores_anterior['recorrentes']['compradores'])
    compradores['pct_recorrentes_diferenca'] = _diferenca_pp(
        compradores['pct_recorrentes'], compradores_anterior['pct_recorrentes'], compradores_anterior['ativos']
    )

    return {
        'total_vendas': total_vendas,
        'total_transacionado': total_transacionado,
        'total_comissao': total_comissao,
        'taxa_atual': taxa_atual,
        'gmv_atual': gmv_atual,
        'gmv_variacao': _variacao(gmv_atual, gmv_anterior),
        'comissao_periodo': comissao_periodo,
        'comissao_variacao': _variacao(comissao_periodo, comissao_periodo_anterior),
        'pedidos_periodo': pedidos_periodo,
        'pedidos_variacao': _variacao(pedidos_periodo, pedidos_periodo_anterior),
        'ticket_medio': ticket_medio,
        'ticket_medio_variacao': _variacao(ticket_medio, ticket_medio_anterior),
        'serie': {'labels': serie_labels, 'valores': serie_valores},
        'ranking': ranking,
        'categorias': categorias,
        'categorias_grafico': {
            'labels': [c['categoria'] for c in categorias],
            'valores': [float(c['gmv']) for c in categorias],
        },
        'saude': saude,
        'disputas_abertas_agora': Dispute.objects.filter(status='OPEN').count(),
        'compradores': compradores,
        'config': config,
    }

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    config = PlatformConfig.load()
    if request.method == 'POST':
        config_form = PlatformConfigForm(request.POST, instance=config)
        if config_form.is_valid():
            config_form.save()
            messages.success(request, 'Configurações atualizadas com sucesso')
            return redirect('admin_dashboard')
        messages.error(request, 'Configuração inválida')
    else:
        config_form = PlatformConfigForm(instance=config)

    periodo = _get_period_range(request)

    return render(request, 'orders/admin_dashboard.html', {
        **_build_report_data(periodo),
        'periodo': periodo,
        'periodo_opcoes': PERIODO_OPCOES,
        'config_form': config_form,
    })

@login_required
def admin_dashboard_pdf(request):
    if not request.user.is_staff:
        return redirect('home')

    periodo = _get_period_range(request)
    pdf = build_admin_report_pdf(_build_report_data(periodo), periodo)

    nome = f"relatorio-megagame-{periodo['inicio']:%Y-%m-%d}-a-{periodo['fim']:%Y-%m-%d}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nome}"'
    return response

@login_required
def update_cart_item(request, item_id):
    item = get_object_or_404(CartItem, pk=item_id, cart__user=request.user)

    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 1))
        except ValueError:
            messages.error(request, 'Quantidade inválida')
            return redirect('cart_detail')

        if quantity < 1:
            messages.error(request, 'A quantidade mínima é 1')
        elif quantity > item.variant.quantity:
            messages.error(request, f'Quantidade indisponível em estoque (máximo: {item.variant.quantity})')
        else:
            item.quantity = quantity
            item.save()

    return redirect('cart_detail')

@login_required
def open_dispute(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if request.user != order.buyer and request.user != order.product.seller:
        return redirect('home')

    if order.status != 'RETURN_REQUESTED' or hasattr(order, 'dispute'):
        return redirect('my_orders')

    if request.method == 'POST':
        form = DisputeForm(request.POST)
        if form.is_valid():
            dispute = form.save(commit=False)
            dispute.order = order
            dispute.opened_by = request.user
            dispute.save()
            order.status = 'DISPUTE_OPEN'
            order.save()
            messages.success(request, 'Disputa aberta. A equipe do MegaGame vai analisar o caso.')
            return redirect('dispute_detail', dispute_id=dispute.pk)
    else:
        form = DisputeForm()

    return render(request, 'orders/open_dispute.html', {'order': order, 'form': form})

@login_required
def contest_decision(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status != 'CANCELLED_NO_RETURN' or hasattr(order, 'dispute'):
        return redirect('my_orders')

    if timezone.now() - order.updated_at > timedelta(days=PlatformConfig.load().dispute_window_days):
        messages.error(request, 'O prazo para contestar essa decisão já passou.')
        return redirect('my_orders')

    if request.method == 'POST':
        form = DisputeForm(request.POST)
        if form.is_valid():
            dispute = form.save(commit=False)
            dispute.order = order
            dispute.opened_by = request.user
            dispute.save()
            order.status = 'DISPUTE_OPEN'
            order.save()
            messages.success(request, 'Contestação registrada. A equipe do MegaGame vai analisar o caso.')
            return redirect('dispute_detail', dispute_id=dispute.pk)
    else:
        form = DisputeForm()

    return render(request, 'orders/open_dispute.html', {'order': order, 'form': form, 'contesting': True})

@login_required
def dispute_detail(request, dispute_id):
    dispute = get_object_or_404(Dispute, pk=dispute_id)
    order = dispute.order

    is_participant = request.user in (order.buyer, order.product.seller)
    if not is_participant and not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST' and 'send_message' in request.POST:
        message_form = DisputeMessageForm(request.POST)
        if message_form.is_valid():
            msg = message_form.save(commit=False)
            msg.dispute = dispute
            msg.author = request.user
            msg.save()
            return redirect('dispute_detail', dispute_id=dispute.pk)
    else:
        message_form = DisputeMessageForm()

    resolution_form = DisputeResolutionForm() if request.user.is_staff and dispute.status == 'OPEN' else None

    return render(request, 'orders/dispute_detail.html', {
        'dispute': dispute,
        'order': order,
        'message_form': message_form,
        'resolution_form': resolution_form,
    })

@login_required
def resolve_dispute(request, dispute_id):
    if not request.user.is_staff:
        return redirect('home')

    dispute = get_object_or_404(Dispute, pk=dispute_id)
    order = dispute.order

    if dispute.status != 'OPEN':
        return redirect('dispute_detail', dispute_id=dispute.pk)

    if request.method == 'POST':
        form = DisputeResolutionForm(request.POST)
        if form.is_valid():
            resolution = form.cleaned_data['resolution']
            dispute.resolution_notes = form.cleaned_data['resolution_notes']
            dispute.resolved_by = request.user
            dispute.resolved_at = timezone.now()

            if resolution == 'buyer_return':
                dispute.status = 'RESOLVED_BUYER_RETURN'
                order.status = 'RETURN_ACCEPTED'
            elif resolution == 'buyer_refund':
                dispute.status = 'RESOLVED_BUYER_REFUND'
                order.status = 'CANCELLED_NO_RETURN'
                if hasattr(order, 'commission'):
                    order.commission.delete()
            else:
                dispute.status = 'RESOLVED_SELLER'
                order.status = 'COMPLETED'
                if not hasattr(order, 'commission'):
                    rate = PlatformConfig.get_commission_rate()
                    gross = order.total_price
                    commission_amount = (gross * rate / Decimal('100')).quantize(Decimal('0.01'))
                    Commission.objects.create(
                        order=order, rate=rate, gross_amount=gross,
                        commission_amount=commission_amount, net_amount=gross - commission_amount,
                    )

            dispute.save()
            order.save()
            messages.success(request, 'Disputa resolvida')
            return redirect('dispute_detail', dispute_id=dispute.pk)

    return redirect('dispute_detail', dispute_id=dispute.pk)

@login_required
def dispute_list(request):
    if not request.user.is_staff:
        return redirect('home')

    disputes = Dispute.objects.filter(status='OPEN').select_related(
        'order', 'order__product', 'order__buyer'
    ).order_by('created_at')
    return render(request, 'orders/dispute_list.html', {'disputes': disputes})

@login_required
def track_order(request, order_id):
    order = get_object_or_404(Order, pk=order_id)

    if request.user not in (order.buyer, order.product.seller):
        return JsonResponse({'error': 'Não autorizado'}, status=403)

    if not order.tracking_code:
        return JsonResponse({'error': 'Este pedido não possui código de rastreio'}, status=400)

    try:
        response = requests.post(
            'https://api-labs.wonca.com.br/wonca.labs.v1.LabsService/Track',
            json={'code': order.tracking_code},
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Apikey {settings.SITERASTREIO_API_KEY}',
                'User-Agent': 'Mozilla/5.0 (compatible; MegaGame/1.0)',
                'Accept': 'application/json',
            },
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.HTTPError:
        return JsonResponse({'error': f'Erro ao consultar rastreio (HTTP {response.status_code})'}, status=502)
    except requests.exceptions.RequestException:
        return JsonResponse({'error': 'Não foi possível consultar o rastreio no momento'}, status=502)

    return JsonResponse(data, safe=False)

def _create_mp_preference(seller, seller_orders, mp_account, request):
    rate = PlatformConfig.get_commission_rate()
    total = sum(o.total_price for o in seller_orders)
    marketplace_fee = (total * rate / Decimal('100')).quantize(Decimal('0.01'))

    items = [{
        'title': f'{o.product.title} — {o.variant.name}',
        'quantity': o.quantity,
        'unit_price': float(o.variant.price),
        'currency_id': 'BRL',
    } for o in seller_orders]

    order_ids_str = ','.join(str(o.pk) for o in seller_orders)
    notification_url = request.build_absolute_uri(reverse('mp_webhook')) + f'?seller_id={seller.pk}'
    return_url = request.build_absolute_uri(reverse('mp_return'))

    response = requests.post(
        'https://api.mercadopago.com/checkout/preferences',
        json={
            'items': items,
            'marketplace_fee': float(marketplace_fee),
            'external_reference': order_ids_str,
            'back_urls': {
                'success': return_url,
                'failure': return_url,
                'pending': return_url,
            },
            'auto_return': 'approved',
            'notification_url': notification_url,
        },
        headers={
            'Authorization': f'Bearer {mp_account.access_token}',
            'Content-Type': 'application/json',
        },
        timeout=10,
    )

    if response.status_code not in (200, 201):
        return None
    return response.json()

@login_required
def mp_pay_next(request):
    order_ids = request.session.get('mp_pending_orders', [])
    orders = list(Order.objects.filter(
        pk__in=order_ids, buyer=request.user, status='PENDING'
    ).select_related('product__seller', 'variant'))

    if not orders:
        request.session.pop('mp_pending_orders', None)
        return redirect('my_orders')

    seller = orders[0].product.seller
    seller_orders = [o for o in orders if o.product.seller_id == seller.pk]
    mp_account = getattr(seller, 'mp_account', None)

    if not mp_account:
        remaining = [o.pk for o in orders if o.product.seller_id != seller.pk]
        request.session['mp_pending_orders'] = remaining
        messages.error(request, f'"{seller.username}" ainda não conectou o Mercado Pago; esses itens não puderam ser cobrados.')
        return redirect('mp_pay_next')

    preference = _create_mp_preference(seller, seller_orders, mp_account, request)
    if not preference:
        messages.error(request, 'Não foi possível iniciar o pagamento. Tente novamente.')
        return redirect('cart_detail')

    init_point = preference.get('sandbox_init_point') or preference.get('init_point')
    return redirect(init_point)

@login_required
def mp_return(request):
    return redirect('mp_pay_next')

@csrf_exempt
def mp_webhook(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'ok'})

    payment_id = request.GET.get('data.id') or request.GET.get('id')
    if not payment_id:
        try:
            body = json.loads(request.body.decode('utf-8'))
            payment_id = body.get('data', {}).get('id')
        except (json.JSONDecodeError, AttributeError):
            payment_id = None

    seller_id = request.GET.get('seller_id')
    if not payment_id or not seller_id:
        return JsonResponse({'status': 'ignored'})

    mp_account = MercadoPagoAccount.objects.filter(user_id=seller_id).first()
    if not mp_account:
        return JsonResponse({'status': 'ignored'})

    response = requests.get(
        f'https://api.mercadopago.com/v1/payments/{payment_id}',
        headers={'Authorization': f'Bearer {mp_account.access_token}'},
        timeout=10,
    )
    if response.status_code != 200:
        return JsonResponse({'status': 'error'}, status=502)

    payment = response.json()
    if payment.get('status') == 'approved':
        order_ids = payment.get('external_reference', '').split(',')
        Order.objects.filter(pk__in=order_ids, status='PENDING').update(status='PAID')

    return JsonResponse({'status': 'ok'})

@login_required
def choose_pickup(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status == 'PAID' and order.product.accepts_pickup and not order.pickup:
        order.pickup = True
        order.save()
        messages.success(request, 'Pedido atualizado para retirada em mãos')

    return redirect('my_orders')