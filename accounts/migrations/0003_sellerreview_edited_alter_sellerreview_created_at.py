from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0002_profile'),
    ]

    operations = [
        migrations.AddField(
            model_name='sellerreview',
            name='edited',
            field=models.BooleanField(default=False, verbose_name='Já editada?'),
        ),
        migrations.AlterField(
            model_name='sellerreview',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criada em'),
        ),
    ]