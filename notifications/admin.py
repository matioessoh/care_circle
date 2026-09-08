from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'title', 'kind', 'is_read', 'timestamp']
    list_filter = ['kind', 'is_read', 'timestamp']
    search_fields = ['user__username', 'title', 'message']
    readonly_fields = ['user', 'title', 'kind', 'message', 'url', 'is_read', 'timestamp']