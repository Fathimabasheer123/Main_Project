# apps/prescriptions/forms.py

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
import re


class RegisterForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'})
    )
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'})
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'})
    )
    phone = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '10-digit mobile'})
    )
    user_type = forms.ChoiceField(
        choices=[('doctor', 'Doctor'), ('patient', 'Patient'), ('pharmacy', 'Pharmacy')],
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Choose username'
            })
        }

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip().lower()
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            raise ValidationError('Username: letters, numbers, underscores only.')
        if len(username) < 3:
            raise ValidationError('Username must be at least 3 characters.')
        if User.objects.filter(username=username).exists():
            raise ValidationError('This username is already taken.')
        return username

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if not re.match(r'^[1-9][0-9]{9}$', phone):
            raise ValidationError('Phone must be 10 digits and cannot start with 0.')
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if User.objects.filter(email=email).exists():
            raise ValidationError('This email is already registered.')
        return email

    def clean_password2(self):
        p1 = self.cleaned_data.get('password1', '')
        p2 = self.cleaned_data.get('password2', '')
        if p1 and p2 and p1 != p2:
            raise ValidationError('Passwords do not match.')
        # Validate strength
        if len(p1) < 8:
            raise ValidationError('Password must be at least 8 characters.')
        return p2

    def save(self, commit=True):
        user          = super().save(commit=False)
        user.username = self.cleaned_data['username']
        user.set_password(self.cleaned_data['password1'])
        if commit:
            user.save()
        return user