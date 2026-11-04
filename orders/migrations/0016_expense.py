import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0015_order_trade_fee_order_trade_paid_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Expense',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('description', models.CharField(max_length=120, verbose_name='Descrição')),
                ('category', models.CharField(choices=[('INFRA', 'Infraestrutura e servidores'), ('SUBSCRIPTIONS', 'Assinaturas e serviços'), ('MARKETING', 'Marketing'), ('FEES', 'Pagamentos e taxas'), ('STAFF', 'Pessoal'), ('TAXES', 'Impostos'), ('OTHER', 'Outros')], default='OTHER', max_length=20, verbose_name='Categoria')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('0.01'))], verbose_name='Valor (R$)')),
                ('date', models.DateField(help_text='Nos gastos mensais, a data da primeira cobrança', verbose_name='Data')),
                ('recurring', models.BooleanField(default=False, verbose_name='Repetir todo mês')),
                ('end_date', models.DateField(blank=True, help_text='Deixe em branco enquanto o gasto continuar', null=True, verbose_name='Última cobrança')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Lançado por')),
            ],
            options={
                'verbose_name': 'Gasto',
                'verbose_name_plural': 'Gastos',
                'ordering': ['-date', '-pk'],
            },
        ),
    ]