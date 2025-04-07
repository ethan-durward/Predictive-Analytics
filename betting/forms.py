from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, PlacedBet, UserBookmakerPreference

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add bootstrap classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'placeholder': self.fields[field].label
            })

class CustomAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add bootstrap classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({
                'class': 'form-control',
                'placeholder': self.fields[field].label
            })

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['default_edge_threshold', 'bankroll', 'kelly_fraction']
        labels = {
            'default_edge_threshold': 'Minimum Edge (%)',
            'bankroll': 'Your Bankroll ($)',
            'kelly_fraction': 'Kelly Criterion Fraction (0-1)',
        }
        help_texts = {
            'default_edge_threshold': 'Minimum edge percentage to show value bets (1.03 = 3% edge)',
            'bankroll': 'Your total betting bankroll for Kelly calculations',
            'kelly_fraction': 'Fraction of Kelly to use (0.5 = Half Kelly, recommended for most bettors)',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert edge threshold to percentage for display
        if 'default_edge_threshold' in self.initial:
            self.initial['default_edge_threshold'] = (self.initial['default_edge_threshold'] - 1) * 100
        
        # Add bootstrap classes
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
    
    def clean_default_edge_threshold(self):
        # Convert percentage back to factor
        value = self.cleaned_data['default_edge_threshold']
        return (value / 100) + 1

class BookmakerPreferenceForm(forms.Form):
    def __init__(self, *args, bookmakers=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        
        if bookmakers:
            for bookmaker in bookmakers:
                # Check if the user has a preference for this bookmaker
                initial = True
                if user:
                    pref = UserBookmakerPreference.objects.filter(
                        user=user, bookmaker=bookmaker).first()
                    if pref:
                        initial = pref.is_enabled
                
                field_name = f"bookmaker_{bookmaker.replace(' ', '_')}"
                self.fields[field_name] = forms.BooleanField(
                    label=bookmaker,
                    required=False,
                    initial=initial,
                    widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
                )
    
    def save(self):
        if not self.user:
            return
        
        for field_name, value in self.cleaned_data.items():
            if field_name.startswith('bookmaker_'):
                bookmaker = field_name[10:].replace('_', ' ')
                pref, created = UserBookmakerPreference.objects.get_or_create(
                    user=self.user, bookmaker=bookmaker)
                pref.is_enabled = value
                pref.save()

class PlacedBetResultForm(forms.ModelForm):
    class Meta:
        model = PlacedBet
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'})
        } 