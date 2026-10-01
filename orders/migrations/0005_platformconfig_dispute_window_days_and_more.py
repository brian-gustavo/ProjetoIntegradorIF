import django.core.validators
from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0004_alter_order_status_dispute_disputemessage'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformconfig',
            name='dispute_window_days',
            field=models.PositiveIntegerField(default=7, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Prazo para contestar cancelamento sem devolução (dias)'),
        ),
        migrations.AlterField(
            model_name='platformconfig',
            name='commission_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('10.00'), max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Taxa de comissão (%)'),
        ),
    ]