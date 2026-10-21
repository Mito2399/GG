from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from .models import (
    ClientPersonalInfo, Beneficiary, GovernmentID,
    UserLog, ClientStatus, Booking, IntermentRecipient,
)
import re
from datetime import date
from decimal import Decimal, ROUND_HALF_UP


RELATIONSHIP_CHOICES = [
    ("",              "Select Relationship"),
    ("Spouse",        "Spouse"), ("Son",           "Son"),
    ("Daughter",      "Daughter"), ("Father",       "Father"),
    ("Mother",        "Mother"), ("Brother",       "Brother"),
    ("Sister",        "Sister"), ("Grandfather",   "Grandfather"),
    ("Grandmother",   "Grandmother"), ("Grandson",  "Grandson"),
    ("Granddaughter", "Granddaughter"), ("Uncle",   "Uncle"),
    ("Aunt",          "Aunt"), ("Nephew",          "Nephew"),
    ("Niece",         "Niece"), ("Cousin",         "Cousin"),
    ("Father-in-law", "Father-in-law"), ("Mother-in-law", "Mother-in-law"),
    ("Brother-in-law","Brother-in-law"), ("Sister-in-law", "Sister-in-law"),
    ("Guardian",      "Guardian"), ("Friend",       "Friend"),
    ("Other",         "Other"),
]


# ─────────────────────────────────────────────── helpers ──────────────────────

class BootstrapForm(forms.ModelForm):
    placeholders = {}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = (existing + " form-control").strip()
            ph = self.placeholders.get(field_name)
            if ph and not isinstance(field.widget, forms.Select):
                field.widget.attrs["placeholder"] = ph

        if "data" in kwargs:
            data = kwargs["data"].copy()
            for key, value in data.items():
                if isinstance(value, str):
                    data[key] = value.strip()
            self.data = data

    def clean(self):
        cleaned_data = super().clean()
        for field, value in cleaned_data.items():
            if isinstance(value, str):
                cleaned_data[field] = value.strip()
        return cleaned_data


def clean_name(value, field_name="Name"):
    value = (value or "").strip()
    if not value:
        raise forms.ValidationError(f"{field_name} is required.")
    if not re.match(r"^[A-Za-z\s\-\.]+$", value):
        raise forms.ValidationError(
            f"{field_name} can only contain letters, spaces, hyphens, or periods."
        )
    return value.title()


def clean_address(value, field_name="Address"):
    value = (value or "").strip()
    if not value:
        raise forms.ValidationError(f"{field_name} is required.")
    return value.title()


def clean_phone_number(number):
    number = (number or "").strip()
    digits = re.sub(r"\D", "", number)
    if len(digits) == 11 and digits.startswith("09"):
        return digits
    if len(digits) == 12 and digits.startswith("639"):
        return "0" + digits[2:]
    raise forms.ValidationError("Enter a valid Philippine mobile number (09XXXXXXXXX).")


def clean_date_of_birth(dob, min_age=18):
    if dob:
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < min_age:
            raise forms.ValidationError(f"Person must be at least {min_age} years old.")
    return dob


def clean_pin_field(value):
    pin = str(value or "").strip()
    if not pin.isdigit() or len(pin) != 4:
        raise forms.ValidationError("PIN must be exactly 4 digits (e.g. 0010).")
    return pin


def clean_id_number(value):
    v = (value or "").strip()
    if not v:
        raise forms.ValidationError("ID number is required.")
    if len(v) < 3:
        raise forms.ValidationError("ID number is too short.")
    if len(v) > 50:
        raise forms.ValidationError("ID number is too long (max 50 characters).")
    if not re.match(r"^[A-Za-z0-9\-\s]+$", v):
        raise forms.ValidationError(
            "ID number can only contain letters, digits, hyphens, and spaces."
        )
    return v


# ─────────────────────────────────────────────── ClientForm ───────────────────

