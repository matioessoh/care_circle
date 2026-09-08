from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_POST
from .models import Conversation, Message


@login_required
def inbox(request):
    conversations = request.user.conversations.all()
    conv_data = []
    for conv in conversations:
        other = conv.participants.exclude(id=request.user.id).first()
        last_msg = conv.last_message
        unread = conv.messages.filter(is_read=False).exclude(sender=request.user).count()
        conv_data.append({
            'conversation': conv,
            'other_user': other,
            'last_message': last_msg,
            'unread_count': unread,
        })
    return render(request, 'messaging/inbox.html', {'conversations': conv_data})


@login_required
def conversation_detail(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    other_user = conversation.participants.exclude(id=request.user.id).first()
    messages_list = conversation.messages.select_related('sender')
    messages_list.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    if request.method == 'POST':
        content = request.POST.get('content')
        if content:
            Message.objects.create(
                conversation=conversation,
                sender=request.user,
                content=content,
            )
            return redirect('conversation_detail', conversation_id=conversation.id)

    return render(request, 'messaging/conversation.html', {
        'conversation': conversation,
        'other_user': other_user,
        'messages': messages_list,
    })


@login_required
def start_conversation(request, user_id):
    other_user = get_object_or_404(User, id=user_id)
    if other_user == request.user:
        return redirect('inbox')
    existing = Conversation.objects.filter(
        participants=request.user
    ).filter(participants=other_user).first()
    if existing:
        return redirect('conversation_detail', conversation_id=existing.id)
    conversation = Conversation.objects.create()
    conversation.participants.add(request.user, other_user)
    return redirect('conversation_detail', conversation_id=conversation.id)


@login_required
def conversation_poll(request, conversation_id):
    """AJAX: renvoie les nouveaux messages depuis `after_id` au format JSON."""
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    after_id = request.GET.get('after_id', 0)
    try:
        after_id = int(after_id)
    except (TypeError, ValueError):
        after_id = 0

    # Marquer comme lus les messages entrants
    conversation.messages.filter(is_read=False).exclude(sender=request.user).update(is_read=True)

    new_messages = conversation.messages.filter(id__gt=after_id).select_related('sender')
    html = render_to_string('messaging/_messages.html', {
        'messages': new_messages,
        'user': request.user,
    })
    last_id = conversation.messages.order_by('-id').values_list('id', flat=True).first()

    return JsonResponse({
        'html': html,
        'last_id': last_id or after_id,
    })


@login_required
@require_POST
def conversation_send_ajax(request, conversation_id):
    conversation = get_object_or_404(Conversation, id=conversation_id, participants=request.user)
    content = request.POST.get('content', '').strip()
    if content:
        msg = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            content=content,
        )
        html = render_to_string('messaging/_messages.html', {
            'messages': [msg],
            'user': request.user,
        })
        return JsonResponse({'ok': True, 'html': html, 'id': msg.id})
    return JsonResponse({'ok': False, 'error': 'Message vide'}, status=400)
