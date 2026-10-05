import django.core.validators
from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0014_order_trade_platformconfig_trade_response_days'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='trade_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Taxa da troca'),
        ),
        migrations.AddField(
            model_name='order',
            name='trade_paid',
            field=models.BooleanField(default=False, verbose_name='Parte da troca paga'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='trade_fee',
            field=models.DecimalField(decimal_places=2, default=Decimal('5.00'), help_text='Cobrada quando a troca é aceita e dividida igualmente entre os dois lados, junto com a volta, se houver. A comissão continua incidindo sobre a volta', max_digits=10, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Taxa fixa por troca (R$)'),
        ),
    ]