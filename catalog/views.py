from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Count, F, Max, Min, OuterRef, Subquery, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse

from .forms import ProductForm, ProductVariantFormSet, ProductReviewForm
from .models import Category, Product, ProductImage, ProductVariant, ProductReview
from .templatetags.catalog_extras import brl
from accounts.models import SellerReview
from orders.models import Order, PlatformConfig

RATING_OPTIONS = [
    ('4.0', '4,0 ou mais'),
    ('4.5', '4,5 ou mais'),
]

SORT_OPTIONS = {
    'recentes': ('Mais recentes', ('-created_at',)),
    'avaliacao': ('Mais bem avaliados', (F('avg_rating').desc(nulls_last=True), '-created_at')),
    'menor_preco': ('Menor preço', ('min_price', '-created_at')),
    'maior_preco': ('Maior preço', ('-min_price', '-created_at')),
}

def _apply_sort(request, qs):
    ordem = request.GET.get('ordem', '')
    if ordem not in SORT_OPTIONS:
        ordem = 'recentes'
    order_by = SORT_OPTIONS[ordem][1]

    params = request.GET.copy()
    params.pop('page', None)

    return qs.order_by(*order_by), {
        'atual': ordem,
        'opcoes': [{'key': key, 'label': opcao[0]} for key, opcao in SORT_OPTIONS.items()],
        'hidden': [
            (key, value)
            for key, values in params.lists()
            if key != 'ordem'
            for value in values
        ],
    }

def _parse_preco(valor):
    valor = (valor or '').strip().replace('R$', '').replace(' ', '')
    if ',' in valor:
        valor = valor.replace('.', '').replace(',', '.')
    try:
        preco = Decimal(valor)
    except InvalidOperation:
        return None
    if not preco.is_finite() or preco < 0:
        return None
    return preco.quantize(Decimal('0.01'))

def _get_preco_range(request):
    preco_min = _parse_preco(request.GET.get('preco_min'))
    preco_max = _parse_preco(request.GET.get('preco_max'))
    if preco_min is not None and preco_max is not None and preco_min > preco_max:
        preco_min, preco_max = preco_max, preco_min
    return preco_min, preco_max

def _annotate_products(qs):
    rating_subquery = ProductReview.objects.filter(
        product=OuterRef('pk')
    ).values('product').annotate(avg=Avg('rating')).values('avg')

    return qs.annotate(
        stock_total=Sum('variants__quantity'),
        min_price=Min('variants__price'),
        avg_rating=Subquery(rating_subquery),
    ).filter(stock_total__gt=0)

def _apply_filters(qs, preco_min, preco_max, local, avaliacao, profile):
    if preco_min is not None:
        qs = qs.filter(min_price__gte=preco_min)
    if preco_max is not None:
        qs = qs.filter(min_price__lte=preco_max)

    if local == 'cidade' and profile and profile.city:
        qs = qs.filter(seller__profile__city=profile.city)
    elif local == 'estado' and profile and profile.uf:
        qs = qs.filter(seller__profile__uf=profile.uf)

    if avaliacao:
        qs = qs.filter(avg_rating__gte=Decimal(avaliacao))

    return qs

def _facet_url(request, **overrides):
    params = request.GET.copy()
    params.pop('page', None)
    for key, value in overrides.items():
        if value:
            params[key] = value
        else:
            params.pop(key, None)
    query = params.urlencode()
    return f'?{query}' if query else '?'

def _build_filter_context(request, base_qs):
    preco_min, preco_max = _get_preco_range(request)
    local = request.GET.get('local', '')
    avaliacao = request.GET.get('avaliacao', '')
    if avaliacao not in dict(RATING_OPTIONS):
        avaliacao = ''

    profile = None
    if request.user.is_authenticated and not request.user.is_staff:
        profile = request.user.profile

    produtos_qs = _apply_filters(base_qs, preco_min, preco_max, local, avaliacao, profile)

    local_options = [('', 'Qualquer lugar'), ('cidade', 'Na sua cidade'), ('estado', 'No seu estado')]
    local_facets = []
    for key, label in local_options:
        disponivel = key == '' or (profile and (profile.city if key == 'cidade' else profile.uf))
        if not disponivel:
            continue
        count = _apply_filters(base_qs, preco_min, preco_max, key, avaliacao, profile).count()
        local_facets.append({
            'label': label, 'count': count,
            'active': local == key, 'url': _facet_url(request, local=key),
        })

    rating_facets = []
    for key, label in [('', 'Qualquer nota')] + RATING_OPTIONS:
        count = _apply_filters(base_qs, preco_min, preco_max, local, key, profile).count()
        rating_facets.append({
            'label': label, 'count': count,
            'active': avaliacao == key, 'url': _facet_url(request, avaliacao=key),
        })

    chips = []
    if preco_min is not None or preco_max is not None:
        if preco_min is not None and preco_max is not None:
            label = f'R$ {brl(preco_min)} a R$ {brl(preco_max)}'
        elif preco_min is not None:
            label = f'A partir de R$ {brl(preco_min)}'
        else:
            label = f'Até R$ {brl(preco_max)}'
        chips.append({'label': label, 'url': _facet_url(request, preco_min=None, preco_max=None)})
    for facet in local_facets:
        if facet['active'] and local:
            chips.append({'label': facet['label'], 'url': _facet_url(request, local=None)})
    if avaliacao:
        chips.append({'label': f'Nota {dict(RATING_OPTIONS)[avaliacao]}', 'url': _facet_url(request, avaliacao=None)})

    params = request.GET.copy()
    params.pop('page', None)

    faixa = base_qs.aggregate(menor=Min('min_price'), maior=Max('min_price'))
    query = request.GET.get('q', '').strip()
    ordem = request.GET.get('ordem', '')
    limpar = {key: value for key, value in (('q', query), ('ordem', ordem)) if value}

    return produtos_qs, {
        'preco_min': '' if preco_min is None else brl(preco_min),
        'preco_max': '' if preco_max is None else brl(preco_max),
        'preco_hidden': [
            (key, value)
            for key, values in params.lists()
            if key not in ('preco_min', 'preco_max')
            for value in values
        ],
        'faixa': faixa,
        'local_facets': local_facets,
        'rating_facets': rating_facets,
        'chips': chips,
        'filtros_ativos': bool(chips),
        'limpar_url': f'?{urlencode(limpar)}' if limpar else '?',
        'page_qs': params.urlencode(),
    }

