import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0003_alter_order_status'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='order',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Aguardando pagamento'), ('PAID', 'Pago'), ('CONFIRMED', 'Confirmado pelo vendedor'), ('PREPARING', 'Em preparação'), ('SHIPPED', 'Enviado'), ('READY_PICKUP', 'Pronto para retirada'), ('DELIVERED', 'Entregue'), ('RETURN_WINDOW', 'Período de devolução'), ('RETURN_REQUESTED', 'Devolução solicitada'), ('DISPUTE_OPEN', 'Em disputa'), ('RETURN_ACCEPTED', 'Devolução aceita'), ('RETURNED', 'Devolvido'), ('CANCELLED_NO_RETURN', 'Cancelado sem devolução'), ('COMPLETED', 'Concluído'), ('CANCELLED', 'Cancelado')], default='PENDING', max_length=20, verbose_name='Status'),
        ),
        migrations.CreateModel(
            name='Dispute',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('reason', models.TextField(verbose_name='Motivo')),
                ('status', models.CharField(choices=[('OPEN', 'Aberta'), ('RESOLVED_BUYER_RETURN', 'A favor do comprador (com devolução)'), ('RESOLVED_BUYER_REFUND', 'A favor do comprador (sem devolução)'), ('RESOLVED_SELLER', 'A favor do vendedor')], default='OPEN', max_length=25, verbose_name='Status')),
                ('resolution_notes', models.TextField(blank=True, verbose_name='Notas da resolução')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criada em')),
                ('resolved_at', models.DateTimeField(blank=True, null=True, verbose_name='Resolvida em')),
                ('opened_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='disputes_opened', to=settings.AUTH_USER_MODEL, verbose_name='Aberta por')),
                ('order', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='dispute', to='orders.order', verbose_name='Pedido')),
                ('resolved_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='disputes_resolved', to=settings.AUTH_USER_MODEL, verbose_name='Resolvida por')),
            ],
            options={
                'verbose_name': 'Disputa',
                'verbose_name_plural': 'Disputas',
            },
        ),
        migrations.CreateModel(
            name='DisputeMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('message', models.TextField(verbose_name='Mensagem')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Enviada em')),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Autor')),
                ('dispute', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='messages', to='orders.dispute', verbose_name='Disputa')),
            ],
            options={
                'verbose_name': 'Mensagem de disputa',
                'verbose_name_plural': 'Mensagens de disputa',
            },
        ),
    ]