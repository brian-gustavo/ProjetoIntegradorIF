from django import template

register = template.Library()

@register.filter
def coins(value):
    try:
        return f"{int(value):,}".replace(',', '.')
    except (TypeError, ValueError):
        return value

@register.simple_tag
def review_reward():
    from orders.models import PlatformConfig
    return PlatformConfig.load().coins_review_reward

@register.filter
def signed_coins(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return value
    return f"{'+' if value > 0 else '−'}{coins(abs(value))}"