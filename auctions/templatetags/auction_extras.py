from datetime import timedelta
from django import template
from django.utils import timezone

from auctions.services import mask_username

register = template.Library()

@register.filter
def time_left(fim):
    restante = int((fim - timezone.now()).total_seconds())
    if restante <= 0:
        return 'Encerrado'
    dias, resto = divmod(restante, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)
    if dias:
        return f'{dias}d {horas}h'
    if horas:
        return f'{horas}h {minutos}min'
    if minutos:
        return f'{minutos}min {segundos}s'
    return f'{segundos}s'

@register.filter
def ends_soon(fim):
    return fim - timezone.now() < timedelta(days=1)

@register.filter
def masked(user):
    return mask_username(user.username) if user else 'usuário removido'