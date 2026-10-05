import random, string
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from catalog.models import Category, Product, ProductVariant
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
    coins_used = models.PositiveIntegerField(default=0, verbose_name="MegaCoins utilizadas")
    coins_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Desconto em MegaCoins")
    seller_coupon = models.ForeignKey('coupons.CouponRedemption', null=True, blank=True, on_delete=models.SET_NULL, related_name='seller_orders', verbose_name="Cupom da loja")
    seller_coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Desconto do cupom da loja")
    platform_coupon = models.ForeignKey('coupons.CouponRedemption', null=True, blank=True, on_delete=models.SET_NULL, related_name='platform_orders', verbose_name="Cupom MegaGame")
    platform_coupon_discount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Desconto do cupom MegaGame")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Pedido"
        verbose_name_plural = "Pedidos"

    def __str__(self):
        return f"Pedido #{self.pk} — {self.product.title} ({self.variant.name})"

    @property
    def sale_amount(self):
        return self.total_price - self.seller_coupon_discount

    @property
    def platform_discount(self):
        return self.coins_discount + self.platform_coupon_discount

    @property
    def amount_paid(self):
        return self.sale_amount - self.platform_discount

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

DEFAULT_DISPUTE_REASONS = '\n'.join([
    'Produto com defeito',
    'Produto diferente do anunciado',
    'Produto incompleto',
    'Produto não recebido',
    'Key ou código digital inválido',
    'Produto devolvido com avarias',
    'Devolução sem justificativa',
    'Outro',
])

DEFAULT_RETURN_REASONS = '\n'.join([
    'Produto com defeito',
    'Produto diferente do anunciado',
    'Produto incompleto',
    'Key ou código digital inválido',
    'Produto chegou danificado',
    'Desisti da compra',
    'Outro',
])

class PlatformConfig(models.Model):
    commission_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Taxa de comissão (%)"
    )
    dispute_window_days = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1)],
        verbose_name="Prazo para contestar cancelamento sem devolução (dias)"
    )
    return_window_days = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1)],
        verbose_name="Prazo para solicitar devolução após a entrega (dias)"
    )
    seller_response_days = models.PositiveIntegerField(
        default=3,
        validators=[MinValueValidator(1)],
        help_text="Após uma solicitação de devolução, o comprador só pode abrir disputa depois que esse prazo terminar sem solução",
        verbose_name="Prazo de resposta do vendedor antes de uma disputa (dias)"
    )
    escalation_window_days = models.PositiveIntegerField(
        default=7,
        validators=[MinValueValidator(1)],
        help_text="Encerrado o prazo do vendedor, o comprador tem esse prazo para abrir disputa; depois disso, a solicitação de devolução é encerrada e o pedido é concluído",
        verbose_name="Prazo para o comprador abrir disputa (dias)"
    )
    ranking_size = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name="Vendedores exibidos no ranking do painel"
    )
    dispute_reasons = models.TextField(
        default=DEFAULT_DISPUTE_REASONS,
        help_text="Um motivo por linha",
        verbose_name="Motivos de disputa"
    )
    return_reasons = models.TextField(
        default=DEFAULT_RETURN_REASONS,
        help_text="Um motivo por linha",
        verbose_name="Motivos de devolução"
    )
    shelf_size = models.PositiveIntegerField(
        default=15,
        validators=[MinValueValidator(5), MaxValueValidator(30)],
        help_text="Quantidade máxima de produtos em cada prateleira (entre 5 e 30)",
        verbose_name="Produtos por prateleira da página inicial"
    )
    home_categories = models.ManyToManyField(
        Category,
        blank=True,
        related_name='+',
        help_text="Cada categoria marcada vira uma prateleira na página inicial; se nenhuma for marcada, são exibidas as 3 categorias com mais anúncios",
        verbose_name="Categorias em destaque na página inicial"
    )
    coins_cashback_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(0), MaxValueValidator(20)],
        help_text="Percentual do valor pago devolvido em MegaCoins (100 moedas = R$ 1,00), antes do multiplicador de nível do comprador",
        verbose_name="Cashback em MegaCoins (%)"
    )
    coins_max_redeem_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('10.00'),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Desconto máximo por pedido; nunca ultrapassa a taxa de comissão, já que o desconto é custeado pela plataforma e o vendedor recebe o valor integral",
        verbose_name="Limite de uso de MegaCoins por pedido (%)"
    )
    coins_review_reward = models.PositiveIntegerField(
        default=20,
        validators=[MaxValueValidator(1000)],
        help_text="Concedidas uma única vez por produto ou vendedor avaliado",
        verbose_name="MegaCoins por avaliação"
    )
    auction_payment_days = models.PositiveIntegerField(
        default=4,
        validators=[MinValueValidator(1), MaxValueValidator(30)],
        help_text="Encerrado o prazo sem pagamento, o vendedor pode cancelar a venda e relistar o item",
        verbose_name="Prazo para o vencedor de um leilão pagar (dias)"
    )
    second_chance_window_days = models.PositiveIntegerField(
        default=60,
        validators=[MinValueValidator(1), MaxValueValidator(365)],
        help_text="Após o fim de um leilão não vendido ou não pago, o vendedor pode oferecer o item a outro participante dentro desse prazo",
        verbose_name="Prazo para enviar ofertas de segunda chance (dias)"
    )

    class Meta:
        verbose_name = "Configuração da plataforma"
        verbose_name_plural = "Configurações da plataforma"

    def __str__(self):
        return f"Comissão: {self.commission_rate}%"

    @classmethod
    def load(cls):
        return cls.objects.first() or cls.objects.create()

    def dispute_reason_list(self):
        return [linha.strip() for linha in self.dispute_reasons.splitlines() if linha.strip()]

    def return_reason_list(self):
        return [linha.strip() for linha in self.return_reasons.splitlines() if linha.strip()]

    @classmethod
    def get_commission_rate(cls):
        config = cls.objects.first()
        return config.commission_rate if config else Decimal('10.00')

