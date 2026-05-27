from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0002_product_accepts_pickup'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='published',
            field=models.BooleanField(default=False, verbose_name='Publicado'),
        ),
    ]