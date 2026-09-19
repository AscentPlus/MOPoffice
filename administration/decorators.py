from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    """Decorator to restrict access to Secretary (priority 1) only"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        
        if request.user.post.priority != 1:
            messages.error(request, 'Access denied. This function is restricted to administrators only.')
            return redirect('dashboard')
        
        return view_func(request, *args, **kwargs)
    return wrapper


def post_permission_required(max_priority):
    """
    Decorator to restrict access based on post priority
    max_priority: Maximum priority level allowed (lower number = higher authority)
    Example: @post_permission_required(3) allows priority 1, 2, 3
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if request.user.post.priority > max_priority:
                messages.error(request, 'Access denied. Insufficient permissions.')
                return redirect('dashboard')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
