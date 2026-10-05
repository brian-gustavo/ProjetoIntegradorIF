from datetime import timedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from . import services
from .forms import AuctionForm
from .models import Auction, Bid, SecondChanceOffer
from catalog.models import Product, ProductImage
from catalog.templatetags.catalog_extras import brl
from catalog.views import _annotate_products, _apply_sort, _build_filter_context

MAX_IMAGES = 5
MAX_IMAGE_SIZE = 10 * 1024 * 1024

AUCTION_SORT_OPTIONS = {
    'terminando': ('Terminando primeiro', ('auction__ends_at',)),
    'recentes': ('Recém-anunciados', ('-auction__starts_at',)),
    'menor_preco': ('Menor lance', ('min_price', 'auction__ends_at')),
    'maior_preco': ('Maior lance', ('-min_price', 'auction__ends_at')),
    'mais_lances': ('Mais lances', ('-auction__bid_count', 'auction__ends_at')),
}

def _image_error(existentes, imagens):
    if existentes + len(imagens) > MAX_IMAGES:
        return f'Limite de imagens ultrapassado. Insira no máximo {MAX_IMAGES} e tente novamente.'
    grandes = [img.name for img in imagens if img.size > MAX_IMAGE_SIZE]
    if grandes:
        return f'As seguintes imagens excedem o limite de 10MB: {", ".join(grandes)}'
    return None

def _product_url(product_id, ancora=''):
    return reverse('product_detail', args=[product_id]) + ancora

def _next_or_product(request, product_id):
    destino = request.POST.get('next', '')
    if url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return destino
    return _product_url(product_id)

def auction_list(request):
    services.close_expired_auctions()
    base_qs = _annotate_products(
        Product.objects.filter(published=True, deleted=False, auction__status='ACTIVE')
    ).select_related('seller__profile', 'auction').prefetch_related('images', 'variants')

    produtos_qs, filtros = _build_filter_context(request, base_qs)
    produtos_qs, ordenacao = _apply_sort(request, produtos_qs, AUCTION_SORT_OPTIONS, 'terminando')

    return render(request, 'auctions/auction_list.html', {
        'produtos': Paginator(produtos_qs, 24).get_page(request.GET.get('page')),
        'filtros': filtros,
        'ordenacao': ordenacao,
    })

@login_required
def setup_auction(request, product_id):
    product = get_object_or_404(Product, pk=product_id, seller=request.user, deleted=False)
    if product.variants.exists():
        return redirect('edit_product', product_id=product.pk)

    image_error = None
    if request.method == 'POST':
        form = AuctionForm(request.POST)
        images = request.FILES.getlist('images')
        image_error = _image_error(product.images.count(), images)
        if form.is_valid() and not image_error:
            for image in images:
                ProductImage.objects.create(product=product, image=image)
            auction = services.publish(product, form.save(commit=False))
            messages.success(request, f'Leilão publicado! Ele termina em {auction.ends_at:%d/%m/%Y} às {auction.ends_at:%H:%M}.')
            return redirect('product_detail', product_id=product.pk)
    else:
        form = AuctionForm()

    return render(request, 'auctions/setup_auction.html', {
        'product': product,
        'form': form,
        'image_error': image_error,
        'increments': services.increment_table(),
    })

@login_required
def place_bid(request, product_id):
    auction = get_object_or_404(Auction, product_id=product_id, product__deleted=False)
    if request.method != 'POST':
        return redirect('product_detail', product_id=product_id)

    resultado, erro = services.place_bid(auction.pk, request.user, services.parse_amount(request.POST.get('amount')))
    if erro:
        messages.error(request, erro)
    elif resultado['lider'] and resultado['aumentou']:
        messages.success(request, f'Seu lance máximo foi atualizado. O lance atual segue em R$ {brl(resultado["preco"])}.')
    elif resultado['lider']:
        auction.refresh_from_db()
        aviso = '' if auction.reserve_met else ', mas o preço de reserva ainda não foi atingido'
        messages.success(request, f'Você é o maior lance{aviso}! Lance atual: R$ {brl(resultado["preco"])}.')
    else:
        messages.warning(request, f'Você foi superado pelo lance automático de outro participante. O lance atual subiu para R$ {brl(resultado["preco"])}. Tente um valor maior.')

    return redirect(_product_url(product_id, '#leilao'))

