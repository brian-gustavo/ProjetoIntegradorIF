from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render, redirect, get_object_or_404

from .models import Order, Cart, CartItem, generate_tracking_code
from catalog.models import Product

@login_required
def add_to_cart(request, product_id):
    if request.user.is_staff:
        return redirect('home')

    product = get_object_or_404(Product, pk=product_id)

    if product.seller == request.user:
        return redirect('home')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))

        if quantity > product.stock.quantity:
            return render(request, 'orders/add_to_cart.html', {
                'product': product,
                'error': 'Quantidade indisponível em estoque',
            })

        cart, _ = Cart.objects.get_or_create(user=request.user)
        item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity},
        )
        if not created:
            new_quantity = item.quantity + quantity
            if new_quantity > product.stock.quantity:
                return render(request, 'orders/add_to_cart.html', {
                    'product': product,
                    'error': 'Quantidade indisponível em estoque',
                })
            item.quantity = new_quantity
            item.save()

        messages.success(request, f'"{product.title}" adicionado ao carrinho')
        return redirect('cart_detail')

    return render(request, 'orders/add_to_cart.html', {'product': product})

@login_required
def cart_detail(request):
    cart, _ = Cart.objects.get_or_create(user=request.user)
    items = cart.items.select_related('product').all()
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
    items = cart.items.select_related('product__stock').all()

    if not items:
        return redirect('cart_detail')

    out_of_stock = [item for item in items if item.quantity > item.product.stock.quantity]
    if out_of_stock:
        for item in out_of_stock:
            messages.error(request, f'"{item.product.title}" não tem estoque suficiente para a quantidade selecionada')
        return redirect('cart_detail')

    for item in items:
        Order.objects.create(
            buyer=request.user,
            product=item.product,
            quantity=item.quantity,
            total_price=item.subtotal,
        )

    cart.items.all().delete()
    return redirect('my_orders')

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
        stock = order.product.stock
        stock.quantity -= order.quantity
        stock.save()

        order.status = 'PAID'
        order.save()

    return redirect('my_orders')

@login_required
def cancel_order_buyer(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status == 'PENDING':
        order.status = 'CANCELLED'
        order.save()
    elif order.status == 'PAID':
        stock = order.product.stock
        stock.quantity += order.quantity
        stock.save()
        order.status = 'CANCELLED'
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

    if order.status == 'PREPARING':
        tracking_code = request.POST.get('tracking_code', '').strip()
        order.tracking_code = tracking_code if tracking_code else generate_tracking_code()
        order.status = 'SHIPPED'
        order.save()

    return redirect('seller_orders')

@login_required
def cancel_order_seller(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status in ('PAID', 'CONFIRMED', 'PREPARING'):
        if order.status != 'PENDING':
            stock = order.product.stock
            stock.quantity += order.quantity
            stock.save()
        order.status = 'CANCELLED'
        order.save()

    return redirect('seller_orders')

@login_required
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, pk=order_id, buyer=request.user)

    if order.status == 'SHIPPED':
        order.status = 'DELIVERED'
        order.save()

    return redirect('my_orders')

@login_required
def seller_dashboard(request):
    orders = Order.objects.filter(product__seller=request.user)

    total_vendas = orders.filter(status__in=['SHIPPED', 'DELIVERED']).count()

    total_arrecadado = orders.filter(
        status__in=['SHIPPED', 'DELIVERED']
    ).aggregate(total=Sum('total_price'))['total'] or 0

    pendentes = orders.filter(status__in=['PAID', 'CONFIRMED', 'PREPARING']).count()

    produto_mais_vendido = (
        orders.filter(status__in=['SHIPPED', 'DELIVERED'])
        .values('product__title')
        .annotate(total=Count('id'))
        .order_by('-total')
        .first()
    )

    return render(request, 'orders/seller_dashboard.html', {
        'total_vendas': total_vendas,
        'total_arrecadado': total_arrecadado,
        'pendentes': pendentes,
        'produto_mais_vendido': produto_mais_vendido,
    })