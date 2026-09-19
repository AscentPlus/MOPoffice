from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class Department(models.Model):
    """Organization departments"""
    name = models.CharField(max_length=200, unique=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'department'
        ordering = ['name']

    def __str__(self):
        return self.name


class Post(models.Model):
    """Official posts with hierarchy based on priority"""
    name = models.CharField(max_length=200, unique=True)
    priority = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Lower number = higher authority (e.g., 1.00 for Secretary, 4.01 for Admin Manager)"
    )
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'post'
        ordering = ['priority']

    def __str__(self):
        return self.name

    @property
    def has_multiple_users(self):
        """Returns True if this post has more than one staff assigned"""
        return self.users.filter(is_active=True).count() > 1


class DocumentType(models.Model):
    """Types of documents (letter, memo, circular, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_type'
        ordering = ['name']

    def __str__(self):
        return self.name


class DocumentOrigin(models.Model):
    """Origin of documents (internal, external, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_origin'
        ordering = ['name']

    def __str__(self):
        return self.name


class DocumentPriority(models.Model):
    """Priority levels (Urgent, High, Normal, Low)"""
    name = models.CharField(max_length=100, unique=True)
    level = models.IntegerField(default=10, help_text="Priority level (lower = more urgent)")
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_priority'
        ordering = ['level', 'name']
        verbose_name_plural = 'Document Priorities'

    def __str__(self):
        return self.name


class TransitType(models.Model):
    """How documents move (physical, electronic)"""
    name = models.CharField(max_length=100, unique=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'transit_type'
        ordering = ['name']

    def __str__(self):
        return self.name


class DocumentStatus(models.Model):
    """Status descriptions (pending, approved, rejected, etc.)"""
    name = models.CharField(max_length=100, unique=True)
    remarks = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'document_status'
        ordering = ['name']
        verbose_name_plural = 'Document Statuses'

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    """Custom user model with post-based hierarchy"""
    user_id = models.CharField(max_length=50, unique=True, editable=False)
    post = models.ForeignKey(
        Post,
        on_delete=models.PROTECT,
        related_name='users',
        help_text="Official post assigned to this user"
    )
    mobile = models.CharField(max_length=15, blank=True, null=True)
    created_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_users'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'custom_user'
        ordering = ['post__priority', 'username']

    def save(self, *args, **kwargs):
        # Auto-generate user_id if not set
        if not self.user_id:
            # Get first two letters of username
            prefix = self.username[:2].upper()
            # Get the last user's ID to generate transaction number
            last_user = CustomUser.objects.order_by('-id').first()
            if last_user:
                trans_num = last_user.id + 1
            else:
                trans_num = 1
            self.user_id = f"{prefix}{trans_num:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.post.name})"


class UserLoginLog(models.Model):
    """Log of user login and logout events"""
    user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE,
        related_name='login_logs'
    )
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)

    class Meta:
        db_table = 'user_login_log'
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.username} - {self.login_time}"


class VoucherNumber(models.Model):
    """Tracks sequence numbers for different calendar years"""
    year = models.CharField(max_length=4, help_text="e.g., 2026")
    last_no = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'voucher_number'
        verbose_name = 'Voucher Number'
        verbose_name_plural = 'Voucher Numbers'

    def __str__(self):
        return f"Year {self.year} (Last No: {self.last_no})"