@login_required
def buy_now(request, product_id):
    auction = get_object_or_404(Auction, product_id=product_id, product__deleted=False)
    if request.method != 'POST':
        return redirect('product_detail', product_id=product_id)

    order, erro = services.buy_now(auction.pk, request.user)
    if erro:
        messages.error(request, erro)
        return redirect('product_detail', product_id=product_id)

    messages.success(request, 'Compra confirmada! Conclua o pagamento para que o vendedor envie o item.')
    return redirect('resume_payment', order_id=order.pk)

@login_required
def toggle_watch(request, product_id):
    auction = get_object_or_404(Auction, product_id=product_id, product__deleted=False)

    if request.method == 'POST' and not request.user.is_staff and auction.product.seller_id != request.user.pk:
        if services.toggle_watch(auction, request.user):
            messages.success(request, f'"{auction.product.title}" adicionado aos leilões que você acompanha')
        else:
            messages.success(request, f'Você deixou de acompanhar "{auction.product.title}"')

    return redirect(_next_or_product(request, product_id))

def bid_history(request, product_id):
    services.close_expired_auctions()
    auction = get_object_or_404(
        Auction.objects.select_related('product__seller', 'winner'), product_id=product_id, product__deleted=False
    )
    viewer = request.user if request.user.is_authenticated else None
    historico, retirados = services.bid_history(auction, viewer)

    return render(request, 'auctions/bid_history.html', {
        'auction': auction,
        'product': auction.product,
        'historico': historico,
        'retirados': retirados,
        'bidders': services.bidder_count(auction),
        'increments': services.increment_table(),
    })

@login_required
def my_bids(request):
    if request.user.is_staff:
        return redirect('auction_list')

    services.close_expired_auctions()
    dados = services.my_bids(request.user)
    abas = [
        ('ativos', 'Em andamento'),
        ('vencidos', 'Arrematados'),
        ('perdidos', 'Não arrematados'),
        ('acompanhando', 'Acompanhando'),
        ('ofertas', 'Ofertas de segunda chance'),
    ]
    aba = request.GET.get('aba')
    if aba not in dict(abas):
        aba = 'ativos'

    return render(request, 'auctions/my_bids.html', {
        'aba': aba,
        'abas': [{'chave': chave, 'titulo': titulo, 'total': len(dados[chave])} for chave, titulo in abas],
        'leiloes': dados[aba],
    })

def _seller_auction(request, product_id):
    return get_object_or_404(
        Auction.objects.select_related('product', 'order', 'leader'), product_id=product_id, product__seller=request.user
    )

@login_required
def end_auction(request, product_id):
    auction = _seller_auction(request, product_id)
    if request.method == 'POST':
        auction, erro = services.end_early(auction.pk, request.user)
        if erro:
            messages.error(request, erro)
        elif auction.status == 'SOLD':
            messages.success(request, f'Leilão encerrado. O item foi vendido ao maior lance por R$ {brl(auction.current_price)}.')
        else:
            messages.success(request, 'Leilão encerrado sem venda.')
    return redirect(_next_or_product(request, product_id))

@login_required
def cancel_unpaid(request, product_id):
    auction = _seller_auction(request, product_id)
    if request.method == 'POST':
        erro = services.cancel_unpaid(auction)
        if erro:
            messages.error(request, erro)
        else:
            messages.success(request, 'Venda cancelada por falta de pagamento. Você já pode relistar o item.')
    return redirect(_next_or_product(request, product_id))

