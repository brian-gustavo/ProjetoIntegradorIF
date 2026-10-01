from django import forms

from .models import Dispute, DisputeMessage, PlatformConfig

class PlatformConfigForm(forms.ModelForm):
    class Meta:
        model = PlatformConfig
        fields = ('commission_rate', 'dispute_window_days', 'return_window_days', 'ranking_size', 'dispute_reasons', 'shelf_size', 'home_categories')
        widgets = {
            'dispute_reasons': forms.Textarea(attrs={'rows': 8}),
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

class DisputeResolutionForm(forms.Form):
    RESOLUTION_CHOICES = [
        ('buyer_return', 'A favor do comprador (com devolução)'),
        ('buyer_refund', 'A favor do comprador (sem devolução)'),
        ('seller', 'A favor do vendedor'),
    ]
    resolution = forms.ChoiceField(choices=RESOLUTION_CHOICES, widget=forms.RadioSelect, label='Decisão')
    resolution_notes = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False, label='Notas da decisão')