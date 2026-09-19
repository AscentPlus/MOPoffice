from django import forms
from administration.models import (
    CustomUser, Post, Department, DocumentType, 
    DocumentOrigin, DocumentPriority, TransitType, DocumentStatus
)
from django.contrib.auth.hashers import make_password
import random
import string


class UserCreationForm(forms.ModelForm):
    """Form for creating new users"""
    
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter first name'
        })
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter last name'
        })
    )
    
    username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter username',
            'autocomplete': 'off'
        }),
        help_text='Username will be used for login'
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter email address'
        })
    )
    
    mobile = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter mobile number'
        })
    )
    
    post = forms.ModelChoiceField(
        queryset=Post.objects.filter(is_active=True).order_by('priority'),
        required=True,
        empty_label="Select Post",
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text='Select the official post for this user'
    )
    
    password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password',
            'autocomplete': 'new-password'
        }),
        help_text='Minimum 6 characters'
    )
    
    confirm_password = forms.CharField(
        max_length=128,
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm password',
            'autocomplete': 'new-password'
        }),
        label='Confirm Password'
    )
    
    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'mobile', 'post']
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if CustomUser.objects.filter(username=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        
        if password and confirm_password:
            if password != confirm_password:
                raise forms.ValidationError('Passwords do not match.')
            
            if len(password) < 4:
                raise forms.ValidationError('Password must be at least 4 characters long.')
        
        return cleaned_data
    
    def save(self, commit=True, created_by=None):
        user = super().save(commit=False)
        
        # Set password from form
        user.set_password(self.cleaned_data['password'])
        
        # Set created_by
        if created_by:
            user.created_by = created_by
        
        if commit:
            user.save()
        
        return user


class UserEditForm(forms.ModelForm):
    """Form for editing existing users"""
    
    first_name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    mobile = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    post = forms.ModelChoiceField(
        queryset=Post.objects.filter(is_active=True).order_by('priority'),
        required=True,
        empty_label="Select Post",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    is_active = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Uncheck to deactivate user login'
    )
    
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'mobile', 'post', 'is_active']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            # Hide "Active" checkbox for superusers or Priority 1.0 accounts
            # to prevent accidental deactivation of administrative access.
            if self.instance.is_superuser or (self.instance.post and self.instance.post.priority == 1.0):
                if 'is_active' in self.fields:
                    del self.fields['is_active']


class PostForm(forms.ModelForm):
    """Form for creating and editing official posts"""
    
    name = forms.CharField(
        max_length=200,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter post name'
        })
    )
    
    priority = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
        }),
        help_text='Lower number means higher authority'
    )
    
    def clean_priority(self):
        priority = self.cleaned_data.get('priority')
        if priority is None:
            # Set a default priority (e.g., 99.00) if not provided
            return 99.00
        return priority
    
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter internal remarks',
            'rows': 3
        })
    )
    
    is_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Post is active'
    )
    
    class Meta:
        model = Post
        fields = ['name', 'priority', 'remarks', 'is_active']
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        # Check if another post with same name exists (excluding current instance)
        qs = Post.objects.filter(name__iexact=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('A post with this name already exists.')
        return name

class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'remarks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter department name'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'remarks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter document type'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class DocumentOriginForm(forms.ModelForm):
    class Meta:
        model = DocumentOrigin
        fields = ['name', 'remarks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter origin name'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class DocumentPriorityForm(forms.ModelForm):
    class Meta:
        model = DocumentPriority
        fields = ['name', 'remarks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter priority name'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class TransitTypeForm(forms.ModelForm):
    class Meta:
        model = TransitType
        fields = ['name', 'remarks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter transit type'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class DocumentStatusForm(forms.ModelForm):
    class Meta:
        model = DocumentStatus
        fields = ['name', 'remarks', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter status name'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'})
        }

class AdminPasswordChangeForm(forms.Form):
    """Form for administrators to reset a user's password"""
    new_password = forms.CharField(
        label="New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password'}),
        help_text="Minimum 4 characters."
    )
    confirm_password = forms.CharField(
        label="Confirm New Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'})
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise forms.ValidationError("Passwords do not match.")
            if len(new_password) < 4:
                raise forms.ValidationError("Password must be at least 4 characters long.")
        return cleaned_data
