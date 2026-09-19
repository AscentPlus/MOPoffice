from django.db import models
from django.conf import settings
from administration.models import (
    Department, Post, DocumentType, DocumentOrigin, 
    DocumentPriority, DocumentStatus
)
from django.core.exceptions import ValidationError


class FileMaster(models.Model):
    """Main file record for tracking"""
    file_number = models.CharField(max_length=50, unique=True, editable=False)
    subject = models.CharField(max_length=500)
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name='files'
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name='files'
    )
    document_origin = models.ForeignKey(
        DocumentOrigin,
        on_delete=models.PROTECT,
        related_name='files'
    )
    document_priority = models.ForeignKey(
        DocumentPriority,
        on_delete=models.PROTECT,
        related_name='files'
    )
    current_holder = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name='current_files',
        help_text="Post currently holding this file"
    )
    current_status = models.ForeignKey(
        DocumentStatus,
        on_delete=models.PROTECT,
        related_name='files',
        null=True,
        blank=True
    )
    current_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='held_files',
        null=True,
        blank=True,
        help_text="Specific user holding this file (if applicable)"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_files'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='closed_files',
        null=True,
        blank=True
    )
    remarks = models.TextField(blank=True, null=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='approved_files_master',
        null=True,
        blank=True
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    processing_note = models.TextField(
        blank=True, 
        null=True,
        help_text="Current holder's internal processing status/note"
    )


    class Meta:
        db_table = 'file_master'
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        # Auto-generate file_number if not set
        if not self.file_number:
            from django.utils import timezone
            from administration.models import VoucherNumber
            from django.db import transaction
            
            now = timezone.now()
            current_year = now.year
            
            # Use atomic transaction to prevent race conditions during sequence increment
            with transaction.atomic():
                # Find the VoucherNumber record for the current calendar year
                vn = VoucherNumber.objects.select_for_update().filter(year=str(current_year)).first()
                
                if not vn:
                    # If no record exists for this year, create a new one starting from 0
                    vn = VoucherNumber.objects.create(
                        year=str(current_year),
                        last_no=0
                    )
                
                # Increment the sequence
                vn.last_no += 1
                vn.save()
                
                # Format: GB-FILE/00001/2026 (5-digit padding)
                self.file_number = f"GB-FILE/{vn.last_no:04d}/{current_year}"
            
        super().save(*args, **kwargs)


    def __str__(self):
        return f"{self.file_number} - {self.subject[:50]}"


class FileMovement(models.Model):
    """Transaction log for file movements"""
    file = models.ForeignKey(
        FileMaster,
        on_delete=models.CASCADE,
        related_name='movements'
    )
    from_post = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name='sent_files',
        null=True,
        blank=True,
        help_text="Sender post (null for initial creation)"
    )
    to_post = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name='received_files',
        help_text="Receiver post"
    )
    to_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='received_file_movements',
        null=True,
        blank=True,
        help_text="Specific receiver user (if applicable)"
    )
    action_required = models.BooleanField(
        default=True,
        help_text="True if action required, False for view-only"
    )
    is_return = models.BooleanField(
        default=False,
        help_text="True if this movement is a return action"
    )
    remarks = models.TextField(blank=True, null=True)
    moved_at = models.DateTimeField(auto_now_add=True)
    is_recalled = models.BooleanField(
        default=False,
        help_text="True if this forward was recalled by the sender"
    )
    moved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='file_movements'
    )

    class Meta:
        db_table = 'file_movement'
        ordering = ['moved_at']

    @property
    def is_currently_recallable(self):
        """Check if the movement can be recalled by the sender currently."""
        from django.utils import timezone
        from .models import FileAction # Need lazy import or we can just use the absolute path since we're in models.py
        
        if self.is_return or self.is_recalled:
            return False
            
        # Prevent self-movements (where from_post == to_post) from being recallable
        if self.from_post == self.to_post:
            return False
            
        time_diff = timezone.now() - self.moved_at
        if time_diff.total_seconds() > 24 * 3600:
            return False
            
        if self.file.current_holder != self.to_post:
            return False
            
        if self.to_user and self.file.current_user != self.to_user:
            return False
            
        # Needs to be imported inside or just use self.__class__.__module__... 
        # Actually FileAction is defined right after FileMovement in the same file!
        receiver_actions = FileAction.objects.filter(
            file=self.file,
            post=self.to_post,
            action_at__gte=self.moved_at
        ).exclude(action_type='RECALL')
        
        if receiver_actions.exists():
            return False
            
        return True

    def __str__(self):
        return f"{self.file.file_number} - {self.from_post} to {self.to_post}"


class FileAction(models.Model):
    """Actions taken on files"""
    ACTION_CHOICES = [
        ('APPROVE', 'Approve'),
        ('REJECT', 'Reject'),
        ('RETURN', 'Return for Clarification'),
        ('FORWARD', 'Forward'),
        ('CLOSE', 'Close File'),
        ('RECALL', 'Recall Forwarded File'),
        ('KEEP_IN_FILE', 'Keep in File'),
        ('EXTERNAL', 'Send to Government/External'),
        ('ACK_RETURN', 'Acknowledge Return'),
        ('PROCESSING_NOTE', 'Add Processing Note'),
    ]

    file = models.ForeignKey(
        FileMaster,
        on_delete=models.CASCADE,
        related_name='actions'
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name='file_actions',
        help_text="Post that took this action"
    )
    action_type = models.CharField(max_length=20, choices=ACTION_CHOICES)
    remarks = models.TextField(help_text="Required remarks for the action")
    action_at = models.DateTimeField(auto_now_add=True)
    action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='file_actions'
    )
    view_by_id = models.CharField(
        max_length=255, 
        null=True, 
        blank=True,
        help_text="Comma-separated IDs of posts assigned to view this file during this action"
    )


    class Meta:
        db_table = 'file_action'
        ordering = ['action_at']

    def __str__(self):
        return f"{self.file.file_number} - {self.action_type} by {self.post}"


class FileDocument(models.Model):
    """Uploaded supporting documents stored in the database"""
    file = models.ForeignKey(
        FileMaster,
        on_delete=models.CASCADE,
        related_name='documents'
    )
    # The actual file content stored as binary
    content = models.BinaryField(null=True)
    file_name = models.CharField(max_length=255, null=True)
    mimetype = models.CharField(max_length=100, null=True)
    
    # Optional link to the specific action that uploaded this document
    action = models.ForeignKey(
        'FileAction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='action_documents'
    )
    
    description = models.CharField(max_length=200, blank=True, null=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Even stored in DB, we might want to limit size to avoid DB bloat
        # 200KB limit as per existing logic
        if self.content and len(self.content) > 200 * 1024:
            raise ValidationError("File size must be under 200KB.")
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'file_document'
        ordering = ['uploaded_at']

    def __str__(self):
        return f"{self.file.file_number} - {self.file_name}"


class FileShare(models.Model):
    """Tracks files shared for viewing (CC)"""
    file = models.ForeignKey(
        FileMaster,
        on_delete=models.CASCADE,
        related_name='shares'
    )
    shared_with = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name='shared_files',
        help_text="Post that has view access"
    )
    shared_with_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='shared_files_user',
        null=True,
        blank=True,
        help_text="Specific user who has view access"
    )
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='shared_files_by'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_viewed = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'file_share'
        ordering = ['-created_at']
        unique_together = ['file', 'shared_with', 'shared_with_user']

    def __str__(self):
        user_part = f" ({self.shared_with_user.get_full_name() or self.shared_with_user.username})" if self.shared_with_user else ""
        return f"{self.file.file_number} shared with {self.shared_with}{user_part}"
