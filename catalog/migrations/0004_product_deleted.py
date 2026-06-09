from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0003_product_published'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='deleted',
            field=models.BooleanField(default=False, verbose_name='Excluído'),
        ),
    ]