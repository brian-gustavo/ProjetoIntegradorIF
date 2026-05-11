from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0003_alter_product_condition_stock'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preço (em reais)'),
        ),
    ]