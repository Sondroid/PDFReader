from django import forms
from .models import Firma

class FirmaForm(forms.ModelForm):
    class Meta:
        model = Firma
        fields = ['ad', 'vergi_no', 'adres', 'telefon', 'email']
        widgets = {
            'adres': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'ad': forms.TextInput(attrs={'class': 'form-control'}),
            'vergi_no': forms.TextInput(attrs={'class': 'form-control'}),
            'telefon': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        } 