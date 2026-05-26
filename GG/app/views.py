import calendar as cal_module
import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import auth, User
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.timezone import localtime
from django.views.decorators.http import require_POST
from dateutil.relativedelta import relativedelta

from .forms import (
    BeneficiaryFormSet, BookingForm, ClientForm,
    EmployeeCreateForm, EmployeeUpdateForm, PlanForm,
)
from .models import Booking, ClientPersonalInfo, ClientStatus, Payment, UserLog


# ─────────────────────────────────────────────── helpers ──────────────────────

def _get_pin(user):
    if user.is_superuser or user.username == "admin":
        from django.conf import settings
        return str(getattr(settings, "ADMIN_PIN", "0000"))
    log = UserLog.objects.filter(user=user).first()
    return str(log.pin) if log else "1234"


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
    auth.logout(request)
    return redirect("login")


# ─────────────────────────────────────────────── dashboard ────────────────────

@login_required(login_url="login")
def homepage_view(request):
    total_clients    = ClientPersonalInfo.objects.count()
    active_status    = ClientStatus.objects.filter(status=True).count()
    collected        = sum(ClientStatus.objects.values_list("paid_balance", flat=True))
    pending_payments = sum(ClientStatus.objects.values_list("months_remaining", flat=True))

    return render(request, "app/homepage.html", {
        "total_clients":    total_clients,
        "collected":        collected,
        "active_status":    active_status,
        "pending_payments": pending_payments,
    })


# ─────────────────────────────────────────────── clients ──────────────────────

@login_required(login_url="login")
def add_client_view(request):
    if request.method == "POST":
        form                = ClientForm(request.POST)
        beneficiary_formset = BeneficiaryFormSet(request.POST, prefix="beneficiaries")

        if form.is_valid() and beneficiary_formset.is_valid():
            client = form.save(commit=False)

            if ClientPersonalInfo.objects.filter(
                client_first_name__iexact=client.client_first_name,
                client_last_name__iexact=client.client_last_name,
                client_date_birth=client.client_date_birth,
            ).exists():
                form.add_error(None, "A client with this name and date of birth already exists.")
                return render(request, "app/addclient.html", {
                    "form": form, "beneficiary_formset": beneficiary_formset,
                })

            with transaction.atomic():
                client.save()
                beneficiary_formset.instance = client
                beneficiary_formset.save()

                today = datetime.date.today()
                cs = ClientStatus.objects.create(
                    client=client, plan="No Plan",
                    monthly_payment=0, duration=0,
                    months_remaining=0, start_date=today,
                    balance=0, paid_balance=0.00, status=False,
                )
                _generate_payment_rows(cs)

            messages.success(request, f"Client '{client.full_name()}' added successfully.")
            return redirect("records")
    else:
        form                = ClientForm()
        beneficiary_formset = BeneficiaryFormSet(prefix="beneficiaries")

    return render(request, "app/addclient.html", {
        "form": form, "beneficiary_formset": beneficiary_formset,
    })


@login_required(login_url="login")
def records_view(request):
    query   = request.GET.get("q", "").strip()
    clients = ClientPersonalInfo.objects.all().order_by("client_last_name", "client_first_name")

    if query:
        clients = clients.filter(
            Q(client_first_name__icontains=query)     |
            Q(client_middle_name__icontains=query)    |
            Q(client_last_name__icontains=query)      |
            Q(client_contact_number__icontains=query) |
            Q(client_civil_status__icontains=query)   |
            Q(clientstatus__plan__icontains=query)
        ).distinct()

    return render(request, "app/records.html", {"client": clients, "query": query})


@login_required(login_url="login")
def client_details_view(request, pk):
    client        = get_object_or_404(ClientPersonalInfo, pk=pk)
    client_status = ClientStatus.objects.filter(client=client).first()
    return render(request, "app/client-details.html", {
        "client": client, "client_status": client_status,
    })


@login_required(login_url="login")
def edit_details_view(request, pk):
    client = get_object_or_404(ClientPersonalInfo, pk=pk)

    if request.method == "POST":
        form                = ClientForm(request.POST, instance=client)
        beneficiary_formset = BeneficiaryFormSet(
            request.POST, instance=client, prefix="beneficiaries"
        )
        if form.is_valid() and beneficiary_formset.is_valid():
            with transaction.atomic():
                form.save()
                beneficiary_formset.save()
            messages.success(request, "Client updated successfully.")
            return redirect("records")
    else:
        form                = ClientForm(instance=client)
        beneficiary_formset = BeneficiaryFormSet(instance=client, prefix="beneficiaries")

    return render(request, "app/edit_details.html", {
        "form": form, "beneficiary_formset": beneficiary_formset, "client": client,
    })


