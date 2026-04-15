from django.db import models

from catalog.models import Product
from django.contrib.auth.models import User

class Order(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Aguardando pagamento'),
        ('PAID', 'Pago'),
        ('CANCELLED', 'Cancelado'),
        ('DELIVERED', 'Entregue'),
    ]

    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders', verbose_name="Comprador")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='orders', verbose_name="Produto")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço total")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} — {self.product.title}"