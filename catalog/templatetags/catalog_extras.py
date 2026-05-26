from django import template

register = template.Library()

@register.filter
def brl(value):
    try:
        return f"{float(value):,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    except (TypeError, ValueError):
        return value