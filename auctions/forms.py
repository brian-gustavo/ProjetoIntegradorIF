from datetime import timedelta
from decimal import Decimal, ROUND_UP
from django import forms
from django.utils import timezone

from catalog.templatetags.catalog_extras import brl
from .models import Auction
from .services import BUY_NOW_MIN_MARKUP

PRICE_HELP = 'Use ponto como separador decimal (ex: 4.5)'

class AuctionForm(forms.ModelForm):
    start_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('1.00'),
        label='Lance inicial (em reais)',
        help_text=f'Valor a partir do qual os lances começam. Lances iniciais baixos costumam atrair mais participantes. {PRICE_HELP}',
    )
    reserve_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='Preço de reserva (opcional)',
        help_text='Valor mínimo, mantido em sigilo, para que o item seja vendido. Se nenhum lance atingi-lo, o leilão termina sem venda. Deixe em branco para vender ao maior lance.',
    )
    buy_now_price = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        required=False,
        label='Comprar agora (opcional)',
        help_text='Permite que alguém compre o item na hora por esse valor, encerrando o leilão. A opção some após o primeiro lance (ou, havendo reserva, quando ela for atingida). Precisa ser pelo menos 30% maior que o lance inicial.',
    )

    class Meta:
        model = Auction
        fields = ('start_price', 'duration_days', 'reserve_price', 'buy_now_price')
        labels = {'duration_days': 'Duração'}
        help_texts = {'duration_days': 'O leilão começa assim que for publicado e termina exatamente após esse período'}
        widgets = {'duration_days': forms.RadioSelect}

    def __init__(self, *args, locked=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.locked = locked
        if locked:
            for field in self.fields.values():
                field.disabled = True

    def clean(self):
        dados = super().clean()
        inicial = dados.get('start_price')
        reserva = dados.get('reserve_price')
        imediato = dados.get('buy_now_price')

        if inicial is None:
            return dados

        if reserva is not None and reserva <= inicial:
            self.add_error('reserve_price', 'O preço de reserva precisa ser maior que o lance inicial')

        if imediato is not None:
            minimo = (inicial * BUY_NOW_MIN_MARKUP).quantize(Decimal('0.01'), rounding=ROUND_UP)
            if imediato < minimo:
                self.add_error('buy_now_price', f'Para este lance inicial, o Comprar agora precisa ser de pelo menos R$ {brl(minimo)}')
            elif reserva is not None and imediato <= reserva:
                self.add_error('buy_now_price', 'O Comprar agora precisa ser maior que o preço de reserva')

        duracao = dados.get('duration_days')
        if self.instance.pk and duracao and self.instance.starts_at + timedelta(days=duracao) <= timezone.now():
            self.add_error('duration_days', 'Com essa duração, o leilão já teria terminado. Escolha um período maior.')

        return dados