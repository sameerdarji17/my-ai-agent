import uuid
from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User


class SignupForm(forms.ModelForm):
    name = forms.CharField(label="Full Name", max_length=150, required=True, widget=forms.TextInput(attrs={
        'placeholder': 'Enter your full name', 'class': 'form-control'
    }))
    email = forms.EmailField(required=True, widget=forms.EmailInput(attrs={
        'placeholder': 'Enter your email', 'class': 'form-control'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Enter password', 'class': 'form-control', 'id': 'id_password'
    }))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Confirm password', 'class': 'form-control', 'id': 'id_confirm_password'
    }))

    class Meta:
        model = User
        fields = ("name", "email", "password")

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email is already registered. Please log in.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")

        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "Passwords do not match!")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        name_parts = self.cleaned_data.get("name").strip().split(" ", 1)
        user.first_name = name_parts[0]
        user.last_name = name_parts[1] if len(name_parts) > 1 else ""
        # Auto-generate username internally from email prefix + unique string
        base_username = self.cleaned_data.get("email").split("@")[0]
        user.username = f"{base_username}_{uuid.uuid4().hex[:6]}"
        user.set_password(self.cleaned_data.get("password"))
        if commit:
            user.save()
        return user


class CustomLoginForm(forms.Form):
    email = forms.EmailField(label="Email Address", widget=forms.EmailInput(attrs={
        'placeholder': 'Enter your email', 'class': 'form-control'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'placeholder': 'Enter password', 'class': 'form-control', 'id': 'id_login_password'
    }))

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                raise forms.ValidationError("No account found with this email.")
            self.user_cache = authenticate(username=user.username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError("Invalid email or password.")
            elif not self.user_cache.is_active:
                raise forms.ValidationError("Your account email is not verified yet. Please check your inbox.")
        return cleaned_data

    def get_user(self):
        return self.user_cache