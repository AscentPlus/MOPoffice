import json

from django.contrib import messages as django_messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import NewConversationForm, SendMessageForm
from .models import Conversation, MessageAttachment
from .permissions import can_message_user, can_view_conversation, get_messageable_users
from .services import (
    get_messages,
    get_or_create_conversation,
    get_total_unread_count,
    get_user_conversations,
    mark_conversation_read,
    send_message,
    serialize_conversation_item,
    serialize_message,
    touch_presence,
)


@login_required
def inbox(request, conversation_id=None):
    touch_presence(request.user)
    conversations = get_user_conversations(request.user)
    active_conversation = None
    active_other = None
    chat_messages = []
    send_form = SendMessageForm()

    if conversation_id:
        active_conversation = get_object_or_404(
            Conversation,
            pk=conversation_id,
            is_active=True,
        )
        if not can_view_conversation(request.user, active_conversation):
            raise Http404
        active_other = active_conversation.other_participant(request.user)
        chat_messages = get_messages(active_conversation, request.user)
        mark_conversation_read(active_conversation, request.user)

    new_form = NewConversationForm(request.user)

    return render(request, 'messaging/inbox.html', {
        'conversations': conversations,
        'active_conversation': active_conversation,
        'active_other': active_other,
        'chat_messages': chat_messages,
        'send_form': send_form,
        'new_form': new_form,
        'messageable_users': get_messageable_users(request.user),
        'total_unread': get_total_unread_count(request.user),
    })


@login_required
@require_POST
def start_conversation(request):
    form = NewConversationForm(request.user, request.POST, request.FILES)
    if not form.is_valid():
        django_messages.error(request, 'Please select a valid recipient.')
        return redirect('messaging_inbox')

    recipient = form.cleaned_data['recipient']
    if not can_message_user(request.user, recipient):
        django_messages.error(request, 'You cannot message this user.')
        return redirect('messaging_inbox')

    try:
        conversation, _ = get_or_create_conversation(request.user, recipient, request.user)
    except PermissionError:
        django_messages.error(request, 'You cannot message this user.')
        return redirect('messaging_inbox')

    initial = form.cleaned_data.get('initial_message', '').strip()
    if initial:
        try:
            send_message(conversation, request.user, initial)
        except ValueError as e:
            django_messages.error(request, str(e))

    return redirect('messaging_conversation', conversation_id=conversation.id)


@login_required
@require_POST
def send_message_view(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id, is_active=True)
    if not can_view_conversation(request.user, conversation):
        raise Http404

    form = SendMessageForm(request.POST, request.FILES)
    if not form.is_valid():
        django_messages.error(request, 'Invalid message.')
        return redirect('messaging_conversation', conversation_id=conversation.id)

    try:
        send_message(
            conversation,
            request.user,
            form.cleaned_data.get('body', ''),
            form.cleaned_data.get('attachment'),
        )
        mark_conversation_read(conversation, request.user)
    except ValueError as e:
        django_messages.error(request, str(e))

    return redirect('messaging_conversation', conversation_id=conversation.id)


@login_required
def download_attachment(request, attachment_id):
    attachment = get_object_or_404(
        MessageAttachment.objects.select_related('message__conversation'),
        pk=attachment_id,
    )
    conversation = attachment.message.conversation
    if not can_view_conversation(request.user, conversation):
        raise Http404

    response = FileResponse(attachment.file.open('rb'), as_attachment=True, filename=attachment.original_name)
    if attachment.content_type:
        response['Content-Type'] = attachment.content_type
    return response


# ── JSON API (polling) ──────────────────────────────────────────────

def _json_body(request):
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            return {}
    return {}


@login_required
@require_GET
def api_inbox(request):
    touch_presence(request.user)
    items = get_user_conversations(request.user)
    data = [serialize_conversation_item(item, request.user, request) for item in items]
    return JsonResponse({
        'conversations': data,
        'total_unread': get_total_unread_count(request.user),
    })


@login_required
@require_GET
def api_messages(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id, is_active=True)
    if not can_view_conversation(request.user, conversation):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    touch_presence(request.user)
    since_id = request.GET.get('since_id')
    since_id = int(since_id) if since_id and since_id.isdigit() else None

    msgs = get_messages(conversation, request.user, since_id=since_id)
    if not since_id:
        mark_conversation_read(conversation, request.user)

    other = conversation.other_participant(request.user)
    try:
        is_online = other.presence.is_online
    except Exception:
        is_online = False

    return JsonResponse({
        'messages': [serialize_message(m, request) for m in msgs],
        'conversation_id': conversation.id,
        'other_user': {
            'id': other.id,
            'name': other.get_full_name() or other.username,
            'username': other.username,
            'post': other.post.name if other.post_id else '',
            'is_online': is_online,
        },
    })


@login_required
@require_POST
def api_send(request, conversation_id):
    conversation = get_object_or_404(Conversation, pk=conversation_id, is_active=True)
    if not can_view_conversation(request.user, conversation):
        return JsonResponse({'error': 'Forbidden'}, status=403)

    body = request.POST.get('body', '')
    attachment = request.FILES.get('attachment')
    if not body and not attachment:
        data = _json_body(request)
        body = data.get('body', '')

    try:
        message = send_message(conversation, request.user, body, attachment)
        mark_conversation_read(conversation, request.user)
        touch_presence(request.user)
        return JsonResponse({'ok': True, 'message': serialize_message(message, request)})
    except ValueError as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_GET
def api_unread_count(request):
    touch_presence(request.user)
    return JsonResponse({'total_unread': get_total_unread_count(request.user)})


@login_required
@require_POST
def api_presence(request):
    touch_presence(request.user)
    return JsonResponse({'ok': True})
