from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from .forms import ProductForm, ProductImageFormSet, StockForm
from .models import Category, Product

def home(request):
    categorias = Category.objects.all()
    produtos = Product.objects.all()

    return render(request, 'home.html', {'categorias': categorias, 'produtos': produtos})

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