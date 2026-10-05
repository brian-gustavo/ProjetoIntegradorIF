from decimal import Decimal
from django import forms

from auctions.services import parse_amount
from catalog.templatetags.catalog_extras import brl
from .services import MAX_ITEMS, MESSAGE_MAX_LENGTH, other

class TradeTermsForm(forms.Form):
    VOLTA_CHOICES = [
        ('nenhuma', 'Sem volta'),
        ('eu', 'Eu pago a volta'),
        ('outro', 'A outra parte paga a volta'),
    ]

    variant = forms.TypedChoiceField(coerce=int, required=False, empty_value=None)
    items = forms.TypedMultipleChoiceField(coerce=int, required=False)
    volta = forms.ChoiceField(choices=VOLTA_CHOICES, initial='nenhuma')
    cash_amount = forms.CharField(required=False)
    message = forms.CharField(required=False, max_length=MESSAGE_MAX_LENGTH, widget=forms.Textarea(attrs={'rows': 3}))

    def __init__(self, *args, inventory, variants=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['items'].choices = [(v.pk, str(v)) for v in inventory]
        if variants is None:
            del self.fields['variant']
        else:
            self.fields['variant'].choices = [(v.pk, str(v)) for v in variants]
            self.fields['variant'].required = True

    def clean_items(self):
        itens = self.cleaned_data['items']
        if not itens:
            raise forms.ValidationError('Escolha pelo menos um item.')
        if len(itens) > MAX_ITEMS:
            raise forms.ValidationError(f'Escolha no máximo {MAX_ITEMS} itens.')
        return itens

    def clean(self):
        dados = super().clean()
        if dados.get('volta', 'nenhuma') == 'nenhuma':
            dados['cash_amount'] = Decimal('0.00')
        else:
            valor = parse_amount(self.data.get('cash_amount'))
            if valor is None:
                self.add_error('cash_amount', 'Informe o valor da volta.')
            dados['cash_amount'] = valor
        return dados

    def terms(self, lado):
        volta = self.cleaned_data['volta']
        pagador = '' if volta == 'nenhuma' else (lado if volta == 'eu' else other(lado))
        return self.cleaned_data['items'], self.cleaned_data['cash_amount'], pagador

    @classmethod
    def initial_for(cls, proposal, lado):
        if not proposal.cash_amount:
            volta = 'nenhuma'
        else:
            volta = 'eu' if proposal.cash_payer == lado else 'outro'
        return {
            'items': list(proposal.items.values_list('variant_id', flat=True)),
            'volta': volta,
            'cash_amount': brl(proposal.cash_amount) if proposal.cash_amount else '',
        }

    def selected_items(self):
        valores = self.data.getlist('items') if self.is_bound else self.initial.get('items', [])
        return {str(v) for v in valores}

    def selected_variant(self):
        return str(self.data.get('variant') if self.is_bound else self.initial.get('variant', ''))

    def value_of(self, campo):
        return self.data.get(campo, '') if self.is_bound else self.initial.get(campo, self.fields[campo].initial or '')
