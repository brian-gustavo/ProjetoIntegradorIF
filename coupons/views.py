from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Exists, OuterRef, Q
from django.shortcuts import render, redirect, get_object_or_404

from orders.models import Order
from .forms import CouponForm
from .models import Coupon
from .services import available_coupons, coupon_stats, redeem_code

@login_required
def my_coupons(request):
    if request.user.is_staff:
        return redirect('manage_coupons')

    if request.method == 'POST':
        coupon, erro = redeem_code(request.user, request.POST.get('code'))
        if erro:
            messages.error(request, erro)
        else:
            messages.success(request, f'Cupom {coupon.code} ({coupon.headline}) adicionado aos seus cupons')
        return redirect('my_coupons')

    cupons = available_coupons(request.user)
    historico = request.user.coupon_redemptions.select_related('coupon__seller').annotate(
        em_uso=Exists(
            Order.objects.exclude(status='CANCELLED')
            .filter(Q(seller_coupon=OuterRef('pk')) | Q(platform_coupon=OuterRef('pk')))
        ),
    )

    return render(request, 'coupons/my_coupons.html', {
        'plataforma': [c for c in cupons if c.is_platform],
        'lojas': [c for c in cupons if not c.is_platform],
        'historico': Paginator(historico, 10).get_page(request.GET.get('page')),
    })

def _owner_filter(user):
    return {'seller__isnull': True} if user.is_staff else {'seller': user}

@login_required
def manage_coupons(request):
    cupons = coupon_stats(list(
        Coupon.objects.filter(**_owner_filter(request.user)).select_related('category')
    ))
    ativos = [c for c in cupons if c.status_label == 'Ativo']

    return render(request, 'coupons/manage_coupons.html', {
        'cupons': cupons,
        'resumo': {
            'ativos': len(ativos),
            'usos': sum(c.used_total for c in cupons),
            'pedidos': sum(c.orders_total for c in cupons),
            'descontos': sum((c.discount_total for c in cupons), Decimal('0')),
            'vendas': sum((c.sales_total for c in cupons), Decimal('0')),
        },
    })

@login_required
def create_coupon(request):
    seller = None if request.user.is_staff else request.user
    if request.method == 'POST':
        form = CouponForm(request.POST, seller=seller)
        if form.is_valid():
            coupon = form.save(commit=False)
            coupon.seller = seller
            coupon.save()
            messages.success(request, f'Cupom {coupon.code} criado')
            return redirect('manage_coupons')
    else:
        form = CouponForm(seller=seller)

    return render(request, 'coupons/coupon_form.html', {'form': form, 'is_platform': seller is None})

def _get_owned(request, coupon_id):
    return get_object_or_404(Coupon, pk=coupon_id, **_owner_filter(request.user))

@login_required
def edit_coupon(request, coupon_id):
    coupon = _get_owned(request, coupon_id)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon, seller=coupon.seller)
        if form.is_valid():
            form.save()
            messages.success(request, f'Cupom {coupon.code} atualizado')
            return redirect('manage_coupons')
    else:
        form = CouponForm(instance=coupon, seller=coupon.seller)

    return render(request, 'coupons/coupon_form.html', {
        'form': form,
        'coupon': coupon,
        'is_platform': coupon.is_platform,
        'used': coupon.redemptions.exists(),
    })

@login_required
def toggle_coupon(request, coupon_id):
    coupon = _get_owned(request, coupon_id)
    if request.method == 'POST':
        coupon.active = not coupon.active
        coupon.save(update_fields=['active'])
        messages.success(request, f'Cupom {coupon.code} {"reativado" if coupon.active else "encerrado"}')
    return redirect('manage_coupons')

@login_required
def delete_coupon(request, coupon_id):
    coupon = _get_owned(request, coupon_id)
    if request.method == 'POST':
        if coupon.redemptions.exists():
            messages.error(request, 'Cupons que já foram usados não podem ser excluídos, apenas encerrados')
        else:
            coupon.delete()
            messages.success(request, f'Cupom {coupon.code} excluído')
    return redirect('manage_coupons')