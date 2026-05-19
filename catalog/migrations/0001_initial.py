import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Nome')),
                ('slug', models.SlugField(unique=True, verbose_name='URL')),
            ],
            options={
                'verbose_name': 'Categoria',
                'verbose_name_plural': 'Categorias',
                'ordering': ['name'],
            },
        ),
        migrations.CreateModel(
            name='Product',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=255, verbose_name='Título')),
                ('description', models.TextField(verbose_name='Descrição')),
                ('condition', models.CharField(choices=[('NEW', 'Novo'), ('USED', 'Usado')], default='NEW', max_length=4, verbose_name='Condição')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Atualizado em')),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to='catalog.category', verbose_name='Categoria')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='products', to=settings.AUTH_USER_MODEL, verbose_name='Vendedor')),
            ],
            options={
                'verbose_name': 'Produto',
                'verbose_name_plural': 'Produtos',
            },
        ),
        migrations.CreateModel(
            name='ProductImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(upload_to='products/', verbose_name='Imagem')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='images', to='catalog.product', verbose_name='Produto')),
            ],
            options={
                'verbose_name': 'Imagem do produto',
                'verbose_name_plural': 'Imagens dos produtos',
            },
        ),
        migrations.CreateModel(
            name='ProductVariant',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, verbose_name='Variação')),
                ('price', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Preço (em reais)')),
                ('quantity', models.PositiveIntegerField(default=1, verbose_name='Quantidade em estoque')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='variants', to='catalog.product', verbose_name='Produto')),
            ],
            options={
                'verbose_name': 'Variação',
                'verbose_name_plural': 'Variações',
            },
        ),
        migrations.CreateModel(
            name='ProductReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.DecimalField(decimal_places=1, max_digits=2, validators=[django.core.validators.MinValueValidator(0.5), django.core.validators.MaxValueValidator(5.0)], verbose_name='Nota')),
                ('comment', models.TextField(blank=True, verbose_name='Comentário')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews', to='catalog.product', verbose_name='Produto')),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='product_reviews', to=settings.AUTH_USER_MODEL, verbose_name='Avaliador')),
            ],
            options={
                'verbose_name': 'Avaliação de produto',
                'verbose_name_plural': 'Avaliações de produtos',
                'unique_together': {('product', 'reviewer')},
            },
        ),
    ]