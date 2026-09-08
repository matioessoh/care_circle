from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Notification


@login_required
def notification_list(request):
    notifications = request.user.notifications.all()
    count = notifications.count()
    unread = notifications.filter(is_read=False).count()
    notifications.update(is_read=True)
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    return render(request, 'notifications/notification_list.html', {
        'page_obj': page_obj,
        'total': count,
        'unread_before': unread,
    })


@login_required
def notification_mark_read(request, notification_id):
    notif = get_object_or_404(Notification, id=notification_id, user=request.user)
    notif.mark_as_read()
    return redirect(notif.url or 'notification_list')


@login_required
def notification_mark_all_read(request):
    request.user.notifications.filter(is_read=False).update(is_read=True)
    target = request.GET.get('next') or 'notification_list'
    return redirect(target)


@login_required
def notification_unread_count(request):
    return JsonResponse({'count': request.user.notifications.filter(is_read=False).count()})