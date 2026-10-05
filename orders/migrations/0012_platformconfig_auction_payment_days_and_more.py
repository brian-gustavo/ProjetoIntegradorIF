import django.core.validators
from decimal import Decimal
from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('catalog', '0005_productreview_edited_alter_productvariant_quantity'),
        ('orders', '0011_order_platform_coupon_order_platform_coupon_discount_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformconfig',
            name='auction_payment_days',
            field=models.PositiveIntegerField(default=4, help_text='Encerrado o prazo sem pagamento, o vendedor pode cancelar a venda e relistar o item', validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(30)], verbose_name='Prazo para o vencedor de um leilão pagar (dias)'),
        ),
        migrations.AlterField(
            model_name='platformconfig',
            name='coins_max_redeem_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('10.00'), help_text='Desconto máximo por pedido; nunca ultrapassa a taxa de comissão, já que o desconto é custeado pela plataforma e o vendedor recebe o valor integral', max_digits=5, validators=[django.core.validators.MinValueValidator(0), django.core.validators.MaxValueValidator(100)], verbose_name='Limite de uso de MegaCoins por pedido (%)'),
        ),
        migrations.AlterField(
            model_name='platformconfig',
            name='home_categories',
            field=models.ManyToManyField(blank=True, help_text='Cada categoria marcada vira uma prateleira na página inicial; se nenhuma for marcada, são exibidas as 3 categorias com mais anúncios', related_name='+', to='catalog.category', verbose_name='Categorias em destaque na página inicial'),
        ),
    ]