from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.shortcuts import render, redirect, get_object_or_404

from .models import Order, Cart, CartItem, generate_tracking_code, PlatformConfig, Commission
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
    reviewed_products = set(
        ProductReview.objects.filter(reviewer=request.user).values_list('product_id', flat=True)
    )

    for order in orders:
        order.seller_reviewed = order.product.seller.pk in reviewed_sellers
        order.product_reviewed = order.product.pk in reviewed_products

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