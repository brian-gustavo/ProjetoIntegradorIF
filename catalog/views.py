from django.shortcuts import render
from .models import Category

def home(request):
    categorias = Category.objects.all()
    return render(request, 'home.html', {'categorias': categorias})