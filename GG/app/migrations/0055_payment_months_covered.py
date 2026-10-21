# Generated for Green Garden — cover-multiple-months fix

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0054_remove_clientstatus_promo_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='months_covered',
            field=models.PositiveIntegerField(
                default=1,
                help_text=(
                    "Number of monthly installments this single payment covers. "
                    "1 = pays only the current installment. "
                    "N>1 = pays the current installment and the next (N-1) installments."
                ),
            ),
        ),
    ]