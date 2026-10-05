import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('auctions', '0001_initial'),
        ('orders', '0012_platformconfig_auction_payment_days_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='bid',
            name='retracted_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Retirado em'),
        ),
        migrations.AddField(
            model_name='bid',
            name='retraction_reason',
            field=models.CharField(blank=True, choices=[('TYPO', 'Digitei o valor errado'), ('DESCRIPTION', 'A descrição do item mudou significativamente'), ('SELLER', 'Não consigo entrar em contato com o vendedor')], max_length=11, verbose_name='Motivo da retirada'),
        ),
        migrations.CreateModel(
            name='SecondChanceOffer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preço')),
                ('duration_days', models.PositiveSmallIntegerField(choices=[(1, '1 dia'), (3, '3 dias'), (5, '5 dias'), (7, '7 dias')], default=3, verbose_name='Validade')),
                ('status', models.CharField(choices=[('PENDING', 'Aguardando resposta'), ('ACCEPTED', 'Aceita'), ('DECLINED', 'Recusada'), ('EXPIRED', 'Expirada')], default='PENDING', max_length=8, verbose_name='Status')),
                ('created_at', models.DateTimeField(default=django.utils.timezone.now, verbose_name='Enviada em')),
                ('expires_at', models.DateTimeField(verbose_name='Expira em')),
                ('responded_at', models.DateTimeField(blank=True, null=True, verbose_name='Respondida em')),
                ('auction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='second_chance_offers', to='auctions.auction', verbose_name='Leilão')),
                ('bidder', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='second_chance_offers', to=settings.AUTH_USER_MODEL, verbose_name='Participante')),
                ('order', models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='second_chance_offer', to='orders.order', verbose_name='Pedido')),
            ],
            options={
                'verbose_name': 'Oferta de segunda chance',
                'verbose_name_plural': 'Ofertas de segunda chance',
                'ordering': ('-created_at',),
                'unique_together': {('auction', 'bidder')},
            },
        ),
    ]