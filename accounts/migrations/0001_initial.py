import django.core.validators, django.db.models.deletion
from django.conf import settings
from django.db import migrations, models

class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='SellerReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('rating', models.DecimalField(decimal_places=1, max_digits=2, validators=[django.core.validators.MinValueValidator(0.5), django.core.validators.MaxValueValidator(5.0)], verbose_name='Nota')),
                ('comment', models.TextField(blank=True, verbose_name='Comentário')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Criado em')),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews_given', to=settings.AUTH_USER_MODEL, verbose_name='Avaliador')),
                ('seller', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reviews_received', to=settings.AUTH_USER_MODEL, verbose_name='Vendedor')),
            ],
            options={
                'verbose_name': 'Avaliação',
                'verbose_name_plural': 'Avaliações',
                'unique_together': {('seller', 'reviewer')},
            },
        ),
    ]