def commission_for(order, rate):
    gross = order.sale_amount
    commission_amount = (gross * rate / Decimal('100')).quantize(Decimal('0.01'))
    return {
        'rate': rate,
        'gross_amount': gross,
        'commission_amount': commission_amount,
        'net_amount': gross - commission_amount,
    }

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
    reason_category = models.CharField(max_length=100, blank=True, verbose_name="Motivo")
    reason = models.TextField(verbose_name="Descrição")
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

class DisputeEvidence(models.Model):
    dispute = models.ForeignKey(Dispute, on_delete=models.CASCADE, related_name='evidences', verbose_name="Disputa")
    message = models.ForeignKey(DisputeMessage, null=True, blank=True, on_delete=models.CASCADE, related_name='images', verbose_name="Mensagem")
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Enviada por")
    image = models.ImageField(upload_to='disputes/', verbose_name="Imagem")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Enviada em")

    class Meta:
        verbose_name = "Evidência de disputa"
        verbose_name_plural = "Evidências de disputa"
        ordering = ('created_at',)

    def __str__(self):
        return f"Evidência de {self.uploaded_by.username} em Disputa #{self.dispute_id}"

class ReturnRequest(models.Model):
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='return_request', verbose_name="Pedido")
    reason_category = models.CharField(max_length=100, verbose_name="Motivo")
    description = models.TextField(verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Solicitada em")

    class Meta:
        verbose_name = "Solicitação de devolução"
        verbose_name_plural = "Solicitações de devolução"

    def __str__(self):
        return f"Devolução do pedido #{self.order_id}"

class ReturnRequestImage(models.Model):
    return_request = models.ForeignKey(ReturnRequest, on_delete=models.CASCADE, related_name='images', verbose_name="Solicitação")
    image = models.ImageField(upload_to='returns/', verbose_name="Imagem")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Enviada em")

    class Meta:
        verbose_name = "Imagem de solicitação de devolução"
        verbose_name_plural = "Imagens de solicitação de devolução"
        ordering = ('created_at',)

    def __str__(self):
        return f"Imagem da devolução do pedido #{self.return_request.order_id}"