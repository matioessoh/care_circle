from django.db import models
from django.conf import settings


class LoginLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='login_logs'
    )
    username_attempted = models.CharField('Pseudo tenté', max_length=150, default='')
    ip_address = models.GenericIPAddressField('Adresse IP', null=True, blank=True)
    user_agent = models.TextField('Navigateur', blank=True, default='')
    success = models.BooleanField('Succès', default=True)
    timestamp = models.DateTimeField('Horodatage', auto_now_add=True)

    class Meta:
        verbose_name = 'Connexion'
        verbose_name_plural = 'Audit des connexions'
        ordering = ['-timestamp']

    def __str__(self):
        who = self.user.username if self.user else (self.username_attempted or 'inconnu')
        return f"{who} - {'OK' if self.success else 'ÉCHEC'} - {self.timestamp}"
