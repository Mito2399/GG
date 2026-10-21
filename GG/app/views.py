# app/views.py

import calendar as cal_module
import datetime
import json
import math
import openpyxl

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password as django_check_password
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import auth, User
from django.db import transaction
from django.db.models import Q, Sum, Max
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
from collections import defaultdict
from openpyxl.styles import Font, PatternFill, Alignment
from decimal import Decimal, ROUND_HALF_UP

from .forms import (
    BeneficiaryFormSet, BookingForm, ClientForm,
    EmployeeCreateForm, EmployeeUpdateForm, PlanForm,
    IntermentRecipientFormSet, GovernmentIDFormSet,
)
from .models import (
    ActivityLog, Booking, ClientPersonalInfo, ClientStatus,
    Payment, UserLog, SystemSecret, TCTARRenewal,
)

# ─────────────────────────────────────────────── helpers ──────────────────────

def _add_months(dt: datetime.date, months: int, day: int | None = None) -> datetime.date:
    total_months = dt.month - 1 + months
    year  = dt.year + total_months // 12
    month = total_months % 12 + 1

    if day is None:
        day = 1
    last_day = cal_module.monthrange(year, month)[1]
    day = max(1, min(int(day), last_day))

    return datetime.date(year, month, day)


def _build_price_table(cs):
    ZERO = Decimal('0.00')

    def _q(v):
        try:
            return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return ZERO

    if cs.plan == "TCT A/R":
        total_price  = _q(cs.total_contract_price)
        down_payment = _q(cs.down_payment) if cs.down_payment else ZERO
        pcare_pct    = _q(cs.pcare_percent) if cs.pcare_percent else ZERO
        doc_fee      = _q(cs.documentation_fee) if cs.documentation_fee else ZERO

        lot_rate   = Decimal('1') - (pcare_pct / Decimal('100'))
        price_lot   = _q(total_price * lot_rate)
        price_pcare = total_price - price_lot
        dp_lot   = _q(down_payment * lot_rate)
        dp_pcare = down_payment - dp_lot
        bal_total = total_price - down_payment
        bal_lot   = _q(bal_total * lot_rate)
        bal_pcare = bal_total - bal_lot

        return {
            'price_lot':      price_lot,
            'price_pcare':    price_pcare,
            'price_total':    total_price,
            'dp_lot':         dp_lot,
            'dp_pcare':       dp_pcare,
            'dp_total':       down_payment,
            'bal_lot':        bal_lot,
            'bal_pcare':      bal_pcare,
            'bal_total':      bal_total,
            'int_lot':        ZERO,
            'int_pcare':      ZERO,
            'int_total':      ZERO,
            'final_lot':      bal_lot,
            'final_pcare':    bal_pcare,
            'final_total':    bal_total,
            'documentation':  doc_fee,
        }

    # Standard Plan Fix
    price_lot   = _q(cs.total_contract_price) 
    price_pcare = _q(cs.total_pcare)
    price_total = _q(cs.total_lot)

    dp_lot   = _q(cs.down_payment_lot)
    dp_pcare = _q(cs.down_payment_pcare)
    dp_total = _q(cs.down_payment_total)

    bal_lot   = price_lot   - dp_lot
    bal_pcare = price_pcare - dp_pcare
    bal_total = price_total - dp_total

    return {
        'price_lot':      price_lot,
        'price_pcare':    price_pcare,
        'price_total':    price_total,
        'dp_lot':         dp_lot,
        'dp_pcare':       dp_pcare,
        'dp_total':       dp_total,
        'bal_lot':        bal_lot,
        'bal_pcare':      bal_pcare,
        'bal_total':      bal_total,
        'int_lot':        ZERO,
        'int_pcare':      ZERO,
        'int_total':      ZERO,
        'final_lot':      bal_lot,
        'final_pcare':    bal_pcare,
        'final_total':    bal_total,
        'documentation':  ZERO,
    }


def _get_admin_pin() -> str:
    pin = SystemSecret.get("ADMIN_PIN", "")
    if pin and pin != "0000":
        return pin
    fallback = str(getattr(settings, "ADMIN_PIN", ""))
    if fallback and fallback != "0000":
        return fallback
    return ""


def _get_current_sales_agent_name(user) -> str | None:
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser or user.username == "admin":
        return "Admin"
    log = UserLog.objects.filter(user=user).first()
    if log and log.full_name:
        return log.full_name
    full = user.get_full_name()
    return full or user.username


def _check_pin(user, entered_pin: str) -> bool:
    entered_pin = str(entered_pin).strip()
    if user.is_superuser or user.username == "admin":
        real_pin = _get_admin_pin()
        if not real_pin:
            return False
        return entered_pin == real_pin
    log = UserLog.objects.filter(user=user).first()
    if not log:
        return False
    return django_check_password(entered_pin, log.pin)


def _admin_required(view_func):
    from functools import wraps

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("login")
        if not (request.user.is_superuser or request.user.username == "admin"):
            messages.error(request, "Access denied. Admin only.")
            return redirect("homepage")
        return view_func(request, *args, **kwargs)

    return wrapper


def _require_role(*allowed_roles):
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if request.user.is_superuser or request.user.username == "admin":
                return view_func(request, *args, **kwargs)
            log = UserLog.objects.filter(user=request.user).first()
            if log and log.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            messages.error(request, "You don't have permission to access this page.")
            return redirect("homepage")
        return wrapper
    return decorator


def _log_activity(user, action: str, detail: str = ""):
    staff_name = "Admin"
    role       = "Admin"

    if user.is_authenticated and not (user.is_superuser or user.username == "admin"):
        log = UserLog.objects.filter(user=user).first()
        if log:
            log.activities = action
            log.save(update_fields=["time_in", "time_out", "activities"])
            staff_name = log.full_name or user.username
            role       = log.role or "—"

    ActivityLog.objects.create(
        user=user if user.is_authenticated else None,
        staff_name=staff_name,
        role=role,
        action=action,
        detail=detail,
    )


def _check_write_role(request, *allowed_roles) -> bool:
    if request.user.is_superuser or request.user.username == "admin":
        return True
    log = UserLog.objects.filter(user=request.user).first()
    return bool(log and log.role in allowed_roles)


def _get_active_status(client):
    return (
        ClientStatus.objects
        .filter(client=client, status=True, is_cancelled=False)
        .exclude(plan="No Plan")
        .order_by("-pk")
        .first()
    ) or ClientStatus.objects.filter(client=client).order_by("-pk").first()


# ═══════════════════════════════════════════════════════════════════════════
# SCHEDULE GENERATOR
# ═══════════════════════════════════════════════════════════════════════════
def _ensure_schedule_row(cs):
    """
    Ensures the FULL payment schedule exists for this plan.
    Idempotent: safe to call on every view.
    """
    if not cs.duration or cs.duration <= 0:
        return None

    existing_nos = set(
        cs.payments.values_list("installment_no", flat=True)
    )
    existing_nos.discard(None)

    missing = [i for i in range(1, cs.duration + 1) if i not in existing_nos]
    if not missing:
        return None

    due_day = getattr(cs, "due_day", None) or 1
    lot_monthly = cs.monthly_lot
    pcare_monthly = cs.monthly_pcare

    to_create = []
    for inst_no in missing:
        month_date = _add_months(cs.start_date, inst_no - 1, day=due_day)
        to_create.append(Payment(
            client_status=cs,
            month=month_date,
            amount=0,
            installment_due=lot_monthly + pcare_monthly,
            lot_amount=lot_monthly,
            pcare_amount=pcare_monthly,
            installment_no=inst_no,
            is_paid=False,
        ))

    if to_create:
        Payment.objects.bulk_create(to_create)

    return None


def _plan_location_string(plan):
    if plan.plan == "Lawn Lot":
        parts = []
        if plan.lawn_lot_type:      parts.append(f"Lawn Lot {plan.lawn_lot_type}")
        if plan.regular_lot_package: parts.append(plan.regular_lot_package)
        if plan.phase:              parts.append(f"Ph {plan.phase}")
        if plan.block:              parts.append(f"Blk {plan.block}")
        if plan.section:            parts.append(f"Sec {plan.section}")
        if plan.lot_number:         parts.append(f"Lot {plan.lot_number}")
        return " / ".join(parts) if parts else "—"
    if plan.plan == "Garden Lot":
        parts = []
        if plan.garden_type:    parts.append(f"Garden {plan.garden_type}")
        if plan.garden_section: parts.append(plan.garden_section)
        if plan.phase:          parts.append(f"Ph {plan.phase}")
        if plan.block:          parts.append(f"Blk {plan.block}")
        if plan.section:        parts.append(f"Sec {plan.section}")
        if plan.lot_number:     parts.append(f"Lot {plan.lot_number}")
        return " / ".join(parts) if parts else "—"
    if plan.plan == "Mausoleum":
        parts = []
        if plan.mausoleum_type: parts.append(plan.mausoleum_type)
        if plan.sqm:            parts.append(f"{plan.sqm} sqm")
        if plan.phase:          parts.append(f"Ph {plan.phase}")
        if plan.block:          parts.append(f"Blk {plan.block}")
        if plan.section:        parts.append(f"Sec {plan.section}")
        if plan.lot_number:     parts.append(f"Lot {plan.lot_number}")
        return " / ".join(parts) if parts else "—"
    if plan.plan == "THS":
        return f"THS — {plan.ths_section or '—'}, Lvl {plan.column_level or '—'}, Col {plan.ths_column or '—'}"
    if plan.plan == "THTC":
        return f"THTC — {plan.section or '—'}, Lvl {plan.column_level or '—'}, Col {plan.ths_column or '—'}"
    if plan.plan == "TCT A/R":
        return f"TCT A/R — {plan.columbarium_type or '—'}, Lvl {plan.column_level or '—'}, Tomb {plan.tomb_number or '—'}"
    parts = []
    if plan.phase:      parts.append(f"Ph {plan.phase}")
    if plan.block:      parts.append(f"Blk {plan.block}")
    if plan.section:    parts.append(f"Sec {plan.section}")
    if plan.lot_number: parts.append(f"Lot {plan.lot_number}")
    return " / ".join(parts) if parts else "—"


def _format_masterlist_lot_desc(plan):
    if plan.plan in ["Lawn Lot", "Garden Lot", "Mausoleum"]:
        parts = []
        if plan.phase:      parts.append(f"P{plan.phase}")
        if plan.block:      parts.append(f"B{plan.block}")
        if plan.section:    parts.append(f"S{plan.section}")
        if plan.lot_number: parts.append(f"L{plan.lot_number}")
        return ", ".join(parts) if parts else "—"
    elif plan.plan == "TCT A/R":
        return f"TCT A/R Niche - {plan.columbarium_type or ''} L{plan.column_level or ''}"
    else:
        return _plan_location_string(plan)


