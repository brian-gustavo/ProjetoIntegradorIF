from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404

from .forms import RegisterForm, ProfileForm, ReviewForm
from .models import SellerReview

def register(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')
    else:
        form = RegisterForm()

    return render(request, 'registration/register.html', {'form': form})

@login_required
def profile_settings(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = PasswordChangeForm(user=request.user)

    if request.method == 'POST':
        if 'save_profile' in request.POST:
            profile_form = ProfileForm(request.POST, instance=request.user)

            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Dados atualizados com sucesso.')
                return redirect('profile_settings')
        elif 'save_password' in request.POST:
            password_form = PasswordChangeForm(user=request.user, data=request.POST)

            if password_form.is_valid():
                password_form.save()
                update_session_auth_hash(request, password_form.user)
                messages.success(request, 'Senha alterada com sucesso.')
                return redirect('profile_settings')

    return render(request, 'accounts/profile_settings.html', {
        'profile_form': profile_form,
        'password_form': password_form,
    })

@login_required
def review_seller(request, seller_id):
    seller = get_object_or_404(User, pk=seller_id)

    if seller == request.user:
        return redirect('my_orders')

    already_reviewed = SellerReview.objects.filter(
        seller=seller, reviewer=request.user
    ).exists()
    if already_reviewed:
        return redirect('my_orders')

    has_delivered_order = request.user.orders.filter(
        product__seller=seller, status='DELIVERED'
    ).exists()
    if not has_delivered_order:
        return redirect('my_orders')

    if request.method == 'POST':
        form = ReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.seller = seller
            review.reviewer = request.user
            review.save()
            messages.success(request, f'Avaliação enviada para {seller.username}.')
            return redirect('my_orders')
    else:
        form = ReviewForm()

    return render(request, 'accounts/review_seller.html', {
        'form': form,
        'seller': seller,
    })