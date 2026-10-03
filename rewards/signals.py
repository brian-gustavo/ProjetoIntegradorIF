from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import SellerReview
from catalog.models import ProductReview
from .services import credit_review

@receiver(post_save, sender=ProductReview)
def reward_product_review(sender, instance, created, **kwargs):
    if created:
        credit_review(instance.reviewer, f'produto:{instance.product_id}', f'Avaliação · {instance.product.title}')

@receiver(post_save, sender=SellerReview)
def reward_seller_review(sender, instance, created, **kwargs):
    if created:
        credit_review(instance.reviewer, f'vendedor:{instance.seller_id}', f'Avaliação do vendedor {instance.seller.username}')