@login_required(login_url="login")
def delete_client_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)

    if request.POST.get("pin", "") != _get_pin(request.user):
        return JsonResponse({"success": False, "error": "Invalid PIN."})

    client = get_object_or_404(ClientPersonalInfo, pk=pk)
    name   = client.full_name()
    client.delete()
    return JsonResponse({"success": True, "name": name})


# ─────────────────────────────────────────────── payments ─────────────────────

def _generate_payment_rows(client_status):
    if client_status.payments.exists():
        return
    first_month = client_status.start_date.replace(day=1)
    Payment.objects.bulk_create([
        Payment(
            client_status=client_status,
            month=first_month + relativedelta(months=i),
            amount=client_status.monthly_payment,
            is_paid=False,
        )
        for i in range(client_status.duration)
    ])


@login_required(login_url="login")
def add_payment_view(request, pk):
    client        = get_object_or_404(ClientPersonalInfo, pk=pk)
    client_status = ClientStatus.objects.filter(client=client).first()
    if client_status:
        _generate_payment_rows(client_status)
    return render(request, "app/add_payment.html", {
        "client": client, "client_status": client_status,
    })


@login_required(login_url="login")
def payment_history_view(request, pk):
    client        = get_object_or_404(ClientPersonalInfo, pk=pk)
    client_status = ClientStatus.objects.filter(client=client).first()

    if not client_status:
        messages.error(request, "No plan found for this client.")
        return redirect("records")

    _generate_payment_rows(client_status)

    if request.method == "POST":
        payment_id = request.POST.get("payment_id", "")
        pin        = request.POST.get("pin", "")

        if pin != _get_pin(request.user):
            return JsonResponse({"success": False, "error": "Invalid PIN."})

        payment = get_object_or_404(Payment, pk=payment_id, client_status=client_status)

        if payment.is_paid:
            return JsonResponse({"success": False, "error": "This month is already paid."})

        with transaction.atomic():
            payment.is_paid   = True
            payment.date_paid = timezone.now()
            payment.save()

            client_status.paid_balance    += payment.amount
            client_status.balance         -= payment.amount
            client_status.months_remaining = client_status.payments.filter(is_paid=False).count()
            client_status.date_paid        = payment.date_paid
            if client_status.months_remaining == 0:
                client_status.status = False
            client_status.save()

        return JsonResponse({
            "success":          True,
            "date_paid":        localtime(payment.date_paid).strftime("%b %d, %Y %I:%M %p"),
            "paid_balance":     str(client_status.paid_balance),
            "balance":          str(client_status.balance),
            "months_remaining": client_status.months_remaining,
        })

    payments = client_status.payments.all()
    return render(request, "app/payment_history.html", {
        "client": client, "client_status": client_status, "payments": payments,
    })


# ─────────────────────────────────────────────── plan ─────────────────────────

@login_required(login_url="login")
def plan(request, pk):
    client = get_object_or_404(ClientPersonalInfo, pk=pk)
    plans  = ClientStatus.objects.filter(client=client)
    form   = PlanForm()

    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            d         = form.cleaned_data
            plan_name = d["plan"]
            monthly   = d["monthly_payment"]
            duration  = d["duration"]
            total     = monthly * duration
            today     = datetime.date.today()

            # Collect optional lot-detail fields
            down_payment = d.get("down_payment")
            phase        = d.get("phase", "").strip() or None
            block        = d.get("block", "").strip() or None
            section      = d.get("section", "").strip() or None
            lot_number   = d.get("lot_number", "").strip() or None
            pa_number    = d.get("pa_number", "").strip() or None

            # Block if a real plan already exists
            if plans.exclude(plan="No Plan").exists():
                messages.error(
                    request,
                    "This client already has an active or completed plan. "
                    "You cannot add another plan while one is ongoing or finished."
                )
                return render(request, "app/plan.html", {
                    "client": client, "plans": plans, "form": form,
                })

            no_plan = plans.filter(plan="No Plan").first()

            if no_plan:
                no_plan.payments.all().delete()
                no_plan.plan             = plan_name
                no_plan.monthly_payment  = monthly
                no_plan.duration         = duration
                no_plan.months_remaining = duration
                no_plan.start_date       = today
                no_plan.balance          = total
                no_plan.paid_balance     = 0
                no_plan.status           = True
                no_plan.date_paid        = None
                no_plan.down_payment     = down_payment
                no_plan.phase            = phase
                no_plan.block            = block
                no_plan.section          = section
                no_plan.lot_number       = lot_number
                no_plan.pa_number        = pa_number
                no_plan.save()
                _generate_payment_rows(no_plan)
            else:
                new_status = ClientStatus.objects.create(
                    client=client, plan=plan_name,
                    monthly_payment=monthly, duration=duration,
                    months_remaining=duration, start_date=today,
                    balance=total, paid_balance=0, status=True,
                    down_payment=down_payment,
                    phase=phase, block=block, section=section,
                    lot_number=lot_number, pa_number=pa_number,
                )
                _generate_payment_rows(new_status)

            messages.success(request, f"Plan '{plan_name}' has been assigned successfully.")
            return redirect("plan", pk=pk)

    return render(request, "app/plan.html", {
        "client": client, "plans": plans, "form": form,
    })


