from django import forms
from .models import FileMaster, FileDocument
from administration.models import Department, DocumentType, DocumentOrigin, DocumentPriority


class MultipleFileInput(forms.FileInput):
    """Custom widget to allow multiple file selection (Django 4.2+)."""
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    """FileField that accepts multiple files."""
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput(attrs={'class': 'form-control'}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        # data is a list of files when multiple=True on the input
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)] if data else []
        return result


class FileCreateForm(forms.ModelForm):
    """Form for creating new files"""
    
    subject = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter file subject or description'
        }),
        help_text='Brief description of the file content'
    )
    
    department = forms.ModelChoiceField(
        queryset=Department.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Department"
    )
    
    document_type = forms.ModelChoiceField(
        queryset=DocumentType.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Document Type"
    )
    
    document_origin = forms.ModelChoiceField(
        queryset=DocumentOrigin.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Origin"
    )
    
    document_priority = forms.ModelChoiceField(
        queryset=DocumentPriority.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="Select Priority"
    )
    
    remarks = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter any initial remarks'
        })
    )
    
    attachment = MultipleFileField(
        required=False,
        help_text='Upload initial documents or compressed files (Max 200KB per file)'
    )

    def clean_attachment(self):
        files = self.files.getlist('attachment')
        for file in files:
            if file.size > 200 * 1024:
                raise forms.ValidationError(f"File '{file.name}' exceeds the 200KB limit.")
        return files


    class Meta:
        model = FileMaster
        fields = [
            'subject', 'department', 'document_type', 
            'document_origin', 'document_priority', 'remarks'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



class FileActionForm(forms.Form):
    """Form for processing file actions"""
    ALL_ACTION_CHOICES = [
        ('FORWARD', 'Forward'),
        ('EXTERNAL', 'Send to Government/External'),
        ('ACK_RETURN', 'Acknowledge Return'),
        ('RETURN', 'Return'),
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('KEEP_IN_FILE', 'Keep in File'),
        ('CLOSE', 'Close File'),
        ('PROCESSING_NOTE', 'Processing Note'),
    ]
    
    action_type = forms.ChoiceField(
        choices=[],  # Set in __init__
        widget=forms.HiddenInput()
    )
    
    assignee = forms.ChoiceField(
        choices=[],  # Set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Assign To"
    )
    
    cc_users = forms.MultipleChoiceField(
        choices=[],  # Set in __init__
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Share Copy With (View Only)"
    )
    
    remarks = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter remarks for this action'
        }),
        required=True,
        help_text='Remarks are required for all actions'
    )

    action_attachment = MultipleFileField(
        required=False,
        label="Attach Documents/Compressed Files (Optional)",
        help_text='Max 200KB per file'
    )


    action_attachment_description = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Brief description of the attachment'
        }),
        label="Attachment Description"
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        self.can_set_cc = kwargs.pop('can_set_cc', False)
        file_status = kwargs.pop('file_status', None)
        super(FileActionForm, self).__init__(*args, **kwargs)
        
        # Filter action choices based on status and role
        if file_status == 'Processing':
            self.fields['action_type'].choices = [
                ('ACK_RETURN', 'Acknowledge Return'),
            ]
        else:
            base_choices = [
                ('FORWARD', 'Forward'),
                ('EXTERNAL', 'Send to Government/External'),
                ('RETURN', 'Return'),
                ('APPROVE', 'Approve'),
                ('REJECT', 'Reject'),
                ('KEEP_IN_FILE', 'Keep in File'),
                ('PROCESSING_NOTE', 'Processing Note'),
            ]
            if user and user.post.priority <= 1.5:
                base_choices.append(('CLOSE', 'Close File'))
            self.fields['action_type'].choices = base_choices
        
        # Populate assignee and CC choices
        from administration.models import Post, CustomUser
        
        assignee_choices = [('', 'Select Recipient (Action Taker)')]
        cc_choices = []
        
        # Get all active posts that have at least one active user, ordered by priority
        posts = Post.objects.filter(
            is_active=True, 
            users__is_active=True
        ).distinct().order_by('priority')
        
        for post in posts:
            # Get users for this post
            post_users = post.users.filter(is_active=True)
            
            # Show individual users (Exclude self)
            for u in post_users:
                if u == user:
                    continue
                display_name = f"{post.name} - {u.get_full_name() or u.username}"
                
                # Receiver choices (Assignee)
                assignee_choices.append((f"user_{u.id}", display_name))
                
                # CC choices
                if self.can_set_cc:
                    cc_choices.append((f"user_{u.id}", display_name))
        
        self.fields['assignee'].choices = assignee_choices
        
        if self.can_set_cc:
            self.fields['cc_users'].choices = cc_choices
        else:
            # If they can't set CC, we could remove the field or just leave it empty and hide it in UI.
            # Best is to remove it from the form to prevent malicious POSTs.
            del self.fields['cc_users']

        
    def clean_action_attachment(self):
        files = self.files.getlist('action_attachment')
        for file in files:
            if file.size > 200 * 1024:
                raise forms.ValidationError(f"File '{file.name}' exceeds the 200KB limit.")
        return files


    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action_type')
        assignee = cleaned_data.get('assignee')
        
        if action == 'FORWARD' and not assignee:
            self.add_error('assignee', 'Please select a recipient for forwarding.')
            
        return cleaned_data
