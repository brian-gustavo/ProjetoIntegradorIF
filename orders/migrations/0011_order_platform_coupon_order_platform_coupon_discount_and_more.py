import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('coupons', '0001_initial'),
        ('orders', '0010_order_coins_discount_order_coins_used_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='platform_coupon',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='platform_orders', to='coupons.couponredemption', verbose_name='Cupom MegaGame'),
        ),
        migrations.AddField(
            model_name='order',
            name='platform_coupon_discount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Desconto do cupom MegaGame'),
        ),
        migrations.AddField(
            model_name='order',
            name='seller_coupon',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='seller_orders', to='coupons.couponredemption', verbose_name='Cupom da loja'),
        ),
        migrations.AddField(
            model_name='order',
            name='seller_coupon_discount',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Desconto do cupom da loja'),
        ),
    ]