def home(request):
    categorias = Category.objects.all()
    query = request.GET.get('q', '').strip()

    base_qs = _annotate_products(
        Product.objects.filter(published=True, deleted=False)
    ).select_related('seller__profile').prefetch_related('images', 'variants')

    if not query:
        return render(request, 'home.html', {
            'categorias': categorias,
            'prateleiras': _build_shelves(base_qs),
        })

    base_qs = base_qs.filter(title__icontains=query)
    produtos_qs, filtros = _build_filter_context(request, base_qs)
    produtos_qs, ordenacao = _apply_sort(request, produtos_qs)

    paginator = Paginator(produtos_qs, 24)
    produtos = paginator.get_page(request.GET.get('page'))

    return render(request, 'home.html', {
        'categorias': categorias,
        'produtos': produtos,
        'query': query,
        'filtros': filtros,
        'ordenacao': ordenacao,
    })

SHELF_FALLBACK_CATEGORIES = 3
NOT_SOLD_STATUSES = ('PENDING', 'CANCELLED', 'RETURNED', 'CANCELLED_NO_RETURN')

def _build_shelves(base_qs):
    review_count = ProductReview.objects.filter(
        product=OuterRef('pk')
    ).values('product').annotate(n=Count('pk')).values('n')
    sold = Order.objects.filter(
        product=OuterRef('pk')
    ).exclude(status__in=NOT_SOLD_STATUSES).values('product').annotate(n=Sum('quantity')).values('n')

    qs = base_qs.annotate(review_count=Subquery(review_count), sold=Subquery(sold))

    prateleiras = [
        {'titulo': 'Mais vendidos', 'produtos': qs.filter(sold__gt=0).order_by('-sold', '-created_at')},
        {'titulo': 'Mais bem avaliados', 'produtos': qs.filter(avg_rating__isnull=False).order_by('-avg_rating', '-review_count', '-created_at')},
        {'titulo': 'Novidades', 'produtos': qs.order_by('-created_at')},
        {'titulo': 'Menores preços', 'produtos': qs.order_by('min_price', '-created_at')},
    ]

    config = PlatformConfig.load()
    destaques = Category.objects.filter(
        products__published=True, products__deleted=False
    ).annotate(n=Count('products')).order_by('-n', 'name')
    escolhidas = config.home_categories.all()
    destaques = destaques.filter(pk__in=escolhidas) if escolhidas.exists() else destaques[:SHELF_FALLBACK_CATEGORIES]
    for categoria in destaques:
        prateleiras.append({
            'titulo': categoria.name,
            'url': reverse('category_detail', args=[categoria.slug]),
            'produtos': qs.filter(category=categoria).order_by('-created_at'),
        })

    for prateleira in prateleiras:
        prateleira['produtos'] = list(prateleira['produtos'][:config.shelf_size])
    return [p for p in prateleiras if p['produtos']]

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

    base_qs = _annotate_products(
        Product.objects.filter(category=category, published=True, deleted=False)
    ).select_related('seller__profile').prefetch_related('images', 'variants')

    produtos_qs, filtros = _build_filter_context(request, base_qs)
    produtos_qs, ordenacao = _apply_sort(request, produtos_qs)

    paginator = Paginator(produtos_qs, 24)
    produtos = paginator.get_page(request.GET.get('page'))

    return render(request, 'catalog/category_detail.html', {
        'category': category,
        'produtos': produtos,
        'filtros': filtros,
        'ordenacao': ordenacao,
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
    qs = Product.objects.filter(seller=request.user, deleted=False).annotate(
        variant_count=Count('variants')
    ).prefetch_related('images', 'variants').order_by('-created_at')

    produtos_qs = qs.filter(variant_count__gt=0)
    rascunhos = qs.filter(variant_count=0)

    paginator = Paginator(produtos_qs, 24)
    produtos = paginator.get_page(request.GET.get('page'))

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
            delete_ids = request.POST.getlist('delete_images')
            total_images = product.images.count() - len(delete_ids) + len(images)

            if total_images > 5:
                return render(request, 'catalog/edit_product.html', {
                    'product': product,
                    'product_form': product_form,
                    'variant_formset': variant_formset,
                    'image_error': 'Limite de imagens ultrapassado. Insira no máximo 5 e tente novamente.',
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