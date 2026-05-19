import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0003_order_tracking_code_alter_order_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='PlatformConfig',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('commission_rate', models.DecimalField(decimal_places=2, default=Decimal('10.00'), max_digits=5, verbose_name='Taxa de comissão (%)')),
            ],
            options={
                'verbose_name': 'Configuração da plataforma',
                'verbose_name_plural': 'Configurações da plataforma',
            },
        ),
        migrations.CreateModel(
            name='Commission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rate', models.DecimalField(decimal_places=2, max_digits=5, verbose_name='Taxa aplicada (%)')),
                ('gross_amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor bruto')),
                ('commission_amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Comissão')),
                ('net_amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor líquido')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='commission', to='orders.order', verbose_name='Pedido')),
            ],
            options={
                'verbose_name': 'Comissão',
                'verbose_name_plural': 'Comissões',
            },
        ),
    ]