from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.shortcuts import render, redirect, get_object_or_404

from .models import Order
from accounts.models import SellerReview
from catalog.models import Product

@login_required
def create_order(request, product_id):
    if request.user.is_staff:
        return redirect('home')
    
    product = get_object_or_404(Product, pk=product_id)

    if product.seller == request.user:
        return redirect('home')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        stock = product.stock

        if quantity > stock.quantity:
            return render(request, 'orders/create_order.html', {
                'product': product,
                'error': 'Quantidade indisponível em estoque',
            })

        Order.objects.create(
            buyer=request.user,
            product=product,
            quantity=quantity,
            total_price=product.price * quantity,
        )

        return redirect('my_orders')

    return render(request, 'orders/create_order.html', {'product': product})

@login_required
def my_orders(request):
    orders = Order.objects.filter(buyer=request.user).order_by('-created_at')

    reviewed_sellers = set(
        SellerReview.objects.filter(reviewer=request.user).values_list('seller_id', flat=True)
    )

    for order in orders:
        order.seller_reviewed = order.product.seller.pk in reviewed_sellers

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
def seller_orders(request):
    orders = Order.objects.filter(product__seller=request.user).order_by('-created_at')
    return render(request, 'orders/seller_orders.html', {'orders': orders})

@login_required
def confirm_delivery(request, order_id):
    order = get_object_or_404(Order, pk=order_id, product__seller=request.user)

    if order.status == 'PAID':
        order.status = 'DELIVERED'
        order.save()

    return redirect('seller_orders')

@login_required
def seller_dashboard(request):
    orders = Order.objects.filter(product__seller=request.user)

    total_vendas = orders.filter(status__in=['PAID', 'DELIVERED']).count()

    total_arrecadado = orders.filter(
        status__in=['PAID', 'DELIVERED']
    ).aggregate(total=Sum('total_price'))['total'] or 0

    pendentes = orders.filter(status='PAID').count()

    produto_mais_vendido = (
        orders.filter(status__in=['PAID', 'DELIVERED'])
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