@login_required
def relist_auction(request, product_id):
    auction = _seller_auction(request, product_id)
    if request.method != 'POST':
        return redirect('product_detail', product_id=product_id)

    if not services.can_relist(auction):
        messages.error(request, 'Este leilão não pode ser relistado.')
        return redirect(_next_or_product(request, product_id))

    novo = services.relist(auction)
    messages.success(request, 'Leilão relistado com as mesmas condições. Se quiser, ajuste os valores antes do primeiro lance.')
    return redirect('edit_product', product_id=novo.pk)

@login_required
def retract_bid(request, product_id):
    auction = get_object_or_404(Auction.objects.select_related('product'), product_id=product_id, product__deleted=False)
    lances = services.retractable_bids(auction, request.user)
    if not lances:
        messages.error(request, 'Você não tem lances que possam ser retirados neste leilão.')
        return redirect('product_detail', product_id=product_id)

    erro = None
    if request.method == 'POST':
        resultado, erro = services.retract_bids(auction.pk, request.user, request.POST.get('motivo'))
        if not erro:
            texto = 'Lance retirado' if resultado['quantidade'] == 1 else f'{resultado["quantidade"]} lances retirados'
            messages.success(request, f'{texto}. O lance atual foi recalculado para R$ {brl(resultado["preco"])}.')
            if request.POST.get('motivo') == 'TYPO':
                messages.info(request, 'Como o valor foi digitado errado, dê um novo lance com o valor correto.')
            return redirect(_product_url(product_id, '#leilao'))

    return render(request, 'auctions/retract_bid.html', {
        'auction': auction,
        'product': auction.product,
        'lances': lances,
        'todos': auction.ends_at - timezone.now() >= timedelta(hours=services.LATE_RETRACTION_HOURS),
        'motivos': Bid.RETRACTION_CHOICES,
        'motivo': request.POST.get('motivo', ''),
        'erro': erro,
        'late_hours': services.LATE_RETRACTION_HOURS,
    })

@login_required
def second_chance(request, product_id):
    auction = _seller_auction(request, product_id)
    erro = services.second_chance_blocker(auction)
    candidatos = [] if erro else services.second_chance_candidates(auction)

    if request.method == 'POST' and not erro:
        try:
            bidder_id, duracao = int(request.POST.get('bidder')), int(request.POST.get('duration_days'))
        except (TypeError, ValueError):
            bidder_id = duracao = None
        offer, erro_envio = services.send_second_chance(auction.pk, request.user, bidder_id, duracao)
        if offer:
            messages.success(request, f'Oferta de R$ {brl(offer.price)} enviada para {offer.bidder.username}. Ela vale até {timezone.localtime(offer.expires_at):%d/%m às %H:%M}.')
            return redirect('second_chance', product_id=product_id)
        messages.error(request, erro_envio)

    return render(request, 'auctions/second_chance.html', {
        'auction': auction,
        'product': auction.product,
        'erro': erro,
        'candidatos': candidatos,
        'duracoes': SecondChanceOffer.DURATION_CHOICES,
        'ofertas': auction.second_chance_offers.select_related('bidder', 'order'),
        'window_days': services.second_chance_window_days(),
    })

@login_required
def respond_offer(request, offer_id):
    offer = get_object_or_404(SecondChanceOffer.objects.select_related('auction'), pk=offer_id, bidder=request.user)
    if request.method != 'POST':
        return redirect('product_detail', product_id=offer.auction.product_id)

    aceitar = request.POST.get('acao') == 'aceitar'
    resultado, erro = services.respond_second_chance(offer.pk, request.user, aceitar)
    if erro:
        messages.error(request, erro)
    elif aceitar:
        messages.success(request, 'Oferta aceita! Conclua o pagamento para que o vendedor envie o item.')
        return redirect('resume_payment', order_id=resultado.order_id)
    else:
        messages.success(request, 'Oferta recusada.')
    return redirect(_next_or_product(request, offer.auction.product_id))