def _format_recipient_name_for_masterlist(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return "—"
    if "," in raw:
        return raw.upper()
    parts = raw.split()
    if len(parts) == 1:
        return parts[0].upper()
    last = parts[-1]
    rest = " ".join(parts[:-1])
    return f"{last.upper()}, {rest.upper()}"


def _filter_interment_masterlist(request):
    query = request.GET.get("q", "").strip()
    qs = ClientStatus.objects.filter(
        status=True, is_cancelled=False,
        interment_date__isnull=False
    ).exclude(plan="No Plan").select_related("client").prefetch_related("interment_recipients")

    if query:
        terms = [t.strip(', ') for t in query.replace(',', ' ').split() if t.strip(', ')]
        q_objects = Q()
        for term in terms:
            if len(term) > 1 and term[0].upper() in ['P', 'B', 'S', 'L'] and term[1:].replace('.', '').isdigit():
                prefix = term[0].upper()
                val = term[1:].replace('.', '')
                if prefix == 'P': q_objects |= Q(phase__icontains=val)
                elif prefix == 'B': q_objects |= Q(block__icontains=val)
                elif prefix == 'S': q_objects |= Q(section__icontains=val)
                elif prefix == 'L': q_objects |= Q(lot_number__icontains=val)
            elif term.isdigit() and len(term) == 4:
                q_objects |= Q(interment_date__year=term)
            else:
                q_objects |= Q(interment_recipients__name__icontains=term)
                q_objects |= Q(plan__icontains=term)
                q_objects |= Q(pa_number__icontains=term)
                q_objects |= Q(la_number__icontains=term)
                q_objects |= Q(client__client_first_name__icontains=term)
                q_objects |= Q(client__client_last_name__icontains=term)
                q_objects |= Q(phase__icontains=term)
                q_objects |= Q(block__icontains=term)
                q_objects |= Q(section__icontains=term)
                q_objects |= Q(lot_number__icontains=term)
        qs = qs.filter(q_objects).distinct()

    return qs, query


def _build_interment_masterlist(qs):
    masterlist = []
    for plan in qs:
        lot_desc       = _format_masterlist_lot_desc(plan).upper()
        classification = plan.plan.upper()
        pa_no          = plan.la_number if plan.plan == "TCT A/R" else plan.pa_number
        pa_no          = str(pa_no).upper() if pa_no else "—"

        first_name  = (plan.client.client_first_name  or "").upper()
        middle_name = (plan.client.client_middle_name or "").upper()
        last_name   = (plan.client.client_last_name   or "").upper()
        middle_part            = f" {middle_name}" if middle_name else ""
        formatted_client_name  = f"{last_name}, {first_name}{middle_part}".strip()

        recipients = list(plan.interment_recipients.all())
        if not recipients:
            masterlist.append({
                "recipient_name": "—", "interment_date": plan.interment_date,
                "lot_description": lot_desc, "classification": classification,
                "pa_no": pa_no, "client": plan.client,
                "client_name_formatted": formatted_client_name,
            })
        else:
            for recipient in recipients:
                masterlist.append({
                    "recipient_name": _format_recipient_name_for_masterlist(recipient.name),
                    "interment_date": plan.interment_date,
                    "lot_description": lot_desc, "classification": classification,
                    "pa_no": pa_no, "client": plan.client,
                    "client_name_formatted": formatted_client_name,
                })

    masterlist.sort(key=lambda x: (x["recipient_name"].lower(), x["lot_description"].lower()))
    return masterlist


# ─────────────────────────────────────────────── auth ─────────────────────────

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = auth.authenticate(username=username, password=password)

        if user is not None:
            auth.login(request, user)
            log = UserLog.objects.filter(user=user).first()
            if log:
                log.time_in    = timezone.now()
                log.time_out   = None
                log.activities = "Login"
                log.save()
            staff_name = "Admin"
            role       = "Admin"
            if not (user.is_superuser or user.username == "admin"):
                ulog = UserLog.objects.filter(user=user).first()
                if ulog:
                    staff_name = ulog.full_name or user.username
                    role       = ulog.role or "—"
            ActivityLog.objects.create(
                user=user, staff_name=staff_name, role=role,
                action="Login", detail="",
            )
            return redirect("homepage")

        messages.error(request, "Invalid username or password.")
        return redirect("login")

    return render(request, "app/login.html")


@login_required(login_url="login")
@require_POST
def logout(request):
    if not (request.user.is_superuser or request.user.username == "admin"):
        log = UserLog.objects.filter(user=request.user).first()
        if log:
            log.time_out   = timezone.now()
            log.activities = "Logout"
            log.save()
    staff_name = "Admin"
    role       = "Admin"
    if not (request.user.is_superuser or request.user.username == "admin"):
        ulog = UserLog.objects.filter(user=request.user).first()
        if ulog:
            staff_name = ulog.full_name or request.user.username
            role       = ulog.role or "—"
    ActivityLog.objects.create(
        user=request.user, staff_name=staff_name, role=role,
        action="Logout", detail="",
    )
    auth.logout(request)
    return redirect("login")


# ─────────────────────────────────────────────── dashboard ────────────────────

@login_required(login_url="login")
def homepage_view(request):
    total_clients = ClientPersonalInfo.objects.count()
    active_status = (ClientStatus.objects.exclude(plan="No Plan")
                     .filter(status=True, is_cancelled=False).count())
    inactive_count = ClientStatus.objects.filter(plan="No Plan").count()
    completed_count = (ClientStatus.objects.exclude(plan="No Plan")
                       .filter(status=False, is_cancelled=False).count())
    collected = (ClientStatus.objects.aggregate(total=Sum("paid_balance"))["total"] or 0)
    pending_payments = (Payment.objects.filter(is_paid=False)
                        .exclude(client_status__plan="No Plan").count())
    recent_payments = (Payment.objects.filter(is_paid=True)
                       .select_related("client_status__client", "processed_by")
                       .order_by("-date_paid")[:5])
    is_admin = request.user.is_superuser or request.user.username == "admin"
    activity_qs = ActivityLog.objects.order_by("-timestamp")
    if not is_admin:
        activity_qs = activity_qs.exclude(role="Admin")
    recent_activity = activity_qs[:8]

    return render(request, "app/homepage.html", {
        "total_clients":    total_clients,
        "active_status":    active_status,
        "inactive_count":   inactive_count,
        "completed_count":  completed_count,
        "collected":        collected,
        "pending_payments": pending_payments,
        "recent_payments":  recent_payments,
        "recent_activity":  recent_activity,
    })


# ─────────────────────────────────────────────── clients ──────────────────────

@login_required(login_url="login")
def add_client_view(request):
    if not _check_write_role(request, "Accounting Staff"):
        messages.error(request, "Access restricted. Only Accounting Staff can add new clients.")
        return redirect("records")

    if request.method == "POST":
        form                 = ClientForm(request.POST)
        beneficiary_formset  = BeneficiaryFormSet(request.POST, prefix="beneficiaries")
        government_id_formset = GovernmentIDFormSet(request.POST, prefix="government_ids")

        if (form.is_valid() and beneficiary_formset.is_valid()
                and government_id_formset.is_valid()):
            client = form.save(commit=False)
            if ClientPersonalInfo.objects.filter(
                client_first_name__iexact=client.client_first_name,
                client_last_name__iexact=client.client_last_name,
                client_date_birth=client.client_date_birth,
            ).exists():
                form.add_error(None, "A client with this name and date of birth already exists.")
                return render(request, "app/addclient.html", {
                    "form": form, "beneficiary_formset": beneficiary_formset,
                    "government_id_formset": government_id_formset,
                })

            with transaction.atomic():
                client.save()
                beneficiary_formset.instance = client
                beneficiary_formset.save()
                government_id_formset.instance = client
                government_id_formset.save()

                today = datetime.date.today()
                cs = ClientStatus.objects.create(
                    client=client, plan="No Plan",
                    monthly_payment=Decimal("0.00"), duration=0,
                    months_remaining=0, start_date=today,
                    balance=Decimal("0.00"), paid_balance=Decimal("0.00"),
                    status=False, total_price=Decimal("0.00"), due_day=2,
                )
                _ensure_schedule_row(cs)

            _log_activity(request.user, "Add Client", f"Client: {client.full_name}")
            messages.success(request, f"Client '{client.full_name}' added successfully.")
            return redirect("records")
    else:
        form                  = ClientForm()
        beneficiary_formset   = BeneficiaryFormSet(prefix="beneficiaries")
        government_id_formset = GovernmentIDFormSet(prefix="government_ids")

    return render(request, "app/addclient.html", {
        "form": form, "beneficiary_formset": beneficiary_formset,
        "government_id_formset": government_id_formset,
    })


def _filter_client_records(request):
    query   = request.GET.get("q", "").strip()
    clients = ClientPersonalInfo.objects.all().order_by("client_last_name", "client_first_name")
    if query:
        clients = clients.filter(
            Q(client_first_name__icontains=query) |
            Q(client_middle_name__icontains=query) |
            Q(client_last_name__icontains=query) |
            Q(client_contact_number__icontains=query) |
            Q(client_civil_status__icontains=query) |
            Q(clientstatus__plan__icontains=query) |
            Q(clientstatus__pa_number__icontains=query) |
            Q(clientstatus__la_number__icontains=query) |
            Q(clientstatus__tomb_number__icontains=query)
        ).distinct()
    active_filters = {"Search": query} if query else {}
    return clients, query, active_filters


@login_required(login_url="login")
def records_view(request):
    clients, query, active_filters = _filter_client_records(request)
    is_ajax = (request.headers.get("X-Requested-With") == "XMLHttpRequest"
               or request.GET.get("ajax") == "1")

    if is_ajax:
        from django.template.loader import render_to_string
        rows_html = render_to_string(
            "app/partials/records_tbody.html",
            {"client": clients, "query": query},
            request=request,
        )
        return JsonResponse({
            "success": True, "html": rows_html,
            "count": clients.count(), "query": query,
        })

    return render(request, "app/records.html", {
        "client": clients, "query": query, "active_filters": active_filters,
    })


@login_required(login_url="login")
def client_details_view(request, pk):
    client      = get_object_or_404(ClientPersonalInfo, pk=pk)
    all_statuses = (ClientStatus.objects.filter(client=client)
                    .exclude(plan="No Plan").order_by("-pk"))
    return render(request, "app/client-details.html", {
        "client": client, "all_statuses": all_statuses,
    })


@login_required(login_url="login")
def edit_details_view(request, pk):
    client = get_object_or_404(ClientPersonalInfo, pk=pk)

    if request.method == "POST":
        if not _check_write_role(request, "Accounting Staff"):
            messages.error(request, "Access restricted. Only Accounting Staff can edit client records.")
            return redirect("client-details", pk=pk)
        form                  = ClientForm(request.POST, instance=client)
        beneficiary_formset   = BeneficiaryFormSet(request.POST, instance=client, prefix="beneficiaries")
        government_id_formset = GovernmentIDFormSet(request.POST, instance=client, prefix="government_ids")

        if (form.is_valid() and beneficiary_formset.is_valid()
                and government_id_formset.is_valid()):
            with transaction.atomic():
                form.save()
                beneficiary_formset.save()
                government_id_formset.save()
            _log_activity(request.user, "Edit Record", f"Client: {client.full_name}")
            messages.success(request, "Client updated successfully.")
            return redirect("records")
    else:
        form                  = ClientForm(instance=client)
        beneficiary_formset   = BeneficiaryFormSet(instance=client, prefix="beneficiaries")
        government_id_formset = GovernmentIDFormSet(instance=client, prefix="government_ids")

    return render(request, "app/edit_details.html", {
        "form": form, "beneficiary_formset": beneficiary_formset,
        "government_id_formset": government_id_formset, "client": client,
    })


@login_required(login_url="login")
def delete_client_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)
    if not _check_write_role(request, "Accounting Staff"):
        return JsonResponse({"success": False, "error": "Access restricted."})
    if not _check_pin(request.user, request.POST.get("pin", "")):
        return JsonResponse({"success": False, "error": "Invalid PIN."})
    client = get_object_or_404(ClientPersonalInfo, pk=pk)
    name   = client.full_name
    client.delete()
    _log_activity(request.user, "Delete Client", f"Client: {name}")
    return JsonResponse({"success": True, "name": name})


# ─────────────────────────────────────────────── payments ─────────────────────

@_require_role("Accounting Staff")
def add_payment_view(request, pk):
    client      = get_object_or_404(ClientPersonalInfo, pk=pk)
    all_statuses = (ClientStatus.objects.filter(client=client)
                    .exclude(plan="No Plan").order_by("-pk"))
    for cs in all_statuses:
        _ensure_schedule_row(cs)
    return render(request, "app/add_payment.html", {
        "client": client, "all_statuses": all_statuses,
    })