class ClientForm(BootstrapForm):
    class Meta:
        model  = ClientPersonalInfo
        fields = [
            "client_first_name", "client_middle_name", "client_last_name",
            "client_address", "client_contact_number", "client_civil_status",
            "client_date_birth", "client_religion", "client_occupation",
            "client_employer_name", "client_employer_address",
            "client_spouse_name", "client_spouse_date_birth",
            "client_spouse_occupation", "client_spouse_employer",
        ]
        widgets = {
            "client_date_birth":        forms.DateInput(attrs={"type": "date"}),
            "client_spouse_date_birth": forms.DateInput(attrs={"type": "date"}),
        }

    placeholders = {
        "client_first_name":        "First name",
        "client_middle_name":       "Middle name (Optional)",
        "client_last_name":         "Last name",
        "client_address":           "Home address",
        "client_contact_number":    "09XXXXXXXXX",
        "client_date_birth":        "YYYY-MM-DD",
        "client_religion":          "Religion",
        "client_occupation":        "Occupation",
        "client_employer_name":     "Employer name",
        "client_employer_address":  "Employer address",
        "client_spouse_name":       "Spouse name",
        "client_spouse_date_birth": "YYYY-MM-DD",
        "client_spouse_occupation": "Spouse occupation",
        "client_spouse_employer":   "Spouse employer",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        civil_choices = [("", "Select Status")] + list(
            ClientPersonalInfo._meta.get_field("client_civil_status").choices
        )
        self.fields["client_civil_status"] = forms.ChoiceField(
            choices=civil_choices,
            widget=forms.Select(attrs={"class": "form-control"}),
            required=True,
        )
        self.fields["client_contact_number"].widget.attrs.update(
            {"maxlength": "11", "inputmode": "numeric"}
        )

    def clean_client_first_name(self):
        return clean_name(self.cleaned_data.get("client_first_name"), "First name")

    def clean_client_last_name(self):
        return clean_name(self.cleaned_data.get("client_last_name"), "Last name")

    def clean_client_contact_number(self):
        return clean_phone_number(self.cleaned_data.get("client_contact_number"))

    def clean_client_address(self):
        return clean_address(self.cleaned_data.get("client_address"), "Home address")

    def clean_client_date_birth(self):
        return clean_date_of_birth(self.cleaned_data.get("client_date_birth"))

    def clean_client_religion(self):
        v = self.cleaned_data.get("client_religion", "").strip()
        if not v:
            raise forms.ValidationError("Religion is required.")
        return v.title()

    def clean_client_occupation(self):
        v = self.cleaned_data.get("client_occupation", "").strip()
        if not v:
            raise forms.ValidationError("Occupation is required.")
        return v.title()

    def clean_client_employer_name(self):
        v = self.cleaned_data.get("client_employer_name", "").strip()
        if not v:
            raise forms.ValidationError("Employer name is required.")
        return v.title()

    def clean_client_employer_address(self):
        v = self.cleaned_data.get("client_employer_address", "").strip()
        if not v:
            raise forms.ValidationError("Employer address is required.")
        return v.title()


# ─────────────────────────────────────────────── BeneficiaryForm ──────────────

class BeneficiaryForm(forms.ModelForm):
    class Meta:
        model  = Beneficiary
        fields = ("name", "relationship", "specify_relationship")
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control beneficiary-name-input",
                "placeholder": "Beneficiary Name",
                "autocomplete": "off",
            }),
            "relationship": forms.Select(
                choices=Beneficiary.RELATIONSHIP_CHOICES,
                attrs={"class": "form-select beneficiary-relationship-select"},
            ),
            "specify_relationship": forms.TextInput(attrs={
                "class": "form-control beneficiary-specify-input",
                "placeholder": "e.g. Brother, Sister, Son, Friend",
                "maxlength": "200",
                "autocomplete": "off",
            }),
        }
        labels = {
            "specify_relationship": "Specify Relationship",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required                 = False
        self.fields["relationship"].required         = False
        self.fields["specify_relationship"].required = False

    def clean(self):
        cleaned = super().clean()

        name = (cleaned.get("name") or "").strip()
        rel  = (cleaned.get("relationship") or "").strip()
        spec = (cleaned.get("specify_relationship") or "").strip()

        if not name and not rel and not spec:
            return cleaned

        if name:
            cleaned["name"] = clean_name(name, "Beneficiary Name")
        else:
            self.add_error("name", "Beneficiary name is required.")

        if not rel:
            self.add_error("relationship", "Relationship is required.")
        elif rel == "Other":
            if not spec:
                self.add_error("specify_relationship",
                               "Please specify the relationship.")
            elif len(spec) < 2:
                self.add_error("specify_relationship",
                               "Specify relationship is too short.")
            else:
                cleaned["specify_relationship"] = spec.title()
        else:
            cleaned["specify_relationship"] = ""

        return cleaned


BeneficiaryFormSet = inlineformset_factory(
    ClientPersonalInfo, Beneficiary, form=BeneficiaryForm, extra=1, can_delete=True,
)


# ─────────────────────────────────────────────── GovernmentIDForm ─────────────

class GovernmentIDForm(forms.ModelForm):
    class Meta:
        model  = GovernmentID
        fields = ("id_type", "id_type_other", "id_number")
        widgets = {
            "id_type": forms.Select(attrs={
                "class": "form-control id-type-select",
            }),
            "id_type_other": forms.TextInput(attrs={
                "class": "form-control id-type-other",
                "placeholder": "Specify ID type",
                "maxlength": "100",
            }),
            "id_number": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. ABC123456",
                "maxlength": "50",
                "autocomplete": "off",
                "spellcheck": "false",
            }),
        }
        labels = {
            "id_type_other": "Specify ID Type",
            "id_number":     "ID Number",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        id_type_field = self.fields["id_type"]
        id_type_field.required = False
        self.fields["id_type_other"].required = False
        self.fields["id_number"].required = False

    def clean_id_number(self):
        return clean_id_number(self.cleaned_data.get("id_number"))

    def clean(self):
        cleaned = super().clean()

        id_type   = (cleaned.get("id_type") or "").strip()
        id_other  = (cleaned.get("id_type_other") or "").strip()
        id_number = (cleaned.get("id_number") or "").strip()

        if not id_type and not id_number:
            return cleaned

        if not id_type:
            self.add_error("id_type", "ID Type is required.")
        if not id_number:
            self.add_error("id_number", "ID Number is required.")

        if id_type == "Other":
            if not id_other:
                self.add_error("id_type_other", "Please specify the ID type.")
            elif len(id_other) < 2:
                self.add_error("id_type_other", "Specify ID type is too short.")
            else:
                cleaned["id_type_other"] = id_other.title()
        else:
            cleaned["id_type_other"] = ""

        return cleaned


GovernmentIDFormSet = inlineformset_factory(
    ClientPersonalInfo, GovernmentID,
    form=GovernmentIDForm, extra=1, can_delete=True,
)


# ─────────────────────────────────────────────── IntermentRecipientForm ───────

class IntermentRecipientForm(forms.ModelForm):
    class Meta:
        model = IntermentRecipient
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                # Guidance: enter in "Last, First Middle" format so the
                # Interment Masterlist can display it in LOT OWNER style.
                # The view's _format_recipient_name_for_masterlist() uppercases
                # and, if no comma is present, reorders using the last token
                # as the surname.
                "placeholder": "e.g. Dela Cruz, Juan  (Last, First Middle)",
            })
        }
        labels = {
            "name": "Name of Deceased",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].required = False

    def clean_name(self):
        v = (self.cleaned_data.get("name") or "").strip()
        if not v:
            return ""
        return clean_name(v, "Name of Deceased")


