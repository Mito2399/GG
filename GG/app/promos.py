# app/promos.py
#
# Memorial Plan Promo scheme definitions.
# Single source of truth for promo rules, discount rates, and display copy.
#
# SCHEME 3 MATH NOTE:
#   "20% less on spot cash payment" + "Additional 10% discount"
#   Interpretation: STACKED (not additive).
#   List price 100 → cash price 80 → additional 10% off 80 → final 72
#   Effective discount = 28%
#   If your business rule is ADDITIVE (30%), change
#   SCHEME_3_EFFECTIVE_DISCOUNT to Decimal("30.00") below.
#
from decimal import Decimal


SCHEME_3_EFFECTIVE_DISCOUNT = Decimal("28.00")   # stacked: 1 − (0.80 × 0.90)


PROMO_SCHEMES = {
    "No Promo": {
        "label":                "No Promo",
        "discount_percent":     Decimal("0.00"),
        "down_payment_percent": None,      # manual entry
        "down_payment_months":  None,
        "balance_months":       None,
        "interest_rate":        Decimal("0.00"),
        "is_spot_cash":         False,
        "promo_min_monthly":    None,
        "details":              [],
    },

    "Scheme 1": {
        "label":                "Scheme 1",
        "discount_percent":     Decimal("20.00"),
        "down_payment_percent": Decimal("20.00"),
        "down_payment_months":  3,
        "balance_months":       48,
        "interest_rate":        Decimal("0.00"),
        "is_spot_cash":         False,
        "promo_min_monthly":    Decimal("2000.00"),
        "details": [
            "20% Discount",
            "20% Down Payment",
            "Down payment payable in 3 months",
            "Remaining balance payable in 4 years / 48 months",
            "0% Interest",
            "Promotional monthly payment: as low as ₱2,000/month",
        ],
    },

    "Scheme 2": {
        "label":                "Scheme 2",
        "discount_percent":     Decimal("0.00"),
        "down_payment_percent": Decimal("0.00"),
        "down_payment_months":  0,
        "balance_months":       60,
        "interest_rate":        Decimal("0.00"),
        "is_spot_cash":         False,
        "promo_min_monthly":    Decimal("2500.00"),
        "details": [
            "Straight Monthly Payment",
            "No Down Payment",
            "Payable in 5 years / 60 months",
            "Promotional monthly payment: as low as ₱2,500/month",
        ],
    },

    "Scheme 3": {
        "label":                "Scheme 3",
        "discount_percent":     SCHEME_3_EFFECTIVE_DISCOUNT,
        "down_payment_percent": Decimal("100.00"),
        "down_payment_months":  0,
        "balance_months":       0,
        "interest_rate":        Decimal("0.00"),
        "is_spot_cash":         True,
        "promo_min_monthly":    None,
        "details": [
            "20% less on spot cash payment",
            "Additional 10% discount",
            "Free bone transfer from another cemetery",
            "Promo valid until further notice",
        ],
    },
}


PROMO_SCHEME_CHOICES = [
    ("No Promo", "No Promo"),
    ("Scheme 1", "Scheme 1"),
    ("Scheme 2", "Scheme 2"),
    ("Scheme 3", "Scheme 3"),
]


def get_promo_config(scheme_name: str) -> dict:
    """Return the config dict for a scheme, defaulting to No Promo."""
    return PROMO_SCHEMES.get(scheme_name, PROMO_SCHEMES["No Promo"])