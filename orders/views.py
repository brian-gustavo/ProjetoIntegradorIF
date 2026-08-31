import requests
from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone

from .forms import DisputeForm, DisputeMessageForm, DisputeResolutionForm
from .models import Order, Cart, CartItem, generate_tracking_code, PlatformConfig, Commission, Dispute, DisputeMessage
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
        for item in items:
            pickup = request.POST.get(f'pickup_{item.pk}') == '1'
            if pickup and not item.product.accepts_pickup:
                pickup = False
            Order.objects.create(
                buyer=request.user,
                product=item.product,
                variant=item.variant,
                quantity=item.quantity,
                total_price=item.subtotal,
                pickup=pickup,
            )
        cart.items.all().delete()
        return redirect('my_orders')

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

    for order in orders:
        order.seller_reviewed = order.product.seller.pk in reviewed_sellers
        order.seller_review_edited = order.product.seller.pk in edited_seller_reviews
        order.product_reviewed = order.product.pk in reviewed_products
        order.product_review_edited = order.product.pk in edited_product_reviews
        order.can_contest = (
            order.status == 'CANCELLED_NO_RETURN'
            and not hasattr(order, 'dispute')
            and timezone.now() - order.updated_at <= timedelta(days=DISPUTE_WINDOW_DAYS)
        )

    return render(request, 'orders/my_orders.html', {'orders': orders})

@login_required
def simulate_payment(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status == 'PENDING':
        order.status = 'PAID'
        order.save()

    return redirect('my_orders')

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
    })

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('home')

    if request.method == 'POST':
        nova_taxa = request.POST.get('commission_rate', '').strip()
        try:
            taxa = Decimal(nova_taxa)
            if taxa < 0 or taxa > 100:
                raise ValueError
            config, _ = PlatformConfig.objects.get_or_create(pk=1)
            config.commission_rate = taxa
            config.save()
            messages.success(request, 'Taxa de comissão atualizada com sucesso')
        except:
            messages.error(request, 'Taxa inválida')
        return redirect('admin_dashboard')

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

    vendedores = (
        Order.objects.filter(status__in=['DELIVERED', 'RETURN_WINDOW', 'COMPLETED'])
        .values('product__seller__username')
        .annotate(
            total_vendas=Sum('quantity'),
            total_bruto=Sum('total_price'),
        )
        .order_by('-total_bruto')[:10]
    )

    return render(request, 'orders/admin_dashboard.html', {
        'total_vendas': total_vendas,
        'total_transacionado': total_transacionado,
        'total_comissao': total_comissao,
        'taxa_atual': taxa_atual,
        'vendedores': vendedores,
    })

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

DISPUTE_WINDOW_DAYS = 7

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

    if timezone.now() - order.updated_at > timedelta(days=DISPUTE_WINDOW_DAYS):
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