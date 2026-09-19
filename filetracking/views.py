from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from .models import FileMaster, FileMovement, FileAction, FileShare, FileDocument
from datetime import timedelta


def login_view(request):
    """Login page for MOP system"""
    if request.user.is_authenticated:
        return redirect('dashboard')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            if user.is_active:
                login(request, user)
                # Store user post information in session
                # (Decimal must be converted to float/string for JSON serializability)
                request.session['post_name'] = user.post.name
                try:
                    request.session['post_priority'] = float(user.post.priority)
                except (TypeError, ValueError, AttributeError):
                    request.session['post_priority'] = 99.0
                messages.success(request, f'Welcome, {user.get_full_name() or user.username}!')
                return redirect('dashboard')
            else:
                messages.error(request, 'Your account has been deactivated. Please contact the administrator.')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'auth/login.html')


@login_required
def logout_view(request):
    """Logout user and clear session"""
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def change_password(request):
    """Allow users to change their password"""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm
    
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Updating the password logs out all other sessions; we must
            # update the session auth hash to keep the current user logged in.
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'auth/change_password.html', {'form': form})


@login_required
def dashboard_view(request):
    """Dashboard showing file statistics"""
    from filetracking.models import FileMaster, FileMovement
    
    user_post = request.user.post
    
    from django.db.models import Q
    from filetracking.models import FileShare
    
    # Get IDs of ALL shared files (to show in recent)
    all_shared_file_ids = FileShare.objects.filter(
        shared_with_user=request.user,
        is_active=True
    ).values_list('file_id', flat=True)
    
    # Get IDs of UNVIEWED shared files (for the stats count)
    unviewed_shared_file_ids = FileShare.objects.filter(
        shared_with_user=request.user,
        is_active=True,
        is_viewed=False
    ).values_list('file_id', flat=True)

    # 1. Assigned to this post (Action Required)
    # File must be currently held by this post AND (assigned to nobody specifically OR assigned to me)
    assigned_count = FileMaster.objects.filter(
        current_holder=user_post,
        is_closed=False
    ).exclude(
        current_status__name='Keep in File'
    ).exclude(
        current_status__name='Processing'
    ).filter(
        Q(current_user__isnull=True) | Q(current_user=request.user)
    ).count()

    # 2. Shared with this post (Files to View - ALL for the pending count, but UNVIEWED for the specific stat)
    # File must be shared with this user AND NOT currently held by their post for ACTION
    all_shared_qs = FileMaster.objects.filter(
        id__in=all_shared_file_ids,
        is_closed=False
    ).exclude(
        current_status__name='Keep in File'
    ).exclude(
        current_status__name='Processing'
    ).exclude(
        Q(current_holder=user_post) & (Q(current_user__isnull=True) | Q(current_user=request.user))
    )
    
    # Total shared (all shared files to match Inbox "ALL" tab)
    total_shared_count = all_shared_qs.distinct().count()
    
    # Unviewed shared (specifically for the "Files to View" card as requested)
    shared_count = all_shared_qs.filter(id__in=unviewed_shared_file_ids).distinct().count()

    # Get file statistics
    pending_total_count = assigned_count + shared_count
    
    sent_count = FileMovement.objects.filter(
        moved_by=request.user
    ).values('file').distinct().count()

    approved_count = FileMaster.objects.filter(
        actions__action_type='APPROVE',
        actions__action_by=request.user
    ).distinct().count()

    created_count = FileMaster.objects.filter(
        created_by=request.user
    ).count()
    
    # Get recent files in inbox (matching logic for both assigned and UNVIEWED shared)
    recent_files = FileMaster.objects.filter(
        Q(current_holder=user_post) | Q(id__in=unviewed_shared_file_ids)
    ).filter(
        is_closed=False
    ).exclude(
        current_status__name='Keep in File'
    ).exclude(
        current_status__name='Processing'
    ).filter(
        Q(current_user__isnull=True) | Q(current_user=request.user)
    ).exclude(
        # Exclude files that are only shared and already viewed
        Q(id__in=all_shared_file_ids) & ~Q(id__in=unviewed_shared_file_ids) & 
        ~Q(current_holder=user_post)
    ).order_by('-created_at')[:5]

    
    # Admin-only statistics: All users pending counts
    user_stats = None
    is_admin = False
    if hasattr(request.user, 'post') and request.user.post and float(request.user.post.priority) <= 1.5:
        is_admin = True
        from administration.models import CustomUser
        from django.db.models import Count
        
        pending_filter = Q(held_files__is_closed=False) & ~Q(held_files__current_status__name='Keep in File') & ~Q(held_files__current_status__name='Processing')

        # Get users and their specifically assigned (held) files, broken down by priority
        user_stats = CustomUser.objects.filter(is_active=True).annotate(
            holding_files_count=Count('held_files', filter=pending_filter),
            very_urgent_holding=Count(
                'held_files',
                filter=pending_filter & Q(held_files__document_priority__name='Very Urgent'),
            ),
            urgent_holding=Count(
                'held_files',
                filter=pending_filter & Q(held_files__document_priority__name='Urgent'),
            ),
            normal_holding=Count(
                'held_files',
                filter=pending_filter & Q(held_files__document_priority__name='Normal'),
            ),
        ).select_related('post').order_by('post__priority', 'username')

        # Unassigned open files at each post (total and by priority)
        post_unassigned_qs = FileMaster.objects.filter(
            current_user__isnull=True,
            is_closed=False,
        ).exclude(
            current_status__name='Keep in File'
        ).exclude(
            current_status__name='Processing'
        )
        post_unassigned = post_unassigned_qs.values('current_holder').annotate(count=Count('id'))
        unassigned_map = {item['current_holder']: item['count'] for item in post_unassigned}

        post_unassigned_by_priority = post_unassigned_qs.values(
            'current_holder', 'document_priority__name',
        ).annotate(count=Count('id'))
        unassigned_priority_map = {}
        for item in post_unassigned_by_priority:
            post_id = item['current_holder']
            if post_id not in unassigned_priority_map:
                unassigned_priority_map[post_id] = {}
            unassigned_priority_map[post_id][item['document_priority__name']] = item['count']

        for u in user_stats:
            unassigned_for_post = unassigned_map.get(u.post.id, 0)
            unassigned_priorities = unassigned_priority_map.get(u.post.id, {})
            u.pending_files_count = u.holding_files_count + unassigned_for_post
            u.very_urgent_count = u.very_urgent_holding + unassigned_priorities.get('Very Urgent', 0)
            u.urgent_count = u.urgent_holding + unassigned_priorities.get('Urgent', 0)
            u.normal_count = u.normal_holding + unassigned_priorities.get('Normal', 0)

    context = {
        'assigned_count': assigned_count,
        'shared_count': shared_count,
        'pending_total_count': pending_total_count,
        'sent_count': sent_count,
        'approved_count': approved_count,
        'created_count': created_count,
        'recent_files': recent_files,
        'user_stats': user_stats,
        'is_admin': is_admin,
    }
    
    
    return render(request, 'dashboard.html', context)


