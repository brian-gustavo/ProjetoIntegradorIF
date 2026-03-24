from django.shortcuts import render
from .models import Category, Product

def home(request):
    categorias = Category.objects.all()
    produtos = Product.objects.all()
    
    context = {
        'categorias': categorias,
        'produtos': produtos,
    }
    return render(request, 'home.html', context)