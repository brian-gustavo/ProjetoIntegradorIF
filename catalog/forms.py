from decimal import Decimal
from django import forms
from django.forms import inlineformset_factory

from .models import Product, ProductVariant, ProductReview

class ProductForm(forms.ModelForm):
    TRADE_FIELDS = ('accepts_trade', 'trade_preferences')

    class Meta:
        model = Product
        fields = ('title', 'category', 'description', 'condition', 'accepts_pickup', 'accepts_trade', 'trade_preferences')
        help_texts = {'accepts_trade': 'Interessados podem oferecer itens anunciados por eles, com ou sem volta em dinheiro. Não vale para leilões.'}
        widgets = {'trade_preferences': forms.TextInput(attrs={'placeholder': 'Ex.: jogos de PS5, controles originais'})}

    def __init__(self, *args, auction=False, **kwargs):
        super().__init__(*args, **kwargs)
        if auction:
            for campo in self.TRADE_FIELDS:
                del self.fields[campo]

    def clean(self):
        dados = super().clean()
        if 'accepts_trade' in self.fields and not dados.get('accepts_trade'):
            dados['trade_preferences'] = ''
        return dados

class ProductVariantForm(forms.ModelForm):
    price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        help_text='Use ponto como separador decimal (ex: 4.5)',
        label='Preço (em reais)',
    )
    quantity = forms.IntegerField(min_value=1, label='Quantidade')

    class Meta:
        model = ProductVariant
        fields = ('name', 'price', 'quantity')

ProductVariantFormSet = inlineformset_factory(
    Product,
    ProductVariant,
    form=ProductVariantForm,
    extra=0,
    min_num=1,
    validate_min=True,
    can_delete=True,
)

class ProductReviewForm(forms.ModelForm):
    rating = forms.DecimalField(
        min_value=0.5,
        max_value=5.0,
        decimal_places=1,
        help_text='Use ponto como separador decimal (ex: 4.5)',
        widget=forms.NumberInput(attrs={'step': '0.5', 'min': '0.5', 'max': '5.0'})
    )

    def clean_rating(self):
        rating = self.cleaned_data.get('rating')
        if rating is not None:
            from decimal import Decimal
            if rating % Decimal('0.5') != 0:
                raise forms.ValidationError('A nota deve ser um múltiplo de 0,5 (ex: 1,0 / 1,5 / 2,0...)')
        return rating

    class Meta:
        model = ProductReview
        fields = ('rating', 'comment')