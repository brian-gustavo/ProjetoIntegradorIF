from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from .models import Category, Product
from .forms import ProductForm, ProductImageForm

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
        image_form = ProductImageForm(request.POST, request.FILES)

        if product_form.is_valid() and image_form.is_valid():
            product = product_form.save(commit=False)
            product.seller = request.user
            product.save()

            if image_form.cleaned_data.get('image'):
                image = image_form.save(commit=False)
                image.product = product
                image.save()

            return redirect('home')
    else:
        product_form = ProductForm()
        image_form = ProductImageForm()

    return render(request, 'catalog/create_product.html', {
        'product_form': product_form,
        'image_form': image_form,
    })