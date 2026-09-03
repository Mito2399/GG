# GG/app/context_processors.py
# Adds role flags to every template automatically.
#
# Revised roles:
#   Admin (Manager)   — full access, including employee management.
#   Accounting Staff  — same as Admin except employee management: can add,
#                       view, edit, print financial reports, and manage
#                       payments and bookings.
#   Marketing Staff   — manage bookings only.
#   General Staff     — view-only access (records/lots/bookings) for
#                       inventory purposes.

def role_context(request):
    if not request.user.is_authenticated:
        return {
            "user_role":           None,
            "is_admin":            False,
            "is_accounting_staff": False,
            "is_marketing_staff":  False,
            "is_general_staff":    False,
        }

    if request.user.is_superuser or request.user.username == "admin":
        return {
            "user_role":           "Admin",
            "is_admin":            True,
            "is_accounting_staff": True,   # admin can do everything Accounting can, plus employee mgmt
            "is_marketing_staff":  True,
            "is_general_staff":    True,
        }

    from .models import UserLog
    log  = UserLog.objects.filter(user=request.user).first()
    role = log.role if log else None

    return {
        "user_role":           role,
        "is_admin":            False,
        "is_accounting_staff": role == "Accounting Staff",
        "is_marketing_staff":  role == "Marketing Staff",
        "is_general_staff":    role == "General Staff",
    }
