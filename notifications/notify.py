from .models import Notification


def notify(user, kind, title, message='', url=''):
    """Crée une notification pour un utilisateur (ignore si grand destinataire absent)."""
    if not user:
        return None
    return Notification.objects.create(
        user=user,
        kind=kind,
        title=title,
        message=message,
        url=url,
    )