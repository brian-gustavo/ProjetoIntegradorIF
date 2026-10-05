from decimal import Decimal
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from catalog.models import Product, ProductVariant

PROPOSER = 'PROPOSER'
OWNER = 'OWNER'
SIDE_CHOICES = [
    (PROPOSER, 'Proponente'),
    (OWNER, 'Anunciante'),
]

class TradeProposal(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Em negociação'),
        ('ACCEPTED', 'Aceita'),
        ('DECLINED', 'Recusada'),
        ('WITHDRAWN', 'Retirada'),
        ('EXPIRED', 'Expirada'),
        ('CANCELLED', 'Cancelada após o aceite'),
    ]

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='trade_proposals', verbose_name="Anúncio")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='trade_proposals', verbose_name="Variação")
    proposer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades_proposed', verbose_name="Proponente")
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades_received', verbose_name="Anunciante")
    cash_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Volta")
    cash_payer = models.CharField(max_length=8, choices=SIDE_CHOICES, blank=True, verbose_name="Quem paga a volta")
    status = models.CharField(max_length=9, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    awaiting = models.CharField(max_length=8, choices=SIDE_CHOICES, default=OWNER, verbose_name="Aguardando resposta de")
    rounds = models.PositiveIntegerField(default=1, verbose_name="Rodadas de negociação")
    expires_at = models.DateTimeField(verbose_name="Expira em")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Criada em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizada em")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Encerrada em")

    class Meta:
        verbose_name = "Proposta de troca"
        verbose_name_plural = "Propostas de troca"
        ordering = ('-updated_at',)

    def __str__(self):
        return f"Troca #{self.pk}: {self.proposer.username} → {self.product.title}"

    @property
    def is_open(self):
        return self.status == 'PENDING' and self.expires_at > timezone.now()

    def party(self, user):
        if user.pk == self.proposer_id:
            return PROPOSER
        if user.pk == self.owner_id:
            return OWNER
        return None

    def user_for(self, lado):
        return self.proposer if lado == PROPOSER else self.owner

    @property
    def awaiting_user(self):
        return self.user_for(self.awaiting)

    @property
    def cash_payer_user(self):
        return self.user_for(self.cash_payer) if self.cash_payer else None

    @property
    def offered_value(self):
        return sum((item.variant.price for item in self.items.all()), Decimal('0.00'))

class TradeItem(models.Model):
    proposal = models.ForeignKey(TradeProposal, on_delete=models.CASCADE, related_name='items', verbose_name="Proposta")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='trade_items', verbose_name="Anúncio")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='trade_items', verbose_name="Variação")

    class Meta:
        verbose_name = "Item oferecido"
        verbose_name_plural = "Itens oferecidos"
        unique_together = ('proposal', 'variant')

    def __str__(self):
        return f"{self.product.title} ({self.variant.name})"

class TradeEvent(models.Model):
    KIND_CHOICES = [
        ('PROPOSED', 'Enviou a proposta'),
        ('COUNTERED', 'Fez uma contraproposta'),
        ('ACCEPTED', 'Aceitou a troca'),
        ('DECLINED', 'Recusou a proposta'),
        ('WITHDRAWN', 'Retirou a proposta'),
        ('EXPIRED', 'Proposta expirada sem resposta'),
        ('CANCELLED', 'Cancelou a troca'),
    ]

    proposal = models.ForeignKey(TradeProposal, on_delete=models.CASCADE, related_name='events', verbose_name="Proposta")
    author = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, verbose_name="Autor")
    kind = models.CharField(max_length=9, choices=KIND_CHOICES, verbose_name="Evento")
    summary = models.TextField(blank=True, verbose_name="Termos")
    message = models.TextField(blank=True, verbose_name="Mensagem")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Registrado em")

    class Meta:
        verbose_name = "Evento de troca"
        verbose_name_plural = "Eventos de troca"
        ordering = ('created_at', 'pk')

    def __str__(self):
        return f"{self.get_kind_display()} · Troca #{self.proposal_id}"
