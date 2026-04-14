from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from catalog.models import Product
from .models import Order

@login_required
def create_order(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if product.seller == request.user:
        return redirect('home')

    if request.method == 'POST':
        quantity = int(request.POST.get('quantity', 1))
        stock = product.stock

        if quantity > stock.quantity:
            return render(request, 'orders/create_order.html', {
                'product': product,
                'error': 'Quantidade indisponível em estoque.',
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