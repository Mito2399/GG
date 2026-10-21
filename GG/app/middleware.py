import time

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect


LOGIN_MAX_ATTEMPTS = 5
LOGIN_WINDOW_SECS  = 600
LOGIN_LOCKOUT_SECS = 900


class LoginRateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path in ("/", "/login/"):
            ip  = self._get_ip(request)
            key = f"gg_login_attempts:{ip}"
            now = time.time()

            attempts = cache.get(key, [])
            attempts = [t for t in attempts if now - t < LOGIN_WINDOW_SECS]

            if len(attempts) >= LOGIN_MAX_ATTEMPTS:
                oldest   = attempts[0]
                wait_sec = int(LOGIN_LOCKOUT_SECS - (now - oldest))
                wait_min = max(1, wait_sec // 60)
                return HttpResponse(
                    f"Too many failed login attempts. "
                    f"Please wait {wait_min} minute(s) before trying again.",
                    status=429,
                    content_type="text/plain",
                )

            request._gg_login_key = key
            request._gg_login_attempts = attempts

        response = self.get_response(request)

        if request.method == "POST" and request.path in ("/", "/login/"):
            key = getattr(request, "_gg_login_key", None)
            if key:
                if request.user.is_authenticated:
                    cache.delete(key)
                else:
                    attempts = getattr(request, "_gg_login_attempts", [])
                    attempts.append(time.time())
                    cache.set(key, attempts, LOGIN_WINDOW_SECS)

        return response

    @staticmethod
    def _get_ip(request) -> str:
        trusted = getattr(settings, "TRUSTED_PROXY_COUNT", 0)
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if trusted and xff:
            parts = [p.strip() for p in xff.split(",")]
            if len(parts) >= trusted:
                return parts[-trusted]
        return request.META.get("REMOTE_ADDR", "unknown")


class BlockNonAdminMiddleware:
    """
    C3 fix — the admin URL is now configurable via settings.ADMIN_URL.
    Previously this middleware checked '/admin/' but the admin was mounted
    at '/aprilPogi/', making the middleware a no-op.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        self._admin_prefix = "/" + getattr(settings, "ADMIN_URL", "admin/").lstrip("/")

    def __call__(self, request):
        if request.path.startswith(self._admin_prefix):
            if not request.user.is_authenticated or not request.user.is_superuser:
                return redirect("login")
        return self.get_response(request)