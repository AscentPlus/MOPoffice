from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from .decorators import admin_required
from .models import (
    CustomUser, Post, Department, DocumentType, 
    DocumentOrigin, DocumentPriority, TransitType, DocumentStatus
)
from .forms import (
    UserCreationForm, UserEditForm, PostForm,
    DepartmentForm, DocumentTypeForm, DocumentOriginForm,
    DocumentPriorityForm, TransitTypeForm, DocumentStatusForm,
    AdminPasswordChangeForm
)


def has_dependencies(obj, category_slug=None):
    """
    Check if a master data item or post is being used in any files.
    """
    from filetracking.models import FileMaster
    
    if category_slug == 'departments':
        return FileMaster.objects.filter(department=obj).exists()
    elif category_slug == 'doc-types':
        return FileMaster.objects.filter(document_type=obj).exists()
    elif category_slug == 'doc-origins':
        return FileMaster.objects.filter(document_origin=obj).exists()
    elif category_slug == 'doc-priorities':
        return FileMaster.objects.filter(document_priority=obj).exists()
    elif category_slug == 'doc-statuses':
        return FileMaster.objects.filter(current_status=obj).exists()
    
    # For Post, check current holder and users
    if isinstance(obj, Post):
        if obj.users.filter(is_active=True).exists():
            return "active users"
        if FileMaster.objects.filter(current_holder=obj).exists():
            return "files currently held"
        from filetracking.models import FileMovement
        if FileMovement.objects.filter(Q(from_post=obj) | Q(to_post=obj)).exists():
            return "historical file movements"
            
    return False


@admin_required
def create_user(request):
    """Create a new user (Secretary only)"""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            # Save user with password from form
            user = form.save(commit=False, created_by=request.user)
            user.save()
            
            messages.success(request, f'User {user.username} (ID: {user.user_id}) created successfully!')
            return redirect('user_list')
    else:
        form = UserCreationForm()
    
    return render(request, 'administration/create_user.html', {'form': form})


@admin_required
def user_created_success(request):
    """Display newly created user credentials"""
    user_details = request.session.get('new_user_details')
    
    if not user_details:
        messages.error(request, 'No user details found.')
        return redirect('user_list')
    
    # Clear session data after displaying
    if 'clear' in request.GET:
        del request.session['new_user_details']
        return redirect('user_list')
    
    return render(request, 'administration/user_created_success.html', {
        'user_details': user_details
    })


@admin_required
def user_list(request):
    """List all users with search and filter"""
    users = CustomUser.objects.select_related('post').order_by('post__priority', 'username')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(user_id__icontains=search_query)
        )
    
    # Filter by post
    post_filter = request.GET.get('post', '')
    if post_filter:
        users = users.filter(post_id=post_filter)
    
    # Filter by active status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    
    # Get all posts for filter dropdown
    posts = Post.objects.filter(is_active=True).order_by('priority')
    
    context = {
        'users': users,
        'posts': posts,
        'search_query': search_query,
        'post_filter': post_filter,
        'status_filter': status_filter,
    }
    
    return render(request, 'administration/user_list.html', context)


@admin_required
def edit_user(request, user_id):
    """Edit user details"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        form = UserEditForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {user.username} updated successfully!')
            return redirect('user_list')
    else:
        form = UserEditForm(instance=user)
    
    return render(request, 'administration/edit_user.html', {
        'form': form,
        'user_obj': user
    })


@admin_required
def reset_user_password(request, user_id):
    """Reset a user's password by an administrator"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    if request.method == 'POST':
        form = AdminPasswordChangeForm(request.POST)
        if form.is_valid():
            user.set_password(form.cleaned_data['new_password'])
            user.save()
            messages.success(request, f'Password for user {user.username} has been reset successfully.')
            return redirect('user_list')
    else:
        form = AdminPasswordChangeForm()
    
    return render(request, 'administration/reset_password.html', {
        'form': form,
        'user_obj': user
    })


@admin_required
def toggle_user_status(request, user_id):
    """Activate or deactivate a user"""
    user = get_object_or_404(CustomUser, id=user_id)
    
    # Prevent deactivating self
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account!')
        return redirect('user_list')
    
    # Check if user is holding any files
    if user.is_active:  # Only check when deactivating
        from filetracking.models import FileMaster
        if FileMaster.objects.filter(current_user=user, is_closed=False).exists():
            messages.error(request, f'User {user.username} cannot be deactivated because they are currently holding active files.')
            return redirect('user_list')
    
    user.is_active = not user.is_active
    user.save()
    
    status = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.username} has been {status}.')
    
    return redirect('user_list')


# --- Post Management Views ---

@admin_required
def post_list(request):
    """List all official posts with decimal priorities"""
    posts = Post.objects.all().order_by('priority')
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        posts = posts.filter(name__icontains=search_query)
    
    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        posts = posts.filter(is_active=True)
    elif status_filter == 'inactive':
        posts = posts.filter(is_active=False)
            
    return render(request, 'administration/post_list.html', {
        'posts': posts,
        'search_query': search_query,
        'status_filter': status_filter
    })


@admin_required
def create_post(request):
    """Create a new official post (Superadmin only)"""
    if request.method == 'POST':
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save()
            messages.success(request, f'Post "{post.name}" created successfully!')
            return redirect('post_list')
    else:
        form = PostForm()
    
    return render(request, 'administration/post_form.html', {
        'form': form,
        'title': 'Create New Post'
    })


