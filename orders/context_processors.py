from django.db.models import Sum

from .models import CartItem

def cart_count(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_staff:
        return {}
    total = CartItem.objects.filter(cart__user=user).aggregate(total=Sum('quantity'))['total']
    return {'cart_count': total or 0}