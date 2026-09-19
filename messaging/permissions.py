from django.conf import settings

from administration.models import CustomUser


def user_in_conversation(user, conversation) -> bool:
    return conversation.involves_user(user)


def can_view_conversation(user, conversation) -> bool:
    return (
        user.is_authenticated
        and user.is_active
        and conversation.is_active
        and user_in_conversation(user, conversation)
    )


def can_message_user(sender, recipient) -> bool:
    """Any active user may start or continue a 1:1 chat with another active user."""
    if not sender.is_authenticated or not recipient.is_authenticated:
        return False
    if sender.id == recipient.id:
        return False
    if not sender.is_active or not recipient.is_active:
        return False
    return True


def get_messageable_users(for_user):
    """Users this person can start a new conversation with."""
    return (
        CustomUser.objects.filter(is_active=True)
        .exclude(pk=for_user.pk)
        .select_related('post')
        .order_by('post__priority', 'username')
    )


def is_user_online(user) -> bool:
    try:
        return user.presence.is_online
    except Exception:
        return False
