import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ('orders', '0010_order_coins_discount_order_coins_used_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='CoinTransaction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('kind', models.CharField(choices=[('PURCHASE', 'Cashback de compra'), ('REVIEW', 'Bônus de avaliação'), ('CHECKIN', 'Check-in diário'), ('REDEEM', 'Desconto em compra'), ('REFUND', 'Devolução de moedas'), ('ADJUST', 'Ajuste manual')], max_length=10, verbose_name='Tipo')),
                ('amount', models.IntegerField(verbose_name='Moedas')),
                ('reference', models.CharField(blank=True, max_length=50, verbose_name='Referência')),
                ('description', models.CharField(max_length=200, verbose_name='Descrição')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criada em')),
                ('order', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='coin_transactions', to='orders.order', verbose_name='Pedido')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='coin_transactions', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Movimentação de MegaCoins',
                'verbose_name_plural': 'Movimentações de MegaCoins',
                'ordering': ('-created_at', '-pk'),
                'constraints': [models.UniqueConstraint(condition=models.Q(('order__isnull', False)), fields=('order', 'kind'), name='unique_coin_kind_per_order'), models.UniqueConstraint(condition=models.Q(('reference', ''), _negated=True), fields=('user', 'kind', 'reference'), name='unique_coin_reference_per_user')],
            },
        ),
    ]