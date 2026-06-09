from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ProductForm, ProductVariantFormSet, ProductReviewForm
from .models import Category, Product, ProductImage, ProductVariant, ProductReview
from accounts.models import SellerReview

def home(request):
    categorias = Category.objects.all()
    query = request.GET.get('q', '').strip()
    produtos = Product.objects.filter(published=True, deleted=False).annotate(
        stock_total=Sum('variants__quantity')
    ).filter(stock_total__gt=0)
    if query:
        produtos = produtos.filter(title__icontains=query)
    return render(request, 'home.html', {
        'categorias': categorias,
        'produtos': produtos,
        'query': query,
    })

def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id, deleted=False)
    variants = product.variants.all()

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
        POST_DELIVERY_STATUSES = ('DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED')
        can_review_product = (
            not already_reviewed_product
            and request.user.orders.filter(product=product, status__in=POST_DELIVERY_STATUSES).exists()
        )
        already_reviewed_seller = SellerReview.objects.filter(
            seller=product.seller, reviewer=request.user
        ).exists()
        can_review_seller = (
            not already_reviewed_seller
            and request.user.orders.filter(product__seller=product.seller, status__in=POST_DELIVERY_STATUSES).exists()
        )

    return render(request, 'catalog/product_detail.html', {
        'product': product,
        'variants': variants,
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
    produtos = Product.objects.filter(category=category, published=True, deleted=False).annotate(
        stock_total=Sum('variants__quantity')
    ).filter(stock_total__gt=0)
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

        if product_form.is_valid():
            product = product_form.save(commit=False)
            product.seller = request.user
            product.save()
            return redirect('manage_variants', product_id=product.pk)
    else:
        product_form = ProductForm()

    return render(request, 'catalog/create_product.html', {
        'product_form': product_form,
    })

@login_required
def manage_variants(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user)

    if request.method == 'POST':
        variant_formset = ProductVariantFormSet(request.POST, instance=product)

        if variant_formset.is_valid():
            images = request.FILES.getlist('images')
            total_images = product.images.count() + len(images)

            if total_images > 5:
                return render(request, 'catalog/manage_variants.html', {
                    'product': product,
                    'variant_formset': variant_formset,
                    'image_error': f'Limite de imagens ultrapassado. Insira no máximo 5 e tente novamente.',
                })

            tamanho_maximo = 10 * 1024 * 1024
            imagens_grandes = [img.name for img in images if img.size > tamanho_maximo]
            if imagens_grandes:
                return render(request, 'catalog/manage_variants.html', {
                    'product': product,
                    'variant_formset': variant_formset,
                    'image_error': f'As seguintes imagens excedem o limite de 10MB: {", ".join(imagens_grandes)}',
                })

            variant_formset.save()

            for image in images:
                ProductImage.objects.create(product=product, image=image)

            product.published = True
            product.save()
            return redirect('home')
    else:
        variant_formset = ProductVariantFormSet(instance=product)

    return render(request, 'catalog/manage_variants.html', {
        'product': product,
        'variant_formset': variant_formset,
    })

def my_products(request):
    qs = Product.objects.filter(seller=request.user, deleted=False).order_by('-created_at')
    produtos = [p for p in qs if p.variants.exists()]
    rascunhos = [p for p in qs if not p.variants.exists()]
    return render(request, 'catalog/my_products.html', {
        'produtos': produtos,
        'rascunhos': rascunhos,
    })

def autocomplete(request):
    query = request.GET.get('q', '').strip()
    resultados = []
    if query:
        resultados = list(
            Product.objects.filter(title__icontains=query, published=True, deleted=False)
            .values_list('title', flat=True)
            .distinct()[:8]
        )
    return JsonResponse(resultados, safe=False)

@login_required
def review_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id)

    if request.user == product.seller or request.user.is_staff:
        messages.error(request, 'Você não pode avaliar o seu próprio produto.')
        return redirect('product_detail', product_id=product_id)

    already_reviewed = ProductReview.objects.filter(
        product=product, reviewer=request.user
    ).exists()
    if already_reviewed:
        messages.error(request, 'Você já avaliou este produto.')
        return redirect('product_detail', product_id=product_id)

    POST_DELIVERY_STATUSES = ('DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED')
    has_delivered_order = request.user.orders.filter(
        product=product, status__in=POST_DELIVERY_STATUSES
    ).exists()
    if not has_delivered_order:
        messages.error(request, 'Você só pode avaliar produtos de pedidos entregues.')
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

@login_required
def unpublish_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user)

    if request.method == 'POST':
        product.published = False
        product.save()
        messages.success(request, f'"{product.title}" foi retirado do ar')
        return redirect('my_products')

    return redirect('my_products')

