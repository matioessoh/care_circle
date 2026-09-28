"""Clé de rate-limit basée sur l'IP réelle du client.

Derrière Vercel (reverse proxy), REMOTE_ADDR est l'IP du proxy : on utilise
X-Forwarded-For (que Vercel renseigne) en prenant la première entrée
(l'adresse du client). Sans cet en-tête, repli sur REMOTE_ADDR.
"""
from django.http import HttpResponse


def client_ip_key(group, request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def limited_response(request):
    """Réponse 429 quand le quota est dépassé (block=False + test manuel,
    pour éviter une 500 via l'exception Ratelimited)."""
    return HttpResponse(
        'Trop de requêtes. Veuillez réessayer plus tard.',
        status=429,
        content_type='text/plain; charset=utf-8',
    )
