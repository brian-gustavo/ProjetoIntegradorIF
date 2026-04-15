from django import forms
from django.forms import inlineformset_factory

from .models import Product, ProductImage, Stock

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('title', 'description', 'category', 'price', 'condition', 'location')

class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ('quantity',)

# Permite inserir mais de uma imagem na criação de um produto
ProductImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=('image',),
    extra=5, # Permite cinco imagens (pode ser alterado se necessário)
    can_delete=False,
)