@login_required
def edit_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user)

    if request.method == 'POST':
        product_form = ProductForm(request.POST, instance=product)
        variant_formset = ProductVariantFormSet(request.POST, instance=product)

        if product_form.is_valid() and variant_formset.is_valid():
            images = request.FILES.getlist('images')
            total_images = product.images.count() + len(images)

            if total_images > 5:
                return render(request, 'catalog/edit_product.html', {
                    'product': product,
                    'product_form': product_form,
                    'variant_formset': variant_formset,
                    'image_error': f'Limite de imagens ultrapassado. Insira no máximo 5 e tente novamente.',
                })

            tamanho_maximo = 10 * 1024 * 1024
            imagens_grandes = [img.name for img in images if img.size > tamanho_maximo]
            if imagens_grandes:
                return render(request, 'catalog/edit_product.html', {
                    'product': product,
                    'product_form': product_form,
                    'variant_formset': variant_formset,
                    'image_error': f'As seguintes imagens excedem o limite de 10MB: {", ".join(imagens_grandes)}',
                })

            delete_ids = request.POST.getlist('delete_images')
            if delete_ids:
                product.images.filter(pk__in=delete_ids).delete()

            product_form.save()
            variant_formset.save()

            for image in images:
                ProductImage.objects.create(product=product, image=image)

            messages.success(request, 'Anúncio atualizado com sucesso')
            return redirect('product_detail', product_id=product.pk)
    else:
        product_form = ProductForm(instance=product)
        variant_formset = ProductVariantFormSet(instance=product)

    return render(request, 'catalog/edit_product.html', {
        'product': product,
        'product_form': product_form,
        'variant_formset': variant_formset,
    })

@login_required
def republish_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user)

    if request.method == 'POST':
        if product.variants.exists() and product.total_stock > 0:
            product.published = True
            product.save()
            messages.success(request, f'"{product.title}" foi republicado')
        else:
            messages.error(request, 'O anúncio precisa ter ao menos uma variação com estoque para ser republicado')
        return redirect('my_products')

    return redirect('my_products')

@login_required
def edit_product_review(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    review = get_object_or_404(ProductReview, product=product, reviewer=request.user)

    if review.edited:
        messages.error(request, 'Você só pode editar sua avaliação uma vez.')
        return redirect('product_detail', product_id=product_id)

    if request.method == 'POST':
        form = ProductReviewForm(request.POST, instance=review)
        if form.is_valid():
            r = form.save(commit=False)
            r.edited = True
            r.save()
            messages.success(request, 'Avaliação atualizada com sucesso')
            return redirect('product_detail', product_id=product_id)
    else:
        form = ProductReviewForm(instance=review)

    return render(request, 'catalog/review_product.html', {
        'form': form,
        'product': product,
        'editing': True,
    })

@login_required
def delete_product(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user)

    if request.method == 'POST':
        if not product.variants.exists():
            product.delete()
            messages.success(request, 'Rascunho excluído')
        else:
            product.deleted = True
            product.published = False
            product.save()
            messages.success(request, f'"{product.title}" foi excluído')
        return redirect('my_products')

    return redirect('my_products')