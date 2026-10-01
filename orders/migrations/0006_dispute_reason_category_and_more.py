import django.core.validators
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('orders', '0005_platformconfig_dispute_window_days_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='dispute',
            name='reason_category',
            field=models.CharField(blank=True, max_length=100, verbose_name='Motivo'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='dispute_reasons',
            field=models.TextField(default='Produto com defeito\nProduto diferente do anunciado\nProduto incompleto\nProduto não recebido\nKey ou código digital inválido\nProduto devolvido com avarias\nDevolução sem justificativa\nOutro', help_text='Um motivo por linha', verbose_name='Motivos de disputa'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='ranking_size',
            field=models.PositiveIntegerField(default=10, validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(100)], verbose_name='Vendedores exibidos no ranking do painel'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='return_window_days',
            field=models.PositiveIntegerField(default=7, validators=[django.core.validators.MinValueValidator(1)], verbose_name='Prazo para solicitar devolução após a entrega (dias)'),
        ),
        migrations.AlterField(
            model_name='dispute',
            name='reason',
            field=models.TextField(verbose_name='Descrição'),
        ),
    ]