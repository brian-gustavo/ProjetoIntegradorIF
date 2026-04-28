from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from .forms import ProductForm, ProductImageFormSet, StockForm
from .models import Category, Product

def home(request):
    categorias = Category.objects.all()
    produtos = Product.objects.all()

    return render(request, 'home.html', {'categorias': categorias, 'produtos': produtos})

def product_detail(request, product_id):
    product = get_object_or_404(Product, pk=product_id)
    return render(request, 'catalog/product_detail.html', {'product': product})

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