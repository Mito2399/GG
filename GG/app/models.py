# app/models.py

import math
from decimal import Decimal, ROUND_HALF_UP
from functools import cached_property

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class ClientPersonalInfo(models.Model):
    client_first_name       = models.CharField(max_length=200)
    client_middle_name      = models.CharField(max_length=200, blank=True, null=True)
    client_last_name        = models.CharField(max_length=200)
    client_address          = models.CharField(max_length=200)
    client_contact_number   = models.CharField(max_length=13)

    client_civil_status = models.CharField(
        max_length=20,
        choices=[
            ("Single",    "Single"),
            ("Married",   "Married"),
            ("Widowed",   "Widowed"),
            ("Separated", "Separated"),
        ],
    )

    client_date_birth        = models.DateField()
    client_religion          = models.CharField(max_length=200)
    client_occupation        = models.CharField(max_length=200)
    client_employer_name     = models.CharField(max_length=200)
    client_employer_address  = models.CharField(max_length=200)
    client_spouse_name       = models.CharField(max_length=200, blank=True, null=True)
    client_spouse_date_birth = models.DateField(blank=True, null=True)
    client_spouse_occupation = models.CharField(max_length=200, blank=True, null=True)
    client_spouse_employer   = models.CharField(max_length=200, blank=True, null=True)

    client_id_type = models.CharField(
        max_length=50, blank=True, null=True,
        choices=[
            ("Passport",         "Passport"),
            ("Driver's License", "Driver's License"),
            ("National ID",      "National ID"),
            ("SSS ID",           "SSS ID"),
            ("GSIS ID",          "GSIS ID"),
            ("UMID",             "UMID"),
            ("Postal ID",        "Postal ID"),
            ("Other",            "Other"),
        ],
        help_text="DEPRECATED — use GovernmentID model instead.",
    )
    client_id_type_other = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="DEPRECATED — specify ID type when 'Other' was selected.",
    )
    client_id_number = models.CharField(
        max_length=50, blank=True, null=True,
        help_text="DEPRECATED — use GovernmentID model instead.",
    )

    @property
    def full_name(self):
        middle = f" {self.client_middle_name}" if self.client_middle_name else ""
        return f"{self.client_first_name}{middle} {self.client_last_name}".strip()

    @property
    def display_id_type(self):
        if self.client_id_type == "Other" and self.client_id_type_other:
            return self.client_id_type_other
        return self.client_id_type

    def __str__(self):
        return self.full_name


class Beneficiary(models.Model):
    RELATIONSHIP_CHOICES = [
        ("Husband", "Husband"),
        ("Wife",    "Wife"),
        ("Other",   "Other"),
    ]

    client       = models.ForeignKey(
        ClientPersonalInfo,
        on_delete=models.CASCADE,
        related_name="beneficiaries",
    )
    name         = models.CharField(max_length=200)
    relationship = models.CharField(
        max_length=20,
        choices=RELATIONSHIP_CHOICES,
        help_text="Beneficiary's relationship to the client.",
    )
    specify_relationship = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Custom relationship when 'Other' is selected.",
    )

    @property
    def display_relationship(self):
        if self.relationship == "Other" and (self.specify_relationship or "").strip():
            return self.specify_relationship
        return self.relationship

    def __str__(self):
        return f"{self.client.full_name}: {self.name} — {self.display_relationship}"


class GovernmentID(models.Model):
    ID_TYPE_CHOICES = [
        ("Passport",         "Passport"),
        ("Driver's License", "Driver's License"),
        ("National ID",      "National ID"),
        ("SSS ID",           "SSS ID"),
        ("GSIS ID",          "GSIS ID"),
        ("UMID",             "UMID"),
        ("Postal ID",        "Postal ID"),
        ("Other",            "Other"),
    ]

    client        = models.ForeignKey(
        ClientPersonalInfo,
        on_delete=models.CASCADE,
        related_name="government_ids",
    )
    id_type       = models.CharField(max_length=50, choices=ID_TYPE_CHOICES)
    id_type_other = models.CharField(
        max_length=100, blank=True, null=True,
        help_text="Specify ID type when 'Other' is selected.",
    )
    id_number     = models.CharField(
        max_length=50,
        help_text="Alphanumeric ID number (letters, digits, hyphens, spaces).",
    )

    class Meta:
        ordering = ["pk"]

    @property
    def display_id_type(self):
        if self.id_type == "Other" and self.id_type_other:
            return self.id_type_other
        return self.id_type

    def __str__(self):
        return f"{self.client.full_name}: {self.display_id_type} — {self.id_number}"


