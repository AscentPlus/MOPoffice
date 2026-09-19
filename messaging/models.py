from django.conf import settings
from django.db import models
from django.utils import timezone


def message_attachment_path(instance, filename):
    return f'messaging/{instance.message.conversation_id}/{filename}'


class Conversation(models.Model):
    """One-to-one chat between two users."""
    participant_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_a',
    )
    participant_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_b',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='conversations_started',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'messaging_conversation'
        ordering = ['-updated_at']
        constraints = [
            models.UniqueConstraint(
                fields=['participant_a', 'participant_b'],
                name='unique_conversation_pair',
            ),
        ]
        indexes = [
            models.Index(fields=['-updated_at']),
            models.Index(fields=['participant_a']),
            models.Index(fields=['participant_b']),
        ]

    def __str__(self):
        return f'Chat {self.participant_a_id} ↔ {self.participant_b_id}'

    def other_participant(self, user):
        if user.id == self.participant_a_id:
            return self.participant_b
        return self.participant_a

    def involves_user(self, user):
        return user.id in (self.participant_a_id, self.participant_b_id)


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='sent_messages',
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)

    class Meta:
        db_table = 'messaging_message'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['conversation', 'created_at']),
        ]

    def __str__(self):
        return f'Message {self.id} in conversation {self.conversation_id}'


class ConversationParticipantState(models.Model):
    """Tracks read position per user per conversation."""
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='participant_states',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversation_states',
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_read_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
    )

    class Meta:
        db_table = 'messaging_participant_state'
        constraints = [
            models.UniqueConstraint(
                fields=['conversation', 'user'],
                name='unique_participant_state',
            ),
        ]

    def __str__(self):
        return f'{self.user_id} read state for conv {self.conversation_id}'


class MessageAttachment(models.Model):
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments',
    )
    file = models.FileField(upload_to=message_attachment_path)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'messaging_attachment'

    def __str__(self):
        return self.original_name


class UserPresence(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='presence',
    )
    last_seen_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'messaging_user_presence'

    @property
    def is_online(self):
        if not self.last_seen_at:
            return False
        return (timezone.now() - self.last_seen_at).total_seconds() < 120
