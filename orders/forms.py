from django import forms

from .models import Dispute, DisputeMessage

class DisputeForm(forms.ModelForm):
    class Meta:
        model = Dispute
        fields = ('reason',)
        labels = {'reason': 'Motivo da disputa'}
        widgets = {'reason': forms.Textarea(attrs={'rows': 4})}

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