from .services import awaiting_count

def trade_count(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or user.is_staff:
        return {}
    return {'trade_count': awaiting_count(user)}
