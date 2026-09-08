from django.db import models
from django.conf import settings
from django.utils import timezone


class Notification(models.Model):
    KIND_CHOICES = [
        ('appointment', 'Rendez-vous'),
        ('message', 'Message'),
        ('connection', 'Connexion'),
        ('forum', 'Forum'),
        ('system', 'Système'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications',
        verbose_name='Destinataire',
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default='system')
    title = models.CharField(max_length=200, verbose_name='Titre')
    message = models.TextField(blank=True, verbose_name='Message')
    url = models.CharField(max_length=300, blank=True, verbose_name='Lien')
    is_read = models.BooleanField(default=False, verbose_name='Lue')
    timestamp = models.DateTimeField(default=timezone.now, verbose_name='Créée le')

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f'{self.user.username} - {self.title}'

    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])