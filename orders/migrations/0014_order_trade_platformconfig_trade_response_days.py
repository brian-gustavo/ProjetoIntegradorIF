import django.core.validators
import django.db.models.deletion
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0013_platformconfig_second_chance_window_days'),
        ('trades', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='order',
            name='trade',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='orders', to='trades.tradeproposal', verbose_name='Troca'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='trade_response_days',
            field=models.PositiveIntegerField(default=3, help_text='Vale para a proposta inicial e para cada contraproposta; sem resposta nesse prazo, a proposta expira', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(14)], verbose_name='Prazo para responder uma proposta de troca (dias)'),
        ),
    ]