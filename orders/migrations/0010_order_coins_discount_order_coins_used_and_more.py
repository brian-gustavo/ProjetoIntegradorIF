import django.core.validators
from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0009_platformconfig_escalation_window_days_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='coins_discount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Desconto em MegaCoins'),
        ),
        migrations.AddField(
            model_name='order',
            name='coins_used',
            field=models.PositiveIntegerField(default=0, verbose_name='MegaCoins utilizadas'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='coins_cashback_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('1.00'), help_text='Percentual do valor pago devolvido em MegaCoins (100 moedas = R$ 1,00), antes do multiplicador de nível do comprador', max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(20)], verbose_name='Cashback em MegaCoins (%)'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='coins_max_redeem_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('10.00'), help_text='Desconto máximo por pedido. Nunca ultrapassa a taxa de comissão, já que o desconto é custeado pela plataforma e o vendedor recebe o valor integral', max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Limite de uso de MegaCoins por pedido (%)'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='coins_review_reward',
            field=models.PositiveIntegerField(default=20, help_text='Concedidas uma única vez por produto ou vendedor avaliado', validators=[django.core.validators.MaxValueValidator(1000)], verbose_name='MegaCoins por avaliação'),
        ),
    ]