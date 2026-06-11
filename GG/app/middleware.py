from django.shortcuts import redirect


class BlockNonAdminMiddleware:
    """
    Prevent non-admin (and unauthenticated) users from reaching Django's
    built-in /admin/ interface.

    FIX: previously redirected to 'homepage', which itself requires login,
    causing an unnecessary extra redirect for unauthenticated users.
    Now redirects directly to 'login'.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/admin/"):
            if not request.user.is_authenticated or not request.user.is_superuser:
                return redirect("login")   # ← was redirect("homepage")
        return self.get_response(request)
