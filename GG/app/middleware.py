import time
from collections import defaultdict

from django.shortcuts import redirect
from django.http import HttpResponse


# ─────────────────────────────── Login Rate Limiter ───────────────────────────

_login_attempts: dict = defaultdict(list)

LOGIN_MAX_ATTEMPTS = 5    # max failed attempts
LOGIN_WINDOW_SECS  = 600  # 10-minute window
LOGIN_LOCKOUT_SECS = 900  # 15-minute lockout after limit reached


class LoginRateLimitMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == "POST" and request.path in ("/", "/login/"):
            ip  = self._get_ip(request)
            now = time.time()

            # Remove attempts outside the window
            _login_attempts[ip] = [
                t for t in _login_attempts[ip]
                if now - t < LOGIN_WINDOW_SECS
            ]

            if len(_login_attempts[ip]) >= LOGIN_MAX_ATTEMPTS:
                oldest   = _login_attempts[ip][0]
                wait_sec = int(LOGIN_LOCKOUT_SECS - (now - oldest))
                wait_min = max(1, wait_sec // 60)
                return HttpResponse(
                    f"Too many failed login attempts. "
                    f"Please wait {wait_min} minute(s) before trying again.",
                    status=429,
                    content_type="text/plain",
                )

        response = self.get_response(request)

        if (
            request.method == "POST"
            and request.path in ("/", "/login/")
            and not request.user.is_authenticated
        ):
            ip = self._get_ip(request)
            _login_attempts[ip].append(time.time())
        elif (
            request.method == "POST"
            and request.path in ("/", "/login/")
            and request.user.is_authenticated
        ):
            ip = self._get_ip(request)
            _login_attempts[ip] = []

        return response

    @staticmethod
    def _get_ip(request) -> str:
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded:
            return x_forwarded.split(",")[0].strip()
        return request.META.get("REMOTE_ADDR", "unknown")


# ─────────────────────────────── Admin Block ──────────────────────────────────

class BlockNonAdminMiddleware:
    """
    Prevent non-admin (and unauthenticated) users from reaching /admin/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            if not request.user.is_authenticated or not request.user.is_superuser:
                return redirect("login")
        return self.get_response(request)