class ClientStatus(models.Model):
    PLAN_CHOICES = [
        ("No Plan",    "No Plan"),
        ("Lawn Lot",   "Lawn Lot"),
        ("Garden Lot", "Garden Lot"),
        ("Mausoleum",  "Mausoleum"),
        ("THS",        "THS"),
        ("THTC",       "THTC"),
        ("TCT A/R",    "TCT A/R"),
    ]

    REMAINS_TYPE_CHOICES = [
        ("Fresh Body",    "Fresh Body"),
        ("Bone Transfer", "Bone Transfer"),
        ("Ash",           "Ash"),
        ("Others",        "Others"),
    ]

    TCT_INITIAL_TERM_YEARS = 7
    TCT_RENEWAL_TERM_YEARS = 1

    client           = models.ForeignKey(ClientPersonalInfo, on_delete=models.CASCADE)
    plan             = models.CharField(max_length=200, choices=PLAN_CHOICES)
    monthly_payment  = models.DecimalField(max_digits=20, decimal_places=2)
    duration         = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Duration in months (free-form positive integer).",
    )
    down_payment     = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)

    total_price = models.DecimalField(
        max_digits=20, decimal_places=2,
        null=True, blank=True,
        help_text="Contract price as entered in the plan form (Lot Price).",
    )
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentage discount on the down payment (0 = no discount).",
    )
    pcare_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0.00,
        help_text="Percentage of the total contract price allocated to perpetual care.",
    )
    months_remaining = models.IntegerField()
    start_date       = models.DateField()
    balance          = models.DecimalField(max_digits=20, decimal_places=2)
    paid_balance     = models.DecimalField(max_digits=20, decimal_places=2)
    date_paid        = models.DateTimeField(blank=True, null=True)
    status           = models.BooleanField(default=True)

    phase      = models.CharField(max_length=200, blank=True, null=True)
    block      = models.CharField(max_length=200, blank=True, null=True)
    section    = models.CharField(max_length=200, blank=True, null=True)
    lot_number = models.CharField(max_length=200, blank=True, null=True)
    pa_number  = models.CharField(max_length=200, blank=True, null=True)

    la_number  = models.CharField(max_length=200, blank=True, null=True,
                     help_text="Used instead of P.A. Number for TCT A/R lots.")

    contract_number  = models.CharField(max_length=200, blank=True, null=True)
    interment_date   = models.DateField(blank=True, null=True)
    date_fully_paid  = models.DateField(blank=True, null=True,
        help_text="Auto-filled when the last monthly payment is settled.")
    pa_date          = models.DateField(blank=True, null=True)

    date_of_death            = models.DateField(blank=True, null=True,
        help_text="Date of death (relevant for TCT A/R plans).")
    death_certificate_number = models.CharField(max_length=200, blank=True, null=True,
        help_text="Death certificate number (relevant for TCT A/R plans).")

    remains_type = models.CharField(
        max_length=50,
        choices=REMAINS_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text="Type of remains being interred.",
    )
    remains_type_other = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Specify the type of remains when 'Others' is selected.",
    )

    documentation_fee = models.DecimalField(
        max_digits=20, decimal_places=2, default=0,
        help_text="Documentation fee (relevant for TCT A/R contracts).")

    sales_agent = models.CharField(
        max_length=200, blank=True, null=True,
        help_text="Auto-assigned from the user who created the plan.",
    )

    due_day = models.PositiveSmallIntegerField(
        default=2,
        help_text=(
            "Day of the month (1–31) on which monthly installments are due. "
            "The payment schedule is generated on this day of every month."
        ),
    )

    penalty_rate = models.DecimalField(
        max_digits=5, decimal_places=2, default=3.00,
        help_text="Monthly penalty rate for overdue installments (%)."
    )

    column_level = models.CharField(max_length=200, blank=True, null=True,
        help_text="Column/level value for THTC and TCT A/R lots.")

    LAWN_LOT_TYPE_CHOICES = [
        ("Regular", "Regular"),
        ("Deluxe",  "Deluxe"),
        ("Prime B", "Prime B"),
        ("Prime A", "Prime A"),
    ]
    lawn_lot_type = models.CharField(
        max_length=50, blank=True, null=True,
        choices=LAWN_LOT_TYPE_CHOICES,
        help_text="Lawn Lot subcategory (relevant for Lawn Lot plans).")

    REGULAR_LOT_PACKAGE_CHOICES = [
        ("3 in 1",                     "3 in 1 — Lot / 3 Days Viewing / Interment Service"),
        ("2 in 1 - Lot/Interment",     "2 in 1 — Lawn Lot Regular / Interment"),
        ("2 in 1 - Viewing/Interment", "2 in 1 — 3-Days Viewing / Interment Service"),
    ]
    regular_lot_package = models.CharField(
        max_length=100, blank=True, null=True,
        choices=REGULAR_LOT_PACKAGE_CHOICES,
        help_text="Regular Lawn Lot package (only for Regular Lawn Lot).")

    GARDEN_TYPE_CHOICES = [
        ("Love",      "Love"),
        ("Happiness", "Happiness"),
        ("Peace",     "Peace"),
    ]
    garden_type = models.CharField(
        max_length=50, blank=True, null=True,
        choices=GARDEN_TYPE_CHOICES,
        help_text="Garden Lot subcategory (relevant for Garden Lot plans).")

    GARDEN_SECTION_CHOICES = [
        ("Regular", "Regular"),
        ("Deluxe",  "Deluxe"),
        ("Prime",   "Prime"),
    ]
    garden_section = models.CharField(
        max_length=50, blank=True, null=True,
        choices=GARDEN_SECTION_CHOICES,
        help_text="Garden Lot section (relevant for Garden Lot plans).")

    MAUSOLEUM_TYPE_CHOICES = [
        ("Junior Court",    "Junior Court"),
        ("Senior Court",    "Senior Court"),
        ("Executive Court", "Executive Court"),
        ("The Estate",      "The Estate"),
    ]
    mausoleum_type = models.CharField(
        max_length=50, blank=True, null=True,
        choices=MAUSOLEUM_TYPE_CHOICES,
        help_text="Mausoleum subcategory (relevant for Mausoleum plans).")
    sqm = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True,
        help_text="Size in square meters (relevant for Mausoleum plans).")

    THS_TYPE_CHOICES = [
        ("Niche",       "Niche"),
        ("Columbarium", "Columbarium"),
    ]
    THS_NICHE_SECTIONS = [
        ("St. Vincent", "St. Vincent"),
        ("St. John",    "St. John"),
        ("St. Luke",    "St. Luke"),
        ("St. Mathew",  "St. Mathew"),
        ("St. Mark",    "St. Mark"),
    ]
    THS_COLUMBARIUM_SECTIONS = [
        ("St. Paul - Love",    "St. Paul - Love"),
        ("St. Paul - Hope",    "St. Paul - Hope"),
        ("St. Paul - Faith",   "St. Paul - Faith"),
        ("St. Paul - Justice", "St. Paul - Justice"),
    ]
    THS_SECTION_CHOICES = THS_NICHE_SECTIONS + THS_COLUMBARIUM_SECTIONS

    THTC_SECTION_CHOICES = [
        ("St. Gabriel I",   "St. Gabriel I"),
        ("St. Gabriel II",  "St. Gabriel II"),
        ("St. Gabriel III", "St. Gabriel III"),
        ("St. Rafael III",  "St. Rafael III"),
    ]
    ths_type    = models.CharField(max_length=50, blank=True, null=True,
                      choices=THS_TYPE_CHOICES,
                      help_text="THS classification — Niche or Columbarium.")
    ths_section = models.CharField(max_length=50, blank=True, null=True,
                      choices=THS_SECTION_CHOICES)
    ths_column  = models.CharField(max_length=200, blank=True, null=True)

    COLUMBARIUM_TYPE_CHOICES = [
        ("TCT A/R Niche 1", "TCT A/R Niche 1"),
        ("TCT A/R Niche 2", "TCT A/R Niche 2"),
    ]
    COLUMBARIUM_LEVEL_CHOICES = [
        (1, "Level 1"),
        (2, "Level 2"),
        (3, "Level 3"),
        (4, "Level 4"),
    ]
    columbarium_type  = models.CharField(max_length=50, blank=True, null=True,
                            choices=COLUMBARIUM_TYPE_CHOICES)
    columbarium_level = models.IntegerField(blank=True, null=True,
                            choices=COLUMBARIUM_LEVEL_CHOICES)
    tomb_number       = models.CharField(max_length=200, blank=True, null=True)

    is_cancelled        = models.BooleanField(default=False)
    cancellation_reason = models.TextField(blank=True, null=True)
    cancellation_date   = models.DateField(blank=True, null=True)

    # ══════════════════════════════════════════════════════════════════════
    # FINANCIAL PROPERTIES
    # ══════════════════════════════════════════════════════════════════════

    @property
    def is_tct_ar(self):
        return self.plan == "TCT A/R"

    @property
    def total_lot(self):
        return self.total_price or Decimal('0.00')

    @property
    def total_pcare(self):
        if self.total_lot and self.pcare_percent:
            return (self.total_lot * (self.pcare_percent / Decimal('100'))
                    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @property
    def total_contract_price(self):
        return self.total_lot - self.total_pcare

    @property
    def total_price_alias(self):
        return self.total_contract_price

    @property
    def total_lot_excl_doc(self):
        return self.total_contract_price

    @property
    def down_payment_total(self):
        return self.down_payment or Decimal('0.00')

    @property
    def down_payment_pcare(self):
        if self.down_payment_total and self.pcare_percent:
            return (self.down_payment_total * (self.pcare_percent / Decimal('100'))
                    ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @property
    def down_payment_lot(self):
        return self.down_payment_total - self.down_payment_pcare

    @property
    def effective_down_payment(self):
        return self.down_payment_total

    @property
    def financed_balance_lot(self):
        return self.total_contract_price - self.down_payment_lot

    @property
    def financed_balance_pcare(self):
        return self.total_pcare - self.down_payment_pcare

    @property
    def financed_balance(self):
        return self.financed_balance_lot + self.financed_balance_pcare

    @property
    def monthly_lot(self):
        if self.duration and self.duration > 0:
            net_lot_balance = self.total_contract_price - self.down_payment_lot
            if net_lot_balance > 0:
                return (net_lot_balance / self.duration).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    @property
    def monthly_pcare(self):
        if self.duration and self.duration > 0:
            net_pcare_balance = self.total_pcare - self.down_payment_pcare
            if net_pcare_balance > 0:
                return (net_pcare_balance / self.duration).quantize(
                    Decimal('0.01'), rounding=ROUND_HALF_UP)
        return Decimal('0.00')

    # ══════════════════════════════════════════════════════════════════════
    # DYNAMIC MONTHLY PAYMENT LOGIC
    # ══════════════════════════════════════════════════════════════════════

    @property
    def effective_monthly_payment(self):
        if self.is_tct_ar or self.duration <= 0 or self.balance <= 0:
            return self.monthly_payment

        sibling_plans = ClientStatus.objects.filter(
            client=self.client,
            is_cancelled=False,
            status=True,
            balance__gt=0,
        ).exclude(pk=self.pk)

        total_active_plans = sibling_plans.count() + 1

        if total_active_plans > 1:
            return (self.monthly_payment / Decimal('2')).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP)

        return self.monthly_payment

    # ══════════════════════════════════════════════════════════════════════
    # DISPLAY-ONLY PROPERTIES
    # ══════════════════════════════════════════════════════════════════════

    @property
    def monthly_lot_display(self):
        val = self.effective_monthly_payment
        if val and val > 0:
            return Decimal(math.ceil(val))
        return Decimal('0.00')

    @property
    def monthly_pcare_display(self):
        return Decimal('0.00')

    # ══════════════════════════════════════════════════════════════════════
    # INSTALLMENT DUE — NET
    # ══════════════════════════════════════════════════════════════════════

    @property
    def installment_due_lot(self):
        if self.is_tct_ar or not self.duration or self.duration <= 0:
            return Decimal('0.00')
        net_lot_balance = self.total_contract_price - self.down_payment_lot
        if net_lot_balance <= 0:
            return Decimal('0.00')
        return (net_lot_balance / Decimal(str(self.duration))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    @property
    def installment_due_lot_display(self):
        val = self.installment_due_lot
        if val and val > 0:
            return Decimal(math.ceil(val))
        return Decimal('0.00')

    @property
    def pcare_amount(self):
        return self.monthly_pcare

    @property
    def lot_amount(self):
        return self.monthly_lot

    @cached_property
    def paid_lot_total(self):
        return sum((p.lot_amount or Decimal('0.00'))
                   for p in self.payments.filter(is_paid=True))

    @cached_property
    def paid_pcare_total(self):
        return sum((p.pcare_amount or Decimal('0.00'))
                   for p in self.payments.filter(is_paid=True))

    @property
    def pcare_balance(self):
        return max(self.financed_balance_pcare - self.paid_pcare_total, Decimal('0.00'))

    @property
    def total_balance(self):
        return self.balance

    @property
    def maturity_date(self):
        if not self.start_date or not self.duration:
            return None
        total_months = self.start_date.month - 1 + self.duration
        year  = self.start_date.year + total_months // 12
        month = total_months % 12 + 1
        return self.start_date.replace(year=year, month=month, day=1)

    # ══════════════════════════════════════════════════════════════════════
    # DUE-DAY DISPLAY
    # ══════════════════════════════════════════════════════════════════════

    @property
    def due_day_display(self):
        d = self.due_day or 2
        if 10 <= (d % 100) <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(d % 10, "th")
        return f"Every {d}{suffix} day of the month"

    # ══════════════════════════════════════════════════════════════════════
    # HEADER-CARD INSTALLMENT DUE
    # ══════════════════════════════════════════════════════════════════════

    @property
    def total_monthly_installment(self):
        if self.is_tct_ar or not self.duration or self.duration <= 0:
            return Decimal('0.00')
        
        # 138,000 / 60 = 2,300
        total_balance = self.total_lot - self.down_payment_total
        if total_balance <= 0:
            return Decimal('0.00')
            
        return (total_balance / Decimal(str(self.duration))).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )

    @property
    def total_monthly_installment_display(self):
        val = self.total_monthly_installment
        if val and val > 0:
            return Decimal(math.ceil(val))
        return Decimal('0.00')

    # ══════════════════════════════════════════════════════════════════════
    # TCT/A/R EXPIRATION & RENEWAL
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _safe_add_years(dt, years):
        if dt is None:
            return None
        try:
            return dt.replace(year=dt.year + years)
        except ValueError:
            return dt.replace(year=dt.year + years, day=28)

    @property
    def tct_initial_expiration_date(self):
        if self.plan != "TCT A/R" or not self.start_date:
            return None
        return self._safe_add_years(self.start_date, self.TCT_INITIAL_TERM_YEARS)

    @property
    def tct_active_renewal(self):
        if self.plan != "TCT A/R" or not self.pk:
            return None
        return self.tct_renewals.filter(status="Active").order_by("-renewal_number").first()

    @property
    def tct_current_expiration_date(self):
        if self.plan != "TCT A/R":
            return None
        active = self.tct_active_renewal
        if active:
            return active.new_expiration_date
        return self.tct_initial_expiration_date

    @property
    def tct_renewal_status(self):
        if self.plan != "TCT A/R":
            return None
        if self.is_cancelled:
            return "CANCELLED"
        exp = self.tct_current_expiration_date
        if exp is None:
            return None
        today = timezone.localdate()
        if today > exp:
            return "EXPIRED"
        if self.tct_active_renewal:
            return "RENEWED"
        return "ACTIVE"

    @property
    def tct_days_until_expiration(self):
        exp = self.tct_current_expiration_date
        if exp is None:
            return None
        return (exp - timezone.localdate()).days

    @property
    def tct_can_renew(self):
        if self.plan != "TCT A/R" or self.is_cancelled:
            return False
        initial = self.tct_initial_expiration_date
        if initial is None:
            return False
        return timezone.localdate() > initial

    @property
    def tct_next_renewal_number(self):
        last = self.tct_renewals.order_by("-renewal_number").first()
        return (last.renewal_number if last else 0) + 1

    @property
    def tct_renewal_count(self):
        return self.tct_renewals.count()


class TCTARRenewal(models.Model):
    STATUS_CHOICES = [
        ("Active",     "Active"),
        ("Superseded", "Superseded"),
        ("Cancelled",  "Cancelled"),
    ]

    client_status = models.ForeignKey(
        ClientStatus, on_delete=models.CASCADE, related_name="tct_renewals")
    renewal_number           = models.PositiveIntegerField()
    previous_expiration_date = models.DateField()
    renewal_date             = models.DateField()
    new_expiration_date      = models.DateField()
    renewal_period_years     = models.PositiveIntegerField(default=1)
    status                   = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="Active")
    note = models.CharField(max_length=500, blank=True, default="")
    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="processed_tct_renewals")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["client_status_id", "renewal_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["client_status", "renewal_number"],
                name="unique_tct_renewal_number_per_plan",
            ),
        ]

    def __str__(self):
        return (f"{self.client_status.client.full_name} — "
                f"Renewal #{self.renewal_number} → {self.new_expiration_date}")


