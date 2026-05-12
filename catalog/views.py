from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ProductForm, ProductImageFormSet, StockForm, ProductReviewForm
from .models import Category, Product, ProductReview
from accounts.models import SellerReview

def home(request):
    categorias = Category.objects.all()
    query = request.GET.get('q', '').strip()

    produtos = Product.objects.all()
    if query:
        produtos = produtos.filter(title__icontains=query)

    return render(request, 'home.html', {
        'categorias': categorias,
        'produtos': produtos,
        'query': query,
    })

def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    seller_rating = SellerReview.objects.filter(
        seller=product.seller
    ).aggregate(media=Avg('rating'))['media']

    product_rating = ProductReview.objects.filter(
        product=product
    ).aggregate(media=Avg('rating'))['media']

    reviews = ProductReview.objects.filter(product=product).order_by('-created_at')

    already_reviewed_product = False
    can_review_product = False
    already_reviewed_seller = False
    can_review_seller = False

    if request.user.is_authenticated and not request.user.is_staff and request.user != product.seller:
        already_reviewed_product = ProductReview.objects.filter(
            product=product, reviewer=request.user
        ).exists()
        can_review_product = (
            not already_reviewed_product
            and request.user.orders.filter(product=product, status='DELIVERED').exists()
        )
        already_reviewed_seller = SellerReview.objects.filter(
            seller=product.seller, reviewer=request.user
        ).exists()
        can_review_seller = (
            not already_reviewed_seller
            and request.user.orders.filter(product__seller=product.seller, status='DELIVERED').exists()
        )

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'seller_rating': round(seller_rating, 1) if seller_rating else None,
        'product_rating': round(product_rating, 1) if product_rating else None,
        'reviews': reviews,
        'can_review_product': can_review_product,
        'already_reviewed_product': already_reviewed_product,
        'can_review_seller': can_review_seller,
        'already_reviewed_seller': already_reviewed_seller,
    })

def category_detail(request, slug):
    category = get_object_or_404(Category, slug=slug)
    produtos = Product.objects.filter(category=category)
    return render(request, 'catalog/category_detail.html', {
        'category': category,
        'produtos': produtos,
    })

def category_list(request):
    categorias = Category.objects.all()
    return render(request, 'catalog/category_list.html', {'categorias': categorias})

@login_required
def create_product(request):
    if request.user.is_staff:
        return redirect('home')
    
    if request.method == 'POST':
        product_form = ProductForm(request.POST)
        image_formset = ProductImageFormSet(request.POST, request.FILES)
        stock_form = StockForm(request.POST)

        if product_form.is_valid() and image_formset.is_valid() and stock_form.is_valid():
            product = product_form.save(commit=False)
            product.seller = request.user
            product.save()

            image_formset.instance = product
            image_formset.save()

            stock = stock_form.save(commit=False)
            stock.product = product
            stock.save()

            return redirect('home')
    else:
        product_form = ProductForm()
        image_formset = ProductImageFormSet()
        stock_form = StockForm()

    return render(request, 'catalog/create_product.html', {
        'product_form': product_form,
        'image_formset': image_formset,
        'stock_form': stock_form,
    })

@login_required
def my_products(request):
    produtos = Product.objects.filter(seller=request.user).order_by('-created_at')
    return render(request, 'catalog/my_products.html', {'produtos': produtos})

# Autocomplete por nome nas buscas
def autocomplete(request):
    query = request.GET.get('q', '').strip()
    resultados = []

    if query:
        resultados = list(
            Product.objects.filter(title__icontains=query)
            .values_list('title', flat=True)
            .distinct()[:8]
        )

    return JsonResponse(resultados, safe=False)

@login_required
def review_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.user == product.seller or request.user.is_staff:
        return redirect('product_detail', product_id=product_id)

    already_reviewed = ProductReview.objects.filter(
        product=product, reviewer=request.user
    ).exists()
    if already_reviewed:
        return redirect('product_detail', product_id=product_id)

    has_delivered_order = request.user.orders.filter(
        product=product, status='DELIVERED'
    ).exists()
    if not has_delivered_order:
        return redirect('product_detail', product_id=product_id)

    if request.method == 'POST':
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.product = product
            review.reviewer = request.user
            review.save()
            messages.success(request, 'Avaliação enviada com sucesso')
            return redirect('product_detail', product_id=product_id)
    else:
        form = ProductReviewForm()

    return render(request, 'catalog/review_product.html', {
        'form': form,
        'product': product,
    })