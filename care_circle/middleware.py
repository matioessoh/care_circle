"""
Middleware de durcissement HTTP.

Ajoute des en-têtes de sécurité et une Content-Security-Policy (CSP) fondée
sur des nonces afin d'empêcher l'exécution de scripts injectés (XSS).

Le nonce CSP est généré par requête et exposé sous ``request.csp_nonce`` ;
les templates utilisent ``nonce="{{ request.csp_nonce }}"`` sur les balises
``<script>`` inline.
"""

import secrets

from django.conf import settings


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(24)
        response = self.get_response(request)

        # En-têtes de sécurité (hors CSP)
        for name, value in settings.SECURITY_HEADERS.items():
            response.setdefault(name, value)

        # Content-Security-Policy construite à partir des sources autorisées
        # (settings.CSP_SOURCES) + le nonce de la requête.
        directives = []
        for directive, sources in settings.CSP_SOURCES.items():
            if directive == 'script-src':
                sources = [*sources, f"'nonce-{request.csp_nonce}'"]
            directives.append('{} {}'.format(directive, ' '.join(sources)))
        response.setdefault('Content-Security-Policy', '; '.join(directives))

        return response