class IntermentRecipient(models.Model):
    client_status = models.ForeignKey(
        ClientStatus, on_delete=models.CASCADE, related_name="interment_recipients")
    name = models.CharField(max_length=200)

    def __str__(self):
        return f"{self.client_status.client.full_name} — {self.name}"


class Payment(models.Model):
    client_status = models.ForeignKey(
        ClientStatus, on_delete=models.CASCADE, related_name="payments")
    installment_no = models.PositiveIntegerField(null=True, blank=True)
    csi_number = models.CharField(max_length=50, blank=True, null=True)
    lot_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    pcare_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    penalty_charges = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    payment_charges = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    installment_due = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    running_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    running_pcare_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    running_total_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    month = models.DateField(blank=True, null=True)
    amount = models.DecimalField(max_digits=20, decimal_places=2)
    is_paid = models.BooleanField(default=False)
    date_paid = models.DateTimeField(blank=True, null=True)
    note = models.CharField(max_length=500, blank=True, default="")
    processed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="processed_payments")

    overpayment = models.DecimalField(
        max_digits=20, decimal_places=2, default=0.00,
        help_text="Excess payment carried forward to next installment."
    )

    months_covered = models.PositiveIntegerField(
        default=1,
        help_text=(
            "Number of monthly installments this single payment covers. "
            "1 = pays only the current installment. "
            "N>1 = pays the current installment and the next (N-1) installments."
        ),
    )

    class Meta:
        ordering = ["month"]

    def __str__(self):
        status = "Paid" if self.is_paid else "Unpaid"
        return f"{self.client_status.client.full_name} – {status}"


