import django.core.validators
import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('catalog', '0005_productreview_edited_alter_productvariant_quantity'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Coupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=20, unique=True, verbose_name='Código')),
                ('kind', models.CharField(choices=[('PERCENT', 'Percentual'), ('FIXED', 'Valor fixo')], default='PERCENT', max_length=7, verbose_name='Tipo de desconto')),
                ('value', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Valor do desconto')),
                ('max_discount', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Desconto máximo (R$)')),
                ('min_order_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Valor mínimo da compra (R$)')),
                ('first_purchase_only', models.BooleanField(default=False, verbose_name='Apenas primeira compra')),
                ('is_public', models.BooleanField(default=True, verbose_name='Público')),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Início da validade')),
                ('ends_at', models.DateTimeField(blank=True, null=True, verbose_name='Fim da validade')),
                ('usage_limit', models.PositiveIntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Limite total de usos')),
                ('per_user_limit', models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Usos por cliente')),
                ('active', models.BooleanField(default=True, verbose_name='Ativo')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='coupons', to='catalog.category', verbose_name='Categoria')),
                ('seller', models.ForeignKey(blank=True, help_text='Vazio para cupons da MegaGame', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='coupons', to=settings.AUTH_USER_MODEL, verbose_name='Loja')),
            ],
            options={
                'verbose_name': 'Cupom',
                'verbose_name_plural': 'Cupons',
                'ordering': ('-created_at',),
            },
        ),
        migrations.CreateModel(
            name='CouponRedemption',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('discount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Desconto concedido')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Usado em')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='redemptions', to='coupons.coupon', verbose_name='Cupom')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coupon_redemptions', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Uso de cupom',
                'verbose_name_plural': 'Usos de cupons',
                'ordering': ('-created_at', '-pk'),
            },
        ),
        migrations.CreateModel(
            name='SavedCoupon',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Salvo em')),
                ('coupon', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saves', to='coupons.coupon', verbose_name='Cupom')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='saved_coupons', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Cupom salvo',
                'verbose_name_plural': 'Cupons salvos',
                'unique_together': {('user', 'coupon')},
            },
        ),
    ]