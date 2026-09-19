from django.conf import settings


def messaging_unread(request):
    ctx = {
        'messaging_unread_count': 0,
        'MESSAGING_POLL_INTERVAL_MS': getattr(settings, 'MESSAGING_POLL_INTERVAL_MS', 4000),
    }
    if not request.user.is_authenticated:
        return ctx
    try:
        from .services import get_total_unread_count
        ctx['messaging_unread_count'] = get_total_unread_count(request.user)
    except Exception:
        pass
    return ctx
