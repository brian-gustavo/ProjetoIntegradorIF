from django.template import TemplateDoesNotExist
from django.template.loader import get_template

MANUAL_ALIASES = {
    'edit_coupon': 'create_coupon',
    'edit_seller_review': 'review_seller',
    'edit_product_review': 'review_product',
    'contest_decision': 'open_dispute',
    'counter_trade': 'propose_trade',
    'create_expense': 'admin_dashboard',
    'edit_expense': 'admin_dashboard',
}

def manual(request):
    match = request.resolver_match
    if not match or not match.url_name:
        return {}

    nome = MANUAL_ALIASES.get(match.url_name, match.url_name)
    caminho = f'manual/{nome}.html'
    try:
        get_template(caminho)
    except TemplateDoesNotExist:
        return {}
    return {'manual_template': caminho}