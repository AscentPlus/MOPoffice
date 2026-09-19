from django import forms

from administration.models import CustomUser


class NewConversationForm(forms.Form):
    recipient = forms.ModelChoiceField(
        queryset=CustomUser.objects.none(),
        label='Send message to',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    initial_message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-textarea',
            'rows': 3,
            'placeholder': 'Type your first message (optional)...',
        }),
    )

    def __init__(self, user, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from .permissions import get_messageable_users
        self.fields['recipient'].queryset = get_messageable_users(user)


class SendMessageForm(forms.Form):
    body = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'placeholder': 'Type a message...',
            'id': 'message-input',
        }),
    )
    attachment = forms.FileField(required=False)
