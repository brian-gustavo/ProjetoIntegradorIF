from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0006_alter_category_options'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='product',
            name='location',
        ),
    ]