class BaseIntermentRecipientFormSet(BaseInlineFormSet):
    def clean(self):
        return super().clean()


IntermentRecipientFormSet = inlineformset_factory(
    ClientStatus, IntermentRecipient,
    form=IntermentRecipientForm, extra=1, can_delete=True,
    formset=BaseIntermentRecipientFormSet,
)


# ─────────────────────────────────────────────── EmployeeCreateForm ───────────

class EmployeeCreateForm(BootstrapForm):
    username  = forms.CharField()
    email     = forms.EmailField()
    password  = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput, label="Confirm Password")
    pin = forms.CharField(
        max_length=4,
        widget=forms.TextInput(attrs={
            "class": "form-control", "placeholder": "4-digit PIN (e.g. 0010)",
            "inputmode": "numeric", "maxlength": "4",
        }),
    )

    class Meta:
        model  = UserLog
        fields = [
            "first_name", "middle_name", "last_name",
            "date_of_birth", "address", "phone_number",
            "emergency_contact_name", "emergency_contact_number",
            "role", "government_id",
        ]
        widgets = {"date_of_birth": forms.DateInput(attrs={"type": "date"})}

    placeholders = {
        "username": "Username", "password": "Password", "password2": "Confirm Password",
        "first_name": "First Name", "middle_name": "Middle name (Optional)",
        "last_name": "Last name", "date_of_birth": "YYYY-MM-DD",
        "address": "Address", "phone_number": "09XXXXXXXXX",
        "email": "Email", "emergency_contact_name": "Contact Name",
        "emergency_contact_number": "09XXXXXXXXX", "government_id": "Government ID number",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        role_choices = [("", "Select Role")] + list(UserLog._meta.get_field("role").choices)
        self.fields["role"] = forms.ChoiceField(
            choices=role_choices,
            widget=forms.Select(attrs={"class": "form-control"}),
            required=True,
        )
        for f in ["phone_number", "emergency_contact_number"]:
            self.fields[f].widget.attrs.update({"maxlength": "11", "inputmode": "numeric"})

    def clean_username(self):
        username = self.cleaned_data.get("username", "").strip()
        if username.lower() == "admin":
            raise forms.ValidationError("The username 'admin' is reserved.")
        return username
    def clean_first_name(self): return clean_name(self.cleaned_data.get("first_name"), "First name")
    def clean_last_name(self): return clean_name(self.cleaned_data.get("last_name"), "Last name")
    def clean_address(self): return clean_address(self.cleaned_data.get("address"), "Home address")
    def clean_phone_number(self): return clean_phone_number(self.cleaned_data.get("phone_number"))
    def clean_emergency_contact_number(self): return clean_phone_number(self.cleaned_data.get("emergency_contact_number"))
    def clean_date_of_birth(self): return clean_date_of_birth(self.cleaned_data.get("date_of_birth"))
    def clean_pin(self): return clean_pin_field(self.cleaned_data.get("pin"))

    def clean(self):
        cleaned_data = super().clean()
        pw  = cleaned_data.get("password", "")
        pw2 = cleaned_data.get("password2", "")
        if pw and pw2 and pw != pw2:
            raise forms.ValidationError("Passwords do not match.")
        if pw and len(pw) < 6:
            raise forms.ValidationError("Password must be at least 6 characters.")
        return cleaned_data


# ─────────────────────────────────────────────── EmployeeUpdateForm ───────────

class EmployeeUpdateForm(forms.Form):
    first_name               = forms.CharField()
    middle_name              = forms.CharField(required=False)
    last_name                = forms.CharField()
    date_of_birth            = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    address                  = forms.CharField()
    email                    = forms.EmailField()
    phone_number             = forms.CharField()
    emergency_contact_name   = forms.CharField()
    emergency_contact_number = forms.CharField()
    role                     = forms.ChoiceField(
        choices=[("", "Select Role")] + list(UserLog._meta.get_field("role").choices)
    )
    government_id    = forms.CharField()
    pin              = forms.CharField(
        max_length=4,
        widget=forms.TextInput(attrs={"inputmode": "numeric", "maxlength": "4"}),
    )
    new_password     = forms.CharField(required=False, widget=forms.PasswordInput,
                                       label="New Password (leave blank to keep current)")
    confirm_password = forms.CharField(required=False, widget=forms.PasswordInput,
                                       label="Confirm New Password")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "first_name": "First Name", "middle_name": "Middle name (Optional)",
            "last_name": "Last name", "address": "Address", "phone_number": "09XXXXXXXXX",
            "email": "Email", "emergency_contact_name": "Contact Name",
            "emergency_contact_number": "09XXXXXXXXX", "government_id": "Government ID number",
            "pin": "4-digit PIN (e.g. 0010)", "new_password": "Leave blank to keep current",
            "confirm_password": "Confirm new password",
        }
        for name, field in self.fields.items():
            field.widget.attrs["class"] = "form-control"
            if name in placeholders and not isinstance(field.widget, forms.Select):
                field.widget.attrs["placeholder"] = placeholders[name]
        for f in ["phone_number", "emergency_contact_number"]:
            self.fields[f].widget.attrs.update({"maxlength": "11", "inputmode": "numeric"})

    def clean_first_name(self): return clean_name(self.cleaned_data.get("first_name"), "First name")
    def clean_last_name(self): return clean_name(self.cleaned_data.get("last_name"), "Last name")
    def clean_address(self): return clean_address(self.cleaned_data.get("address"), "Home address")
    def clean_phone_number(self): return clean_phone_number(self.cleaned_data.get("phone_number"))
    def clean_emergency_contact_number(self): return clean_phone_number(self.cleaned_data.get("emergency_contact_number"))
    def clean_date_of_birth(self): return clean_date_of_birth(self.cleaned_data.get("date_of_birth"))
    def clean_pin(self): return clean_pin_field(self.cleaned_data.get("pin"))

    def clean(self):
        cleaned_data = super().clean()
        new_pw  = cleaned_data.get("new_password", "")
        conf_pw = cleaned_data.get("confirm_password", "")
        if new_pw:
            if len(new_pw) < 6:
                raise forms.ValidationError("New password must be at least 6 characters.")
            if new_pw != conf_pw:
                raise forms.ValidationError("New passwords do not match.")
        return cleaned_data


