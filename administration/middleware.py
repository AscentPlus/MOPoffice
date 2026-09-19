from django.utils.deprecation import MiddlewareMixin


class PostPermissionMiddleware(MiddlewareMixin):
    """
    Middleware to inject post-based permissions into request context
    Makes post information easily accessible in templates and views
    """
    
    def process_request(self, request):
        if request.user.is_authenticated and hasattr(request.user, 'post'):
            # Convert decimal priority to float for JSON serializability
            try:
                priority_val = float(request.user.post.priority)
            except (TypeError, ValueError, AttributeError):
                priority_val = 99.0  # Default low priority
                
            # Add post information to request object
            request.post_name = request.user.post.name
            request.post_priority = priority_val
            request.is_admin = priority_val == 1.0
            
            # Store in session (Decimal must be converted to float/string for JSON)
            request.session['post_name'] = request.user.post.name
            request.session['post_priority'] = priority_val
        else:
            request.post_name = None
            request.post_priority = None
            request.is_admin = False

class NoCacheMiddleware(MiddlewareMixin):
    """
    Middleware to disable browser caching for all responses.
    This ensures that when a user logs out and presses the back button,
    they are forced to re-authenticate instead of seeing cached data.
    """
    def process_response(self, request, response):
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response