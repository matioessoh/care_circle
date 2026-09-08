import logging

from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.dispatch import receiver

from .models import LoginLog

logger = logging.getLogger(__name__)


def _get_ip(request):
    if request is None:
        return None
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _get_ua(request):
    if request is None:
        return ''
    return request.META.get('HTTP_USER_AGENT', '')[:500]


@receiver(user_logged_in)
def on_login_success(sender, request, user, **kwargs):
    try:
        LoginLog.objects.create(
            user=user,
            username_attempted=user.get_username(),
            ip_address=_get_ip(request),
            user_agent=_get_ua(request),
            success=True,
        )
    except Exception as e:  # pragma: no cover - logging must never break login
        logger.error('Erreur audit connexion réussie: %s', e)


@receiver(user_login_failed)
def on_login_failed(sender, credentials, request=None, **kwargs):
    try:
        LoginLog.objects.create(
            user=None,
            username_attempted=(credentials or {}).get('username', 'inconnu'),
            ip_address=_get_ip(request),
            user_agent=_get_ua(request),
            success=False,
        )
    except Exception as e:  # pragma: no cover
        logger.error('Erreur audit connexion échouée: %s', e)
