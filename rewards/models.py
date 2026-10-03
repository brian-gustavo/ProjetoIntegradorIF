from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q

class CoinTransaction(models.Model):
    KIND_CHOICES = [
        ('PURCHASE', 'Cashback de compra'),
        ('REVIEW', 'Bônus de avaliação'),
        ('CHECKIN', 'Check-in diário'),
        ('REDEEM', 'Desconto em compra'),
        ('REFUND', 'Devolução de moedas'),
        ('ADJUST', 'Ajuste manual'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='coin_transactions', verbose_name="Usuário")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, verbose_name="Tipo")
    amount = models.IntegerField(verbose_name="Moedas")
    order = models.ForeignKey('orders.Order', null=True, blank=True, on_delete=models.CASCADE, related_name='coin_transactions', verbose_name="Pedido")
    reference = models.CharField(max_length=50, blank=True, verbose_name="Referência")
    description = models.CharField(max_length=200, verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criada em")

    class Meta:
        verbose_name = "Movimentação de MegaCoins"
        verbose_name_plural = "Movimentações de MegaCoins"
        ordering = ('-created_at', '-pk')
        constraints = [
            models.UniqueConstraint(fields=('order', 'kind'), condition=Q(order__isnull=False), name='unique_coin_kind_per_order'),
            models.UniqueConstraint(fields=('user', 'kind', 'reference'), condition=~Q(reference=''), name='unique_coin_reference_per_user'),
        ]

    def __str__(self):
        return f"{self.user.username}: {self.amount:+d} ({self.get_kind_display()})"