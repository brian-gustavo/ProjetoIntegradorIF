from django import forms

from .models import Product, Stock, ProductReview

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ('title', 'description', 'category', 'price', 'condition')

class StockForm(forms.ModelForm):
    class Meta:
        model = Stock
        fields = ('quantity',)

class ProductReviewForm(forms.ModelForm):
    rating = forms.DecimalField(
        min_value=0.5,
        max_value=5.0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={'step': '0.5', 'min': '0.5', 'max': '5.0'})
    )

    class Meta:
        model = ProductReview
        fields = ('rating', 'comment')