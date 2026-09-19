from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .models import UserLoginLog
from django.utils import timezone

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    """Record login event"""
    ip = get_client_ip(request)
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    session_key = request.session.session_key
    
    UserLoginLog.objects.create(
        user=user,
        ip_address=ip,
        user_agent=user_agent,
        session_key=session_key
    )

@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    """Update logout time in the last log entry for this session"""
    if user:
        session_key = request.session.session_key
        # Find the latest login log for this user and session that doesn't have a logout time
        log_entry = UserLoginLog.objects.filter(
            user=user, 
            session_key=session_key, 
            logout_time__isnull=True
        ).first()
        
        if log_entry:
            log_entry.logout_time = timezone.now()
            log_entry.save()
