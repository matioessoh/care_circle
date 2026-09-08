from django import template
from datetime import date

register = template.Library()


@register.filter
def member_badge(user):
    """Badge communautaire selon le statut du membre."""
    if user is None or getattr(user, 'is_anonymous', False):
        return None
    if getattr(user, 'doctor_profile', None):
        return {'label': 'Médecin', 'css': 'green'}
    return {'label': 'Membre', 'css': 'blue'}


@register.filter
def forum_rank(user):
    """Badge basé sur la participation au forum."""
    if user is None or getattr(user, 'is_anonymous', False):
        return None
    posts = getattr(user, 'forum_posts', None)
    comments = getattr(user, 'forum_comments', None)
    total = 0
    if posts is not None:
        try:
            total += posts.count()
        except Exception:
            total += 0
    if comments is not None:
        try:
            total += comments.count()
        except Exception:
            total += 0
    if total >= 50:
        return {'label': 'Contributeur expert', 'css': 'green'}
    if total >= 20:
        return {'label': 'Contributeur', 'css': 'blue'}
    if total >= 5:
        return {'label': 'Membre actif', 'css': 'blue'}
    return None