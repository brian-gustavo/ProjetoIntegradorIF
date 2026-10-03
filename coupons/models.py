from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Category
from catalog.templatetags.catalog_extras import brl

def _reais(valor):
    texto = brl(valor)
    return f'R$ {texto[:-3] if texto.endswith(",00") else texto}'

class Coupon(models.Model):
    KIND_CHOICES = [
        ('PERCENT', 'Percentual'),
        ('FIXED', 'Valor fixo'),
    ]

    code = models.CharField(max_length=20, unique=True, verbose_name="Código")
    seller = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='coupons', help_text="Vazio para cupons da MegaGame", verbose_name="Loja")
    kind = models.CharField(max_length=7, choices=KIND_CHOICES, default='PERCENT', verbose_name="Tipo de desconto")
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))], verbose_name="Valor do desconto")
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, validators=[MinValueValidator(Decimal('0.01'))], verbose_name="Desconto máximo (R$)")
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(0)], verbose_name="Valor mínimo da compra (R$)")
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.CASCADE, related_name='coupons', verbose_name="Categoria")
    first_purchase_only = models.BooleanField(default=False, verbose_name="Apenas primeira compra")
    is_public = models.BooleanField(default=True, verbose_name="Público")
    starts_at = models.DateTimeField(default=timezone.now, verbose_name="Início da validade")
    ends_at = models.DateTimeField(null=True, blank=True, verbose_name="Fim da validade")
    usage_limit = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1)], verbose_name="Limite total de usos")
    per_user_limit = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)], verbose_name="Usos por cliente")
    active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Cupom"
        verbose_name_plural = "Cupons"
        ordering = ('-created_at',)

    def __str__(self):
        return self.code

    @property
    def is_platform(self):
        return self.seller_id is None

    @property
    def origin(self):
        return 'MegaGame' if self.is_platform else f'Loja {self.seller.username}'

    @property
    def headline(self):
        if self.kind == 'PERCENT':
            return f'{self.value.normalize():f}'.replace('.', ',') + '% OFF'
        return f'{_reais(self.value)} OFF'

    @property
    def conditions(self):
        itens = [f'Compras acima de {_reais(self.min_order_value)}' if self.min_order_value else 'Sem valor mínimo']
        if self.kind == 'PERCENT' and self.max_discount:
            itens.append(f'Até {_reais(self.max_discount)} de desconto')
        if self.category_id:
            itens.append(f'Só em {self.category.name}')
        if self.first_purchase_only:
            itens.append('Primeira compra na MegaGame' if self.is_platform else 'Primeira compra na loja')
        if self.per_user_limit > 1:
            itens.append(f'{self.per_user_limit} usos por cliente')
        return itens

    def discount_for(self, base):
        if self.kind == 'PERCENT':
            desconto = base * self.value / Decimal('100')
            if self.max_discount:
                desconto = min(desconto, self.max_discount)
        else:
            desconto = self.value
        return min(desconto, base).quantize(Decimal('0.01'))

class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='redemptions', verbose_name="Cupom")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coupon_redemptions', verbose_name="Usuário")
    discount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Desconto concedido")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Usado em")

    class Meta:
        verbose_name = "Uso de cupom"
        verbose_name_plural = "Usos de cupons"
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f"{self.coupon.code} por {self.user.username}"

class SavedCoupon(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_coupons', verbose_name="Usuário")
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name='saves', verbose_name="Cupom")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Salvo em")

    class Meta:
        verbose_name = "Cupom salvo"
        verbose_name_plural = "Cupons salvos"
        unique_together = ('user', 'coupon')

    def __str__(self):
        return f"{self.coupon.code} salvo por {self.user.username}"