# ─────────────────────────────────────────────── lots ─────────────────────────

@login_required(login_url="login")
def lots_view(request):
    lots = (
        ClientStatus.objects
        .exclude(plan="No Plan")
        .select_related("client")
        .order_by("phase", "block", "section", "lot_number")
    )

    q_type    = request.GET.get("lot_type", "").strip()
    q_phase   = request.GET.get("phase", "").strip()
    q_block   = request.GET.get("block", "").strip()
    q_section = request.GET.get("section", "").strip()
    q_lot     = request.GET.get("lot_number", "").strip()
    q_status  = request.GET.get("status", "").strip()

    if q_type:
        lots = lots.filter(plan__icontains=q_type)
    if q_phase:
        lots = lots.filter(phase__icontains=q_phase)
    if q_block:
        lots = lots.filter(block__icontains=q_block)
    if q_section:
        lots = lots.filter(section__icontains=q_section)
    if q_lot:
        lots = lots.filter(lot_number__icontains=q_lot)
    if q_status == "Active":
        lots = lots.filter(status=True)
    elif q_status == "Completed":
        lots = lots.filter(status=False)

    plan_choices = [c[0] for c in ClientStatus._meta.get_field("plan").choices]

    return render(request, "app/lots.html", {
        "lots":         lots,
        "q_type":       q_type,
        "q_phase":      q_phase,
        "q_block":      q_block,
        "q_section":    q_section,
        "q_lot":        q_lot,
        "q_status":     q_status,
        "plan_choices": plan_choices,
    })


# ─────────────────────────────────────────────── bookings ─────────────────────

@login_required(login_url="login")
def bookings_view(request):
    form     = BookingForm()
    bookings = Booking.objects.order_by("-booking_date", "booking_time")

    if request.method == "POST":
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save()
            messages.success(
                request,
                f"Booking saved for {booking.client_name} on "
                f"{booking.booking_date} at {booking.get_booking_time_display()}."
            )
            return redirect("bookings")

    return render(request, "app/bookings.html", {
        "form":     form,
        "bookings": bookings,
    })


@login_required(login_url="login")
def calendar_view(request):
    today = datetime.date.today()

    try:
        year  = int(request.GET.get("year",  today.year))
        month = int(request.GET.get("month", today.month))
    except ValueError:
        year, month = today.year, today.month

    # Clamp month to valid range
    if month < 1:
        month, year = 12, year - 1
    elif month > 12:
        month, year = 1, year + 1

    # Booked dates this month
    month_bookings = Booking.objects.filter(
        booking_date__year=year, booking_date__month=month
    )
    booked_dates = set(b.booking_date.day for b in month_bookings)

    # Calendar grid (list of weeks; 0 = padding day)
    cal_weeks = cal_module.monthcalendar(year, month)

    # Prev / next navigation
    if month == 1:
        prev_month, prev_year = 12, year - 1
    else:
        prev_month, prev_year = month - 1, year

    if month == 12:
        next_month, next_year = 1, year + 1
    else:
        next_month, next_year = month + 1, year

    # Selected-date time slots
    selected_date_str = request.GET.get("date", "").strip()
    selected_date     = None
    booked_times      = set()

    if selected_date_str:
        try:
            selected_date = datetime.date.fromisoformat(selected_date_str)
            booked_times  = set(
                Booking.objects.filter(booking_date=selected_date)
                               .values_list("booking_time", flat=True)
            )
        except ValueError:
            selected_date_str = ""

    return render(request, "app/calendar.html", {
        "cal_weeks":        cal_weeks,
        "month":            month,
        "year":             year,
        "month_name":       cal_module.month_name[month],
        "booked_dates":     booked_dates,
        "prev_month":       prev_month,
        "prev_year":        prev_year,
        "next_month":       next_month,
        "next_year":        next_year,
        "today":            today,
        "time_slots":       Booking.TIME_SLOTS,
        "booked_times":     booked_times,
        "selected_date":    selected_date,
        "selected_date_str": selected_date_str,
    })


# ─────────────────────────────────────────────── monitor ──────────────────────

