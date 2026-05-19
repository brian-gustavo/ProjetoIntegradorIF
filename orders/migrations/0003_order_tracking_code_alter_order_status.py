from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0002_cart_cartitem'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='tracking_code',
            field=models.CharField(blank=True, max_length=13, verbose_name='Código de rastreio'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Aguardando pagamento'), ('PAID', 'Pago'), ('CONFIRMED', 'Confirmado pelo vendedor'), ('PREPARING', 'Em preparação'), ('SHIPPED', 'Enviado'), ('DELIVERED', 'Entregue'), ('CANCELLED', 'Cancelado')], default='PENDING', max_length=10, verbose_name='Status'),
        ),
    ]