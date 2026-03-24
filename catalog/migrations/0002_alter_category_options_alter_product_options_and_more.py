import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='category',
            options={'verbose_name': 'Categoria', 'verbose_name_plural': 'Categorias'},
        ),
        migrations.AlterModelOptions(
            name='product',
            options={'verbose_name': 'Produto', 'verbose_name_plural': 'Produtos'},
        ),
        migrations.AlterModelOptions(
            name='productimage',
            options={'verbose_name': 'Imagem do produto', 'verbose_name_plural': 'Imagens dos produtos'},
        ),
        migrations.AlterField(
            model_name='category',
            name='name',
            field=models.CharField(max_length=100, verbose_name='Nome'),
        ),
        migrations.AlterField(
            model_name='category',
            name='slug',
            field=models.SlugField(unique=True, verbose_name='URL'),
        ),
        migrations.AlterField(
            model_name='product',
            name='category',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='catalog.category', verbose_name='Categoria'),
        ),
        migrations.AlterField(
            model_name='product',
            name='condition',
            field=models.CharField(choices=[('NEW', 'Novo'), ('USED', 'Usado')], default='USED', max_length=4, verbose_name='Condição'),
        ),
        migrations.AlterField(
            model_name='product',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, verbose_name='Criado em'),
        ),
        migrations.AlterField(
            model_name='product',
            name='description',
            field=models.TextField(verbose_name='Descrição'),
        ),
        migrations.AlterField(
            model_name='product',
            name='location',
            field=models.CharField(help_text='Cidade/Estado', max_length=100, verbose_name='Localização'),
        ),
        migrations.AlterField(
            model_name='product',
            name='price',
            field=models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preço'),
        ),
        migrations.AlterField(
            model_name='product',
            name='seller',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to=settings.AUTH_USER_MODEL, verbose_name='Vendedor'),
        ),
        migrations.AlterField(
            model_name='product',
            name='title',
            field=models.CharField(max_length=255, verbose_name='Título'),
        ),
        migrations.AlterField(
            model_name='product',
            name='updated_at',
            field=models.DateTimeField(auto_now=True, verbose_name='Atualizado em'),
        ),
        migrations.AlterField(
            model_name='productimage',
            name='image',
            field=models.ImageField(upload_to='products/', verbose_name='Imagem'),
        ),
        migrations.AlterField(
            model_name='productimage',
            name='product',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='catalog.product', verbose_name='Produto'),
        ),
    ]