@admin_required
def edit_post(request, post_id):
    """Edit an existing official post"""
    post = get_object_or_404(Post, id=post_id)
    
    if request.method == 'POST':
        form = PostForm(request.POST, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, f'Post "{post.name}" updated successfully!')
            return redirect('post_list')
    else:
        form = PostForm(instance=post)
    
    return render(request, 'administration/post_form.html', {
        'form': form,
        'title': f'Edit Post: {post.name}',
        'post_obj': post
    })


@admin_required
def toggle_post_status(request, post_id):
    """Toggle post active/inactive status"""
    post = get_object_or_404(Post, id=post_id)
    
    if post.is_active:  # Only check when deactivating
        dep_reason = has_dependencies(post)
        if dep_reason:
            messages.error(request, f'Post "{post.name}" cannot be deactivated because it has {dep_reason}.')
            return redirect('post_list')
    
    post.is_active = not post.is_active
    post.save()
    
    status = 'activated' if post.is_active else 'deactivated'
    messages.success(request, f'Post "{post.name}" has been {status}.')
    return redirect('post_list')

# --- Master Data Management Views ---

MASTER_DATA_MODELS = {
    'departments': {
        'model': Department,
        'form': DepartmentForm,
        'title': 'Departments',
        'singular': 'Department'
    },
    'doc-types': {
        'model': DocumentType,
        'form': DocumentTypeForm,
        'title': 'Document Types',
        'singular': 'Document Type'
    },
    'doc-origins': {
        'model': DocumentOrigin,
        'form': DocumentOriginForm,
        'title': 'Document Origins',
        'singular': 'Document Origin'
    },
    # 'doc-priorities': {
    #     'model': DocumentPriority,
    #     'form': DocumentPriorityForm,
    #     'title': 'Document Priorities',
    #     'singular': 'Document Priority'
    # },
    # 'transit-types': {
        # 'model': TransitType,
        # 'form': TransitTypeForm,
        # 'title': 'Transit Types',
        # 'singular': 'Transit Type'
    # },
    # 'doc-statuses': {
        # 'model': DocumentStatus,
        # 'form': DocumentStatusForm,
        # 'title': 'Document Statuses',
        # 'singular': 'Document Status'
    # },
}

@admin_required
def master_data_index(request):
    """Dashboard for master data categories"""
    categories = []
    for slug, config in MASTER_DATA_MODELS.items():
        categories.append({
            'slug': slug,
            'title': config['title'],
            'count': config['model'].objects.count(),
            'active_count': config['model'].objects.filter(is_active=True).count()
        })
    
    return render(request, 'administration/master_data/index.html', {
        'categories': categories
    })

@admin_required
def master_data_list(request, category_slug):
    """Generic list view for master data"""
    config = MASTER_DATA_MODELS.get(category_slug)
    if not config:
        messages.error(request, "Invalid category.")
        return redirect('master_data_index')
    
    items = config['model'].objects.all()
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        items = items.filter(name__icontains=search_query)
    
    return render(request, 'administration/master_data/list.html', {
        'items': items,
        'config': config,
        'category_slug': category_slug,
        'search_query': search_query
    })

@admin_required
def master_data_create(request, category_slug):
    """Generic create view for master data"""
    config = MASTER_DATA_MODELS.get(category_slug)
    if not config:
        return redirect('master_data_index')
    
    if request.method == 'POST':
        form = config['form'](request.POST)
        if form.is_valid():
            item = form.save()
            messages.success(request, f'{config["singular"]} "{item.name}" created successfully!')
            return redirect('master_data_list', category_slug=category_slug)
    else:
        form = config['form']()
    
    return render(request, 'administration/master_data/form.html', {
        'form': form,
        'config': config,
        'category_slug': category_slug,
        'title': f'Create New {config["singular"]}'
    })

@admin_required
def master_data_edit(request, category_slug, item_id):
    """Generic edit view for master data"""
    config = MASTER_DATA_MODELS.get(category_slug)
    if not config:
        return redirect('master_data_index')
    
    item = get_object_or_404(config['model'], id=item_id)
    
    if request.method == 'POST':
        form = config['form'](request.POST, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f'{config["singular"]} "{item.name}" updated successfully!')
            return redirect('master_data_list', category_slug=category_slug)
    else:
        form = config['form'](instance=item)
    
    return render(request, 'administration/master_data/form.html', {
        'form': form,
        'config': config,
        'category_slug': category_slug,
        'item_id': item_id,
        'title': f'Edit {config["singular"]}'
    })

@admin_required
def master_data_toggle(request, category_slug, item_id):
    """Generic toggle active status view with dependency checks"""
    config = MASTER_DATA_MODELS.get(category_slug)
    if not config:
        return redirect('master_data_index')
    
    item = get_object_or_404(config['model'], id=item_id)
    
    if item.is_active:  # Only check when deactivating
        if has_dependencies(item, category_slug):
            messages.error(request, f'{config["singular"]} "{item.name}" cannot be deactivated because it is currently used in one or more files.')
            return redirect('master_data_list', category_slug=category_slug)
            
    item.is_active = not item.is_active
    item.save()
    
    status = 'activated' if item.is_active else 'deactivated'
    messages.success(request, f'{config["singular"]} "{item.name}" has been {status}.')
    return redirect('master_data_list', category_slug=category_slug)
