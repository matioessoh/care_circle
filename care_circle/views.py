"""Vues transverses (connexion avec rate-limit)."""
from django.contrib import messages
from django.contrib.auth.views import LoginView
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit

from care_circle.ratelimit import client_ip_key, limited_response


@method_decorator(ratelimit(key=client_ip_key, rate='30/h', method='POST', block=False), name='dispatch')
class RateLimitedLoginView(LoginView):
    """LoginView standard + quota 30 tentatives/h par IP (anti brute-force).
    Quota dépassé -> 429 au lieu de traiter la tentative."""

    def post(self, request, *args, **kwargs):
        if getattr(request, 'limited', False):
            return limited_response(request)
        return super().post(request, *args, **kwargs)
