import random, string
from decimal import Decimal
from django.db import models

from catalog.models import Product, ProductVariant
from django.contrib.auth.models import User

def generate_tracking_code():
    letters = ''.join(random.choices(string.ascii_uppercase, k=2))
    digits = ''.join(random.choices(string.digits, k=9))
    return f"{letters}{digits}BR"

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Aguardando pagamento'),
        ('PAID', 'Pago'),
        ('CONFIRMED', 'Confirmado pelo vendedor'),
        ('PREPARING', 'Em preparação'),
        ('SHIPPED', 'Enviado'),
        ('READY_PICKUP', 'Pronto para retirada'),
        ('DELIVERED', 'Entregue'),
        ('RETURN_WINDOW', 'Período de devolução'),
        ('RETURN_REQUESTED', 'Devolução solicitada'),
        ('DISPUTE_OPEN', 'Em disputa'),
        ('RETURN_ACCEPTED', 'Devolução aceita'),
        ('RETURNED', 'Devolvido'),
        ('CANCELLED_NO_RETURN', 'Cancelado sem devolução'),
        ('COMPLETED', 'Concluído'),
        ('CANCELLED', 'Cancelado'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Comprador")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders', verbose_name="Produto")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='orders', verbose_name="Variação")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço total")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    pickup = models.BooleanField(default=False, verbose_name="Retirada em mãos")
    tracking_code = models.CharField(max_length=13, blank=True, verbose_name="Código de rastreio")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} — {self.product.title} ({self.variant.name})"

class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='cart', verbose_name="Usuário")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Carrinho"
        verbose_name_plural = "Carrinhos"

    def __str__(self):
        return f"Carrinho de {self.user.username}"

class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items', verbose_name="Carrinho")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='cart_items', verbose_name="Produto")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='cart_items', verbose_name="Variação")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")

    class Meta:
        verbose_name = "Item do carrinho"
        verbose_name_plural = "Itens do carrinho"
        unique_together = ('cart', 'variant')

    def __str__(self):
        return f"{self.quantity}× {self.product.title} ({self.variant.name})"

    @property
    def subtotal(self):
        return self.variant.price * self.quantity

class PlatformConfig(models.Model):
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        verbose_name="Taxa de comissão (%)"
    )

    class Meta:
        verbose_name = "Configuração da plataforma"
        verbose_name_plural = "Configurações da plataforma"

    def __str__(self):
        return f"Comissão: {self.commission_rate}%"

    @classmethod
    def get_commission_rate(cls):
        config = cls.objects.first()
        return config.commission_rate if config else Decimal('10.00')

class Commission(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='commission', verbose_name="Pedido")
    rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name="Taxa aplicada (%)")
    gross_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor bruto")
    commission_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Comissão")
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor líquido")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Comissão"
        verbose_name_plural = "Comissões"

    def __str__(self):
        return f"Comissão do pedido #{self.order.pk}"

class Dispute(models.Model):
    STATUS_CHOICES = [
        ('OPEN', 'Aberta'),
        ('RESOLVED_BUYER_RETURN', 'A favor do comprador (com devolução)'),
        ('RESOLVED_BUYER_REFUND', 'A favor do comprador (sem devolução)'),
        ('RESOLVED_SELLER', 'A favor do vendedor'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='dispute', verbose_name="Pedido")
    opened_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='disputes_opened', verbose_name="Aberta por")
    reason = models.TextField(verbose_name="Motivo")
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='OPEN', verbose_name="Status")
    resolution_notes = models.TextField(blank=True, verbose_name="Notas da resolução")
    resolved_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='disputes_resolved', verbose_name="Resolvida por")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Resolvida em")

    class Meta:
        verbose_name = "Disputa"
        verbose_name_plural = "Disputas"

    def __str__(self):
        return f"Disputa #{self.pk} — Pedido #{self.order.pk}"

class DisputeMessage(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='messages', verbose_name="Disputa")
    author = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Autor")
    message = models.TextField(verbose_name="Mensagem")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Enviada em")

    class Meta:
        verbose_name = "Mensagem de disputa"
        verbose_name_plural = "Mensagens de disputa"

    def __str__(self):
        return f"{self.author.username} em Disputa #{self.dispute_id}"