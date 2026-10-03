from .services import balance

def coin_balance(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_staff:
        return {}
    return {'coin_balance': balance(user)}