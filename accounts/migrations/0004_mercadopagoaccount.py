import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0003_sellerreview_edited_alter_sellerreview_created_at'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='MercadoPagoAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mp_user_id', models.CharField(max_length=50, verbose_name='ID do usuário no Mercado Pago')),
                ('access_token', models.CharField(max_length=255)),
                ('refresh_token', models.CharField(max_length=255)),
                ('public_key', models.CharField(blank=True, max_length=255)),
                ('connected_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='mp_account', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Conta Mercado Pago',
                'verbose_name_plural': 'Contas Mercado Pago',
            },
        ),
    ]