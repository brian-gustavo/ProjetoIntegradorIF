from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0005_productreview'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'ordering': ['name'], 'verbose_name': 'Categoria', 'verbose_name_plural': 'Categorias'},
        ),
    ]