from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Category, Product
from .forms import ProductForm, ProductImageFormSet

def home(request):
    categorias = Category.objects.all()
    produtos = Product.objects.all()

    context = {
        'categorias': categorias,
        'produtos': produtos,
    }
    return render(request, 'home.html', context)

@login_required
def create_product(request):
    if request.method == 'POST':
        product_form = ProductForm(request.POST)
        image_formset = ProductImageFormSet(request.POST, request.FILES)

        if product_form.is_valid() and image_formset.is_valid():
            product = product_form.save(commit=False)
            product.seller = request.user
            product.save()

            image_formset.instance = product
            image_formset.save()

            return redirect('home')
    else:
        product_form = ProductForm()
        image_formset = ProductImageFormSet()

    return render(request, 'catalog/create_product.html', {
        'product_form': product_form,
        'image_formset': image_formset,
    })