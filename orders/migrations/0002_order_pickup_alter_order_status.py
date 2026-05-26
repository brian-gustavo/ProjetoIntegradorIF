from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='pickup',
            field=models.BooleanField(default=False, verbose_name='Retirada em mãos'),
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Aguardando pagamento'), ('PAID', 'Pago'), ('CONFIRMED', 'Confirmado pelo vendedor'), ('PREPARING', 'Em preparação'), ('SHIPPED', 'Enviado'), ('READY_PICKUP', 'Pronto para retirada'), ('DELIVERED', 'Entregue'), ('RETURN_WINDOW', 'Período de devolução'), ('RETURN_REQUESTED', 'Devolução solicitada'), ('RETURNED', 'Devolvido'), ('COMPLETED', 'Concluído'), ('CANCELLED', 'Cancelado')], default='PENDING', max_length=20, verbose_name='Status'),
        ),
    ]