# ═══════════════════════════════════════════════════════════════════════════
# PAYMENT HISTORY VIEW (The core accounting engine)
# ═══════════════════════════════════════════════════════════════════════════
@_require_role("Accounting Staff")
def payment_history_view(request, pk):
    client = get_object_or_404(ClientPersonalInfo, pk=pk)
    all_statuses = (ClientStatus.objects.filter(client=client)
                    .exclude(plan="No Plan").order_by("-pk"))
    if not all_statuses.exists():
        messages.info(request, "This client has no plan assigned yet.")
        return redirect("add-payment", pk=pk)

    if request.method == "POST":
        if not _check_write_role(request, "Accounting Staff"):
            return JsonResponse({"success": False, "error": "Access restricted."})
        if not _check_pin(request.user, request.POST.get("pin", "")):
            return JsonResponse({"success": False, "error": "Invalid PIN."})

        try:
            amount = Decimal(request.POST.get("amount", "0"))
        except Exception:
            return JsonResponse({"success": False, "error": "Invalid amount."})
        if amount <= 0:
            return JsonResponse({"success": False, "error": "Amount must be greater than zero."})

        note           = request.POST.get("note", "").strip()
        csi_number     = request.POST.get("csi_number", "").strip()

        date_paid_str = request.POST.get("date_paid", "").strip()
        if date_paid_str:
            try:
                parsed_date = datetime.datetime.strptime(date_paid_str, "%Y-%m-%d").date()
                if parsed_date > datetime.date.today():
                    return JsonResponse({"success": False, "error": "Payment date cannot be in the future."})
                local_tz = timezone.get_current_timezone()
                date_paid = timezone.make_aware(
                    datetime.datetime.combine(parsed_date, datetime.time(12, 0)),
                    local_tz
                )
            except ValueError:
                return JsonResponse({"success": False, "error": "Invalid date format."})
        else:
            date_paid = timezone.now()

        with transaction.atomic():
            try:
                cs = (ClientStatus.objects.select_for_update()
                      .get(pk=request.POST.get("client_status_id"), client=client))
            except ClientStatus.DoesNotExist:
                return JsonResponse({"success": False, "error": "Plan not found."})
            if cs.is_cancelled:
                return JsonResponse({"success": False, "error": "This plan is cancelled."})

            _ensure_schedule_row(cs)

            unpaid_rows = list(cs.payments.filter(is_paid=False).order_by("month"))
            
            # 1. Penalty Calculation
            today = timezone.localdate()
            overdue_lot_rows = [r for r in unpaid_rows if r.month < today and r.lot_amount > 0]
            total_overdue_lot = sum(r.lot_amount for r in overdue_lot_rows)

            last_payment = cs.payments.filter(is_paid=True).order_by("-date_paid").first()
            previous_penalty = last_payment.penalty_charges if last_payment else Decimal('0.00')

            penalty = Decimal(0)
            if total_overdue_lot > 0:
                base_penalty = (total_overdue_lot * cs.penalty_rate / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                penalty = base_penalty + previous_penalty

            # 2. Deduct penalty from amount first
            amount_for_dues = amount - penalty
            if amount_for_dues < 0:
                amount_for_dues = Decimal('0.00')
                penalty = amount

            # 3. Allocate to unpaid rows in order
            covered_rows = []
            lot_payment_total = Decimal('0.00')
            pcare_payment_total = Decimal('0.00')
            
            for r in unpaid_rows:
                if amount_for_dues <= 0:
                    break
                    
                row_lot_due = r.lot_amount
                row_pcare_due = r.pcare_amount
                row_total_due = row_lot_due + row_pcare_due
                
                if amount_for_dues >= row_total_due:
                    # Fully covered
                    covered_rows.append((r, row_lot_due, row_pcare_due))
                    lot_payment_total += row_lot_due
                    pcare_payment_total += row_pcare_due
                    amount_for_dues -= row_total_due
                else:
                    # Partial payment
                    ratio = amount_for_dues / row_total_due
                    lot_paid = (row_lot_due * ratio).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                    pcare_paid = amount_for_dues - lot_paid
                    
                    covered_rows.append((r, lot_paid, pcare_paid))
                    lot_payment_total += lot_paid
                    pcare_payment_total += pcare_paid
                    amount_for_dues = Decimal('0.00')
            
            overpayment = amount_for_dues

            # 4. Calculate Balances
            ZERO = Decimal('0.00')
            starting_lot_bal = cs.total_contract_price - cs.down_payment_lot
            starting_pc_bal = cs.total_pcare - cs.down_payment_pcare

            paid_lot = sum((p.lot_amount or ZERO) for p in cs.payments.filter(is_paid=True))
            paid_pcare = sum((p.pcare_amount or ZERO) for p in cs.payments.filter(is_paid=True))

            new_lot_balance = max(starting_lot_bal - (paid_lot + lot_payment_total), ZERO)
            new_pcare_balance = max(starting_pc_bal - (paid_pcare + pcare_payment_total), ZERO)
            new_total_balance = new_lot_balance + new_pcare_balance

            # 5. Save Payment Records
            payment = None
            for idx, (r, lot_paid, pcare_paid) in enumerate(covered_rows):
                r.is_paid = True
                r.date_paid = date_paid
                r.csi_number = csi_number
                r.processed_by = request.user
                if idx == 0:
                    r.amount = amount
                    r.lot_amount = lot_payment_total
                    r.pcare_amount = pcare_payment_total
                    r.penalty_charges = penalty
                    r.installment_due = len(covered_rows) * cs.monthly_lot
                    r.overpayment = overpayment
                    r.running_balance = new_lot_balance
                    r.running_pcare_balance = new_pcare_balance
                    r.running_total_balance = new_total_balance
                    r.note = note
                    payment = r
                else:
                    r.amount = 0
                    r.lot_amount = 0
                    r.pcare_amount = 0
                    r.note = f"Covered by payment on {date_paid.strftime('%b %d, %Y')}"
                r.save()

            cs.paid_balance += amount
            cs.balance = new_total_balance
            if cs.monthly_payment > 0:
                cs.months_remaining = int(-(-new_total_balance // cs.monthly_payment))
            if new_total_balance <= 0:
                cs.status = False
                cs.date_fully_paid = datetime.date.today()
            cs.save()

        _log_activity(
            request.user, "Add Payment",
            f"Client: {client.full_name} — {cs.plan} — ₱{amount} "
            f"(Paid: {date_paid.strftime('%b %d, %Y')})"
        )

        return JsonResponse({"success": True})

    # ── GET: build ledger display ──────────────────────────────────────
    selected_pk = request.GET.get("plan")
    if selected_pk:
        try:
            client_status = all_statuses.get(pk=selected_pk)
        except ClientStatus.DoesNotExist:
            client_status = _get_active_status(client) or all_statuses.first()
    else:
        client_status = _get_active_status(client) or all_statuses.first()

    _ensure_schedule_row(client_status)
    all_payments = client_status.payments.all().order_by("month", "date_paid")
    price_table = _build_price_table(client_status)

    ZERO = Decimal('0.00')
    
    starting_lot_bal = client_status.total_contract_price - client_status.down_payment_lot
    starting_pc_bal = client_status.total_pcare - client_status.down_payment_pcare
    current_total_balance = starting_lot_bal + starting_pc_bal

    # Build payment lookup for covered counts
    payment_lookup = {}
    for p in all_payments:
        if p.is_paid and (p.amount or ZERO) > 0:
            covered = [x for x in all_payments if x.is_paid and x.date_paid == p.date_paid and x.csi_number == p.csi_number]
            payment_lookup[p.pk] = {
                "covered_count": len(covered),
            }

    # Build unified events list to sort chronologically
    events = []
    for p in all_payments:
        if p.month is not None:
            events.append({"date": p.month, "kind": "schedule", "payment": p})
        if p.is_paid and (p.amount or ZERO) > 0:
            events.append({"date": p.date_paid.date(), "kind": "payment", "payment": p})

    events.sort(key=lambda x: x["date"])

    ledger_rows = []
    running_lot = ZERO
    running_pcare = ZERO
    cumulative_lot_due = ZERO
    cumulative_pcare_due = ZERO
    previous_penalty = ZERO
    today = timezone.localdate()

    for event in events:
        p = event["payment"]
        
        if event["kind"] == "schedule":
            if not p.is_paid and client_status.is_cancelled:
                continue

            cumulative_lot_due += p.lot_amount or ZERO
            cumulative_pcare_due += p.pcare_amount or ZERO

            if not p.is_paid and p.month < today:
                base_penalty = (cumulative_lot_due * client_status.penalty_rate / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP)
                accrued_penalty = base_penalty + previous_penalty
                previous_penalty = accrued_penalty
            else:
                accrued_penalty = ZERO

            ledger_rows.append({
                "kind": "schedule",
                "payment": p,
                "installment_no": p.installment_no or "",
                "csi_number": "",
                "date": p.month,
                "lot_amount": client_status.monthly_lot,
                "pcare_amount": client_status.monthly_pcare,
                "installment_due": cumulative_lot_due,
                "pc_installment_due": cumulative_pcare_due,
                "amount_paid": ZERO,
                "penalty_charges": accrued_penalty,
                "payment_charges": ZERO,
                "pc_payment_charges": ZERO,
                "lot_balance": starting_lot_bal - running_lot,
                "pc_balance": starting_pc_bal - running_pcare,
                "total_balance": current_total_balance,
                "is_first_schedule": (p.installment_no == 1),
            })

        elif event["kind"] == "payment":
            running_lot += p.lot_amount or ZERO
            running_pcare += p.pcare_amount or ZERO

            lot_bal_after = max(starting_lot_bal - running_lot, ZERO)
            pcare_bal_after = max(starting_pc_bal - running_pcare, ZERO)
            current_total_balance = lot_bal_after + pcare_bal_after

            lookup = payment_lookup.get(p.pk, {})
            covered_count = lookup.get("covered_count", 1)
            
            covered_lot_due = covered_count * client_status.monthly_lot
            covered_pcare_due = covered_count * client_status.monthly_pcare

            ledger_rows.append({
                "kind": "payment",
                "payment": p,
                "installment_no": "",
                "csi_number": p.csi_number or "",
                "date": p.date_paid,
                "lot_amount": ZERO,
                "pcare_amount": ZERO,
                "installment_due": covered_lot_due,
                "pc_installment_due": covered_pcare_due,
                "amount_paid": p.amount,
                "penalty_charges": ZERO, # Hidden in template
                "payment_charges": p.lot_amount or ZERO,
                "pc_payment_charges": p.pcare_amount or ZERO,
                "lot_balance": lot_bal_after,
                "pc_balance": pcare_bal_after,
                "total_balance": current_total_balance,
                "is_first_schedule": False,
            })

            cumulative_lot_due = ZERO
            cumulative_pcare_due = ZERO
            previous_penalty = ZERO

    return render(request, "app/payment_history.html", {
        "client":        client,
        "client_status": client_status,
        "all_statuses":  all_statuses,
        "ledger_rows":   ledger_rows,
        "payments":      client_status.payments.filter(is_paid=True).order_by("-date_paid"),
        "price_table":   price_table,
    })


# ─────────────────────────────────────────── renew TCT/A/R ────────────────────

@login_required(login_url="login")
def renew_tct_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)
    if not _check_write_role(request, "Accounting Staff"):
        return JsonResponse({"success": False, "error": "Access restricted."})
    if not _check_pin(request.user, request.POST.get("pin", "")):
        return JsonResponse({"success": False, "error": "Invalid PIN."})

    note = request.POST.get("note", "").strip()

    with transaction.atomic():
        try:
            cs = ClientStatus.objects.select_for_update().get(pk=pk)
        except ClientStatus.DoesNotExist:
            return JsonResponse({"success": False, "error": "Plan not found."})
        if cs.plan != "TCT A/R":
            return JsonResponse({"success": False, "error": "Only TCT/A/R plans can be renewed."})
        if cs.is_cancelled:
            return JsonResponse({"success": False, "error": "This TCT/A/R is cancelled."})

        today   = timezone.localdate()
        initial = cs.tct_initial_expiration_date
        if initial is None:
            return JsonResponse({"success": False, "error": "Initial 7-year expiration not found."})
        if today <= initial:
            return JsonResponse({"success": False,
                "error": f"The initial 7-year term has not yet ended (expires {initial.strftime('%b %d, %Y')})."})

        previous_exp = cs.tct_current_expiration_date
        if previous_exp is None:
            return JsonResponse({"success": False, "error": "No active expiration date found."})

        try:
            new_exp = previous_exp.replace(year=previous_exp.year + 1)
        except ValueError:
            new_exp = previous_exp.replace(year=previous_exp.year + 1, day=28)

        cs.tct_renewals.filter(status="Active").update(status="Superseded")
        renewal = TCTARRenewal.objects.create(
            client_status=cs,
            renewal_number=cs.tct_next_renewal_number,
            previous_expiration_date=previous_exp,
            renewal_date=today, new_expiration_date=new_exp,
            renewal_period_years=1, status="Active", note=note,
            processed_by=request.user,
        )

    _log_activity(request.user, "Renew TCT A/R",
        f"{cs.client.full_name} — Renewal #{renewal.renewal_number}: {previous_exp} → {new_exp}")

    return JsonResponse({
        "success": True, "renewal_id": renewal.pk,
        "renewal_number": renewal.renewal_number,
        "previous_expiration": previous_exp.strftime("%b %d, %Y"),
        "new_expiration": new_exp.strftime("%b %d, %Y"),
    })


# ─────────────────────────────────────────────── plan ─────────────────────────

@_require_role("Accounting Staff")
def plan(request, pk):
    client = get_object_or_404(ClientPersonalInfo, pk=pk)
    plans  = ClientStatus.objects.filter(client=client)
    form   = PlanForm()
    recipient_formset = IntermentRecipientFormSet(instance=None, prefix="interment_recipients")

    if request.method == "POST":
        if not _check_write_role(request, "Accounting Staff"):
            messages.error(request, "Access restricted. Only Accounting Staff can assign plans.")
            return redirect("plan", pk=pk)

        form = PlanForm(request.POST)
        recipient_formset = IntermentRecipientFormSet(request.POST, prefix="interment_recipients")

        if form.is_valid() and recipient_formset.is_valid():
            d         = form.cleaned_data
            plan_name = d["plan"]
            today     = datetime.date.today()

            total_lot         = d["total_price"]
            down_payment      = d.get("down_payment") or Decimal('0')
            pcare_percent     = d.get("pcare_percent") or Decimal('0.00')
            documentation_fee = d.get("documentation_fee") or Decimal('0.00')

            is_tct = (plan_name == "TCT A/R")

            if is_tct:
                duration = 0
                monthly  = Decimal('0.00')
                financed_balance = total_lot - down_payment
                starting_lot_balance = (financed_balance * (
                    Decimal('1') - pcare_percent / Decimal('100')
                )).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                discount_percent = d.get("discount_percent") or 0
                starting_total_bal = financed_balance
            else:
                duration = d["duration"]
                if not duration or duration < 1:
                    messages.error(request, "Duration must be at least 1 month.")
                    return render(request, "app/plan.html", {
                        "client": client, "plans": plans, "form": form,
                        "recipient_formset": recipient_formset,
                    })
                
                # FIXED DP SPLIT LOGIC
                pcare_pct = Decimal(pcare_percent)
                total_pcare = (total_lot * (pcare_pct / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_contract_price = total_lot - total_pcare

                dp_total = down_payment
                dp_pcare = (dp_total * (pcare_pct / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                dp_lot   = dp_total - dp_pcare

                starting_lot_bal = total_contract_price - dp_lot
                starting_pc_bal  = total_pcare - dp_pcare
                starting_total_bal = starting_lot_bal + starting_pc_bal

                monthly_lot   = (starting_lot_bal / duration).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                monthly_pcare = (starting_pc_bal  / duration).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                monthly = monthly_lot + monthly_pcare

                discount_percent     = d.get("discount_percent") or 0
                starting_lot_balance = total_contract_price - dp_lot

            phase            = d.get("phase", "").strip() or None
            block            = d.get("block", "").strip() or None
            section          = d.get("section", "").strip() or None
            lot_number       = d.get("lot_number", "").strip() or None
            pa_number        = d.get("pa_number", "").strip() or None
            la_number        = d.get("la_number", "").strip() or None
            interment_date   = d.get("interment_date")
            pa_date          = d.get("pa_date")
            date_of_death            = d.get("date_of_death")
            death_certificate_number = d.get("death_certificate_number", "").strip() or None
            column_level     = d.get("column_level", "").strip() or None
            ths_type         = d.get("ths_type", "").strip() or None
            ths_section      = d.get("ths_section", "").strip() or None
            ths_column       = d.get("ths_column", "").strip() or None
            columbarium_type = d.get("columbarium_type", "").strip() or None
            columbarium_level= d.get("columbarium_level") or None
            tomb_number      = d.get("tomb_number", "").strip() or None
            remains_type       = d.get("remains_type", "").strip() or None
            remains_type_other = d.get("remains_type_other", "").strip() or None
            mausoleum_type       = d.get("mausoleum_type", "").strip() or None
            sqm                  = d.get("sqm")
            lawn_lot_type        = d.get("lawn_lot_type", "").strip() or None
            regular_lot_package  = d.get("regular_lot_package", "").strip() or None
            garden_type          = d.get("garden_type", "").strip() or None
            garden_section       = d.get("garden_section", "").strip() or None
            due_day              = d.get("due_day") or 2

            blocking = plans.exclude(plan="No Plan").filter(is_cancelled=False, status=True)
            if blocking.exists():
                messages.error(request, "This client already has an active plan. Cancel or complete it first.")
                return render(request, "app/plan.html", {
                    "client": client, "plans": plans, "form": form,
                    "recipient_formset": recipient_formset,
                })

            no_plan = plans.filter(plan="No Plan").first()

            def _apply(cs):
                if cs.pk:
                    cs.payments.all().delete()
                    cs.tct_renewals.all().delete()
                cs.plan              = plan_name
                cs.monthly_payment   = monthly
                cs.total_price       = total_lot
                cs.duration          = duration
                cs.months_remaining  = duration
                cs.start_date        = today
                cs.balance           = starting_total_bal
                cs.paid_balance      = Decimal('0.00')
                cs.status            = True
                cs.date_paid         = None
                cs.down_payment      = down_payment
                cs.discount_percent  = discount_percent
                cs.pcare_percent     = pcare_percent
                cs.documentation_fee = documentation_fee
                cs.sales_agent       = _get_current_sales_agent_name(request.user)
                cs.due_day           = due_day
                cs.phase             = phase
                cs.block             = block
                cs.section           = section
                cs.lot_number        = lot_number
                cs.pa_number         = pa_number
                cs.la_number         = la_number
                cs.interment_date    = interment_date
                cs.pa_date           = pa_date
                cs.date_of_death            = date_of_death
                cs.death_certificate_number = death_certificate_number
                cs.column_level      = column_level
                cs.ths_type          = ths_type
                cs.ths_section       = ths_section
                cs.ths_column        = ths_column
                cs.columbarium_type  = columbarium_type
                cs.columbarium_level = columbarium_level
                cs.tomb_number       = tomb_number
                cs.mausoleum_type    = mausoleum_type
                cs.sqm               = sqm
                cs.lawn_lot_type        = lawn_lot_type
                cs.regular_lot_package  = regular_lot_package
                cs.garden_type          = garden_type
                cs.garden_section       = garden_section
                cs.remains_type         = remains_type
                cs.remains_type_other   = remains_type_other if remains_type == "Others" else None
                cs.is_cancelled        = False
                cs.cancellation_reason = None
                cs.cancellation_date   = None
                cs.date_fully_paid     = None
                cs.save()
                _ensure_schedule_row(cs)

            if no_plan:
                _apply(no_plan)
                cs = no_plan
            else:
                cs = ClientStatus(client=client)
                _apply(cs)

            recipient_formset.instance = cs
            recipient_formset.save()

            _log_activity(request.user, "Add Plan", f"Client: {client.full_name} — Plan: {plan_name}")
            messages.success(request, f"Plan '{plan_name}' has been assigned successfully.")
            return redirect("plan", pk=pk)

    return render(request, "app/plan.html", {
        "client": client, "plans": plans, "form": form,
        "recipient_formset": recipient_formset,
    })


# ─────────────────────────────────────────────── edit plan ─────────────────────────

@_require_role("Accounting Staff")
def edit_plan_view(request, pk):
    cs = get_object_or_404(ClientStatus, pk=pk)
    client = cs.client
    has_payments = cs.payments.filter(is_paid=True).exists()

    initial_data = {
        "plan": cs.plan,
        "total_price": cs.total_price or cs.total_contract_price,
        "monthly_payment": cs.monthly_payment,
        "down_payment": cs.down_payment,
        "discount_percent": cs.discount_percent,
        "pcare_percent": cs.pcare_percent,
        "duration": cs.duration,
        "due_day": cs.due_day,
        "phase": cs.phase, "block": cs.block, "section": cs.section,
        "lot_number": cs.lot_number, "pa_number": cs.pa_number, "la_number": cs.la_number,
        "column_level": cs.column_level,
        "ths_type": cs.ths_type, "ths_section": cs.ths_section, "ths_column": cs.ths_column,
        "columbarium_type": cs.columbarium_type, "columbarium_level": cs.columbarium_level,
        "tomb_number": cs.tomb_number, "interment_date": cs.interment_date,
        "pa_date": cs.pa_date, "date_of_death": cs.date_of_death,
        "death_certificate_number": cs.death_certificate_number,
        "documentation_fee": cs.documentation_fee,
        "mausoleum_type": cs.mausoleum_type, "sqm": cs.sqm,
        "lawn_lot_type": cs.lawn_lot_type, "regular_lot_package": cs.regular_lot_package,
        "garden_type": cs.garden_type, "garden_section": cs.garden_section,
        "remains_type": cs.remains_type, "remains_type_other": cs.remains_type_other,
    }

    form = PlanForm(initial=initial_data)
    recipient_formset = IntermentRecipientFormSet(instance=cs, prefix="interment_recipients")

    if request.method == "POST":
        if not _check_write_role(request, "Accounting Staff"):
            messages.error(request, "Access restricted.")
            return redirect("plan", pk=client.pk)

        if has_payments:
            recipient_formset = IntermentRecipientFormSet(
                request.POST, instance=cs, prefix="interment_recipients")
            if recipient_formset.is_valid():
                recipient_formset.save()
                _log_activity(request.user, "Edit Plan", f"Plan ID: {pk} — Name of Deceased updated")
                messages.success(request, "Name of Deceased updated successfully.")
                return redirect("plan", pk=client.pk)
            return render(request, "app/edit_plan.html", {
                "client": client, "cs": cs, "form": form,
                "recipient_formset": recipient_formset,
                "has_payments": has_payments,
            })

        form = PlanForm(request.POST)
        recipient_formset = IntermentRecipientFormSet(
            request.POST, instance=cs, prefix="interment_recipients")

        if form.is_valid() and recipient_formset.is_valid():
            d = form.cleaned_data
            total_lot         = d["total_price"]
            down_payment      = d.get("down_payment") or Decimal('0')
            pcare_percent     = d.get("pcare_percent") or Decimal('0.00')
            documentation_fee = d.get("documentation_fee") or Decimal('0.00')

            plan_name = d["plan"]
            is_tct    = (plan_name == "TCT A/R")

            if is_tct:
                duration = 0
                monthly  = Decimal('0.00')
                financed_balance = total_lot - down_payment
                starting_lot_balance = (financed_balance * (
                    Decimal('1') - pcare_percent / Decimal('100')
                )).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                discount_percent = d.get("discount_percent") or 0
                starting_total_bal = financed_balance
            else:
                duration = d["duration"]
                if not duration or duration < 1:
                    messages.error(request, "Duration must be at least 1 month.")
                    return render(request, "app/edit_plan.html", {
                        "client": client, "cs": cs, "form": form,
                        "recipient_formset": recipient_formset,
                        "has_payments": has_payments,
                    })
                
                # FIXED DP SPLIT LOGIC
                pcare_pct = Decimal(pcare_percent)
                total_pcare = (total_lot * (pcare_pct / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                total_contract_price = total_lot - total_pcare

                dp_total = down_payment
                dp_pcare = (dp_total * (pcare_pct / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                dp_lot   = dp_total - dp_pcare

                starting_lot_bal = total_contract_price - dp_lot
                starting_pc_bal  = total_pcare - dp_pcare
                starting_total_bal = starting_lot_bal + starting_pc_bal

                monthly_lot   = (starting_lot_bal / duration).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                monthly_pcare = (starting_pc_bal  / duration).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
                monthly = monthly_lot + monthly_pcare

                discount_percent     = d.get("discount_percent") or 0
                starting_lot_balance = total_contract_price - dp_lot

            cs.plan              = plan_name
            cs.monthly_payment   = monthly
            cs.total_price       = total_lot
            cs.duration          = duration
            cs.pcare_percent     = pcare_percent
            cs.documentation_fee = documentation_fee
            cs.balance           = starting_total_bal
            cs.months_remaining  = duration
            cs.down_payment      = down_payment
            cs.discount_percent  = discount_percent
            cs.due_day           = d.get("due_day") or cs.due_day or 2
            cs.phase             = d.get("phase", "").strip() or None
            cs.block             = d.get("block", "").strip() or None
            cs.section           = d.get("section", "").strip() or None
            cs.lot_number        = d.get("lot_number", "").strip() or None
            cs.pa_number         = d.get("pa_number", "").strip() or None
            cs.la_number         = d.get("la_number", "").strip() or None
            cs.interment_date    = d.get("interment_date")
            cs.pa_date           = d.get("pa_date")
            cs.date_of_death            = d.get("date_of_death")
            cs.death_certificate_number = d.get("death_certificate_number", "").strip() or None
            cs.column_level      = d.get("column_level", "").strip() or None
            cs.ths_type          = d.get("ths_type", "").strip() or None
            cs.ths_section       = d.get("ths_section", "").strip() or None
            cs.ths_column        = d.get("ths_column", "").strip() or None
            cs.columbarium_type  = d.get("columbarium_type", "").strip() or None
            cs.columbarium_level = d.get("columbarium_level") or None
            cs.tomb_number       = d.get("tomb_number", "").strip() or None
            cs.mausoleum_type    = d.get("mausoleum_type", "").strip() or None
            cs.sqm               = d.get("sqm")
            cs.lawn_lot_type        = d.get("lawn_lot_type", "").strip() or None
            cs.regular_lot_package  = d.get("regular_lot_package", "").strip() or None
            cs.garden_type          = d.get("garden_type", "").strip() or None
            cs.garden_section       = d.get("garden_section", "").strip() or None
            cs.remains_type         = d.get("remains_type", "").strip() or None
            cs.remains_type_other   = d.get("remains_type_other", "").strip() or None \
                                       if cs.remains_type == "Others" else None
            cs.save()

            cs.payments.all().delete()
            cs.tct_renewals.all().delete()
            _ensure_schedule_row(cs)

            recipient_formset.instance = cs
            recipient_formset.save()

            _log_activity(request.user, "Edit Plan", f"Plan ID: {pk} — {cs.plan}")
            messages.success(request, "Plan updated successfully.")
            return redirect("plan", pk=client.pk)

    return render(request, "app/edit_plan.html", {
        "client": client, "cs": cs, "form": form,
        "recipient_formset": recipient_formset,
        "has_payments": has_payments,
    })


# ─────────────────────────────────────────────── cancel plan ──────────────────

@login_required(login_url="login")
def cancel_plan_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)
    if not _check_write_role(request, "Accounting Staff"):
        return JsonResponse({"success": False, "error": "Access restricted."})
    if not _check_pin(request.user, request.POST.get("pin", "")):
        return JsonResponse({"success": False, "error": "Invalid PIN."})

    cs = get_object_or_404(ClientStatus, pk=pk)
    if cs.is_cancelled:
        return JsonResponse({"success": False, "error": "Plan is already cancelled."})
    if cs.plan == "No Plan":
        return JsonResponse({"success": False, "error": "No active plan to cancel."})

    reason = request.POST.get("reason", "").strip() or "No reason provided."
    cs.status              = False
    cs.is_cancelled        = True
    cs.cancellation_reason = reason
    cs.cancellation_date   = datetime.date.today()
    cs.save()

    cs.tct_renewals.filter(status="Active").update(status="Cancelled")
    _log_activity(request.user, "Cancel Plan", f"Plan ID: {pk} — {cs.plan}")
    return JsonResponse({"success": True})


# ─────────────────────────────────────────────── lots ─────────────────────────

def _filter_lots(request):
    lots = (ClientStatus.objects.exclude(plan="No Plan")
            .select_related("client").order_by("phase", "block", "section", "lot_number"))

    q_type              = request.GET.get("lot_type", "").strip()
    q_phase             = request.GET.get("phase", "").strip()
    q_block             = request.GET.get("block", "").strip()
    q_section           = request.GET.get("section", "").strip()
    q_lot               = request.GET.get("lot_number", "").strip()
    q_status            = request.GET.get("status", "").strip()
    q_column_level      = request.GET.get("column_level", "").strip()
    q_columbarium_type  = request.GET.get("columbarium_type", "").strip()
    q_columbarium_level = request.GET.get("columbarium_level", "").strip()
    q_tomb_number       = request.GET.get("tomb_number", "").strip()
    q_mausoleum_type    = request.GET.get("mausoleum_type", "").strip()
    q_lawn_lot_type     = request.GET.get("lawn_lot_type", "").strip()
    q_garden_type       = request.GET.get("garden_type", "").strip()
    q_garden_section    = request.GET.get("garden_section", "").strip()

    if q_type:              lots = lots.filter(plan__icontains=q_type)
    if q_phase:             lots = lots.filter(phase__icontains=q_phase)
    if q_block:             lots = lots.filter(block__icontains=q_block)
    if q_section:           lots = lots.filter(Q(section__icontains=q_section) | Q(ths_section__icontains=q_section))
    if q_lot:               lots = lots.filter(lot_number__icontains=q_lot)
    if q_column_level:      lots = lots.filter(column_level__icontains=q_column_level)
    if q_columbarium_type:  lots = lots.filter(columbarium_type=q_columbarium_type)
    if q_columbarium_level:
        try: lots = lots.filter(columbarium_level=int(q_columbarium_level))
        except ValueError: pass
    if q_tomb_number:       lots = lots.filter(tomb_number__icontains=q_tomb_number)
    if q_mausoleum_type:    lots = lots.filter(mausoleum_type__icontains=q_mausoleum_type)
    if q_lawn_lot_type:     lots = lots.filter(lawn_lot_type__icontains=q_lawn_lot_type)
    if q_garden_type:       lots = lots.filter(garden_type__icontains=q_garden_type)
    if q_garden_section:    lots = lots.filter(garden_section__icontains=q_garden_section)
    if q_status == "Active":     lots = lots.filter(status=True,  is_cancelled=False)
    elif q_status == "Completed":lots = lots.filter(status=False, is_cancelled=False)
    elif q_status == "Cancelled":lots = lots.filter(is_cancelled=True)

    query_context = {
        "q_type": q_type, "q_phase": q_phase, "q_block": q_block, "q_section": q_section,
        "q_lot": q_lot, "q_status": q_status, "q_column_level": q_column_level,
        "q_columbarium_type": q_columbarium_type, "q_columbarium_level": q_columbarium_level,
        "q_tomb_number": q_tomb_number, "q_mausoleum_type": q_mausoleum_type,
        "q_lawn_lot_type": q_lawn_lot_type, "q_garden_type": q_garden_type,
        "q_garden_section": q_garden_section,
    }
    active_filters = {
        "Lot Type": q_type, "Phase": q_phase, "Block": q_block, "Section": q_section,
        "Lot No.": q_lot, "Column Level": q_column_level, "Col. Type": q_columbarium_type,
        "Col. Level": q_columbarium_level, "Tomb No.": q_tomb_number,
        "Mausoleum Type": q_mausoleum_type, "Lawn Lot Type": q_lawn_lot_type,
        "Garden Type": q_garden_type, "Garden Section": q_garden_section, "Status": q_status,
    }
    active_filters = {k: v for k, v in active_filters.items() if v}
    return lots, query_context, active_filters


@login_required(login_url="login")
def lots_view(request):
    lots, query_context, active_filters = _filter_lots(request)
    plan_choices = [c[0] for c in ClientStatus.PLAN_CHOICES if c[0] != "No Plan"]
    return render(request, "app/lots.html", {
        "lots": lots, "active_filters": active_filters,
        "q_type": query_context["q_type"], "q_phase": query_context["q_phase"],
        "q_block": query_context["q_block"], "q_section": query_context["q_section"],
        "q_lot": query_context["q_lot"], "q_status": query_context["q_status"],
        "q_column_level": query_context["q_column_level"],
        "q_columbarium_type": query_context["q_columbarium_type"],
        "q_columbarium_level": query_context["q_columbarium_level"],
        "q_tomb_number": query_context["q_tomb_number"],
        "q_mausoleum_type": query_context["q_mausoleum_type"],
        "q_lawn_lot_type": query_context["q_lawn_lot_type"],
        "q_garden_type": query_context["q_garden_type"],
        "q_garden_section": query_context["q_garden_section"],
        "plan_choices": plan_choices,
    })


# ─────────────────────────────────────────────── bookings ─────────────────────

@login_required(login_url="login")
def bookings_view(request):
    today = timezone.localdate()
    Booking.objects.filter(status="Active", booking_date__lt=today).update(status="Completed")
    form = BookingForm()

    if request.method == "POST":
        action = request.POST.get("action", "")
        if action == "no_show":
            if not _check_write_role(request, "Accounting Staff", "Marketing Staff"):
                return JsonResponse({"success": False, "error": "Access restricted."})
            if not _check_pin(request.user, request.POST.get("pin", "")):
                return JsonResponse({"success": False, "error": "Invalid PIN."})
            booking = get_object_or_404(Booking, pk=request.POST.get("pk"))
            booking.status              = "No Show"
            booking.cancellation_reason = request.POST.get("reason", "").strip() or "Client did not show up."
            booking.cancelled_at        = timezone.now()
            booking.save()
            _log_activity(request.user, "Cancel Booking", f"{booking.client_name} — No Show on {booking.booking_date}")
            return JsonResponse({"success": True})

        if not _check_write_role(request, "Accounting Staff", "Marketing Staff"):
            messages.error(request, "Access restricted.")
            return redirect("bookings")
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save()
            _log_activity(request.user, "Add Booking",
                f"{booking.client_name} on {booking.booking_date} at {booking.get_booking_time_display()}")
            messages.success(request, f"Booking saved for {booking.client_name}.")
            return redirect("bookings")

    active_plans_by_client = {}
    for cs in (ClientStatus.objects.filter(status=True, is_cancelled=False)
               .exclude(plan="No Plan").order_by("client_id", "-pk")
               .prefetch_related("interment_recipients")):
        if cs.client_id not in active_plans_by_client:
            active_plans_by_client[cs.client_id] = cs

    bookings_list = list(Booking.objects.order_by("-booking_date", "booking_time").select_related("client"))
    for b in bookings_list:
        if b.client_id and b.client_id in active_plans_by_client:
            plan = active_plans_by_client[b.client_id]
            b.client_interment_date       = plan.interment_date
            b.client_plan_name            = plan.plan
            b.client_interment_recipients = [r.name for r in plan.interment_recipients.all()]
        else:
            b.client_interment_date       = None
            b.client_plan_name            = None
            b.client_interment_recipients = []

    active_bookings_qs = Booking.objects.filter(status="Active").values("booking_date", "booking_time", "event_type")
    booked_slots = defaultdict(list)
    day_events   = defaultdict(set)
    for b in active_bookings_qs:
        date_str = b["booking_date"].strftime("%Y-%m-%d")
        booked_slots[date_str].append(b["booking_time"])
        day_events[date_str].add(b["event_type"])
    day_events_json = {d: sorted(types) for d, types in day_events.items()}

    clients_qs = (ClientPersonalInfo.objects.all()
                  .order_by("client_last_name", "client_first_name")
                  .prefetch_related("clientstatus_set__interment_recipients"))
    client_data = {}
    for c in clients_qs:
        active_plan = None
        for cs in c.clientstatus_set.all():
            if cs.status and not cs.is_cancelled and cs.plan != "No Plan":
                if active_plan is None or cs.pk > active_plan.pk:
                    active_plan = cs
        plan_info = None
        if active_plan:
            recipients = [r.name for r in active_plan.interment_recipients.all()]
            plan_info = {
                "id": active_plan.pk, "plan": active_plan.plan,
                "location": _plan_location_string(active_plan),
                "interment_date": active_plan.interment_date.strftime("%b %d, %Y") if active_plan.interment_date else None,
                "interment_date_iso": active_plan.interment_date.isoformat() if active_plan.interment_date else None,
                "recipients": recipients,
            }
        client_data[str(c.pk)] = {"name": c.full_name, "contact": c.client_contact_number, "plan": plan_info}

    tomorrow = today + datetime.timedelta(days=1)
    week_end = today + datetime.timedelta(days=7)
    today_bookings    = [b for b in bookings_list if b.booking_date == today     and b.status == "Active"]
    tomorrow_bookings = [b for b in bookings_list if b.booking_date == tomorrow  and b.status == "Active"]
    upcoming_bookings = [b for b in bookings_list if tomorrow < b.booking_date <= week_end and b.status == "Active"]

    interment_window_end = today + datetime.timedelta(days=30)
    upcoming_interments = []
    for plan in (ClientStatus.objects.filter(
        status=True, is_cancelled=False,
        interment_date__isnull=False,
        interment_date__gte=today, interment_date__lte=interment_window_end,
    ).exclude(plan="No Plan").select_related("client")
     .prefetch_related("interment_recipients").order_by("interment_date")):
        upcoming_interments.append({
            "plan": plan, "days_until": (plan.interment_date - today).days,
            "location": _plan_location_string(plan),
            "recipients": [r.name for r in plan.interment_recipients.all()],
        })

    masterlist_qs, masterlist_query = _filter_interment_masterlist(request)
    interment_masterlist = _build_interment_masterlist(masterlist_qs)

    return render(request, "app/bookings.html", {
        "form": form, "bookings": bookings_list,
        "booked_slots_json": json.dumps(dict(booked_slots)),
        "day_events_json": json.dumps(day_events_json),
        "client_data_json": json.dumps(client_data),
        "today_bookings": today_bookings, "tomorrow_bookings": tomorrow_bookings,
        "upcoming_bookings": upcoming_bookings,
        "today_date": today, "tomorrow_date": tomorrow,
        "upcoming_interments": upcoming_interments,
        "interment_masterlist": interment_masterlist,
        "masterlist_query": masterlist_query,
    })


# ─────────────────────────────────────────────── cancel booking ───────────────

@login_required(login_url="login")
def cancel_booking_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)
    if not _check_write_role(request, "Accounting Staff", "Marketing Staff"):
        return JsonResponse({"success": False, "error": "Access restricted."})
    if not _check_pin(request.user, request.POST.get("pin", "")):
        return JsonResponse({"success": False, "error": "Invalid PIN."})

    booking = get_object_or_404(Booking, pk=pk)
    if booking.status == "Cancelled":
        return JsonResponse({"success": False, "error": "Booking is already cancelled."})

    reason = request.POST.get("reason", "").strip() or "No reason provided."
    booking.status              = "Cancelled"
    booking.cancellation_reason = reason
    booking.cancelled_at        = timezone.now()
    booking.save()

    _log_activity(request.user, "Cancel Booking", f"Booking ID: {pk} — {booking.client_name}")
    return JsonResponse({"success": True})


# ─────────────────────────────────────────────── calendar ─────────────────────

@login_required(login_url="login")
def calendar_view(request):
    from collections import Counter
    today = datetime.date.today()

    try:
        year  = int(request.GET.get("year",  today.year))
        month = int(request.GET.get("month", today.month))
    except ValueError:
        year, month = today.year, today.month
    if month < 1:  month, year = 12, year - 1
    elif month > 12: month, year = 1, year + 1

    month_bookings = Booking.objects.filter(
        booking_date__year=year, booking_date__month=month, status="Active")
    total_slots    = len(Booking.TIME_SLOTS)
    booking_counts = Counter(b.booking_date.day for b in month_bookings)
    fully_booked_dates     = {d for d, c in booking_counts.items() if c >= total_slots}
    partially_booked_dates = {d for d in booking_counts if d not in fully_booked_dates}
    cal_weeks = cal_module.monthcalendar(year, month)
    prev_month, prev_year = (12, year - 1) if month == 1  else (month - 1, year)
    next_month, next_year = (1,  year + 1) if month == 12 else (month + 1, year)

    selected_date_str = request.GET.get("date", "").strip()
    selected_date     = None
    booked_times      = set()
    if selected_date_str:
        try:
            selected_date = datetime.date.fromisoformat(selected_date_str)
            booked_times  = set(Booking.objects.filter(
                booking_date=selected_date, status="Active"
            ).values_list("booking_time", flat=True))
        except ValueError:
            selected_date_str = ""

    interment_days = set()
    for cs in (ClientStatus.objects.filter(
        status=True, is_cancelled=False,
        interment_date__year=year, interment_date__month=month,
    ).exclude(plan="No Plan").only("interment_date")):
        interment_days.add(cs.interment_date.day)

    interments_on_selected = []
    if selected_date:
        for cs in (ClientStatus.objects.filter(
            status=True, is_cancelled=False, interment_date=selected_date,
        ).exclude(plan="No Plan").select_related("client")):
            interments_on_selected.append(cs.client.full_name)

    return render(request, "app/calendar.html", {
        "cal_weeks": cal_weeks, "month": month, "year": year,
        "month_name": cal_module.month_name[month],
        "booked_dates": fully_booked_dates, "partially_booked_dates": partially_booked_dates,
        "prev_month": prev_month, "prev_year": prev_year,
        "next_month": next_month, "next_year": next_year,
        "today": today, "time_slots": Booking.TIME_SLOTS,
        "booked_times": booked_times, "selected_date": selected_date,
        "selected_date_str": selected_date_str,
        "day_names": ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
        "interment_days": interment_days,
        "interments_on_selected": interments_on_selected,
    })


# ─────────────────────────────────────────────── monitor ──────────────────────

@_admin_required
def monitor_view(request):
    logs = ActivityLog.objects.select_related("user").order_by("-timestamp")
    q_name   = request.GET.get("name",      "").strip()
    q_action = request.GET.get("action",    "").strip()
    q_from   = request.GET.get("date_from", "").strip()
    q_to     = request.GET.get("date_to",   "").strip()
    if q_name:   logs = logs.filter(staff_name__icontains=q_name)
    if q_action and q_action != "All": logs = logs.filter(action=q_action)
    if q_from:   logs = logs.filter(timestamp__date__gte=q_from)
    if q_to:     logs = logs.filter(timestamp__date__lte=q_to)
    return render(request, "app/monitor.html", {
        "logs": logs, "q_name": q_name, "q_action": q_action,
        "q_from": q_from, "q_to": q_to,
    })


# ─────────────────────────────────────────────── employees ────────────────────

@_admin_required
def employee_view(request):
    query     = request.GET.get("q", "").strip()
    employees = UserLog.objects.select_related("user").all().order_by("last_name", "first_name")
    if query:
        employees = employees.filter(
            Q(first_name__icontains=query) | Q(last_name__icontains=query) |
            Q(middle_name__icontains=query) | Q(role__icontains=query) |
            Q(phone_number__icontains=query)
        ).distinct()
    return render(request, "app/viewemployee.html", {"employees": employees, "query": query})


@_admin_required
def add_employee_view(request):
    if request.method == "POST":
        form = EmployeeCreateForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            if d["username"].lower() == "admin":
                form.add_error("username", "The username 'admin' is reserved.")
                return render(request, "app/add-employee.html", {"form": form})
            if User.objects.filter(username__iexact=d["username"]).exists():
                form.add_error("username", "Username already exists.")
                return render(request, "app/add-employee.html", {"form": form})

            with transaction.atomic():
                user = User.objects.create_user(
                    username=d["username"], password=d["password"],
                    email=d.get("email", ""),
                    first_name=d["first_name"], last_name=d["last_name"])
                UserLog.objects.create(
                    user=user, role=d["role"],
                    first_name=d["first_name"],
                    middle_name=d.get("middle_name", "") or "",
                    last_name=d["last_name"],
                    date_of_birth=d["date_of_birth"],
                    government_id=d.get("government_id", ""),
                    phone_number=d.get("phone_number", ""),
                    email=d.get("email", ""), address=d["address"],
                    emergency_contact_name=d["emergency_contact_name"],
                    emergency_contact_number=d["emergency_contact_number"],
                    activities="Account created", pin=make_password(d["pin"]))

            messages.success(request, f"Employee '{d['first_name']} {d['last_name']}' created.")
            _log_activity(request.user, "Add Employee",
                f"Employee: {d['first_name']} {d['last_name']} ({d['role']})")
            return redirect("employee")
        return render(request, "app/add-employee.html", {"form": form})
    return render(request, "app/add-employee.html", {"form": EmployeeCreateForm()})


@_admin_required
def details_employee_view(request, pk):
    employee = get_object_or_404(UserLog, pk=pk)
    duration_str = "—"
    if employee.time_in and employee.time_out:
        delta   = employee.time_out - employee.time_in
        minutes = int(delta.total_seconds() // 60)
        duration_str = f"{minutes // 60}h {minutes % 60}m"
    return render(request, "app/employee-details.html", {"employee": employee, "duration_str": duration_str})


@_admin_required
def edit_employee_view(request, pk):
    employee = get_object_or_404(UserLog, pk=pk)
    if request.method == "POST":
        form = EmployeeUpdateForm(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            with transaction.atomic():
                employee.first_name               = d["first_name"]
                employee.middle_name              = d.get("middle_name", "") or ""
                employee.last_name                = d["last_name"]
                employee.date_of_birth            = d["date_of_birth"]
                employee.address                  = d["address"]
                employee.email                    = d["email"]
                employee.phone_number             = d["phone_number"]
                employee.emergency_contact_name   = d["emergency_contact_name"]
                employee.emergency_contact_number = d["emergency_contact_number"]
                employee.role                     = d["role"]
                employee.government_id            = d["government_id"]
                employee.pin                      = make_password(d["pin"])
                employee.save()
                if employee.user:
                    employee.user.first_name = d["first_name"]
                    employee.user.last_name  = d["last_name"]
                    employee.user.email      = d["email"]
                    if d.get("new_password"):
                        employee.user.set_password(d["new_password"])
                    employee.user.save()
            messages.success(request, "Employee updated.")
            _log_activity(request.user, "Edit Employee", f"Employee: {employee.full_name}")
            return redirect("details-employee", pk=pk)
    else:
        form = EmployeeUpdateForm(initial={
            "first_name": employee.first_name, "middle_name": employee.middle_name,
            "last_name": employee.last_name, "date_of_birth": employee.date_of_birth,
            "address": employee.address, "email": employee.email,
            "phone_number": employee.phone_number,
            "emergency_contact_name": employee.emergency_contact_name,
            "emergency_contact_number": employee.emergency_contact_number,
            "role": employee.role, "government_id": employee.government_id,
        })
    return render(request, "app/employee-edit.html", {"form": form, "employee": employee})


@_admin_required
def delete_employee_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)
    if not _check_pin(request.user, request.POST.get("pin", "")):
        return JsonResponse({"success": False, "error": "Invalid PIN."})
    employee = get_object_or_404(UserLog, pk=pk)
    if employee.user == request.user:
        return JsonResponse({"success": False, "error": "You cannot delete your own account."})
    name = employee.full_name
    with transaction.atomic():
        if employee.user: employee.user.delete()
        else: employee.delete()
    _log_activity(request.user, "Delete Employee", f"Employee: {name}")
    return JsonResponse({"success": True, "name": name})


def _xl_response(wb, filename):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    wb.save(response)
    return response


def _xl_header_row(ws, headers):
    ws.append(headers)
    row = ws.max_row
    dark  = PatternFill(start_color="2F3640", end_color="2F3640", fill_type="solid")
    white = Font(bold=True, color="FFFFFF", size=11)
    for col in range(1, len(headers) + 1):
        cell = ws.cell(row=row, column=col)
        cell.fill = dark
        cell.font = white
        cell.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[row].height = 20
    return row


def _xl_auto_width(ws):
    for col in ws.columns:
        max_len = 0
        letter  = col[0].column_letter
        for cell in col:
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[letter].width = min(max_len + 4, 55)


@_admin_required
@require_POST
def backup_now_view(request):
    from .backup import trigger_manual_backup
    return JsonResponse(trigger_manual_backup())


@_admin_required
def backup_status_view(request):
    from django.conf import settings as django_settings
    from pathlib import Path
    backup_dir = Path(getattr(django_settings, "BACKUP_OFFLINE_DIR",
                              str(django_settings.BASE_DIR / "backups")))
    files = []
    if backup_dir.exists():
        all_zips = sorted(backup_dir.glob("backup_*.zip"), reverse=True)
        for f in all_zips[:15]:
            stat = f.stat()
            files.append({
                "name": f.name, "size_kb": round(stat.st_size / 1024, 1),
                "modified": datetime.datetime.fromtimestamp(stat.st_mtime)
                            .strftime("%b %d, %Y %I:%M %p"),
            })
        last = all_zips[0] if all_zips else None
        last_info = {"filename": last.name,
                     "modified": datetime.datetime.fromtimestamp(last.stat().st_mtime)
                                .strftime("%b %d, %Y %I:%M %p")} if last else None
    else:
        last_info = None
    return JsonResponse({
        "files": files, "directory": str(backup_dir),
        "last": last_info, "total": len(files),
    })


@_admin_required
def system_settings_view(request):
    DEFAULTS = [
        ("BACKUP_EMAIL_HOST", "smtp.gmail.com", "Email SMTP Host"),
        ("BACKUP_EMAIL_PORT", "587", "Email SMTP Port"),
        ("BACKUP_EMAIL_USER", "", "Email Sender Address"),
        ("BACKUP_EMAIL_PASSWORD", "", "Email App Password"),
        ("BACKUP_EMAIL_TO", "", "Email Recipient Address"),
        ("ADMIN_PIN", "", "Admin PIN (4 digits)"),
    ]
    for key, default_val, label in DEFAULTS:
        SystemSecret.objects.get_or_create(key=key, defaults={"label": label, "encrypted_value": ""})

    message = None; error = None
    if request.method == "POST":
        pin = request.POST.get("pin", "")
        if pin != _get_admin_pin():
            error = "Incorrect PIN."
        else:
            new_admin_pin = request.POST.get("ADMIN_PIN", "").strip()
            if new_admin_pin and not (new_admin_pin.isdigit() and len(new_admin_pin) == 4):
                error = "Admin PIN must be exactly 4 digits."
            else:
                for key, _, _ in DEFAULTS:
                    new_val = request.POST.get(key, "").strip()
                    if new_val:
                        obj = SystemSecret.objects.get(key=key)
                        obj.set_value(new_val)
                        obj.save()
                _log_activity(request.user, "System Settings", "Updated encrypted system secrets.")
                message = "Settings saved and encrypted successfully."

    secrets = []
    for key, _, label in DEFAULTS:
        obj = SystemSecret.objects.get(key=key)
        val = obj.get_value()
        secrets.append({"key": key, "label": label, "set": bool(val)})
    return render(request, "app/system_settings.html", {"secrets": secrets, "message": message, "error": error})


# ── Exports ──────────────────────────────────────────────────────────────────

@login_required(login_url="login")
def export_bookings_excel(request):
    from django.utils import timezone
    today = timezone.localdate()
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Bookings"
    ws.append(["GREEN GARDEN — BOOKING RECORDS"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today.strftime('%B %d, %Y')}"]); ws.append([])
    _xl_header_row(ws, ["#","Client Name","Contact Number","Event Type","Booking Date","Time","Notes","Status"])
    for i, b in enumerate(Booking.objects.order_by("-booking_date","booking_time"), 1):
        ws.append([i, b.client_name, b.contact_number, b.event_type,
                   b.booking_date.strftime("%B %d, %Y"), b.get_booking_time_display(),
                   b.notes or "", b.status])
    ws.freeze_panes = "A5"; _xl_auto_width(ws)
    return _xl_response(wb, f"bookings_{today}.xlsx")


@login_required(login_url="login")
def export_interment_masterlist_excel(request):
    import datetime as _dt
    today = _dt.date.today().strftime("%B %d, %Y")
    masterlist_qs, query = _filter_interment_masterlist(request)
    export_rows = _build_interment_masterlist(masterlist_qs)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Interment Masterlist"
    ws.append(["GREEN GARDEN — INTERMENT MASTERLIST"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today}"])
    ws.append([f'Search applied: "{query}"' if query else "Search applied: None (showing all records)"])
    ws.cell(row=ws.max_row, column=1).font = Font(italic=True, size=10, color="666666")
    ws.append([f"Total records: {len(export_rows)}"])
    ws.cell(row=ws.max_row, column=1).font = Font(italic=True, size=10, color="666666")
    ws.append([])
    _xl_header_row(ws, ["#","LOT DESCRIPTION","RECIPIENT","LOT OWNER","CLASSIFICATION","P.A. NO.","INTERMENT DATE"])
    for i, row in enumerate(export_rows, 1):
        ws.append([i, row["lot_description"], row["recipient_name"],
                   row["client_name_formatted"], row["classification"], row["pa_no"],
                   row["interment_date"].strftime("%B %d, %Y") if row["interment_date"] else "—"])
    ws.freeze_panes = "A7"; _xl_auto_width(ws)
    suffix = "filtered" if query else "all"
    return _xl_response(wb, f"interment_masterlist_{suffix}_{_dt.date.today()}.xlsx")


def _tctar_contract_sheet(ws, client, cs, today):
    ws.append(["GREEN GARDEN, INC. — TCT A/R CONTRACT"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today}"]); ws.append([])
    ws.append(["PURCHASER'S INFORMATION"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    info_rows = [
        ("L.A. No.", cs.la_number or "—"),
        ("Date of Purchase", cs.start_date.strftime("%d-%b-%y") if cs.start_date else "—"),
        ("Product Classification", cs.columbarium_type or "—"),
        ("Name", client.full_name), ("Address", client.client_address),
        ("Contact No.", client.client_contact_number), ("Block", cs.block or "—"),
        ("Section", cs.section or "—"), ("Level", cs.column_level or "—"),
        ("Tomb No.", cs.tomb_number or "—"), ("Sales Agent", cs.sales_agent or "—"),
        ("Initial Expiration", cs.tct_initial_expiration_date.strftime("%d-%b-%y") if cs.tct_initial_expiration_date else "—"),
        ("Current Expiration", cs.tct_current_expiration_date.strftime("%d-%b-%y") if cs.tct_current_expiration_date else "—"),
        ("Validity Status", cs.tct_renewal_status or "—"),
        ("Renewals on Record", str(cs.tct_renewal_count)),
    ]
    for label, value in info_rows:
        ws.append([label, value]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])
    ws.append(["FINANCIAL BREAKDOWN"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    for label, value in [
        ("LOT PRICE", float(cs.total_lot_excl_doc)),
        ("PERPETUAL CARE", float(cs.total_pcare)),
        ("DOCUMENTATION", float(cs.documentation_fee or 0)),
        ("TOTAL AMOUNT", float(cs.total_contract_price)),
        ("TOTAL PAID", float(cs.paid_balance or 0)),
        ("OUTSTANDING BALANCE", float(cs.balance or 0)),
    ]:
        ws.append([label, value]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])
    ws.append(["INTERMENT RECORD"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    recipients = list(cs.interment_recipients.all())
    ws.append(["Name of Deceased", ", ".join(r.name for r in recipients) if recipients else "—"])
    ws.append(["Death Certificate No.", cs.death_certificate_number or "—"])
    ws.append(["Date of Death", str(cs.date_of_death) if cs.date_of_death else "—"])
    ws.append(["Date of Interment", str(cs.interment_date) if cs.interment_date else "—"])
    ws.append([])
    ws.append(["RENEWAL HISTORY"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    _xl_header_row(ws, ["#","Renewal Date","Previous Expiration","New Expiration","Period (yrs)","Status","Note"])
    for r in cs.tct_renewals.all():
        ws.append([r.renewal_number,
                   r.renewal_date.strftime("%d-%b-%y") if r.renewal_date else "—",
                   r.previous_expiration_date.strftime("%d-%b-%y") if r.previous_expiration_date else "—",
                   r.new_expiration_date.strftime("%d-%b-%y") if r.new_expiration_date else "—",
                   r.renewal_period_years, r.status, r.note or ""])
    _xl_auto_width(ws)


def _tctar_ledger_sheet(ws, client, cs, today):
    ws.append(["GREEN GARDEN, INC. — TCT A/R RECORD OF PAYMENT"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today}"]); ws.append([])
    ws.append(["CLIENT INFORMATION"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    for label, value in [
        ("L.A. No.", cs.la_number or "—"), ("Name", client.full_name),
        ("Address", client.client_address), ("Contact No.", client.client_contact_number),
        ("Current Expiration", cs.tct_current_expiration_date.strftime("%d-%b-%y") if cs.tct_current_expiration_date else "—"),
        ("Validity Status", cs.tct_renewal_status or "—"),
    ]:
        ws.append([label, value]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([])
    _xl_header_row(ws, ["RENEWAL PERIOD","LEASE AMT.","PENALTY CHARGES","TOTAL DUE","DATE","REF. NO.","AMOUNT PAID","YEAR","BALANCE"])
    contract_price = cs.total_contract_price
    initial_exp = cs.tct_initial_expiration_date
    ws.append([initial_exp.strftime("%m/%d/%Y") if initial_exp else "—",
               float(contract_price), "—", float(contract_price),
               "—","—","—","—", float(contract_price)])
    running = Decimal('0.00')
    for p in cs.payments.filter(is_paid=True).order_by("date_paid"):
        running += p.amount
        balance_after = max(contract_price - running, Decimal('0.00'))
        ws.append(["—","—", float(p.penalty_charges or 0), "—",
                   p.date_paid.strftime("%m/%d/%Y") if p.date_paid else "—",
                   p.csi_number or "—", float(p.amount),
                   p.date_paid.year if p.date_paid else "—", float(balance_after)])
    ws.append([]); ws.append(["TOTAL PAID", float(running)])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append(["OUTSTANDING BALANCE", float(max(contract_price - running, Decimal('0.00')))])
    ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([]); ws.append(["RENEWAL LEDGER"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    _xl_header_row(ws, ["RENEWAL #","RENEWAL DATE","PERIOD (YEARS)","PREVIOUS EXPIRATION","NEW EXPIRATION","STATUS","NOTE"])
    for r in cs.tct_renewals.all():
        ws.append([r.renewal_number,
                   r.renewal_date.strftime("%m/%d/%Y") if r.renewal_date else "—",
                   r.renewal_period_years,
                   r.previous_expiration_date.strftime("%m/%d/%Y") if r.previous_expiration_date else "—",
                   r.new_expiration_date.strftime("%m/%d/%Y") if r.new_expiration_date else "—",
                   r.status, r.note or ""])
    _xl_auto_width(ws)


@login_required(login_url="login")
def export_payment_history_excel(request, pk):
    import datetime as _dt
    client = get_object_or_404(ClientPersonalInfo, pk=pk)
    all_statuses = ClientStatus.objects.filter(client=client).exclude(plan="No Plan").order_by("-pk")
    selected_pk = request.GET.get("plan")
    if selected_pk:
        try: client_status = all_statuses.get(pk=selected_pk)
        except ClientStatus.DoesNotExist:
            client_status = _get_active_status(client) or all_statuses.first()
    else:
        client_status = _get_active_status(client) or all_statuses.first()

    if not client_status:
        messages.info(request, "No plan found for this client.")
        return redirect("payment-history", pk=pk)

    today   = _dt.date.today().strftime("%B %d, %Y")
    section = (request.GET.get("section") or "").strip().lower()

    if client_status.plan == "TCT A/R":
        wb = openpyxl.Workbook(); wb.remove(wb.active)
        want_contract = section in ("", "contract", "both")
        want_ledger   = section in ("", "ledger",   "both")
        if want_contract:
            ws = wb.create_sheet("Contract"); _tctar_contract_sheet(ws, client, client_status, today)
        if want_ledger:
            ws = wb.create_sheet("Payment Ledger"); _tctar_ledger_sheet(ws, client, client_status, today)
        if section == "contract": fname = f"tctar_contract_{client.pk}.xlsx"
        elif section == "ledger": fname = f"tctar_ledger_{client.pk}.xlsx"
        else: fname = f"tctar_{client.pk}.xlsx"
        return _xl_response(wb, fname)

    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Payment Ledger"
    ws.append(["GREEN GARDEN — INSTALLMENT SALES RECEIVABLE LEDGER"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today}"]); ws.append([])
    ws.append(["CLIENT INFORMATION"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    for label, value in [
        ("ID", client.pk), ("Full Name", client.full_name),
        ("Contact", client.client_contact_number), ("Civil Status", client.client_civil_status),
        ("Date of Birth", str(client.client_date_birth)), ("Address", client.client_address),
    ]:
        ws.append([label, value]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([]); ws.append(["PLAN INFORMATION"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    for label, value in [
        ("Plan", client_status.plan),
        ("Lawn Lot Type", client_status.lawn_lot_type or "—"),
        ("Regular Package", client_status.regular_lot_package or "—"),
        ("Garden Type", client_status.garden_type or "—"),
        ("Garden Section", client_status.garden_section or "—"),
        ("Mausoleum Type", client_status.mausoleum_type or "—"),
        ("SQM", f"{client_status.sqm}" if client_status.sqm else "—"),
        ("Monthly", f"₱{client_status.effective_monthly_payment:,.2f}"),
        ("P-Care %", f"{client_status.pcare_percent}%"),
        ("Total Contract", f"₱{client_status.total_contract_price:,.2f}"),
        ("Total P-Care", f"₱{client_status.total_pcare:,.2f}"),
        ("Total Lot", f"₱{client_status.total_lot:,.2f}"),
        ("Duration", f"{client_status.duration} months"),
        ("Start Date", str(client_status.start_date)),
        ("Down Payment", f"₱{client_status.down_payment:,.2f}" if client_status.down_payment else "—"),
        ("Discount", f"{client_status.discount_percent}%" if client_status.discount_percent else "0%"),
        ("Total Paid", f"₱{client_status.paid_balance:,.2f}"),
        ("Lot Balance", f"₱{client_status.balance:,.2f}"),
        ("Date Fully Paid", str(client_status.date_fully_paid) if client_status.date_fully_paid else "—"),
        ("Status", "Cancelled" if client_status.is_cancelled else ("Active" if client_status.status else "Completed")),
    ]:
        ws.append([label, value]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True)
    ws.append([]); ws.append(["LEDGER"]); ws.cell(row=ws.max_row, column=1).font = Font(bold=True, size=11)
    _xl_header_row(ws, ["#","DATE","INST. NO.","C.S.I. NO.","LOT","P-CARE","AMOUNT PAID","MONTHS COVERED","PENALTY CHARGES","PAYMENT CHARGES","INSTALLMENT DUE","BALANCE","P-CARE BALANCE","TOTAL BALANCE"])
    all_payments = client_status.payments.all().order_by("month", "date_paid")
    total_lot = client_status.total_lot; total_pcare = client_status.total_pcare
    dp_lot = client_status.down_payment_lot; dp_pcare = client_status.down_payment_pcare
    starting_lot_bal = total_lot - dp_lot; starting_pc_bal = total_pcare - dp_pcare
    running_lot = Decimal('0.00'); running_pcare = Decimal('0.00')
    for i, p in enumerate(all_payments, 1):
        if p.is_paid:
            running_lot += p.lot_amount or Decimal('0.00')
            running_pcare += p.pcare_amount or Decimal('0.00')
        balance = max(starting_lot_bal - running_lot, Decimal('0.00'))
        pcare_balance = max(starting_pc_bal - running_pcare, Decimal('0.00'))
        date_val = p.date_paid.strftime("%B %d, %Y") if p.is_paid and p.date_paid else (
            p.month.strftime("%B %d, %Y") if p.month else "—")
        ws.append([
            i, date_val, p.installment_no or "—", p.csi_number or "—",
            float(p.lot_amount) if p.is_paid else 0,
            float(p.pcare_amount) if p.is_paid else 0,
            float(p.amount) if p.is_paid else 0,
            (p.months_covered if p.is_paid else 0),
            float(p.penalty_charges) if p.is_paid else 0,
            float(p.payment_charges) if p.is_paid else 0,
            float(p.installment_due) if p.installment_due else 0,
            float(balance), float(pcare_balance), float(balance - pcare_balance),
        ])
    ws.freeze_panes = "A7"; _xl_auto_width(ws)
    return _xl_response(wb, f"payment_ledger_{client.pk}_{client_status.plan}.xlsx")


@login_required(login_url="login")
def export_lots_excel(request):
    import datetime as _dt
    today = _dt.date.today().strftime("%B %d, %Y")
    lots, _query_context, active_filters = _filter_lots(request)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Lots"
    ws.append(["GREEN GARDEN — LOT RECORDS"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today}"])
    if active_filters:
        ws.append([f"Filters applied: {' | '.join(f'{k}: {v}' for k, v in active_filters.items())}"])
    else:
        ws.append(["Filters applied: None (showing all lots)"])
    ws.cell(row=ws.max_row, column=1).font = Font(italic=True, size=10, color="666666")
    ws.append([f"Total records: {lots.count()}"])
    ws.cell(row=ws.max_row, column=1).font = Font(italic=True, size=10, color="666666")
    ws.append([])
    _xl_header_row(ws, ["PA NUMBER","LA NUMBER","NAME OF BUYER","LOT TYPE","LAWN LOT TYPE","REGULAR PACKAGE","GARDEN TYPE","GARDEN SECTION","MAUSOLEUM TYPE","SQM","PHASE","BLOCK","SECTION","LOT NUMBER","C.O NUMBER","DATE OF SALES","DATE REGISTERED","MONTHLY","BALANCE","STATUS","TCT CURRENT EXPIRATION","TCT VALIDITY STATUS"])
    for lot in lots:
        status = "Cancelled" if lot.is_cancelled else ("Active" if lot.status else "Completed")
        tct_exp = lot.tct_current_expiration_date if lot.plan == "TCT A/R" else None
        tct_st  = lot.tct_renewal_status if lot.plan == "TCT A/R" else ""
        ws.append([lot.pa_number or "—", lot.la_number or "—", lot.client.full_name, lot.plan,
                   lot.lawn_lot_type or "—", lot.regular_lot_package or "—",
                   lot.garden_type or "—", lot.garden_section or "—", lot.mausoleum_type or "—",
                   float(lot.sqm) if lot.sqm else "—",
                   lot.phase or "—", lot.block or "—",
                   lot.section or lot.ths_section or "—", lot.lot_number or "—",
                   lot.contract_number or "—",
                   lot.start_date.strftime("%B %d, %Y") if lot.start_date else "—",
                   lot.pa_date.strftime("%B %d, %Y") if lot.pa_date else "—",
                   float(lot.effective_monthly_payment), float(lot.balance), status,
                   tct_exp.strftime("%B %d, %Y") if tct_exp else "—", tct_st or "—"])
    ws.freeze_panes = "A7"; _xl_auto_width(ws)
    suffix = "filtered" if active_filters else "all"
    return _xl_response(wb, f"lots_{suffix}_{_dt.date.today()}.xlsx")


@login_required(login_url="login")
def export_records_excel(request):
    import datetime as _dt
    today = _dt.date.today().strftime("%B %d, %Y")
    clients, query, active_filters = _filter_client_records(request)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "Client Records"
    ws.append(["GREEN GARDEN — CLIENT RECORDS"])
    ws.cell(row=1, column=1).font = Font(bold=True, size=13)
    ws.append([f"Exported: {today}"])
    if active_filters:
        ws.append([f'Search applied: "{query}"'])
    else:
        ws.append(["Search applied: None (showing all clients)"])
    ws.cell(row=ws.max_row, column=1).font = Font(italic=True, size=10, color="666666")
    ws.append([f"Total records: {clients.count()}"])
    ws.cell(row=ws.max_row, column=1).font = Font(italic=True, size=10, color="666666")
    ws.append([])
    _xl_header_row(ws, ["ID","FIRST NAME","MIDDLE NAME","LAST NAME","ADDRESS","CONTACT","CIVIL STATUS","DATE OF BIRTH","RELIGION","OCCUPATION","EMPLOYER","PLAN","P.A./L.A. NO.","STATUS"])
    for c in clients:
        latest = ClientStatus.objects.filter(client=c).order_by("-pk").first()
        plan = latest.plan if latest else "No Plan"
        active = (ClientStatus.objects.filter(client=c, status=True, is_cancelled=False)
                  .exclude(plan="No Plan").order_by("-pk").first()) or latest
        if active and active.plan == "TCT A/R": pa_la = active.la_number or ""
        elif active: pa_la = active.pa_number or ""
        else: pa_la = ""
        status = ("Cancelled" if (latest and latest.is_cancelled)
                  else ("Active" if (latest and latest.status) else "Completed"))
        ws.append([c.pk, c.client_first_name, c.client_middle_name or "", c.client_last_name,
                   c.client_address, c.client_contact_number, c.client_civil_status,
                   str(c.client_date_birth), c.client_religion, c.client_occupation,
                   c.client_employer_name, plan, pa_la or "—", status])
    ws.freeze_panes = "A7"; _xl_auto_width(ws)
    suffix = "filtered" if active_filters else "all"
    return _xl_response(wb, f"client_records_{suffix}_{_dt.date.today()}.xlsx")