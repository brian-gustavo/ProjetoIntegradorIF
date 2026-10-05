from django import forms

from .models import Dispute, DisputeMessage, PlatformConfig, ReturnRequest

class PlatformConfigForm(forms.ModelForm):
    class Meta:
        model = PlatformConfig
        fields = ('commission_rate', 'dispute_window_days', 'return_window_days', 'seller_response_days', 'escalation_window_days', 'ranking_size', 'dispute_reasons', 'return_reasons', 'shelf_size', 'home_categories', 'coins_cashback_rate', 'coins_max_redeem_rate', 'coins_review_reward', 'auction_payment_days', 'second_chance_window_days')
        widgets = {
            'dispute_reasons': forms.Textarea(attrs={'rows': 8}),
            'return_reasons': forms.Textarea(attrs={'rows': 7}),
            'home_categories': forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxSelectMultiple):
                field.widget.attrs['class'] = 'input'

    def clean_dispute_reasons(self):
        linhas = [linha.strip() for linha in self.cleaned_data['dispute_reasons'].splitlines() if linha.strip()]
        if not linhas:
            raise forms.ValidationError('Informe pelo menos um motivo')
        if any(len(linha) > 100 for linha in linhas):
            raise forms.ValidationError('Cada motivo pode ter no máximo 100 caracteres')
        return '\n'.join(linhas)

    def clean_return_reasons(self):
        linhas = [linha.strip() for linha in self.cleaned_data['return_reasons'].splitlines() if linha.strip()]
        if not linhas:
            raise forms.ValidationError('Informe pelo menos um motivo')
        if any(len(linha) > 100 for linha in linhas):
            raise forms.ValidationError('Cada motivo pode ter no máximo 100 caracteres')
        return '\n'.join(linhas)

class ReturnRequestForm(forms.ModelForm):
    reason_category = forms.ChoiceField(label='Motivo da devolução')

    class Meta:
        model = ReturnRequest
        fields = ('reason_category', 'description')
        labels = {'description': 'Descreva o problema'}
        widgets = {'description': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        motivos = PlatformConfig.load().return_reason_list()
        self.fields['reason_category'].choices = [('', 'Selecione um motivo')] + [(m, m) for m in motivos]

class DisputeForm(forms.ModelForm):
    reason_category = forms.ChoiceField(label='Motivo da disputa')

    class Meta:
        model = Dispute
        fields = ('reason_category', 'reason')
        labels = {'reason': 'Descreva o problema'}
        widgets = {'reason': forms.Textarea(attrs={'rows': 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        motivos = PlatformConfig.load().dispute_reason_list()
        self.fields['reason_category'].choices = [('', 'Selecione um motivo')] + [(m, m) for m in motivos]

class DisputeMessageForm(forms.ModelForm):
    class Meta:
        model = DisputeMessage
        fields = ('message',)
        labels = {'message': 'Nova mensagem'}
        widgets = {'message': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, has_images=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_images = has_images
        self.fields['message'].required = False

    def clean_message(self):
        message = self.cleaned_data['message'].strip()
        if not message and not self.has_images:
            raise forms.ValidationError('Escreva uma mensagem ou anexe pelo menos uma imagem')
        return message

class DisputeResolutionForm(forms.Form):
    RESOLUTION_CHOICES = [
        ('buyer_return', 'A favor do comprador (com devolução)'),
        ('buyer_refund', 'A favor do comprador (sem devolução)'),
        ('seller', 'A favor do vendedor'),
    ]
    resolution = forms.ChoiceField(choices=RESOLUTION_CHOICES, widget=forms.RadioSelect, label='Decisão')
    resolution_notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Notas da decisão')