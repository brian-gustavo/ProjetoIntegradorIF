from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0005_productreview_edited_alter_productvariant_quantity'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='accepts_trade',
            field=models.BooleanField(default=False, verbose_name='Aceita trocas'),
        ),
        migrations.AddField(
            model_name='product',
            name='trade_preferences',
            field=models.CharField(blank=True, help_text='Opcional. Ex.: jogos de PS5, controles originais. Deixe em branco para receber qualquer proposta.', max_length=300, verbose_name='O que você aceita em troca'),
        ),
    ]