from decimal import Decimal
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from catalog.models import Product
from orders.models import Order

class Auction(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Em andamento'),
        ('SOLD', 'Vendido'),
        ('UNSOLD', 'Encerrado sem venda'),
    ]
    DURATION_CHOICES = [
        (1, '1 dia'),
        (3, '3 dias'),
        (5, '5 dias'),
        (7, '7 dias'),
        (10, '10 dias'),
    ]

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name='auction', verbose_name="Produto")
    start_price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('1.00'))], verbose_name="Lance inicial")
    reserve_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço de reserva")
    buy_now_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Preço do Comprar agora")
    duration_days = models.PositiveSmallIntegerField(choices=DURATION_CHOICES, default=7, verbose_name="Duração")
    starts_at = models.DateTimeField(default=timezone.now, verbose_name="Início")
    ends_at = models.DateTimeField(verbose_name="Término")
    status = models.CharField(max_length=6, choices=STATUS_CHOICES, default='ACTIVE', verbose_name="Status")
    current_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Lance atual")
    bid_count = models.PositiveIntegerField(default=0, verbose_name="Lances")
    leader = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='auctions_leading', verbose_name="Maior lance")
    winner = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='auctions_won', verbose_name="Vencedor")
    order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='auction', verbose_name="Pedido")
    bought_now = models.BooleanField(default=False, verbose_name="Vendido pelo Comprar agora")
    ended_early = models.BooleanField(default=False, verbose_name="Encerrado antes do prazo")
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name="Encerrado em")
    payment_due_at = models.DateTimeField(null=True, blank=True, verbose_name="Prazo de pagamento")
    relisted_as = models.OneToOneField('self', null=True, blank=True, on_delete=models.SET_NULL, related_name='relisted_from', verbose_name="Relistado como")

    class Meta:
        verbose_name = "Leilão"
        verbose_name_plural = "Leilões"

    def __str__(self):
        return f"Leilão de {self.product.title}"

    @property
    def is_open(self):
        return self.status == 'ACTIVE' and self.ends_at > timezone.now()

    @property
    def has_reserve(self):
        return self.reserve_price is not None

    @property
    def reserve_met(self):
        return not self.has_reserve or (self.leader_id is not None and self.current_price >= self.reserve_price)

    @property
    def buy_now_available(self):
        if not self.is_open or self.buy_now_price is None:
            return False
        return self.bid_count == 0 or (self.has_reserve and not self.reserve_met)

class Bid(models.Model):
    RETRACTION_CHOICES = [
        ('TYPO', 'Digitei o valor errado'),
        ('DESCRIPTION', 'A descrição do item mudou significativamente'),
        ('SELLER', 'Não consigo entrar em contato com o vendedor'),
    ]

    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='bids', verbose_name="Leilão")
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bids', verbose_name="Participante")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Valor")
    is_auto = models.BooleanField(default=False, verbose_name="Lance automático")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Feito em")
    retracted_at = models.DateTimeField(null=True, blank=True, verbose_name="Retirado em")
    retraction_reason = models.CharField(max_length=11, choices=RETRACTION_CHOICES, blank=True, verbose_name="Motivo da retirada")

    class Meta:
        verbose_name = "Lance"
        verbose_name_plural = "Lances"
        ordering = ('-created_at', '-pk')

    def __str__(self):
        return f"{self.bidder.username}: R$ {self.amount} em {self.auction}"

class AuctionWatch(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='auction_watches', verbose_name="Usuário")
    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='watches', verbose_name="Leilão")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Acompanhando desde")

    class Meta:
        verbose_name = "Leilão acompanhado"
        verbose_name_plural = "Leilões acompanhados"
        unique_together = ('user', 'auction')

    def __str__(self):
        return f"{self.user.username} acompanha {self.auction}"

class SecondChanceOffer(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Aguardando resposta'),
        ('ACCEPTED', 'Aceita'),
        ('DECLINED', 'Recusada'),
        ('EXPIRED', 'Expirada'),
    ]
    DURATION_CHOICES = [
        (1, '1 dia'),
        (3, '3 dias'),
        (5, '5 dias'),
        (7, '7 dias'),
    ]

    auction = models.ForeignKey(Auction, on_delete=models.CASCADE, related_name='second_chance_offers', verbose_name="Leilão")
    bidder = models.ForeignKey(User, on_delete=models.CASCADE, related_name='second_chance_offers', verbose_name="Participante")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço")
    duration_days = models.PositiveSmallIntegerField(choices=DURATION_CHOICES, default=3, verbose_name="Validade")
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default='PENDING', verbose_name="Status")
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Enviada em")
    expires_at = models.DateTimeField(verbose_name="Expira em")
    responded_at = models.DateTimeField(null=True, blank=True, verbose_name="Respondida em")
    order = models.OneToOneField(Order, null=True, blank=True, on_delete=models.SET_NULL, related_name='second_chance_offer', verbose_name="Pedido")

    class Meta:
        verbose_name = "Oferta de segunda chance"
        verbose_name_plural = "Ofertas de segunda chance"
        unique_together = ('auction', 'bidder')
        ordering = ('-created_at',)

    def __str__(self):
        return f"Segunda chance para {self.bidder.username} em {self.auction}"

    @property
    def is_pending(self):
        return self.status == 'PENDING' and self.expires_at > timezone.now()