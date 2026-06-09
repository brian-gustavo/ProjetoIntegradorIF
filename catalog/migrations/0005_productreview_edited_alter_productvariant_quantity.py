from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0004_product_deleted'),
    ]

    operations = [
        migrations.AddField(
            model_name='productreview',
            name='edited',
            field=models.BooleanField(default=False, verbose_name='Já editado?'),
        ),
        migrations.AlterField(
            model_name='productvariant',
            name='quantity',
            field=models.PositiveIntegerField(default=1, verbose_name='Quantidade'),
        ),
    ]