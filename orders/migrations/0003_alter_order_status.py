from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0002_order_pickup_alter_order_status'),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Aguardando pagamento'), ('PAID', 'Pago'), ('CONFIRMED', 'Confirmado pelo vendedor'), ('PREPARING', 'Em preparação'), ('SHIPPED', 'Enviado'), ('READY_PICKUP', 'Pronto para retirada'), ('DELIVERED', 'Entregue'), ('RETURN_WINDOW', 'Período de devolução'), ('RETURN_REQUESTED', 'Devolução solicitada'), ('RETURN_ACCEPTED', 'Devolução aceita'), ('RETURNED', 'Devolvido'), ('CANCELLED_NO_RETURN', 'Cancelado sem devolução'), ('COMPLETED', 'Concluído'), ('CANCELLED', 'Cancelado')], default='PENDING', max_length=20, verbose_name='Status'),
        ),
    ]