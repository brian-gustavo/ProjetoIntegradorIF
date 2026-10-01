import django.core.validators
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0005_productreview_edited_alter_productvariant_quantity'),
        ('orders', '0006_dispute_reason_category_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformconfig',
            name='home_categories',
            field=models.ManyToManyField(blank=True, help_text='Cada categoria marcada vira uma prateleira na página inicial. Se nenhuma for marcada, são exibidas as 3 categorias com mais anúncios.', related_name='+', to='catalog.category', verbose_name='Categorias em destaque na página inicial'),
        ),
        migrations.AddField(
            model_name='platformconfig',
            name='shelf_size',
            field=models.PositiveIntegerField(default=15, help_text='Quantidade máxima de produtos em cada prateleira (entre 5 e 30)', validators=[django.core.validators.MinValueValidator(5), django.core.validators.MaxValueValidator(30)], verbose_name='Produtos por prateleira da página inicial'),
        ),
    ]