# ─────────────────────────────────────────────── PlanForm ─────────────────────

# ─────────────────────────────────────────────── PlanForm ─────────────────────

class PlanForm(forms.Form):
    PLAN_CHOICES = [
        ("", "Select Plan"),
        ("Lawn Lot",   "Lawn Lot"),
        ("Garden Lot", "Garden Lot"),
        ("Mausoleum",  "Mausoleum"),
        ("THS",        "THS"),
        ("THTC",       "THTC"),
        ("TCT A/R",    "TCT A/R"),
    ]
    DISCOUNT_CHOICES = [
        (0, "No discount (0%)"), (5, "5%"), (10, "10%"),
        (15, "15%"), (20, "20%"), (25, "25%"), (30, "30%"),
    ]
    MAUSOLEUM_TYPE_CHOICES = [
        ("", "Select Mausoleum Type"),
        ("Junior Court",    "Junior Court"),
        ("Senior Court",    "Senior Court"),
        ("Executive Court", "Executive Court"),
        ("The Estate",      "The Estate"),
    ]
    LAWN_LOT_TYPE_CHOICES = [
        ("", "Select Lawn Lot Type"),
        ("Regular", "Regular"),
        ("Deluxe",  "Deluxe"),
        ("Prime B", "Prime B"),
        ("Prime A", "Prime A"),
    ]
    REGULAR_LOT_PACKAGE_CHOICES = [
        ("", "Select Regular Lot Package"),
        ("3 in 1",                     "3 in 1 — Lot / 3 Days Viewing / Interment Service"),
        ("2 in 1 - Lot/Interment",     "2 in 1 — Lawn Lot Regular / Interment"),
        ("2 in 1 - Viewing/Interment", "2 in 1 — 3-Days Viewing / Interment Service"),
    ]
    GARDEN_TYPE_CHOICES = [
        ("", "Select Garden Type"),
        ("Love",      "Love"),
        ("Happiness", "Happiness"),
        ("Peace",     "Peace"),
    ]
    GARDEN_SECTION_CHOICES = [
        ("", "Select Garden Section"),
        ("Regular", "Regular"),
        ("Deluxe",  "Deluxe"),
        ("Prime",   "Prime"),
    ]
    REMAINS_TYPE_CHOICES = [
        ("",             "Select Type of Remains"),
        ("Fresh Body",   "Fresh Body"),
        ("Bone Transfer", "Bone Transfer"),
        ("Ash",          "Ash"),
        ("Others",       "Others"),
    ]

    # 1st .. 31st — value is the integer, label is the ordinal
    DUE_DAY_CHOICES = [
        (1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (5, "5th"),
        (6, "6th"), (7, "7th"), (8, "8th"), (9, "9th"), (10, "10th"),
        (11, "11th"), (12, "12th"), (13, "13th"), (14, "14th"), (15, "15th"),
        (16, "16th"), (17, "17th"), (18, "18th"), (19, "19th"), (20, "20th"),
        (21, "21st"), (22, "22nd"), (23, "23rd"), (24, "24th"), (25, "25th"),
        (26, "26th"), (27, "27th"), (28, "28th"), (29, "29th"), (30, "30th"),
        (31, "31st"),
    ]

    total_price = forms.DecimalField(
        max_digits=20, decimal_places=2,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "placeholder": "e.g. 145600.00",
            "min": "0", "step": "0.01", "id": "id_total_price",
        }),
        label="Total Price",
    )

    plan = forms.ChoiceField(
        choices=PLAN_CHOICES,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_plan"}),
    )

    monthly_payment = forms.DecimalField(
        max_digits=20, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "id": "id_monthly_payment", "step": "0.01",
        }),
    )

    down_payment = forms.DecimalField(
        max_digits=20, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "placeholder": "e.g. 29120.00",
            "min": "0", "step": "0.01", "id": "id_down_payment",
        }),
    )
    discount_percent = forms.ChoiceField(
        choices=DISCOUNT_CHOICES, required=False, initial=0,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_discount_percent"}),
        label="Discount %",
    )
    pcare_percent = forms.DecimalField(
        max_digits=5, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "placeholder": "e.g. 20.00",
            "min": "0", "max": "100", "step": "0.01", "id": "id_pcare_percent",
        }),
        label="P-Care %",
    )

    duration = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=600,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "placeholder": "e.g. 18",
            "id": "id_duration",
            "min": "1",
            "max": "600",
            "step": "1",
            "inputmode": "numeric",
        }),
        label="Duration (Months)",
    )

    # ── NEW: day-of-month the client pays ────────────────────────────────
    due_day = forms.TypedChoiceField(
        choices=DUE_DAY_CHOICES,
        coerce=int,
        empty_value=None,
        required=False,          # required-ness is enforced in clean() for non-TCT
        initial=2,
        widget=forms.Select(attrs={
            "class": "form-control",
            "id": "id_due_day",
        }),
        label="Due Day of the Month",
    )

    lawn_lot_type = forms.ChoiceField(
        choices=LAWN_LOT_TYPE_CHOICES, required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_lawn_lot_type"}),
        label="Lawn Lot Type",
    )
    regular_lot_package = forms.ChoiceField(
        choices=REGULAR_LOT_PACKAGE_CHOICES, required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_regular_lot_package"}),
        label="Regular Lot Package",
    )
    garden_type = forms.ChoiceField(
        choices=GARDEN_TYPE_CHOICES, required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_garden_type"}),
        label="Garden Type",
    )
    garden_section = forms.ChoiceField(
        choices=GARDEN_SECTION_CHOICES, required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_garden_section"}),
        label="Garden Section",
    )
    mausoleum_type = forms.ChoiceField(
        choices=MAUSOLEUM_TYPE_CHOICES, required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_mausoleum_type"}),
        label="Mausoleum Type",
    )
    sqm = forms.DecimalField(
        max_digits=10, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "placeholder": "e.g. 12.50",
            "min": "0", "step": "0.01", "id": "id_sqm",
        }),
        label="SQM",
    )

    phase = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 1", "data-uppercase": "true"}))
    block = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 2", "data-uppercase": "true"}))
    section = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. A", "data-uppercase": "true"}))
    lot_number = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 12", "data-uppercase": "true"}))
    pa_number = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 00123", "data-uppercase": "true"}),
        label="P.A. Number")
    la_number = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 00123", "data-uppercase": "true"}),
        label="L.A. Number")
    column_level = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. A", "data-uppercase": "true"}),
        label="Level")
    ths_type = forms.ChoiceField(
        choices=[("", "Select…")] + ClientStatus.THS_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="THS Type",
    )
    ths_section = forms.ChoiceField(
        choices=[("", "Select…")] + ClientStatus.THS_SECTION_CHOICES,
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="Section",
    )
    ths_column = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. B-1", "data-uppercase": "true"}),
        label="Column")
    columbarium_type = forms.ChoiceField(
        choices=[("", "Select Type"),
                 ("TCT A/R Niche 1", "TCT A/R Niche 1"),
                 ("TCT A/R Niche 2", "TCT A/R Niche 2")],
        required=False,
        widget=forms.Select(attrs={"class": "form-control"}),
        label="TCT A/R Type",
    )
    tomb_number = forms.CharField(max_length=200, required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Tomb Number", "data-uppercase": "true"}),
        label="Tomb Number")
    interment_date = forms.DateField(required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))
    pa_date = forms.DateField(required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}))

    date_of_death = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
        label="Date of Death",
    )
    death_certificate_number = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control", "placeholder": "e.g. 2024-00123",
            "data-uppercase": "true",
        }),
        label="Death Certificate No.",
    )

    remains_type = forms.ChoiceField(
        choices=REMAINS_TYPE_CHOICES, required=False,
        widget=forms.Select(attrs={"class": "form-control", "id": "id_remains_type"}),
        label="Type of Remains",
    )
    remains_type_other = forms.CharField(
        max_length=200, required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control", "placeholder": "Specify type of remains",
            "id": "id_remains_type_other", "data-uppercase": "true",
        }),
        label="Specify Type of Remains",
    )

    documentation_fee = forms.DecimalField(
        max_digits=20, decimal_places=2, required=False,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "placeholder": "e.g. 500.00",
            "min": "0", "step": "0.01", "id": "id_documentation_fee",
        }),
        label="Documentation Fee",
    )

    # NOTE: `sales_agent` was removed — it is auto-assigned server-side.

    # ── Field-level validators ─────────────────────────────────────────────

    def clean_plan(self):
        v = self.cleaned_data.get("plan")
        if not v:
            raise forms.ValidationError("Please select a plan.")
        return v

    def clean_total_price(self):
        v = self.cleaned_data.get("total_price")
        if v is None or v <= 0:
            raise forms.ValidationError("Total price must be greater than zero.")
        return v

    def clean_down_payment(self):
        v = self.cleaned_data.get("down_payment")
        if v is not None and v < 0:
            raise forms.ValidationError("Down payment cannot be negative.")
        return v

    def clean_discount_percent(self):
        v = self.cleaned_data.get("discount_percent")
        try:
            v = int(v or 0)
        except (ValueError, TypeError):
            v = 0
        if not (0 <= v <= 100):
            raise forms.ValidationError("Discount must be between 0 and 100.")
        return v

    def clean_pcare_percent(self):
        v = self.cleaned_data.get("pcare_percent")
        if v is None:
            return Decimal("0.00")
        if v < 0 or v > 100:
            raise forms.ValidationError("P-Care percent must be between 0 and 100.")
        return v.quantize(Decimal("0.01"))

    def clean_documentation_fee(self):
        v = self.cleaned_data.get("documentation_fee")
        if v is None:
            return Decimal("0.00")
        if v < 0:
            raise forms.ValidationError("Documentation fee cannot be negative.")
        return v.quantize(Decimal("0.01"))

    def clean_sqm(self):
        v = self.cleaned_data.get("sqm")
        if v is None:
            return None
        if v <= 0:
            raise forms.ValidationError("SQM must be greater than zero.")
        return v.quantize(Decimal("0.01"))

    def clean_remains_type_other(self):
        remains = (self.cleaned_data.get("remains_type") or "").strip()
        other   = (self.cleaned_data.get("remains_type_other") or "").strip()
        if remains == "Others" and not other:
            raise forms.ValidationError(
                "Please specify the type of remains when 'Others' is selected."
            )
        if remains != "Others":
            return ""
        return other

    def clean_due_day(self):
        v = self.cleaned_data.get("due_day")
        plan = self.cleaned_data.get("plan")
        # TCT A/R has no monthly schedule → ignore
        if plan == "TCT A/R":
            return v or 2
        if v is None:
            raise forms.ValidationError("Please choose the day of the month when payment is due.")
        if not (1 <= int(v) <= 31):
            raise forms.ValidationError("Due day must be between 1 and 31.")
        return int(v)

    def clean_duration(self):
        plan   = self.cleaned_data.get("plan")
        v      = self.cleaned_data.get("duration")

        if plan == "TCT A/R":
            return 0

        if v is None:
            raise forms.ValidationError("Please enter a duration in months.")

        try:
            v = int(v)
        except (TypeError, ValueError):
            raise forms.ValidationError("Duration must be a whole number of months.")

        if v < 1:
            raise forms.ValidationError("Duration must be at least 1 month.")

        if v > 600:
            raise forms.ValidationError("Duration cannot exceed 600 months (50 years).")

        return v

    _UPPERCASE_FIELDS = [
        "phase", "block", "section", "lot_number", "pa_number", "la_number",
        "column_level", "tomb_number", "ths_column", "death_certificate_number",
        "remains_type_other",
        # NOTE: "sales_agent" removed — it is now auto-assigned.
    ]

    def clean(self):
        cleaned_data = super().clean()

        for field in self._UPPERCASE_FIELDS:
            val = cleaned_data.get(field)
            if val and isinstance(val, str):
                cleaned_data[field] = val.strip().upper()

        total = cleaned_data.get("total_price")
        dp    = cleaned_data.get("down_payment")
        if total and dp and dp > total:
            self.add_error("down_payment", "Down payment cannot exceed the Total Price.")

        plan = cleaned_data.get("plan")

        if plan == "Mausoleum":
            if not cleaned_data.get("mausoleum_type"):
                self.add_error("mausoleum_type", "Mausoleum Type is required when Mausoleum is selected.")
            if not cleaned_data.get("sqm"):
                self.add_error("sqm", "SQM is required when Mausoleum is selected.")
            cleaned_data["lawn_lot_type"] = ""
            cleaned_data["regular_lot_package"] = ""
            cleaned_data["garden_type"] = ""
            cleaned_data["garden_section"] = ""
        elif plan == "Lawn Lot":
            lawn_type = cleaned_data.get("lawn_lot_type")
            if not lawn_type:
                self.add_error("lawn_lot_type", "Lawn Lot Type is required when Lawn Lot is selected.")
            elif lawn_type == "Regular" and not cleaned_data.get("regular_lot_package"):
                self.add_error("regular_lot_package", "Regular Lot Package is required when Lawn Lot Type is Regular.")
            if lawn_type and lawn_type != "Regular":
                cleaned_data["regular_lot_package"] = ""
            cleaned_data["mausoleum_type"] = ""
            cleaned_data["sqm"] = None
            cleaned_data["garden_type"] = ""
            cleaned_data["garden_section"] = ""
        elif plan == "Garden Lot":
            garden_type = cleaned_data.get("garden_type")
            if not garden_type:
                self.add_error("garden_type", "Garden Type is required when Garden Lot is selected.")
            if not cleaned_data.get("garden_section"):
                self.add_error("garden_section", "Garden Section is required when Garden Lot is selected.")
            cleaned_data["lawn_lot_type"] = ""
            cleaned_data["regular_lot_package"] = ""
            cleaned_data["mausoleum_type"] = ""
            cleaned_data["sqm"] = None
        else:
            cleaned_data["lawn_lot_type"] = ""
            cleaned_data["regular_lot_package"] = ""
            cleaned_data["garden_type"] = ""
            cleaned_data["garden_section"] = ""
            cleaned_data["mausoleum_type"] = ""
            cleaned_data["sqm"] = None

        return cleaned_data