@login_required(login_url="login")
@_admin_required
def monitor_view(request):
    logs = UserLog.objects.select_related("user").all().order_by("-time_in")

    q_name   = request.GET.get("name", "").strip()
    q_action = request.GET.get("action", "").strip()
    q_from   = request.GET.get("date_from", "").strip()
    q_to     = request.GET.get("date_to", "").strip()

    if q_name:
        logs = logs.filter(
            Q(first_name__icontains=q_name) | Q(last_name__icontains=q_name)
        )
    if q_action and q_action != "All":
        logs = logs.filter(activities__icontains=q_action)
    if q_from:
        logs = logs.filter(time_in__date__gte=q_from)
    if q_to:
        logs = logs.filter(time_in__date__lte=q_to)

    return render(request, "app/monitor.html", {
        "logs":     logs,
        "q_name":   q_name,
        "q_action": q_action,
        "q_from":   q_from,
        "q_to":     q_to,
    })


# ─────────────────────────────────────────────── employees ────────────────────

@login_required(login_url="login")
@_admin_required
def employee_view(request):
    query     = request.GET.get("q", "").strip()
    employees = UserLog.objects.select_related("user").all().order_by("last_name", "first_name")

    if query:
        employees = employees.filter(
            Q(first_name__icontains=query)  |
            Q(last_name__icontains=query)   |
            Q(middle_name__icontains=query) |
            Q(role__icontains=query)        |
            Q(phone_number__icontains=query)
        ).distinct()

    return render(request, "app/viewemployee.html", {
        "employees": employees, "query": query,
    })


@login_required(login_url="login")
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
                    username=d["username"],
                    password=d["password"],
                    email=d.get("email", ""),
                    first_name=d["first_name"],
                    last_name=d["last_name"],
                )
                UserLog.objects.create(
                    user=user,
                    role=d["role"],
                    first_name=d["first_name"],
                    middle_name=d.get("middle_name", "") or "",
                    last_name=d["last_name"],
                    date_of_birth=d["date_of_birth"],
                    government_id=d.get("government_id", ""),
                    phone_number=d.get("phone_number", ""),
                    email=d.get("email", ""),
                    address=d["address"],
                    emergency_contact_name=d["emergency_contact_name"],
                    emergency_contact_number=d["emergency_contact_number"],
                    activities="Account created",
                    pin=d["pin"],
                )

            messages.success(
                request,
                f"Employee '{d['first_name']} {d['last_name']}' created successfully."
            )
            return redirect("employee")

        return render(request, "app/add-employee.html", {"form": form})

    return render(request, "app/add-employee.html", {"form": EmployeeCreateForm()})


@login_required(login_url="login")
@_admin_required
def details_employee_view(request, pk):
    employee = get_object_or_404(UserLog, pk=pk)

    duration_str = "—"
    if employee.time_in and employee.time_out:
        delta   = employee.time_out - employee.time_in
        minutes = int(delta.total_seconds() // 60)
        duration_str = f"{minutes // 60}h {minutes % 60}m"

    return render(request, "app/employee-details.html", {
        "employee": employee, "duration_str": duration_str,
    })


@login_required(login_url="login")
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
                employee.pin                      = d["pin"]
                employee.save()

                if employee.user:
                    employee.user.first_name = d["first_name"]
                    employee.user.last_name  = d["last_name"]
                    employee.user.email      = d["email"]
                    if d.get("new_password"):
                        employee.user.set_password(d["new_password"])
                    employee.user.save()

            messages.success(request, "Employee updated successfully.")
            return redirect("details-employee", pk=pk)
    else:
        form = EmployeeUpdateForm(initial={
            "first_name":               employee.first_name,
            "middle_name":              employee.middle_name,
            "last_name":                employee.last_name,
            "date_of_birth":            employee.date_of_birth,
            "address":                  employee.address,
            "email":                    employee.email,
            "phone_number":             employee.phone_number,
            "emergency_contact_name":   employee.emergency_contact_name,
            "emergency_contact_number": employee.emergency_contact_number,
            "role":                     employee.role,
            "government_id":            employee.government_id,
            "pin":                      employee.pin,
        })

    return render(request, "app/employee-edit.html", {
        "form": form, "employee": employee,
    })


@login_required(login_url="login")
@_admin_required
def delete_employee_view(request, pk):
    if request.method != "POST":
        return JsonResponse({"success": False, "error": "Method not allowed."}, status=405)

    if request.POST.get("pin", "") != _get_pin(request.user):
        return JsonResponse({"success": False, "error": "Invalid PIN."})

    employee = get_object_or_404(UserLog, pk=pk)
    if employee.user == request.user:
        return JsonResponse({"success": False, "error": "You cannot delete your own account."})

    name = employee.full_name()
    with transaction.atomic():
        if employee.user:
            employee.user.delete()
        else:
            employee.delete()

    return JsonResponse({"success": True, "name": name})
