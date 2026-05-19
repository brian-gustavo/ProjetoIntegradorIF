import random, string
from django.db import models

from catalog.models import Product
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
        ('DELIVERED', 'Entregue'),
        ('CANCELLED', 'Cancelado'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Comprador")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders', verbose_name="Produto")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço total")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    tracking_code = models.CharField(max_length=13, blank=True, verbose_name="Código de rastreio")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} — {self.product.title}"

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
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")

    class Meta:
        verbose_name = "Item do carrinho"
        verbose_name_plural = "Itens do carrinho"
        unique_together = ('cart', 'product')

    def __str__(self):
        return f"{self.quantity}x {self.product.title}"

    @property
    def subtotal(self):
        return self.product.price * self.quantity