@login_required
def create_file(request):
    """Create a new file"""
    from .forms import FileCreateForm
    from .models import FileDocument, DocumentStatus
    
    if request.method == 'POST':
        form = FileCreateForm(request.POST, request.FILES)
        if form.is_valid():
            file_obj = form.save(commit=False)
            file_obj.created_by = request.user
            file_obj.current_holder = request.user.post
            file_obj.current_user = request.user
            
            # Set initial status
            status = DocumentStatus.objects.filter(name='Pending').first()
            if not status:
                status = DocumentStatus.objects.filter(is_active=True).first()
            file_obj.current_status = status
            file_obj.save()
            
            # Handle attachments
            attachments = request.FILES.getlist('attachment')
            for attachment in attachments:
                FileDocument.objects.create(
                    file=file_obj,
                    content=attachment.read(),
                    file_name=attachment.name,
                    mimetype=attachment.content_type,
                    uploaded_by=request.user,
                    description='Initial attachment'
                )

            
            messages.success(request, f'File {file_obj.file_number} created successfully!')
            
            # If user clicked "Save & Forward", redirect to detail with forward flag
            if request.POST.get('action') == 'forward':
                return redirect(reverse('file_detail', args=[file_obj.id]) + '?action=forward')
            
            # If user clicked "Send to Secretary"
            if request.POST.get('action') == 'send_to_secretary':
                from administration.models import Post
                from .models import FileMovement
                
                # Secretary is priority 1
                secretary_post = Post.objects.filter(priority=1.0, is_active=True).first()
                if secretary_post:
                    # Find unique active user if any
                    post_users = secretary_post.users.filter(is_active=True)
                    to_user = post_users.first() if post_users.count() == 1 else None
                    
                    # Create movement
                    FileMovement.objects.create(
                        file=file_obj,
                        from_post=request.user.post,
                        to_post=secretary_post,
                        to_user=to_user,
                        remarks=file_obj.remarks, # Carry over initial remarks
                        moved_by=request.user,
                        action_required=True,
                        is_return=False
                    )
                    
                    # Update file holder and user
                    file_obj.current_holder = secretary_post
                    file_obj.current_user = to_user
                    file_obj.save()
                    
                    messages.success(request, f'File {file_obj.file_number} created and sent to {secretary_post.name} successfully!')
                    return redirect('dashboard')
                else:
                    messages.warning(request, f'File {file_obj.file_number} created, but Secretary post was not found to forward.')
            
            return redirect('dashboard')
    else:
        form = FileCreateForm()
    
    return render(request, 'filetracking/create_file.html', {'form': form})


