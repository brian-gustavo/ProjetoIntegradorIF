import re, secrets, string
from decimal import Decimal, ROUND_UP
from django import forms

from catalog.templatetags.catalog_extras import brl
from orders.models import PlatformConfig
from .models import Coupon
from .services import normalize_code

DATETIME_FORMAT = '%Y-%m-%dT%H:%M'

def generate_code(prefixo=''):
    prefixo = re.sub(r'[^A-Z0-9]', '', prefixo.upper())[:8]
    while True:
        code = prefixo + ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
        if not Coupon.objects.filter(code=code).exists():
            return code

class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = (
            'code', 'kind', 'value', 'max_discount', 'min_order_value', 'category', 'first_purchase_only',
            'starts_at', 'ends_at', 'usage_limit', 'per_user_limit', 'is_public',
        )
        labels = {
            'value': 'Desconto',
            'category': 'Válido apenas na categoria',
            'first_purchase_only': 'Apenas para a primeira compra',
            'is_public': 'Exibir publicamente',
        }
        help_texts = {
            'code': 'Letras e números, de 4 a 20 caracteres. Deixe em branco para gerar automaticamente. Não pode ser alterado depois.',
            'value': 'Em % para descontos percentuais ou em R$ para valor fixo',
            'max_discount': 'Teto do desconto percentual. Deixe em branco para não limitar.',
            'min_order_value': 'Soma dos itens elegíveis no carrinho necessária para usar o cupom',
            'category': 'Deixe em branco para valer em todas as categorias',
            'ends_at': 'Deixe em branco para não expirar',
            'usage_limit': 'Quantidade total de cupons disponíveis. Deixe em branco para não limitar.',
            'is_public': 'Cupons públicos aparecem automaticamente para os compradores; os privados só podem ser usados por quem digitar o código',
        }
        widgets = {
            'kind': forms.RadioSelect,
            'starts_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DATETIME_FORMAT),
            'ends_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format=DATETIME_FORMAT),
        }

    def __init__(self, *args, seller=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.seller = seller
        self.commission_rate = PlatformConfig.get_commission_rate()
        self.fields['code'].required = False
        self.fields['category'].empty_label = 'Todas as categorias'
        for campo in ('starts_at', 'ends_at'):
            self.fields[campo].input_formats = [DATETIME_FORMAT]

        if self.instance.pk:
            self.fields['code'].disabled = True
            self.fields['code'].help_text = 'O código não pode ser alterado depois de criado'

        if seller is None:
            self.fields['first_purchase_only'].help_text = 'Só pode ser usado por quem nunca comprou na MegaGame'
            self.fields['value'].help_text += (
                f'. Cupons MegaGame são custeados pela comissão da plataforma ({self.commission_rate.normalize():f}%), '
                'então o desconto em cada pedido nunca a ultrapassa.'
            )
        else:
            self.fields['first_purchase_only'].help_text = 'Só pode ser usado por quem nunca comprou na sua loja'

    def clean_code(self):
        if self.instance.pk:
            return self.instance.code
        code = normalize_code(self.cleaned_data['code'])
        if not code:
            return generate_code(self.seller.username if self.seller else 'MEGA')
        if not re.fullmatch(r'[A-Z0-9]{4,20}', code):
            raise forms.ValidationError('Use de 4 a 20 letras ou números, sem espaços ou símbolos')
        if Coupon.objects.filter(code=code).exists():
            raise forms.ValidationError('Já existe um cupom com esse código')
        return code

    def clean(self):
        dados = super().clean()
        kind, value = dados.get('kind'), dados.get('value')
        minimo = dados.get('min_order_value') or Decimal('0')
        inicio, fim = dados.get('starts_at'), dados.get('ends_at')

        if inicio and fim and fim <= inicio:
            self.add_error('ends_at', 'O fim da validade precisa ser depois do início')

        if kind == 'FIXED':
            dados['max_discount'] = None

        if not kind or value is None:
            return dados

        if kind == 'PERCENT':
            if value > 100:
                self.add_error('value', 'O desconto percentual não pode passar de 100%')
            elif self.seller is None and value > self.commission_rate:
                self.add_error('value', f'Cupons MegaGame podem dar no máximo {self.commission_rate.normalize():f}% de desconto, a taxa de comissão atual')
        elif self.seller is None:
            minimo_necessario = (value * Decimal('100') / self.commission_rate).quantize(Decimal('0.01'), rounding=ROUND_UP) if self.commission_rate else None
            if minimo_necessario is None:
                self.add_error('value', 'Com a comissão zerada, a plataforma não tem margem para custear cupons')
            elif minimo < minimo_necessario:
                self.add_error('min_order_value', f'Para dar R$ {brl(value)} de desconto, o valor mínimo da compra precisa ser de pelo menos R$ {brl(minimo_necessario)} (o desconto é custeado pela comissão de {self.commission_rate.normalize():f}%)')
        elif value >= minimo:
            self.add_error('min_order_value', 'Em cupons de valor fixo, o valor mínimo da compra precisa ser maior que o desconto')

        return dados