from django.conf import settings
from django.db import transaction
from django.db.models import Q, OuterRef, Subquery
from django.utils import timezone

from administration.models import CustomUser

from .models import (
    Conversation,
    ConversationParticipantState,
    Message,
    MessageAttachment,
    UserPresence,
)
from .permissions import can_message_user


def normalize_participants(user_a, user_b):
    if user_a.id < user_b.id:
        return user_a, user_b
    return user_b, user_a


def touch_presence(user):
    UserPresence.objects.update_or_create(
        user=user,
        defaults={'last_seen_at': timezone.now()},
    )


def get_or_create_conversation(user_a, user_b, created_by=None):
    if not can_message_user(user_a, user_b):
        raise PermissionError('Cannot create conversation between these users.')
    pa, pb = normalize_participants(user_a, user_b)
    creator = created_by or user_a
    conversation, created = Conversation.objects.get_or_create(
        participant_a=pa,
        participant_b=pb,
        defaults={'created_by': creator},
    )
    if created:
        for participant in (pa, pb):
            ConversationParticipantState.objects.get_or_create(
                conversation=conversation,
                user=participant,
            )
    return conversation, created


def get_user_conversations(user):
    """Conversations for inbox with last message preview and unread count."""
    last_msg = Message.objects.filter(
        conversation=OuterRef('pk'),
        is_deleted=False,
    ).order_by('-created_at')

    conversations = (
        Conversation.objects.filter(
            is_active=True,
        )
        .filter(Q(participant_a=user) | Q(participant_b=user))
        .select_related('participant_a', 'participant_b', 'participant_a__post', 'participant_b__post')
        .annotate(
            last_message_id=Subquery(last_msg.values('id')[:1]),
            last_message_body=Subquery(last_msg.values('body')[:1]),
            last_message_at=Subquery(last_msg.values('created_at')[:1]),
            last_message_sender_id=Subquery(last_msg.values('sender_id')[:1]),
        )
        .order_by('-updated_at')
    )

    states = {
        s.conversation_id: s
        for s in ConversationParticipantState.objects.filter(user=user).select_related('last_read_message')
    }

    result = []
    for conv in conversations:
        other = conv.other_participant(user)
        state = states.get(conv.id)
        unread = _count_unread(conv, user, state)
        result.append({
            'conversation': conv,
            'other_user': other,
            'last_message_body': conv.last_message_body or '',
            'last_message_at': conv.last_message_at,
            'last_message_sender_id': conv.last_message_sender_id,
            'unread_count': unread,
            'is_online': _other_user_online(other),
        })
    return result


def _other_user_online(user):
    try:
        return user.presence.is_online
    except UserPresence.DoesNotExist:
        return False


def _count_unread(conversation, user, state):
    qs = Message.objects.filter(
        conversation=conversation,
        is_deleted=False,
    ).exclude(sender=user)
    if state and state.last_read_message_id:
        qs = qs.filter(created_at__gt=state.last_read_message.created_at)
    elif state and state.last_read_at:
        qs = qs.filter(created_at__gt=state.last_read_at)
    return qs.count()


def get_total_unread_count(user):
    total = 0
    for item in get_user_conversations(user):
        total += item['unread_count']
    return total


def get_messages(conversation, user, since_id=None, limit=50):
    qs = (
        Message.objects.filter(conversation=conversation, is_deleted=False)
        .select_related('sender', 'sender__post')
        .prefetch_related('attachments')
        .order_by('created_at')
    )
    if since_id:
        qs = qs.filter(id__gt=since_id)
    else:
        qs = qs.order_by('-created_at')[:limit]
        qs = Message.objects.filter(
            id__in=qs.values_list('id', flat=True)
        ).select_related('sender', 'sender__post').prefetch_related('attachments').order_by('created_at')
    return list(qs)


@transaction.atomic
def send_message(conversation, sender, body, attachment_file=None):
    body = (body or '').strip()
    if not body and not attachment_file:
        raise ValueError('Message body or attachment is required.')

    message = Message.objects.create(
        conversation=conversation,
        sender=sender,
        body=body or '(attachment)',
    )

    if attachment_file:
        max_bytes = getattr(settings, 'MESSAGING_ATTACHMENT_MAX_BYTES', 2 * 1024 * 1024)
        if attachment_file.size > max_bytes:
            raise ValueError(f'Attachment exceeds maximum size of {max_bytes // (1024 * 1024)} MB.')
        MessageAttachment.objects.create(
            message=message,
            file=attachment_file,
            original_name=attachment_file.name,
            size=attachment_file.size,
            content_type=getattr(attachment_file, 'content_type', '') or '',
        )

    Conversation.objects.filter(pk=conversation.pk).update(updated_at=timezone.now())

    other = conversation.other_participant(sender)
    ConversationParticipantState.objects.get_or_create(
        conversation=conversation,
        user=other,
    )

    return message


def mark_conversation_read(conversation, user):
    last_message = (
        Message.objects.filter(conversation=conversation, is_deleted=False)
        .order_by('-created_at')
        .first()
    )
    state, _ = ConversationParticipantState.objects.get_or_create(
        conversation=conversation,
        user=user,
    )
    state.last_read_at = timezone.now()
    state.last_read_message = last_message
    state.save(update_fields=['last_read_at', 'last_read_message'])


def serialize_message(message, request=None):
    attachments = []
    for att in message.attachments.all():
        attachments.append({
            'id': att.id,
            'name': att.original_name,
            'size': att.size,
            'url': att.file.url if att.file else '',
            'download_url': f'/messages/attachments/{att.id}/download/',
        })
    return {
        'id': message.id,
        'body': message.body,
        'sender_id': message.sender_id,
        'sender_name': message.sender.get_full_name() or message.sender.username,
        'sender_username': message.sender.username,
        'sender_post': message.sender.post.name if message.sender.post_id else '',
        'created_at': message.created_at.isoformat(),
        'attachments': attachments,
        'is_mine': bool(request and message.sender_id == request.user.id),
    }


def serialize_conversation_item(item, current_user, request=None):
    conv = item['conversation']
    other = item['other_user']
    return {
        'id': conv.id,
        'other_user': {
            'id': other.id,
            'name': other.get_full_name() or other.username,
            'username': other.username,
            'post': other.post.name if other.post_id else '',
            'is_online': item['is_online'],
        },
        'last_message': {
            'body': (item['last_message_body'] or '')[:80],
            'at': item['last_message_at'].isoformat() if item['last_message_at'] else None,
            'is_mine': item['last_message_sender_id'] == current_user.id,
        },
        'unread_count': item['unread_count'],
        'updated_at': conv.updated_at.isoformat(),
    }
