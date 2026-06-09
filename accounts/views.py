from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404

from .forms import RegisterForm, ProfileForm, ProfileDetailForm, ReviewForm
from .models import SellerReview

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.profile.city = form.cleaned_data['city']
            user.profile.uf = form.cleaned_data['uf']
            user.profile.save()
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})

@login_required
def profile_settings(request):
    profile_form = ProfileForm(instance=request.user)
    profile_detail_form = ProfileDetailForm(instance=request.user.profile)
    password_form = PasswordChangeForm(user=request.user)

    if request.method == 'POST':
        if 'save_profile' in request.POST:
            profile_form = ProfileForm(request.POST, instance=request.user)
            profile_detail_form = ProfileDetailForm(request.POST, instance=request.user.profile)

            if profile_form.is_valid() and profile_detail_form.is_valid():
                profile_form.save()
                profile_detail_form.save()
                messages.success(request, 'Dados atualizados com sucesso')
                return redirect('profile_settings')
        elif 'save_password' in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)

            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Senha alterada com sucesso')
                return redirect('profile_settings')

    return render(request, 'accounts/profile_settings.html', {
        'profile_form': profile_form,
        'profile_detail_form': profile_detail_form,
        'password_form': password_form,
    })

@login_required
def review_seller(request, seller_id):
    seller = get_object_or_404(User, pk=seller_id)

    if seller == request.user:
        messages.error(request, 'Você não pode avaliar a si mesmo.')
        return redirect('my_orders')

    already_reviewed = SellerReview.objects.filter(
        seller=seller, reviewer=request.user
    ).exists()
    if already_reviewed:
        messages.error(request, 'Você já avaliou este vendedor.')
        return redirect('my_orders')

    POST_DELIVERY_STATUSES = ('DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED')
    has_delivered_order = request.user.orders.filter(
        product__seller=seller, status__in=POST_DELIVERY_STATUSES
    ).exists()
    if not has_delivered_order:
        messages.error(request, 'Você só pode avaliar vendedores de pedidos entregues.')
        return redirect('my_orders')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.seller = seller
            review.reviewer = request.user
            review.save()
            messages.success(request, f'Avaliação enviada para {seller.username}')
            return redirect('my_orders')
    else:
        form = ReviewForm()

    return render(request, 'accounts/review_seller.html', {
        'form': form,
        'seller': seller,
    })

@login_required
def edit_seller_review(request, seller_id):
    seller = get_object_or_404(User, pk=seller_id)
    review = get_object_or_404(SellerReview, seller=seller, reviewer=request.user)

    if review.edited:
        messages.error(request, 'Você só pode editar sua avaliação uma vez.')
        return redirect('my_orders')

    if request.method == 'POST':
        form = ReviewForm(request.POST, instance=review)
        if form.is_valid():
            r = form.save(commit=False)
            r.edited = True
            r.save()
            messages.success(request, f'Avaliação de {seller.username} atualizada com sucesso')
            return redirect('my_orders')
    else:
        form = ReviewForm(instance=review)

    return render(request, 'accounts/review_seller.html', {
        'form': form,
        'seller': seller,
        'editing': True,
    })