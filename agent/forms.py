from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignupForm(UserCreationForm):
    full_name = forms.CharField(label="Name", max_length=150, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["full_name", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"]
        if User.objects.filter(username=email).exists() or User.objects.filter(email=email).exists():
            raise forms.ValidationError("Is email se pehle se ek account bana hua hai. Login kar lijiye.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.username = self.cleaned_data["email"]  # email doubles as username
        user.first_name = self.cleaned_data["full_name"]
        user.is_active = False  # activated only after clicking the email verification link
        if commit:
            user.save()
        return user
