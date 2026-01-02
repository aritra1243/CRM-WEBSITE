from django import forms
from .models import Payment, Customer

class PaymentForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'customer'}),
        empty_label="Select Customer",
        to_field_name="customer_id"
    )
    
    amount = forms.DecimalField(
        max_digits=12, 
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Enter amount', 'id': 'amount'})
    )
    
    payment_date = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={
            'class': 'form-control', 
            'type': 'datetime-local',
            'id': 'payment_date'
        })
    )
    
    bank_name = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter bank name', 'id': 'bank_name'})
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional notes', 'id': 'notes'})
    )
    
    receipt = forms.FileField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'id': 'receipt', 'accept': '.pdf,.jpg,.jpeg,.png,.gif'})
    )

    class Meta:
        model = Payment
        fields = ['customer', 'amount', 'payment_date', 'bank_name', 'notes', 'receipt']
