from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

from django.contrib.auth.models import User

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    slug = models.SlugField(unique=True, verbose_name="URL")

    class Meta:
        verbose_name = "Categoria"
        verbose_name_plural = "Categorias"
        ordering = ['name']

    def __str__(self):
        return self.name

class Product(models.Model):
    CONDITION_CHOICES = [
        ('NEW', 'Novo'),
        ('USED', 'Usado'),
    ]

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', verbose_name="Categoria")
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='products', verbose_name="Vendedor")
    title = models.CharField(max_length=255, verbose_name="Título")
    description = models.TextField(verbose_name="Descrição")
    condition = models.CharField(max_length=4, choices=CONDITION_CHOICES, default='NEW', verbose_name="Condição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")

    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"

    def __str__(self):
        return self.title

    @property
    def base_price(self):
        variant = self.variants.order_by('price').first()
        return variant.price if variant else None

    @property
    def total_stock(self):
        return sum(v.quantity for v in self.variants.all())

class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants', verbose_name="Produto")
    name = models.CharField(max_length=100, verbose_name="Variação")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço (em reais)")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade em estoque")

    class Meta:
        verbose_name = "Variação"
        verbose_name_plural = "Variações"

    def __str__(self):
        return f"{self.product.title} — {self.name}"

class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='images', verbose_name="Produto")
    image = models.ImageField(upload_to='products/', verbose_name="Imagem")

    class Meta:
        verbose_name = "Imagem do produto"
        verbose_name_plural = "Imagens dos produtos"

class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews', verbose_name="Produto")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='product_reviews', verbose_name="Avaliador")
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        validators=[MinValueValidator(0.5), MaxValueValidator(5.0)],
        verbose_name="Nota"
    )
    comment = models.TextField(blank=True, verbose_name="Comentário")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Avaliação de produto"
        verbose_name_plural = "Avaliações de produtos"
        unique_together = ('product', 'reviewer')

    def __str__(self):
        return f"{self.reviewer.username} → {self.product.title}: {self.rating}"