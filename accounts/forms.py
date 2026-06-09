from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Profile, SellerReview, UF_CHOICES

class RegisterForm(UserCreationForm):
    city = forms.CharField(max_length=100, label="Cidade")
    uf = forms.ChoiceField(choices=[('', '---------')] + UF_CHOICES, label="Estado")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Este email já está cadastrado.')
        return email
    
class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'email')

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Este email já está cadastrado.')
        return email
    
class ProfileDetailForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ('city', 'uf')

    def clean_city(self):
        city = self.cleaned_data.get('city', '').strip()
        if not city:
            raise forms.ValidationError('Este campo é obrigatório.')
        return city

    def clean_uf(self):
        uf = self.cleaned_data.get('uf', '')
        if not uf:
            raise forms.ValidationError('Este campo é obrigatório.')
        return uf
    
class ReviewForm(forms.ModelForm):
    rating = forms.DecimalField(
        min_value=0.5,
        max_value=5.0,
        decimal_places=1,
        widget=forms.NumberInput(attrs={'step': '0.5', 'min': '0.5', 'max': '5.0'})
    )

    class Meta:
        model = SellerReview
        fields = ('rating', 'comment')