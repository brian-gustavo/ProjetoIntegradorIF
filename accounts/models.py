from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

class SellerReview(models.Model):
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_received', verbose_name="Vendedor")
    reviewer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews_given', verbose_name="Avaliador")
    rating = models.DecimalField(
        max_digits=2,
        decimal_places=1,
        validators=[MinValueValidator(0.5), MaxValueValidator(5.0)],
        verbose_name="Nota"
    )
    comment = models.TextField(blank=True, verbose_name="Comentário")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")

    class Meta:
        verbose_name = "Avaliação"
        verbose_name_plural = "Avaliações"
        unique_together = ('seller', 'reviewer')

    def __str__(self):
        return f"{self.reviewer.username} → {self.seller.username}: {self.rating}"