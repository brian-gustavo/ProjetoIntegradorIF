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
        ('orders', '0011_order_platform_coupon_order_platform_coupon_discount_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Auction',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_price', models.DecimalField(decimal_places=2, max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal('1.00'))], verbose_name='Lance inicial')),
                ('reserve_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preço de reserva')),
                ('buy_now_price', models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True, verbose_name='Preço do Comprar agora')),
                ('duration_days', models.PositiveSmallIntegerField(choices=[(1, '1 dia'), (3, '3 dias'), (5, '5 dias'), (7, '7 dias'), (10, '10 dias')], default=7, verbose_name='Duração')),
                ('starts_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Início')),
                ('ends_at', models.DateTimeField(verbose_name='Término')),
                ('status', models.CharField(choices=[('ACTIVE', 'Em andamento'), ('SOLD', 'Vendido'), ('UNSOLD', 'Encerrado sem venda')], default='ACTIVE', max_length=6, verbose_name='Status')),
                ('current_price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Lance atual')),
                ('bid_count', models.PositiveIntegerField(default=0, verbose_name='Lances')),
                ('bought_now', models.BooleanField(default=False, verbose_name='Vendido pelo Comprar agora')),
                ('ended_early', models.BooleanField(default=False, verbose_name='Encerrado antes do prazo')),
                ('closed_at', models.DateTimeField(blank=True, null=True, verbose_name='Encerrado em')),
                ('payment_due_at', models.DateTimeField(blank=True, null=True, verbose_name='Prazo de pagamento')),
                ('leader', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auctions_leading', to=settings.AUTH_USER_MODEL, verbose_name='Maior lance')),
                ('order', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auction', to='orders.order', verbose_name='Pedido')),
                ('product', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='auction', to='catalog.product', verbose_name='Produto')),
                ('relisted_as', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='relisted_from', to='auctions.auction', verbose_name='Relistado como')),
                ('winner', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='auctions_won', to=settings.AUTH_USER_MODEL, verbose_name='Vencedor')),
            ],
            options={
                'verbose_name': 'Leilão',
                'verbose_name_plural': 'Leilões',
            },
        ),
        migrations.CreateModel(
            name='Bid',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Valor')),
                ('is_auto', models.BooleanField(default=False, verbose_name='Lance automático')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Feito em')),
                ('auction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bids', to='auctions.auction', verbose_name='Leilão')),
                ('bidder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='bids', to=settings.AUTH_USER_MODEL, verbose_name='Participante')),
            ],
            options={
                'verbose_name': 'Lance',
                'verbose_name_plural': 'Lances',
                'ordering': ('-created_at', '-pk'),
            },
        ),
        migrations.CreateModel(
            name='AuctionWatch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Acompanhando desde')),
                ('auction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='watches', to='auctions.auction', verbose_name='Leilão')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='auction_watches', to=settings.AUTH_USER_MODEL, verbose_name='Usuário')),
            ],
            options={
                'verbose_name': 'Leilão acompanhado',
                'verbose_name_plural': 'Leilões acompanhados',
                'unique_together': {('user', 'auction')},
            },
        ),
    ]