class Booking(models.Model):
    EVENT_CHOICES = [("Viewing", "Viewing"), ("Interment", "Interment")]
    TIME_SLOTS = [
        ("07:00", "7:00 AM"), ("08:00", "8:00 AM"), ("09:00", "9:00 AM"),
        ("10:00", "10:00 AM"), ("11:00", "11:00 AM"), ("12:00", "12:00 PM"),
        ("13:00", "1:00 PM"), ("14:00", "2:00 PM"), ("15:00", "3:00 PM"),
        ("16:00", "4:00 PM"), ("17:00", "5:00 PM"),
    ]
    STATUS_CHOICES = [
        ("Active", "Active"), ("Completed", "Completed"),
        ("Cancelled", "Cancelled"), ("No Show", "No Show"),
    ]

    client = models.ForeignKey(
        ClientPersonalInfo, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bookings")
    client_name    = models.CharField(max_length=200)
    contact_number = models.CharField(max_length=13)
    event_type     = models.CharField(max_length=50, choices=EVENT_CHOICES)
    booking_date   = models.DateField()
    booking_time   = models.CharField(max_length=5, choices=TIME_SLOTS)
    notes          = models.TextField(blank=True)
    created_at     = models.DateTimeField(auto_now_add=True)
    status              = models.CharField(max_length=20, choices=STATUS_CHOICES, default="Active")
    cancellation_reason = models.TextField(blank=True, null=True)
    cancelled_at        = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["booking_date", "booking_time"]
        constraints = [
            models.UniqueConstraint(
                fields=["booking_date", "booking_time"],
                condition=models.Q(status="Active"),
                name="unique_active_booking_slot",
            ),
        ]

    def __str__(self):
        return (f"{self.client_name} — {self.event_type} on "
                f"{self.booking_date} at {self.get_booking_time_display()}")


class UserLog(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    role = models.CharField(
        max_length=200,
        choices=[
            ("Accounting Staff", "Accounting Staff"),
            ("Marketing Staff",  "Marketing Staff"),
            ("General Staff",    "General Staff"),
        ],
        null=True, blank=True,
    )
    first_name               = models.CharField(max_length=200, null=True, blank=True)
    middle_name              = models.CharField(max_length=200, null=True, blank=True)
    last_name                = models.CharField(max_length=200, null=True, blank=True)
    date_of_birth            = models.DateField(blank=True, null=True)
    government_id            = models.CharField(max_length=200, null=True, blank=True)
    phone_number             = models.CharField(max_length=13, null=True, blank=True)
    address                  = models.CharField(max_length=200, null=True, blank=True)
    email                    = models.EmailField(max_length=200, null=True, blank=True)
    emergency_contact_name   = models.CharField(max_length=200, null=True, blank=True)
    emergency_contact_number = models.CharField(max_length=13, null=True, blank=True)
    time_in                  = models.DateTimeField(blank=True, null=True)
    time_out                 = models.DateTimeField(blank=True, null=True)
    activities               = models.CharField(max_length=500, null=True, blank=True)
    pin                      = models.CharField(max_length=128)

    @property
    def full_name(self):
        middle = f" {self.middle_name}" if self.middle_name else ""
        return f"{self.first_name or ''}{middle} {self.last_name or ''}".strip()

    def __str__(self):
        return self.full_name


class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ("Login", "Login"), ("Logout", "Logout"),
        ("Add Client", "Add Client"), ("Edit Record", "Edit Record"),
        ("Delete Client", "Delete Client"), ("Add Plan", "Add Plan"),
        ("Cancel Plan", "Cancel Plan"), ("Add Payment", "Add Payment"),
        ("Add Booking", "Add Booking"), ("Cancel Booking", "Cancel Booking"),
        ("Add Employee", "Add Employee"), ("Edit Employee", "Edit Employee"),
        ("Delete Employee", "Delete Employee"),
        ("Renew TCT A/R", "Renew TCT A/R"),
    ]
    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="activity_logs")
    staff_name = models.CharField(max_length=200, blank=True)
    role       = models.CharField(max_length=200, blank=True)
    action     = models.CharField(max_length=100, choices=ACTION_CHOICES)
    detail     = models.CharField(max_length=500, blank=True)
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.staff_name} — {self.action}"


class SystemSecret(models.Model):
    key             = models.CharField(max_length=100, unique=True)
    encrypted_value = models.TextField(blank=True, default="")
    label           = models.CharField(max_length=200, blank=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key

    def get_value(self) -> str:
        from .crypto import decrypt_value
        return decrypt_value(self.key, self.encrypted_value)

    def set_value(self, plaintext: str) -> None:
        from .crypto import encrypt_value
        self.encrypted_value = encrypt_value(self.key, plaintext)

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        try:
            obj = cls.objects.get(key=key)
            return obj.get_value() or default
        except cls.DoesNotExist:
            return default