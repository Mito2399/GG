from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('app', '0027_ths_thtc_section_updates'),
    ]

    operations = [
        migrations.AddField(
            model_name='clientstatus',
            name='la_number',
            field=models.CharField(
                blank=True,
                help_text='Used instead of P.A. Number for TCT A/R lots.',
                max_length=200,
                null=True,
            ),
        ),
    ]