# ─────────────────────────────────────────────── BookingForm ──────────────────

class BookingForm(forms.ModelForm):
    client = forms.ModelChoiceField(
        queryset=ClientPersonalInfo.objects.all().order_by("client_last_name", "client_first_name"),
        required=False,
        empty_label="— Walk-in / Not a registered client —",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_client"}),
        label="Select Client",
    )

    class Meta:
        model  = Booking
        fields = ["client", "client_name", "contact_number", "event_type",
                  "booking_date", "booking_time", "notes"]
        widgets = {
            "booking_date": forms.DateInput(attrs={"type": "date", "class": "form-control", "id": "id_booking_date"}),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {"client_name": "Full name", "contact_number": "09XXXXXXXXX"}
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs["class"] = "form-select"
            elif name not in ("booking_date", "notes"):
                field.widget.attrs["class"] = "form-control"
            if name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[name]
        self.fields["booking_time"].widget.attrs.update({"class": "form-select d-none", "id": "id_booking_time"})
        self.fields["contact_number"].widget.attrs.update({"maxlength": "11", "inputmode": "numeric"})
        self.fields["client_name"].required = False
        self.fields["contact_number"].required = False
        self.fields["event_type"].widget.attrs.update({"id": "id_event_type"})

    def clean_client_name(self):
        v = self.cleaned_data.get("client_name", "").strip()
        if not v: return ""
        if not re.match(r"^[A-Za-z\s\.\-]+$", v):
            raise forms.ValidationError("Name can only contain letters, spaces, hyphens, or periods.")
        return v.title()
    def clean_contact_number(self):
        v = (self.cleaned_data.get("contact_number") or "").strip()
        if not v: return ""
        return clean_phone_number(v)
    def clean_booking_date(self):
        d = self.cleaned_data.get("booking_date")
        if d and d < date.today():
            raise forms.ValidationError("Booking date cannot be in the past.")
        return d

    def clean(self):
        cleaned = super().clean()
        client     = cleaned.get("client")
        name       = (cleaned.get("client_name") or "").strip()
        contact    = (cleaned.get("contact_number") or "").strip()
        event_type = cleaned.get("event_type")

        if client:
            if not name: cleaned["client_name"] = client.full_name
            if not contact: cleaned["contact_number"] = client.client_contact_number
        else:
            if not name: self.add_error("client_name", "Client name is required.")
            if not contact: self.add_error("contact_number", "Contact number is required.")

        if event_type == "Interment":
            if not client:
                self.add_error("event_type",
                    "Interment bookings require a registered client with an active plan. "
                    "Walk-in clients can only book Viewing.")
            else:
                has_active_plan = (
                    ClientStatus.objects
                    .filter(client=client, status=True, is_cancelled=False)
                    .exclude(plan="No Plan").exists()
                )
                if not has_active_plan:
                    self.add_error("event_type",
                        "Interment bookings require the client to have an active plan. "
                        "Assign a plan before scheduling an interment.")

        booking_date = cleaned.get("booking_date")
        booking_time = cleaned.get("booking_time")
        if booking_date and booking_time:
            qs = Booking.objects.filter(
                booking_date=booking_date, booking_time=booking_time, status="Active",
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"That time slot is already booked on {booking_date}. "
                    "Please choose a different time.")
        return cleaned