@login_required
def inbox_view(request):
    """View files currently held by user's post"""
    from .models import FileMaster
    from django.core.paginator import Paginator
    from django.db.models import Q, Case, When, Value, BooleanField
    
    # Get files where user's post is the current holder OR has a shared copy
    from django.db.models import Q, Case, When, Value, BooleanField, Exists, OuterRef
    from .models import FileShare
    
    user_post = request.user.post
    status = request.GET.get('status', 'all')
    substatus = request.GET.get('substatus', 'unviewed') # Default to unviewed for 'view' status
    
    # Get IDs of files shared with this user
    shared_file_ids = FileShare.objects.filter(
        shared_with_user=request.user,
        is_active=True
    ).values_list('file_id', flat=True)

    # Filter logic:
    # 1. File is valid (not closed)
    # 2. (User's post holds it AND (assigned to NO ONE OR assigned to THIS user))
    #    OR (it is shared with user's post)
    
    base_qs = FileMaster.objects.filter(
        is_closed=False
    ).exclude(
        current_status__name='Keep in File'
    ).exclude(
        current_status__name='Processing'
    ).filter(
        Q(current_holder=user_post, current_user__isnull=True) | 
        Q(current_holder=user_post, current_user=request.user) |
        Q(id__in=shared_file_ids)
    ).annotate(
        is_for_action=Case(
            When(
                Q(current_holder=user_post) & (Q(current_user__isnull=True) | Q(current_user=request.user)),
                then=Value(True)
            ),
            default=Value(False),
            output_field=BooleanField(),
        ),
        # Annotation to check if the file has been viewed by the current user (if shared)
        is_viewed_shared=Exists(
            FileShare.objects.filter(
                file=OuterRef('pk'),
                shared_with_user=request.user,
                is_active=True,
                is_viewed=True
            )
        )
    )

    # Calculate counts for tabs
    action_count = base_qs.filter(is_for_action=True).count()
    unviewed_view_count = base_qs.filter(is_for_action=False, is_viewed_shared=False).count()
    total_count = action_count + unviewed_view_count
    view_count = base_qs.filter(is_for_action=False).count()
    
    # Sub-counts for VIEW ONLY
    viewed_view_count = base_qs.filter(is_for_action=False, is_viewed_shared=True).count()

    # Apply status filter
    if status == 'action':
        files = base_qs.filter(is_for_action=True)
    elif status == 'view':
        # Default sub-filter is unviewed
        if substatus == 'viewed':
            files = base_qs.filter(is_for_action=False, is_viewed_shared=True)
        else:
            files = base_qs.filter(is_for_action=False, is_viewed_shared=False)
            substatus = 'unviewed'
    else:
        # 'all' shows everything that is actionable OR unviewed shared
        files = base_qs.filter(Q(is_for_action=True) | Q(is_viewed_shared=False))

    files = files.distinct().select_related(
        'department', 'document_type', 'document_priority', 
        'current_status', 'created_by', 'current_holder', 'current_user'
    ).order_by('document_priority__level', '-created_at')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        files = files.filter(
            Q(file_number__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(files, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'filetracking/inbox.html', {
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1) if page_number else paginator.get_elided_page_range(1, on_each_side=1, on_ends=1),
        'search_query': search_query,
        'status': status,
        'substatus': substatus,
        'total_count': total_count,
        'action_count': action_count,
        'view_count': view_count,
        'unviewed_view_count': unviewed_view_count,
        'viewed_view_count': viewed_view_count,
    })




@login_required
def mark_as_read(request, file_id):
    """Mark a shared file as read/viewed"""
    from django.utils import timezone
    
    share = FileShare.objects.filter(
        file_id=file_id,
        shared_with_user=request.user,
        is_active=True
    ).first()
    
    if share:
        share.is_viewed = True
        share.viewed_at = timezone.now()
        share.save()
        messages.success(request, f"File {share.file.file_number} marked as read.")
    else:
        messages.error(request, "You do not have view access to this file or it was not shared with you.")
    
    return redirect(reverse('inbox') + '?status=view')


@login_required
def sent_files_view(request):
    """View files sent by user's post"""
    from .models import FileMovement
    from django.core.paginator import Paginator
    from django.db.models import Q
    
    user_post = request.user.post
    
    # Get the latest movement ID for each file sent by this SPECIFIC user to avoid duplicates
    from django.db.models import Max
    latest_movement_ids = FileMovement.objects.filter(
        moved_by=request.user
    ).values('file_id').annotate(
        latest_id=Max('id')
    ).values_list('latest_id', flat=True)
    
    sent_movements = FileMovement.objects.filter(
        id__in=latest_movement_ids
    ).select_related(
        'file', 'to_post', 'to_user', 'file__current_status', 'file__current_holder', 'file__document_priority'
    ).order_by('-moved_at')
    
    # Search
    search_query = request.GET.get('search', '')
    if search_query:
        sent_movements = sent_movements.filter(
            Q(file__file_number__icontains=search_query) |
            Q(file__subject__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(sent_movements, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'filetracking/sent_files.html', {
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1) if page_number else paginator.get_elided_page_range(1, on_each_side=1, on_ends=1),
        'search_query': search_query
    })


@login_required
def file_detail(request, file_id):
    """View complete file details and history"""
    from django.shortcuts import get_object_or_404
    from .models import FileMaster, FileMovement, FileAction, FileDocument, DocumentStatus
    from .forms import FileActionForm
    from administration.models import Post, CustomUser
    
    # Get file object (select related fields needed for template rendering)
    file_obj = get_object_or_404(
        FileMaster.objects.select_related(
            'approved_by__post', 'closed_by__post',
            'current_holder', 'current_user__post',
            'created_by__post', 'current_status',
            'department', 'document_type', 'document_origin', 'document_priority',
        ),
        pk=file_id
    )

    # ── Access Control ──────────────────────────────────────────────────────
    # Priority-1 (Secretary/superuser) can access any file.
    # All other users must have a LEGITIMATE, non-recalled connection.
    user_post = request.user.post
    if float(user_post.priority) > 1.5:
        from django.db.models import Q as _Q

        # Non-recalled movements that brought this file TO the user's post/user
        legitimate_receive = FileMovement.objects.filter(
            file=file_obj,
            to_post=user_post,
            is_recalled=False
        ).filter(
            _Q(to_user=request.user) | _Q(to_user__isnull=True)
        ).exists()

        # Sent or forwarded by this user (the sender is always involved)
        sent_or_forwarded = FileMovement.objects.filter(
            file=file_obj,
            moved_by=request.user
        ).exists()

        # Created by this user
        created_by_user = (file_obj.created_by == request.user)

        # Currently held by this user's post/user
        holds_file = (
            file_obj.current_holder == user_post and
            (file_obj.current_user is None or file_obj.current_user == request.user)
        )

        # Explicitly shared (CC/view-only)
        file_shared = FileShare.objects.filter(
            file=file_obj, shared_with_user=request.user, is_active=True
        ).exists()

        if not (legitimate_receive or sent_or_forwarded or created_by_user
                or holds_file or file_shared):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied(
                "You do not have access to this file."
            )
    # ────────────────────────────────────────────────────────────────────────

    
    # Check if user is the current holder
    # Logic: Post must match AND (current_user is None OR current_user is me)
    is_holder_post = (file_obj.current_holder == request.user.post)
    is_holder_user = (file_obj.current_user is None or file_obj.current_user == request.user)
    
    is_current_holder = (is_holder_post and is_holder_user and not file_obj.is_closed)
    
    # Restrict CC setting to Creator or Superuser (Priority 1)
    can_set_cc = (file_obj.created_by == request.user or request.user.post.priority <= 1.5)

    if request.method == 'POST' and is_current_holder:
        file_status_name = file_obj.current_status.name if file_obj.current_status else None
        form = FileActionForm(request.POST, request.FILES, user=request.user, can_set_cc=can_set_cc, file_status=file_status_name)
        if form.is_valid():
            action_type = form.cleaned_data['action_type']
            remarks = form.cleaned_data['remarks']
            assignee = form.cleaned_data.get('assignee') # post_X or user_Y
            
            # Capture CC users if any
            cc_users = form.cleaned_data.get('cc_users')
            view_by_id = None
            if cc_users:
                # Store user IDs (format: u1,u2...)
                view_by_id = ",".join([u.split('_')[1] for u in cc_users])

            action_obj = FileAction.objects.create(
                file=file_obj,
                post=request.user.post,
                action_type=action_type,
                remarks=remarks,
                action_by=request.user,
                view_by_id=view_by_id
            )

            # Handle Documents Upload by Action Taker
            action_attachments = request.FILES.getlist('action_attachment')
            for action_attachment in action_attachments:
                FileDocument.objects.create(
                    file=file_obj,
                    content=action_attachment.read(),
                    file_name=action_attachment.name,
                    mimetype=action_attachment.content_type,
                    uploaded_by=request.user,
                    action=action_obj,
                    description=form.cleaned_data.get('action_attachment_description') or f"Attachment during {action_type}"
                )
            
            if action_type == 'FORWARD':
                to_post = None
                to_user = None
                
                if assignee:
                    if assignee.startswith('post_'):
                        post_id = int(assignee.split('_')[1])
                        to_post = Post.objects.get(id=post_id)
                        # If the post has exactly one user, assign that user as current_user
                        active_users = to_post.users.filter(is_active=True)
                        if active_users.count() == 1:
                            to_user = active_users.first()
                    elif assignee.startswith('user_'):
                        user_id = int(assignee.split('_')[1])
                        to_user = CustomUser.objects.get(id=user_id)
                        to_post = to_user.post
                
                # Log File Movement
                FileMovement.objects.create(
                    file=file_obj,
                    from_post=request.user.post,
                    to_post=to_post,
                    to_user=to_user,
                    remarks=remarks,
                    moved_by=request.user,
                    action_required=True,
                    is_return=False
                )

                
                # Handle CC (View Only)
                if cc_users:
                    from administration.models import CustomUser
                    for cc_user_str in cc_users:
                        cc_user_id = int(cc_user_str.split('_')[1])
                        cc_user = CustomUser.objects.get(id=cc_user_id)
                        FileShare.objects.get_or_create(
                            file=file_obj,
                            shared_with=cc_user.post,
                            shared_with_user=cc_user,
                            defaults={'shared_by': request.user}
                        )
                
                # Update file status and holder
                # Persistent Status Logic: Only change to Pending if it wasn't already Approved
                if file_obj.current_status and file_obj.current_status.name != 'Approved':
                    status = DocumentStatus.objects.filter(name='Pending').first()
                    if status:
                        file_obj.current_status = status
                
                # Clear any processing note since we forwarded it
                file_obj.processing_note = None
                
                file_obj.current_holder = to_post
                file_obj.current_user = to_user
                file_obj.save()
                
                messages.success(request, f'File forwarded to {to_post.name} successfully.')
                
            elif action_type == 'RETURN':
                # Find return recipient: Most recent FORWARD to the current post
                # We skip previous returns to follow the true backward path
                last_incoming = FileMovement.objects.filter(
                    file=file_obj,
                    to_post=request.user.post,
                    is_return=False
                ).order_by('-moved_at').first()
                
                to_user = None
                to_post = None

                if last_incoming:
                    # Return to the specific user who moved it (moved_by)
                    # and the post from which it was sent (from_post)
                    to_user = last_incoming.moved_by
                    to_post = last_incoming.from_post
                
                if not to_post:
                    messages.error(request, "Cannot return file: No previous sender found.")
                    return redirect('file_detail', file_id=file_obj.id)

                # Create movement record (return)
                FileMovement.objects.create(
                    file=file_obj,
                    from_post=request.user.post,
                    to_post=to_post,
                    to_user=to_user,
                    remarks=f"RETURNED: {remarks}",
                    moved_by=request.user,
                    is_return=True
                )
                
                # Update status
                status = DocumentStatus.objects.filter(name='Returned').first()
                if status:
                    file_obj.current_status = status
                file_obj.current_holder = to_post
                file_obj.current_user = to_user
                file_obj.processing_note = None
                file_obj.save()
                
                recipient_name = to_user.get_full_name() or to_user.username if to_user else to_post.name
                messages.warning(request, f'File returned to {recipient_name}.')
                
            elif action_type == 'APPROVE':
                # Update status but DO NOT close the file
                status = DocumentStatus.objects.filter(name='Approved').first()
                if status:
                    file_obj.current_status = status
                
                # Populating new approval fields
                from django.utils import timezone
                file_obj.approved_by = request.user
                file_obj.approved_at = timezone.now()
                
                file_obj.save()
                messages.success(request, 'File marked as Approved.')

            elif action_type == 'REJECT':
                # Update status but DO NOT close the file
                status = DocumentStatus.objects.filter(name='Rejected').first()
                if not status:
                    # Fallback if "Rejected" status doesn't exist in master data
                    status = DocumentStatus.objects.filter(is_active=True).first()
                
                file_obj.current_status = status
                file_obj.save()
                messages.warning(request, 'File marked as Rejected.')

            elif action_type == 'CLOSE':
                # Only Secretary (Priority 1) can close
                if request.user.post.priority >= 1.5:
                    messages.error(request, 'Only the Secretary can close a file.')
                    return redirect('file_detail', file_id=file_obj.id)

                from django.utils import timezone
                file_obj.is_closed = True
                file_obj.closed_at = timezone.now()
                file_obj.closed_by = request.user
                
                status = DocumentStatus.objects.filter(name='Closed').first()
                if status:
                    file_obj.current_status = status
                
                file_obj.remarks = f"{file_obj.remarks}\n\nFinal Remarks (Closed): {remarks}"
                file_obj.save()
                
                messages.success(request, 'File has been closed successfully.')
            elif action_type == 'KEEP_IN_FILE':
                status = DocumentStatus.objects.filter(name='Keep in File').first()
                if not status:
                    status = DocumentStatus.objects.create(name='Keep in File', is_active=True)
                
                file_obj.current_status = status
                file_obj.save()

                # Register custody-retaining movement to display in the tracking history
                FileMovement.objects.create(
                    file=file_obj,
                    from_post=request.user.post,
                    to_post=request.user.post,
                    to_user=request.user,
                    remarks=remarks,
                    moved_by=request.user,
                    is_return=False,
                    action_required=False
                )
                
                messages.success(request, 'File status updated to "Keep in File". It remains in your custody.')
            
            elif action_type == 'EXTERNAL':
                status = DocumentStatus.objects.filter(name='Processing').first()
                if not status:
                    status = DocumentStatus.objects.create(name='Processing', is_active=True)
                
                file_obj.current_status = status
                file_obj.save()

                # Register external movement (kept under sender's hand, but status changed to Processing)
                FileMovement.objects.create(
                    file=file_obj,
                    from_post=request.user.post,
                    to_post=request.user.post,
                    to_user=request.user,
                    remarks=f"SENT FOR EXTERNAL/GOVERNMENT APPROVAL: {remarks}",
                    moved_by=request.user,
                    is_return=False,
                    action_required=False
                )
                messages.warning(request, 'File sent to Government/External for approval. Status set to Processing.')

            elif action_type == 'ACK_RETURN':
                status = DocumentStatus.objects.filter(name='Pending').first()
                if not status:
                    status = DocumentStatus.objects.create(name='Pending', is_active=True)
                
                file_obj.current_status = status
                file_obj.processing_note = None
                file_obj.save()

                # Register acknowledgement movement
                FileMovement.objects.create(
                    file=file_obj,
                    from_post=request.user.post,
                    to_post=request.user.post,
                    to_user=request.user,
                    remarks=f"ACKNOWLEDGED RETURN FROM GOVT: {remarks}",
                    moved_by=request.user,
                    is_return=False,
                    action_required=True
                )
                messages.success(request, 'Returned file from Government acknowledged successfully. Status set to Pending.')
                return redirect('file_detail', file_id=file_obj.id)
                
            elif action_type == 'PROCESSING_NOTE':
                file_obj.processing_note = remarks
                file_obj.save()

                messages.success(request, 'Internal processing note added successfully.')
                return redirect('file_detail', file_id=file_obj.id)
            
            if action_type == 'APPROVE':
                return redirect('file_detail', file_id=file_obj.id)
            elif action_type == 'KEEP_IN_FILE':
                return redirect('keep_in_files')
            elif action_type == 'ACK_RETURN':
                return redirect('file_detail', file_id=file_obj.id)
            
            return redirect('dashboard')
    else:
        file_status_name = file_obj.current_status.name if file_obj.current_status else None
        form = FileActionForm(user=request.user, can_set_cc=can_set_cc, file_status=file_status_name)
    
    # Get history — exclude recalled movements so they don't pollute the path
    movements_qs = FileMovement.objects.filter(
        file=file_obj,
        is_recalled=False          # Hide recalled forwards from the timeline
    ).select_related(
        'from_post', 'to_post', 'moved_by'
    ).order_by('moved_at')

    # Exclude RECALL entries from the action log so only meaningful actions are shown
    # (PROCESSING_NOTE is included to display notes in the timeline)
    actions_qs = FileAction.objects.filter(
        file=file_obj
    ).exclude(
        action_type__in=['RECALL']
    ).select_related(
        'post', 'action_by'
    ).order_by('action_at')

    movements_list = list(movements_qs)
    actions_list = list(actions_qs)
    
    # Get all shares for history (CC)
    all_shares = FileShare.objects.filter(file=file_obj).select_related('shared_with_user', 'shared_by', 'shared_with')

    # Associate actions and shares with the correct residency timeframe
    # 1. Actions taken after creation but before first movement
    first_move_at = movements_list[0].moved_at if movements_list else None
    
    # Creation step shares include anything set by the creator (Creation or during first forward)
    if first_move_at:
        creation_actions = [a for a in actions_list if a.action_at < first_move_at]
        creation_shares = [
            s for s in all_shares 
            if s.shared_by == file_obj.created_by and s.created_at <= first_move_at + timedelta(seconds=2)
        ]
    else:
        creation_actions = actions_list
        creation_shares = all_shares

    # 2. Actions and Shares taken by a step (Recipient of movement i)
    for i, move in enumerate(movements_list):
        start_time = move.moved_at
        end_time = movements_list[i+1].moved_at if i+1 < len(movements_list) else None

        # Actions taken by this recipient while they had the file
        move.associated_actions = [
            a for a in actions_list
            if a.post == move.to_post and a.action_at >= start_time and (not end_time or a.action_at < end_time)
        ]
        
        # Shares set BY this recipient when forwarding to the NEXT recipient (i+1)
        if i + 1 < len(movements_list):
            next_move = movements_list[i+1]
            move.associated_shares = [
                s for s in all_shares
                if s.shared_by == next_move.moved_by and s.created_at >= next_move.moved_at - timedelta(seconds=2) and s.created_at <= next_move.moved_at + timedelta(seconds=2)
            ]
        else:
            move.associated_shares = []

    # Get all movements for history
    movements = FileMovement.objects.filter(file=file_obj).select_related('from_post', 'to_post', 'moved_by', 'to_user').order_by('moved_at')
    
    documents = FileDocument.objects.filter(file=file_obj).select_related(
        'uploaded_by'
    ).order_by('-uploaded_at')
    
    return_to_post = None
    return_to_user = None
    if is_current_holder:
        last_forward = FileMovement.objects.filter(
            file=file_obj,
            to_post=request.user.post,
            is_return=False,
            is_recalled=False    # Don't trace back through recalled movements
        ).order_by('-moved_at').first()

        if last_forward:
            return_to_post = last_forward.from_post
            return_to_user = last_forward.moved_by

    # Explicitly shared (CC/view-only)
    share_obj = FileShare.objects.filter(
        file=file_obj, shared_with_user=request.user, is_active=True
    ).first()
    file_shared = (share_obj is not None)

    # Auto-mark as viewed if shared
    if share_obj and not share_obj.is_viewed:
        from django.utils import timezone
        share_obj.is_viewed = True
        share_obj.viewed_at = timezone.now()
        share_obj.save()

    context = {
        'file': file_obj,
        'movements': movements_list,
        'actions_list': actions_list,
        'all_shares': all_shares,
        'creation_actions': creation_actions,
        'creation_shares': creation_shares,
        'documents': documents,
        'form': form,
        'is_current_holder': is_current_holder,
        'return_to_post': return_to_post,
        'return_to_user': return_to_user,
        'is_shared': file_shared,
        'share_obj': share_obj,
    }
    
    return render(request, 'filetracking/file_detail.html', context)


@login_required
def track_file(request):
    """
    Restricted file tracking view with advanced search (Status & Date).
    Users can only search for files they have been involved with:
    - Created by them
    - Currently held by their post
    - Sent by their post
    - Received by their post
    - Action taken by their post
    """
    from django.db.models import Q
    from .models import FileMaster, FileMovement, FileAction
    from administration.models import DocumentStatus
    
    query = request.GET.get('search', '').strip()
    status_id = request.GET.get('status')
    dept_id = request.GET.get('department')
    search_date = request.GET.get('search_date')
    
    # Default to current month and year on initial load
    if not request.GET and not search_date:
        from django.utils import timezone
        search_date = timezone.now().strftime('%Y-%m')
        
    files = []
    
    # Always fetch files if any filter is applied (query, status, department or date)
    if query or status_id or dept_id or search_date:
        user_post = request.user.post
        
        # Determine accessible files based on role
        if float(user_post.priority) <= 1.5:
            # Secretary and users with priority <= 1.5 can track ALL files
            files = FileMaster.objects.all()
        else:
            # Get IDs of files where user was specifically involved in movement
            # 1. Sent by this user
            sent_file_ids = FileMovement.objects.filter(
                from_post=user_post,
                moved_by=request.user
            ).values_list('file_id', flat=True)
            
            # 2. Received by this user — exclude recalled movements
            #    (if a file was forwarded to user but recalled, they never truly received it)
            received_file_ids = FileMovement.objects.filter(
                to_post=user_post,
                is_recalled=False
            ).filter(
                Q(to_user=request.user) | Q(to_user__isnull=True)
            ).values_list('file_id', flat=True)


            # Get IDs of files where this user specifically took an action
            action_file_ids = FileAction.objects.filter(
                action_by=request.user
            ).values_list('file_id', flat=True)
            
            # Get IDs of files shared with this user
            from .models import FileShare
            shared_file_ids = FileShare.objects.filter(
                shared_with_user=request.user,
                is_active=True
            ).values_list('file_id', flat=True)
            
            # Main file filter
            files = FileMaster.objects.filter(
                Q(created_by=request.user) |
                (Q(current_holder=user_post) & (Q(current_user=request.user) | Q(current_user__isnull=True))) |
                Q(id__in=sent_file_ids) |
                Q(id__in=received_file_ids) |
                Q(id__in=action_file_ids) |
                Q(id__in=shared_file_ids)
            ).distinct()

            
        # Apply Text Search (File Number or Subject)
        if query:
            files = files.filter(
                Q(file_number__icontains=query) | Q(subject__icontains=query)
            )

        # Apply Status Filter
        if status_id:
            files = files.filter(current_status_id=status_id)

        # Apply Department Filter
        if dept_id:
            files = files.filter(department_id=dept_id)

        # Apply Date Filter (Created Date - Month and Year)
        if search_date:
            # search_date format is YYYY-MM from <input type="month">
            try:
                year, month = map(int, search_date.split('-'))
                files = files.filter(created_at__year=year, created_at__month=month)
            except (ValueError, AttributeError):
                pass

        files = files.select_related(
            'department', 'current_status', 'current_holder', 'document_type', 'document_priority'
        ).order_by('-id')
        
    # Get all active statuses for the dropdown
    statuses = DocumentStatus.objects.filter(is_active=True)
    
    # Get all active departments for the dropdown
    from administration.models import Department
    departments = Department.objects.filter(is_active=True)
        
    return render(request, 'filetracking/track_file.html', {
        'files': files,
        'search_query': query,
        'statuses': statuses,
        'departments': departments,
        'current_status': int(status_id) if status_id else None,
        'current_dept': int(dept_id) if dept_id else None,
        'search_date': search_date
    })

@login_required
def delete_document(request, doc_id):
    """Delete a document attached to a file"""
    from .models import FileDocument
    from django.shortcuts import get_object_or_404
    
    doc = get_object_or_404(FileDocument, pk=doc_id)
    file_id = doc.file.id
    
    # Access Control: Only creator (same post) can delete
    if doc.file.created_by.post != request.user.post:
        messages.error(request, "You are not authorized to delete this document.")
        return redirect('file_detail', file_id=file_id)
        
    # Access Control: Cannot edit closed files
    if doc.file.is_closed:
        messages.error(request, "Cannot modify a closed file.")
        return redirect('file_detail', file_id=file_id)
        
    doc.delete()
    messages.success(request, "Document removed successfully.")
    return redirect('edit_file', file_id=file_id)


@login_required
def edit_file(request, file_id):
    """Edit file details (Creator only)"""
    from .forms import FileCreateForm
    from .models import FileMaster, FileDocument
    from django.shortcuts import get_object_or_404
    
    file_obj = get_object_or_404(FileMaster, pk=file_id)
    
    # Access Control: Only creator (same post) can edit
    if file_obj.created_by.post != request.user.post:
        messages.error(request, "You are not authorized to edit this file.")
        return redirect('file_detail', file_id=file_obj.id)
        
    # Access Control: Cannot edit closed files
    if file_obj.is_closed:
        messages.error(request, "Cannot edit a closed file.")
        return redirect('file_detail', file_id=file_obj.id)

    if request.method == 'POST':
        form = FileCreateForm(request.POST, request.FILES, instance=file_obj)
        if form.is_valid():
            file_obj = form.save()
            
            # Handle new attachments if provided
            attachments = request.FILES.getlist('attachment')
            for attachment in attachments:
                FileDocument.objects.create(
                    file=file_obj,
                    content=attachment.read(),
                    file_name=attachment.name,
                    mimetype=attachment.content_type,
                    uploaded_by=request.user,
                    description='Additional attachment during edit'
                )

            
            messages.success(request, f'File {file_obj.file_number} updated successfully!')
            return redirect('file_detail', file_id=file_obj.id)
    else:
        form = FileCreateForm(instance=file_obj)
    
    documents = FileDocument.objects.filter(file=file_obj)
    
    return render(request, 'filetracking/edit_file.html', {
        'form': form,
        'file': file_obj,
        'documents': documents
    })

@login_required
def recall_file(request, movement_id):
    """
    Recall a forwarded file within 24 hours if receiver has not taken any action.
    """
    movement = get_object_or_404(FileMovement, id=movement_id)
    file_obj = movement.file

    # 1. Validation: Only the person who sent it can recall it
    if movement.moved_by != request.user:
        messages.error(request, "You are not authorized to recall this file.")
        return redirect('sent_files')

    # 2. Validation: Cannot recall a return or an already recalled movement
    if movement.is_return or movement.is_recalled:
        messages.error(request, "This movement cannot be recalled.")
        return redirect('sent_files')

    # 3. Validation: Time constraint (24 hours)
    time_diff = timezone.now() - movement.moved_at
    if time_diff.total_seconds() > 24 * 3600:
        messages.error(request, "Recall period (24 hours) has expired.")
        return redirect('sent_files')

    # 4. Validation: Check if the file is still with the receiver post
    if file_obj.current_holder != movement.to_post:
        messages.error(request, "Cannot recall: The file has already been moved by the receiver.")
        return redirect('sent_files')
    
    # 5. Validation: If assigned to a specific user, ensure it is still with that user
    if movement.to_user and file_obj.current_user != movement.to_user:
        messages.error(request, "Cannot recall: The receiver user has already moved the file.")
        return redirect('sent_files')

    # 6. Validation: Check if receiver has taken any action (FileAction) since receiving it
    # Note: We look for ANY action by the receiver post on this file after the movement timestamp
    receiver_actions = FileAction.objects.filter(
        file=file_obj,
        post=movement.to_post,
        action_at__gte=movement.moved_at
    ).exclude(action_type='RECALL') # Exclude previous recalls if any (unlikely for current holder)

    if receiver_actions.exists():
        messages.error(request, "Cannot recall: The receiver has already taken an action on this file.")
        return redirect('sent_files')

    # --- ALL CHECKS PASSED ---
    
    # Update FileMaster to revert holder/user
    file_obj.current_holder = movement.from_post
    file_obj.current_user = movement.moved_by
    file_obj.save()

    # Mark the movement as recalled
    movement.is_recalled = True
    movement.save()

    # Create a Recall Action for history
    FileAction.objects.create(
        file=file_obj,
        post=request.user.post,
        action_type='RECALL',
        remarks=f"Recalled forward movement to {movement.to_post.name}",
        action_by=request.user
    )

    # Cleanup: Remove View Access (FileShare) granted during this forward
    # This assumes that if a post was CC'd during this forward, it might still have access.
    # We look for the FORWARD action corresponding to this movement to find CCs.
    forward_action = FileAction.objects.filter(
        file=file_obj,
        action_by=movement.moved_by,
        action_at__gte=movement.moved_at,
        action_type='FORWARD'
    ).order_by('action_at').first()

    if forward_action and forward_action.view_by_id:
        cc_user_ids = forward_action.view_by_id.split(',')
        for uid in cc_user_ids:
            try:
                # Remove View Access (FileShare) granted to specific users
                FileShare.objects.filter(file=file_obj, shared_with_user_id=int(uid)).delete()
            except (ValueError, TypeError):
                continue

    messages.success(request, f"File {file_obj.file_number} has been successfully recalled.")
    return redirect('sent_files')

@login_required
def approved_files_view(request):
    """List of files approved by the current user"""
    from django.db.models import Q, Max
    from django.core.paginator import Paginator
    
    search_query = request.GET.get('search', '')
    approved_files = FileMaster.objects.filter(
        actions__action_type='APPROVE',
        actions__action_by=request.user
    ).annotate(
        user_approved_at=Max('actions__action_at', filter=Q(actions__action_type='APPROVE', actions__action_by=request.user))
    ).distinct()
    
    if search_query:
        approved_files = approved_files.filter(
            Q(file_number__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
    
    approved_files = approved_files.order_by('-user_approved_at')
    
    paginator = Paginator(approved_files, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'filetracking/approved_files.html', {
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1) if page_number else paginator.get_elided_page_range(1, on_each_side=1, on_ends=1),
        'search_query': search_query,
        'approved_count': approved_files.count()
    })


@login_required
def created_files_view(request):
    """List of files created by the current user"""
    from django.db.models import Q
    from django.core.paginator import Paginator
    
    search_query = request.GET.get('search', '')
    created_files = FileMaster.objects.filter(created_by=request.user)
    
    if search_query:
        created_files = created_files.filter(
            Q(file_number__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
    
    created_files = created_files.order_by('-created_at')
    
    paginator = Paginator(created_files, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'filetracking/created_files.html', {
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1) if page_number else paginator.get_elided_page_range(1, on_each_side=1, on_ends=1),
        'search_query': search_query,
        'created_count': created_files.count()
    })

from django.views.decorators.clickjacking import xframe_options_sameorigin

@login_required
@xframe_options_sameorigin
def download_document(request, doc_id):
    """Serve a document from the database"""
    from django.http import HttpResponse
    from .models import FileDocument
    
    doc = get_object_or_404(FileDocument, pk=doc_id)
    
    # Access Control: Check if user has access to the file this document belongs to
    # (Reusing detail view logic or similar)
    # For now, a simple check: can the user view the file?
    file_obj = doc.file
    user_post = request.user.post
    
    # Simple check for now (similar to file_detail access check)
    has_access = False
    if float(user_post.priority) <= 1.5:
        has_access = True
    else:
        # Check if user's post OR user is involved
        from django.db.models import Q
        involved = FileMovement.objects.filter(
            file=file_obj
        ).filter(
            Q(to_post=user_post) | Q(from_post=user_post) | Q(moved_by=request.user)
        ).exists()
        
        shared = FileShare.objects.filter(
            file=file_obj,
            shared_with=user_post,
            is_active=True
        ).exists()
        
        if involved or shared or file_obj.created_by == request.user:
            has_access = True

    if not has_access:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have access to this document.")

    response = HttpResponse(doc.content, content_type=doc.mimetype)
    response['Content-Disposition'] = f'inline; filename="{doc.file_name}"'
    return response


@login_required
def keep_in_files_view(request):
    """
    List of files with status 'Keep in File'
    Exclusively scoped to files currently held by the logged-in user.
    """
    from django.db.models import Q
    from django.core.paginator import Paginator
    from .models import FileMaster
    
    search_query = request.GET.get('search', '').strip()
    
    files = FileMaster.objects.filter(
        current_status__name='Keep in File',
        is_closed=False,
        current_holder=request.user.post,
        current_user=request.user
    )
    
    if search_query:
        files = files.filter(
            Q(file_number__icontains=search_query) |
            Q(subject__icontains=search_query)
        )
        
    files = files.select_related(
        'department', 'current_status', 'current_holder', 'current_user', 'document_type', 'document_priority'
    ).order_by('-created_at')
    
    paginator = Paginator(files, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'filetracking/keep_in_files.html', {
        'page_obj': page_obj,
        'page_range': paginator.get_elided_page_range(page_number, on_each_side=1, on_ends=1) if page_number else paginator.get_elided_page_range(1, on_each_side=1, on_ends=1),
        'search_query': search_query,
        'keep_count': files.count()
    })


@login_required
def summary_dashboard(request):
    """
    Summary Dashboard for Superadmin/Admin (Priority <= 1.5).
    Lists active users and links to dynamic pending files summary.
    """
    if not hasattr(request.user, 'post') or not request.user.post or float(request.user.post.priority) > 1.5:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Access restricted to administrators.")

    from administration.models import CustomUser
    from django.db.models import Count, Q
    from .models import FileMaster

    # Retrieve all active users, pre-fetch their posts
    users = CustomUser.objects.filter(is_active=True).select_related('post').order_by('post__priority', 'username')

    # Optimization: count assigned and unassigned files in 1 query per grouping to prevent N+1 loop queries
    pending_filter = Q(held_files__is_closed=False) & ~Q(held_files__current_status__name='Keep in File') & ~Q(held_files__current_status__name='Processing')
    assigned_counts = CustomUser.objects.filter(is_active=True).annotate(
        assigned_count=Count('held_files', filter=pending_filter)
    ).values('id', 'assigned_count')

    assigned_map = {item['id']: item['assigned_count'] for item in assigned_counts}

    # Count unassigned open files per post
    unassigned_counts = FileMaster.objects.filter(
        current_user__isnull=True,
        is_closed=False
    ).exclude(
        current_status__name='Keep in File'
    ).exclude(
        current_status__name='Processing'
    ).values('current_holder').annotate(count=Count('id'))

    unassigned_map = {item['current_holder']: item['count'] for item in unassigned_counts}

    # Combine counts in memory
    for u in users:
        assigned = assigned_map.get(u.id, 0)
        unassigned = unassigned_map.get(u.post.id, 0)
        u.total_pending = assigned + unassigned

    from django.db.models import Prefetch
    from .models import FileAction, FileMovement

    # Fetch all open files currently in 'Processing' status (sent to Government / External)
    processing_files_qs = FileMaster.objects.filter(
        is_closed=False,
        current_status__name='Processing'
    ).select_related(
        'document_type', 'current_status', 'document_priority', 'current_user', 'current_holder'
    ).prefetch_related(
        Prefetch(
            'actions',
            queryset=FileAction.objects.filter(action_type='EXTERNAL').select_related('action_by', 'post').order_by('-action_at'),
            to_attr='external_actions'
        ),
        Prefetch(
            'movements',
            queryset=FileMovement.objects.select_related('moved_by', 'from_post').order_by('-moved_at'),
            to_attr='recent_movements'
        )
    ).order_by('-created_at')

    processing_files = []
    for f in processing_files_qs:
        ext_action = f.external_actions[0] if f.external_actions else None
        sent_by_user = None
        sent_by_post = None
        narration = ""
        sent_at = None

        if ext_action:
            sent_by_user = ext_action.action_by
            sent_by_post = ext_action.post
            narration = ext_action.remarks
            sent_at = ext_action.action_at
        elif f.recent_movements:
            recent_mov = f.recent_movements[0]
            sent_by_user = recent_mov.moved_by
            sent_by_post = recent_mov.from_post
            narration = recent_mov.remarks
            sent_at = recent_mov.moved_at
        else:
            sent_by_user = f.current_user
            sent_by_post = f.current_holder
            narration = f.remarks
            sent_at = f.created_at

        if narration and narration.startswith('SENT FOR EXTERNAL/GOVERNMENT APPROVAL: '):
            narration = narration.replace('SENT FOR EXTERNAL/GOVERNMENT APPROVAL: ', '', 1)

        processing_files.append({
            'file': f,
            'sent_by_user': sent_by_user,
            'sent_by_post': sent_by_post,
            'narration': narration or 'No narration provided.',
            'sent_at': sent_at,
        })

    return render(request, 'filetracking/summary_dashboard.html', {
        'users': users,
        'processing_files': processing_files,
        'processing_count': len(processing_files),
    })


@login_required
def user_pending_files_api(request, user_id):
    """
    JSON API responding with pending files and latest remarks/reasons for a specific user.
    """
    if not hasattr(request.user, 'post') or not request.user.post or float(request.user.post.priority) > 1.5:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("Access restricted to administrators.")

    from administration.models import CustomUser
    from django.db.models import Q, OuterRef, Subquery
    from .models import FileMaster, FileMovement
    from django.http import JsonResponse

    user = get_object_or_404(CustomUser, id=user_id)

    # Subquery to fetch the latest movement's remarks (reason for pending) efficiently
    latest_movement_remark = FileMovement.objects.filter(
        file=OuterRef('pk'),
        is_recalled=False
    ).order_by('-moved_at').values('remarks')[:1]

    # Fetch pending files at the user's post where they are the current user OR it is unassigned
    pending_files = FileMaster.objects.filter(
        current_holder=user.post,
        is_closed=False
    ).exclude(
        current_status__name='Keep in File'
    ).exclude(
        current_status__name='Processing'
    ).filter(
        Q(current_user=user) | Q(current_user__isnull=True)
    ).annotate(
        recent_remark=Subquery(latest_movement_remark)
    ).select_related('document_type', 'current_status', 'document_priority').order_by('-created_at')

    files_list = []
    for file in pending_files:
        is_unassigned = file.current_user is None
        
        has_processing_note = bool(file.processing_note)
        remark = file.processing_note if has_processing_note else (file.recent_remark if file.recent_remark else (file.remarks or "No remarks provided."))
        
        files_list.append({
            'id': file.id,
            'file_number': file.file_number,
            'subject': file.subject,
            'doc_type': file.document_type.name if file.document_type else 'N/A',
            'status': file.current_status.name if file.current_status else 'Pending',
            'remark': remark,
            'has_processing_note': has_processing_note,
            'is_unassigned': is_unassigned,
            'priority': file.document_priority.name if file.document_priority else 'Normal',
            'created_at': timezone.localtime(file.created_at).strftime('%d-%m-%Y') if file.created_at else ''
        })

    return JsonResponse({
        'user_name': user.get_full_name() or user.username,
        'designation': user.post.name,
        'files': files_list
    })


@login_required
def document_viewer_view(request, file_id, doc_id):
    """
    Unified overlay/viewing page for multiple documents in a single file folder.
    Provides Next/Previous buttons and native browser iframe binary embedding.
    """
    from django.db.models import Q
    
    file_obj = get_object_or_404(FileMaster, pk=file_id)
    doc_obj = get_object_or_404(FileDocument, pk=doc_id, file=file_obj)
    
    # Check permissions (consistent with download_document security controls)
    user_post = request.user.post
    has_access = False
    
    if float(user_post.priority) <= 1.5:
        has_access = True
    else:
        involved = FileMovement.objects.filter(
            file=file_obj
        ).filter(
            Q(to_post=user_post) | Q(from_post=user_post) | Q(moved_by=request.user)
        ).exists()
        
        shared = FileShare.objects.filter(
            file=file_obj,
            shared_with=user_post,
            is_active=True
        ).exists()
        
        if involved or shared or file_obj.created_by == request.user:
            has_access = True

    if not has_access:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You do not have access to this file's documents.")

    # Get list of all documents attached to this file
    documents = list(FileDocument.objects.filter(file=file_obj).order_by('uploaded_at'))
    
    # Find current document index
    current_index = -1
    for i, doc in enumerate(documents):
        if doc.id == doc_obj.id:
            current_index = i
            break
            
    # Calculate previous and next doc
    prev_doc_id = documents[current_index - 1].id if current_index > 0 else None
    next_doc_id = documents[current_index + 1].id if current_index < len(documents) - 1 else None
    
    context = {
        'file': file_obj,
        'doc': doc_obj,
        'prev_doc_id': prev_doc_id,
        'next_doc_id': next_doc_id,
        'current_num': current_index + 1,
        'total_num': len(documents),
        'is_image': doc_obj.mimetype.startswith('image/') if doc_obj.mimetype else False,
    }
    return render(request, 'filetracking/document_viewer.html', context)


