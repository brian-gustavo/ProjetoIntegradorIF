from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='accepts_pickup',
            field=models.BooleanField(default=False, verbose_name='Aceita retirada em mãos'),
        ),
    ]