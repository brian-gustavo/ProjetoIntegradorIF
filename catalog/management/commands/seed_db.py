import random
from datetime import timedelta
from decimal import Decimal, ROUND_DOWN
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import SellerReview
from auctions.models import Auction, AuctionWatch, Bid
from auctions.services import (
    apply_bid, close_auction, increment_for, minimum_bid, publish as publish_auction, respond_second_chance,
    retract_bids, second_chance_candidates, send_second_chance,
)
from catalog.models import Category, Product, ProductVariant, ProductReview
from coupons.models import Coupon, CouponRedemption
from orders.models import Order, Cart, CartItem, PlatformConfig, Commission, Dispute, DisputeMessage, ReturnRequest, commission_for, generate_tracking_code
from trades.models import OWNER, PROPOSER, TradeEvent, TradeProposal
from trades.services import (
    accept as accept_trade, counter as counter_trade, decline as decline_trade, expire_trades, propose as propose_trade,
    target_variants, tradeable_variants, withdraw as withdraw_trade,
)

CATEGORIES = [
    ('Consoles', 'consoles'),
    ('Games', 'games'),
    ('Periféricos', 'perifericos'),
    ('Keys', 'keys'),
    ('Jogos de Tabuleiro', 'jogos-de-tabuleiro'),
    ('Itens In-game', 'itens-in-game'),
    ('Action Figures', 'action-figures'),
    ('Bottons', 'bottons'),
    ('Pôsteres', 'posteres'),
]

FRANCHISES = [
    'Reino Sombrio', 'Corrida Fantasma', 'Guardiões do Vazio', 'Império Estelar',
    'Lenda de Aurora', 'Caçadores de Sombra', 'Terra Partida', 'Última Fronteira',
    'Névoa Eterna', 'Fúria de Ferro', 'Crônicas de Valen', 'Horizonte Quebrado',
    'Trono de Cinzas', 'Ilha Perdida', 'Deuses de Neon', 'Ecos do Abismo',
]

CONSOLE_MODELS = ['PlayStation 5', 'Xbox Series X', 'Nintendo Switch', 'Steam Deck']
CONSOLE_VARIANTS = ['Padrão', '1TB', '2TB']
PLATFORM_VARIANTS = ['PS5', 'PS4', 'Xbox Series X', 'Xbox One', 'Nintendo Switch', 'PC']
KEY_STORES = ['Steam', 'PlayStation Store', 'Xbox Store', 'Nintendo eShop', 'Epic Games']
PERIPHERAL_ITEMS = ['Controle', 'Headset', 'Mouse Gamer', 'Teclado Mecânico', 'Volante']
INGAME_ITEMS = ['Moeda Premium', 'Pacote de Skins', 'Passe de Batalha', 'Pacote de Gemas']
INGAME_VARIANTS = ['100 unidades', '500 unidades', '1000 unidades']
COLLECTIBLE_VARIANTS = ['Padrão', 'Edição Especial', 'Edição de Colecionador']
PERIPHERAL_MODELS = [
    'Viper', 'Titan', 'Vortex', 'Phantom', 'Nova', 'Raptor', 'Spectra', 'Apex',
    'Blaze', 'Orion', 'Falcon', 'Storm', 'Pulse', 'Striker', 'Nebula', 'Fusion',
]

CITIES = [
    ('São Paulo', 'SP'), ('Campinas', 'SP'), ('Ribeirão Preto', 'SP'), ('Sorocaba', 'SP'),
    ('São José dos Campos', 'SP'), ('Rio de Janeiro', 'RJ'), ('Niterói', 'RJ'), ('Petrópolis', 'RJ'),
    ('Belo Horizonte', 'MG'), ('Uberlândia', 'MG'), ('Juiz de Fora', 'MG'), ('Vitória', 'ES'),
    ('Vila Velha', 'ES'), ('Curitiba', 'PR'), ('Londrina', 'PR'), ('Maringá', 'PR'),
    ('Florianópolis', 'SC'), ('Joinville', 'SC'), ('Blumenau', 'SC'), ('Porto Alegre', 'RS'),
    ('Caxias do Sul', 'RS'), ('Pelotas', 'RS'), ('Brasília', 'DF'), ('Goiânia', 'GO'),
    ('Anápolis', 'GO'), ('Campo Grande', 'MS'), ('Cuiabá', 'MT'), ('Salvador', 'BA'),
    ('Feira de Santana', 'BA'), ('Recife', 'PE'), ('Caruaru', 'PE'), ('Fortaleza', 'CE'),
    ('Natal', 'RN'), ('João Pessoa', 'PB'), ('Campina Grande', 'PB'), ('Maceió', 'AL'),
    ('Aracaju', 'SE'), ('Teresina', 'PI'), ('São Luís', 'MA'), ('Belém', 'PA'),
    ('Manaus', 'AM'), ('Porto Velho', 'RO'), ('Palmas', 'TO'), ('Macapá', 'AP'),
    ('Boa Vista', 'RR'), ('Rio Branco', 'AC'),
]

DESCRIPTION_SENTENCES = [
    'Produto conferido e testado antes do envio.',
    'Enviado com embalagem reforçada para evitar danos no transporte.',
    'Acompanha todos os itens mostrados nas fotos do anúncio.',
    'Qualquer dúvida, é só mandar mensagem que respondo rapidinho.',
    'Postagem em até dois dias úteis após a confirmação do pagamento.',
    'Item guardado com cuidado, longe de umidade e luz direta.',
    'Ótima opção para quem quer completar a coleção.',
    'Envio para todo o Brasil com código de rastreio.',
    'Funciona perfeitamente, sem nenhum defeito conhecido.',
    'Vendo porque não uso mais, está em ótimo estado.',
    'Aceito retirada em mãos quando disponível no anúncio.',
    'Nota fiscal disponível mediante solicitação.',
]

POSITIVE_COMMENTS = [
    'Chegou rápido e muito bem embalado. Recomendo!',
    'Exatamente como descrito no anúncio.',
    'Vendedor atencioso, respondeu todas as dúvidas.',
    'Excelente compra, superou as expectativas.',
    'Tudo certo, compraria novamente.',
    'Produto em ótimo estado, valeu cada centavo.',
]
NEUTRAL_COMMENTS = [
    'Produto ok, mas a entrega demorou um pouco.',
    'Atendeu ao esperado, nada de especial.',
    'Embalagem poderia ser melhor, mas o item chegou inteiro.',
    'Bom custo-benefício, apesar de alguns detalhes.',
]
NEGATIVE_COMMENTS = [
    'Demorou muito para ser enviado.',
    'O produto não estava no estado descrito.',
    'Vendedor demorou a responder as mensagens.',
    'Chegou com a caixa danificada.',
]

RESOLUTION_NOTES = [
    'Analisadas as evidências enviadas por ambas as partes.',
    'Decisão tomada com base no histórico de mensagens e no rastreio do pedido.',
    'As fotos apresentadas comprovam a alegação.',
    'Não foram apresentadas evidências suficientes para a alegação.',
    'Caso encerrado após análise da equipe de mediação.',
]

def comment_for(rating):
    if random.random() >= 0.7:
        return ''
    if rating >= 4:
        return random.choice(POSITIVE_COMMENTS)
    if rating >= 2.5:
        return random.choice(NEUTRAL_COMMENTS)
    return random.choice(NEGATIVE_COMMENTS)

STATUS_WEIGHTS = [
    ('PENDING', 8), ('PAID', 8), ('CONFIRMED', 5), ('PREPARING', 5),
    ('SHIPPED', 6), ('READY_PICKUP', 3), ('DELIVERED', 10), ('RETURN_WINDOW', 6),
    ('RETURN_REQUESTED', 3), ('RETURN_ACCEPTED', 2), ('RETURNED', 3),
    ('CANCELLED_NO_RETURN', 2), ('COMPLETED', 25), ('CANCELLED', 6),
]

STOCK_DECREMENTED_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'DISPUTE_OPEN', 'RETURN_ACCEPTED',
    'CANCELLED_NO_RETURN', 'COMPLETED',
}
HAS_COMMISSION_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'DISPUTE_OPEN', 'RETURN_ACCEPTED', 'COMPLETED',
}
CAN_REVIEW_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'DISPUTE_OPEN', 'RETURN_ACCEPTED',
    'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED',
}
TRACKING_ELIGIBLE_STATUSES = {
    'SHIPPED', 'READY_PICKUP', 'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'DISPUTE_OPEN',
    'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED',
}

DISPUTE_CHANCES = {
    'RETURN_REQUESTED': ('OPEN', 0.35),
    'RETURN_ACCEPTED': ('RESOLVED_BUYER_RETURN', 0.3),
    'CANCELLED_NO_RETURN': ('RESOLVED_BUYER_REFUND', 0.35),
    'COMPLETED': ('RESOLVED_SELLER', 0.03),
}
RETURN_FLOW_STATUSES = {'RETURN_REQUESTED', 'DISPUTE_OPEN', 'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN'}
RETURN_REASONS = {
    'Produto com defeito': [
        'O produto apresentou defeito logo nos primeiros dias de uso.',
        'O item liga, mas para de funcionar depois de alguns minutos.',
    ],
    'Produto diferente do anunciado': [
        'Recebi uma edição diferente da que estava no anúncio.',
        'O estado de conservação não corresponde às fotos do anúncio.',
    ],
    'Produto incompleto': [
        'Faltaram acessórios que estavam listados no anúncio.',
        'A caixa veio sem o manual e sem um dos itens do kit.',
    ],
    'Key ou código digital inválido': [
        'A key informa que já foi resgatada em outra conta.',
        'O código não é aceito pela loja da plataforma.',
    ],
    'Produto chegou danificado': [
        'A embalagem chegou amassada e o item tem marcas de impacto.',
        'O produto chegou com partes quebradas por causa do transporte.',
    ],
    'Desisti da compra': [
        'Comprei por engano e gostaria de devolver o item ainda lacrado.',
    ],
    'Outro': [
        'O produto não atendeu ao que eu esperava e gostaria de devolvê-lo.',
    ],
}
BUYER_ESCALATION_TEXTS = [
    'O vendedor não respondeu à solicitação de devolução dentro do prazo.',
    'Tentei resolver diretamente com o vendedor, mas ele não deu retorno.',
    'O vendedor visualizou a solicitação, mas não aceitou nem recusou a devolução.',
]
SELLER_DISPUTE_REASONS = [
    ('Produto devolvido com avarias', 'O comprador quer devolver o produto com avarias que não existiam no envio.'),
    ('Devolução sem justificativa', 'A devolução foi solicitada sem nenhum defeito aparente no item.'),
    ('Produto não recebido', 'O comprador alega não ter recebido, mas o rastreio consta como entregue.'),
]
DISPUTE_REPLIES = [
    'Enviei fotos do produto no momento do envio, estava em perfeito estado.',
    'Posso mandar fotos do item como chegou, se for necessário.',
    'Aguardo uma posição da equipe do MegaGame.',
    'Tentei resolver diretamente, mas não houve acordo.',
    'Concordo em receber o produto de volta se ele estiver lacrado.',
]
RECENT_STATUSES = {'PENDING', 'PAID', 'CONFIRMED', 'PREPARING', 'SHIPPED', 'READY_PICKUP'}
MID_STATUSES = {'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED', 'CANCELLED_NO_RETURN'}

CATEGORY_WEIGHTS = [14, 30, 14, 12, 8, 8, 6, 4, 4]

STATUS_BY_AGE = [
    (2, [('PENDING', 30), ('PAID', 30), ('CONFIRMED', 15), ('PREPARING', 10), ('CANCELLED', 15)]),
    (7, [('PAID', 5), ('CONFIRMED', 10), ('PREPARING', 20), ('SHIPPED', 35), ('READY_PICKUP', 10), ('CANCELLED', 20)]),
    (20, [('SHIPPED', 15), ('READY_PICKUP', 5), ('DELIVERED', 35), ('RETURN_WINDOW', 15), ('RETURN_REQUESTED', 12), ('CANCELLED', 10), ('COMPLETED', 15)]),
    (60, [('DELIVERED', 10), ('RETURN_WINDOW', 10), ('RETURN_REQUESTED', 4), ('RETURN_ACCEPTED', 4), ('CANCELLED_NO_RETURN', 4), ('RETURNED', 6), ('COMPLETED', 55), ('CANCELLED', 7)]),
    (None, [('COMPLETED', 78), ('RETURNED', 8), ('CANCELLED', 8), ('CANCELLED_NO_RETURN', 6)]),
]

def status_for_age(age_days):
    for limit, options in STATUS_BY_AGE:
        if limit is None or age_days < limit:
            statuses, weights = zip(*options)
            return random.choices(statuses, weights=weights)[0]

def random_between(start, end):
    if end <= start:
        return start
    return start + (end - start) * random.random()

PLATFORM_COUPONS = [
    {'code': 'BEMVINDO', 'kind': 'PERCENT', 'value': 10, 'max_discount': 30, 'first_purchase_only': True},
    {'code': 'MEGA5', 'kind': 'PERCENT', 'value': 5, 'max_discount': 25, 'min_order_value': 100},
    {'code': 'MEGA15', 'kind': 'FIXED', 'value': 15, 'min_order_value': 150},
    {'code': 'CONSOLES10', 'kind': 'PERCENT', 'value': 10, 'max_discount': 100, 'category': 'consoles'},
    {'code': 'KEYS8', 'kind': 'PERCENT', 'value': 8, 'category': 'keys', 'usage_limit': 300},
    {'code': 'VIP20', 'kind': 'FIXED', 'value': 20, 'min_order_value': 200, 'is_public': False},
    {'code': 'BLACKFRIDAY', 'kind': 'PERCENT', 'value': 10, 'max_discount': 50, 'starts_days_ago': 330, 'ends_days_ago': 300},
]

SELLER_COUPON_TEMPLATES = [
    {'kind': 'PERCENT', 'value': 5},
    {'kind': 'PERCENT', 'value': 10, 'max_discount': 40, 'min_order_value': 100},
    {'kind': 'PERCENT', 'value': 15, 'max_discount': 30, 'min_order_value': 150, 'usage_limit': 50},
    {'kind': 'FIXED', 'value': 10, 'min_order_value': 80},
    {'kind': 'FIXED', 'value': 25, 'min_order_value': 200},
    {'kind': 'PERCENT', 'value': 10, 'max_discount': 20, 'first_purchase_only': True},
]
COUPON_USE_CHANCE = 0.25

AUCTION_ENDED_SHARE = 0.25
AUCTION_DURATIONS = [1, 3, 5, 7, 7, 7, 10]

TRADE_LISTING_SHARE = 0.25
TRADE_PREFERENCES = [
    'Jogos de PS5 ou Xbox Series', 'Jogos de Switch', 'Controles originais', 'Action figures em bom estado',
    'Consoles retrô', 'Periféricos para PC', '', '', '',
]
TRADE_MESSAGES = [
    'Os itens estão completos, com caixa e manual.', 'Posso enviar fotos extras se quiser.',
    'Topa fechar assim?', 'Tenho interesse faz tempo nesse item!', '', '', '',
]
DECLINE_MESSAGES = ['Já troquei esse item, foi mal.', 'Prefiro vender por enquanto.', 'Não tenho interesse nesses itens.', '']
TRADE_OUTCOMES = [('pendente', 25), ('contraproposta', 15), ('aceita', 30), ('recusada', 15), ('expirada', 10), ('retirada', 5)]

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--sellers', type=int, default=25)
        parser.add_argument('--buyers', type=int, default=60)
        parser.add_argument('--products', type=int, default=250)
        parser.add_argument('--orders', type=int, default=400)
        parser.add_argument('--auctions', type=int, default=30)
        parser.add_argument('--trades', type=int, default=40)
        parser.add_argument('--days', type=int, default=365)
        parser.add_argument('--flush', action='store_true')

    def handle(self, *args, **options):
        if options['flush']:
            self._flush()

        self._reviewed_products = set()
        self._reviewed_sellers = set()
        self._now = timezone.now()
        self._span_start = self._now - timedelta(days=options['days'])
        sellers_latest = self._span_start + (self._now - self._span_start) * 0.5
        buyers_latest = self._now - timedelta(days=2)

        with transaction.atomic():
            PlatformConfig.objects.get_or_create(pk=1, defaults={'commission_rate': Decimal('10.00')})
            categories = self._seed_categories()
            sellers = self._seed_users('vendedor', options['sellers'], sellers_latest)
            buyers = self._seed_users('comprador', options['buyers'], buyers_latest)
            products = self._seed_products(categories, sellers, options['products'])
            self._seed_coupons(categories, sellers)
            self._seed_orders(products, buyers, options['orders'])
            self._seed_carts(products, buyers)
            auctions = self._seed_auctions(categories, sellers, buyers, options['auctions'])
            trades = self._seed_trades(products, sellers, options['trades'])

        self.stdout.write(self.style.SUCCESS(
            f"Banco povoado: {len(sellers)} vendedores, {len(buyers)} compradores, "
            f"{len(products)} produtos, {auctions} leilões, {trades} propostas de troca."
        ))

    def _flush(self):
        Order.objects.all().delete()
        Cart.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        User.objects.filter(is_staff=False).delete()
        self.stdout.write('Dados fictícios anteriores removidos.')

    def _seed_categories(self):
        categories = []
        for name, slug in CATEGORIES:
            category, _ = Category.objects.get_or_create(slug=slug, defaults={'name': name})
            categories.append(category)
        return categories

    def _seed_users(self, prefix, count, latest_join):
        hashed_password = make_password('senha123')
        users = []
        for i in range(count):
            username = f'{prefix}{i + 1}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@teste.com', 'password': hashed_password},
            )
            if created:
                joined = random_between(self._span_start, latest_join)
                User.objects.filter(pk=user.pk).update(date_joined=joined)
                user.date_joined = joined
            user.profile.city, user.profile.uf = random.choice(CITIES)
            user.profile.save()
            users.append(user)
        return users

    def _generate_title(self, category):
        if category.slug == 'games':
            franchise = random.choice(FRANCHISES)
            suffix = random.choice(['', ' II', ' III', ': Renascimento', ': A Queda', ': Origens'])
            return f'{franchise}{suffix}', PLATFORM_VARIANTS
        if category.slug == 'consoles':
            return f'Console {random.choice(CONSOLE_MODELS)}', CONSOLE_VARIANTS
        if category.slug == 'perifericos':
            item = random.choice(PERIPHERAL_ITEMS)
            return f'{item} {random.choice(PERIPHERAL_MODELS)} Pro', ['Padrão', 'Edição RGB']
        if category.slug == 'keys':
            franchise = random.choice(FRANCHISES)
            return f'{franchise} (Key Digital)', KEY_STORES
        if category.slug == 'jogos-de-tabuleiro':
            return f'{random.choice(FRANCHISES)} - Jogo de Tabuleiro', ['Padrão']
        if category.slug == 'itens-in-game':
            item = random.choice(INGAME_ITEMS)
            return f'{item} — {random.choice(FRANCHISES)}', INGAME_VARIANTS

        kind = {'action-figures': 'Action Figure', 'bottons': 'Kit de Bottons', 'posteres': 'Pôster'}[category.slug]
        return f'{kind} — {random.choice(FRANCHISES)}', COLLECTIBLE_VARIANTS

    def _seed_products(self, categories, sellers, count):
        self.stdout.write('Gerando produtos...')
        products = []
        seller_weights = [random.lognormvariate(0, 1) for _ in sellers]

        for _ in range(count):
            category = random.choices(categories, weights=CATEGORY_WEIGHTS)[0]
            seller = random.choices(sellers, weights=seller_weights)[0]
            title, variant_pool = self._generate_title(category)
            is_draft = random.random() < 0.05
            accepts_trade = not is_draft and random.random() < TRADE_LISTING_SHARE

            product = Product(
                category=category,
                seller=seller,
                title=title,
                description=' '.join(random.sample(DESCRIPTION_SENTENCES, 4)),
                condition=random.choices(['NEW', 'USED'], weights=[7, 3])[0],
                accepts_pickup=random.random() < 0.3,
                accepts_trade=accepts_trade,
                trade_preferences=random.choice(TRADE_PREFERENCES) if accepts_trade else '',
                published=not is_draft and random.random() < 0.9,
                deleted=False,
            )
            product.seed_date = random_between(seller.date_joined, self._now - timedelta(days=1))
            product.seed_weight = random.lognormvariate(0, 1)
            product.seed_variant_names = [] if is_draft else random.sample(
                variant_pool, random.randint(1, min(4, len(variant_pool)))
            )
            products.append(product)

        Product.objects.bulk_create(products, batch_size=500)
        for product in products:
            product.created_at = product.seed_date
            product.updated_at = product.seed_date
        Product.objects.bulk_update(products, ['created_at', 'updated_at'], batch_size=500)

        variants = []
        for product in products:
            product.seed_variants = [
                ProductVariant(
                    product=product,
                    name=name,
                    price=Decimal(random.randrange(2000, 45000)) / 100,
                    quantity=random.randint(0, 30),
                )
                for name in product.seed_variant_names
            ]
            variants.extend(product.seed_variants)
        ProductVariant.objects.bulk_create(variants, batch_size=500)

        return products

    def _seed_coupons(self, categories, sellers):
        self.stdout.write('Gerando cupons...')
        por_slug = {c.slug: c for c in categories}
        self._coupons = []
        self._coupon_uses = []
        self._coupon_counts = {}

        for modelo in PLATFORM_COUPONS:
            dados = dict(modelo)
            code = dados.pop('code')
            starts = self._now - timedelta(days=dados.pop('starts_days_ago')) if 'starts_days_ago' in dados else self._span_start
            ends = self._now - timedelta(days=dados.pop('ends_days_ago')) if 'ends_days_ago' in dados else self._now + timedelta(days=random.randint(15, 90))
            category = por_slug.get(dados.pop('category', None))
            coupon, _ = Coupon.objects.update_or_create(code=code, defaults={
                **self._coupon_values(dados), 'seller': None, 'category': category,
                'starts_at': starts, 'ends_at': ends, 'active': True,
            })
            self._coupons.append(coupon)

        for seller in random.sample(sellers, k=len(sellers) // 2):
            for modelo in random.sample(SELLER_COUPON_TEMPLATES, k=random.randint(1, 2)):
                dados = dict(modelo)
                if dados.get('first_purchase_only'):
                    sufixo = 'NOVO'
                else:
                    sufixo = f"{dados['value']}{'OFF' if dados['kind'] == 'PERCENT' else 'REAIS'}"

                sorteio = random.random()
                if sorteio < 0.1:
                    ends = self._now - timedelta(days=random.randint(5, 40))
                elif sorteio < 0.4:
                    ends = self._now + timedelta(days=random.randint(10, 60))
                else:
                    ends = None

                coupon, _ = Coupon.objects.update_or_create(code=f'{seller.username.upper()}{sufixo}', defaults={
                    **self._coupon_values(dados), 'seller': seller,
                    'starts_at': random_between(seller.date_joined, self._now - timedelta(days=60)),
                    'ends_at': ends, 'active': random.random() > 0.1,
                })
                self._coupons.append(coupon)

    def _coupon_values(self, dados):
        return {
            'kind': dados['kind'],
            'value': Decimal(str(dados['value'])),
            'max_discount': Decimal(str(dados['max_discount'])) if dados.get('max_discount') else None,
            'min_order_value': Decimal(str(dados.get('min_order_value', 0))),
            'first_purchase_only': dados.get('first_purchase_only', False),
            'is_public': dados.get('is_public', True),
            'usage_limit': dados.get('usage_limit'),
        }

    def _coupon_fits(self, coupon, product, base, created_at):
        return (
            not coupon.first_purchase_only
            and coupon.starts_at <= created_at
            and (coupon.ends_at is None or created_at < coupon.ends_at)
            and (coupon.category_id is None or coupon.category_id == product.category_id)
            and base >= coupon.min_order_value
            and (coupon.usage_limit is None or self._coupon_counts.get(coupon.pk, 0) < coupon.usage_limit)
        )

    def _maybe_use_coupons(self, order, created_at, commission_rate):
        if random.random() >= COUPON_USE_CHANCE:
            return

        da_loja = [
            c for c in self._coupons
            if c.seller_id == order.product.seller_id and self._coupon_fits(c, order.product, order.total_price, created_at)
        ]
        if da_loja and random.random() < 0.6:
            coupon = random.choice(da_loja)
            order.seller_coupon_discount = coupon.discount_for(order.total_price)
            self._coupon_uses.append((order, coupon, 'seller_coupon', created_at))
            self._coupon_counts[coupon.pk] = self._coupon_counts.get(coupon.pk, 0) + 1

        base = order.sale_amount
        da_plataforma = [c for c in self._coupons if c.is_platform and self._coupon_fits(c, order.product, base, created_at)]
        if da_plataforma and random.random() < 0.6:
            coupon = random.choice(da_plataforma)
            teto = (base * commission_rate / Decimal('100')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
            order.platform_coupon_discount = min(coupon.discount_for(base), teto)
            self._coupon_uses.append((order, coupon, 'platform_coupon', created_at))
            self._coupon_counts[coupon.pk] = self._coupon_counts.get(coupon.pk, 0) + 1

    def _seed_coupon_redemptions(self):
        if not self._coupon_uses:
            return

        redemptions = [
            CouponRedemption(coupon=coupon, user=order.buyer, discount=getattr(order, f'{campo}_discount'))
            for order, coupon, campo, _ in self._coupon_uses
        ]
        CouponRedemption.objects.bulk_create(redemptions, batch_size=500)
        for redemption, (order, _, campo, created_at) in zip(redemptions, self._coupon_uses):
            redemption.created_at = created_at
            setattr(order, campo, redemption)
        CouponRedemption.objects.bulk_update(redemptions, ['created_at'], batch_size=500)

        orders = list({order.pk: order for order, _, _, _ in self._coupon_uses}.values())
        Order.objects.bulk_update(orders, ['seller_coupon', 'platform_coupon'], batch_size=500)

    def _order_timeline(self, status, created_at):
        now = self._now
        if status == 'PENDING':
            return created_at, None
        if status in RECENT_STATUSES or status == 'CANCELLED':
            return min(now, created_at + timedelta(hours=random.randint(1, 120))), None
        delivered_at = min(now, created_at + timedelta(days=random.randint(3, 12), hours=random.randint(0, 23)))
        updated_at = min(now, delivered_at + timedelta(hours=random.randint(0, 240)))
        return updated_at, delivered_at

    def _dispute_time(self, requested_at, buyer_opened):
        earliest = requested_at + (self._response_window if buyer_opened else timedelta(hours=2))
        latest = min(self._now, requested_at + self._response_window + self._escalation_window)
        return random_between(earliest, latest) if earliest <= latest else None

    def _return_flow(self, status, outcome, delivered_at):
        requested_at = random_between(delivered_at, min(self._now, delivered_at + self._return_window))
        dispute_at, buyer_opened = None, None

        if outcome:
            buyer_opened = outcome == 'RESOLVED_BUYER_REFUND' or random.random() < 0.7
            dispute_at = self._dispute_time(requested_at, buyer_opened)
            if dispute_at is None and buyer_opened:
                buyer_opened = False
                dispute_at = self._dispute_time(requested_at, False)
            if dispute_at is None:
                outcome, buyer_opened = None, None
                if status == 'DISPUTE_OPEN':
                    status = 'RETURN_REQUESTED'

        if outcome == 'OPEN':
            updated_at = dispute_at
        elif outcome:
            updated_at = min(self._now, dispute_at + timedelta(hours=random.randint(12, 240)))
        elif status == 'RETURN_REQUESTED':
            expires_at = requested_at + self._response_window + self._escalation_window
            if expires_at <= self._now:
                status, updated_at = 'COMPLETED', expires_at
            else:
                updated_at = requested_at
        else:
            updated_at = min(self._now, random_between(requested_at, requested_at + self._response_window))
            if status == 'RETURNED':
                updated_at = min(self._now, updated_at + timedelta(days=random.randint(3, 10)))

        category = random.choice(list(RETURN_REASONS))
        return {
            'status': status,
            'outcome': outcome,
            'updated_at': updated_at,
            'requested_at': requested_at,
            'dispute_at': dispute_at,
            'buyer_opened': buyer_opened,
            'reason_category': category,
            'description': random.choice(RETURN_REASONS[category]),
        }

    def _seed_orders(self, products, buyers, count):
        published = [p for p in products if p.published and p.seed_variants]
        if not published:
            return

        self.stdout.write('Gerando pedidos...')
        commission_rate = PlatformConfig.get_commission_rate()
        config = PlatformConfig.load()
        self._return_window = timedelta(days=config.return_window_days)
        self._response_window = timedelta(days=config.seller_response_days)
        self._escalation_window = timedelta(days=config.escalation_window_days)
        self._dispute_categories = set(config.dispute_reason_list())
        product_weights = [p.seed_weight for p in published]
        buyer_weights = [random.lognormvariate(0, 1.2) for _ in buyers]

        drafts = []
        dispute_drafts = []
        return_drafts = []
        touched_variants = {}
        attempts = 0

        while len(drafts) < count and attempts < count * 5:
            attempts += 1
            product = random.choices(published, weights=product_weights)[0]
            buyer = random.choices(buyers, weights=buyer_weights)[0]
            if buyer == product.seller:
                continue

            created_at = random_between(max(product.created_at, buyer.date_joined), self._now - timedelta(hours=1))
            status = status_for_age((self._now - created_at).days)
            variant = random.choice(product.seed_variants)
            pickup = product.accepts_pickup and random.random() < 0.2

            if pickup and status == 'SHIPPED':
                status = 'READY_PICKUP'
            elif not pickup and status == 'READY_PICKUP':
                status = 'SHIPPED'

            dispute_outcome = None
            if status in DISPUTE_CHANCES:
                outcome, chance = DISPUTE_CHANCES[status]
                if random.random() < chance:
                    dispute_outcome = outcome
                    if outcome == 'OPEN':
                        status = 'DISPUTE_OPEN'

            if status in STOCK_DECREMENTED_STATUSES and variant.quantity < 1:
                continue

            quantity = random.randint(1, min(3, max(variant.quantity, 1)))
            total_price = (variant.price * quantity).quantize(Decimal('0.01'))
            updated_at, delivered_at = self._order_timeline(status, created_at)

            flow = None
            if status in RETURN_FLOW_STATUSES or dispute_outcome:
                flow = self._return_flow(status, dispute_outcome, delivered_at)
                status, dispute_outcome, updated_at = flow['status'], flow['outcome'], flow['updated_at']

            has_tracking = not pickup and status in TRACKING_ELIGIBLE_STATUSES
            order = Order(
                buyer=buyer,
                product=product,
                variant=variant,
                quantity=quantity,
                total_price=total_price,
                status=status,
                pickup=pickup,
                tracking_code=generate_tracking_code() if has_tracking else '',
            )
            self._maybe_use_coupons(order, created_at, commission_rate)

            if status in STOCK_DECREMENTED_STATUSES:
                variant.quantity = max(variant.quantity - quantity, 0)
                touched_variants[variant.pk] = variant

            drafts.append((order, created_at, updated_at, delivered_at))
            if flow:
                return_drafts.append((order, flow))
            if dispute_outcome:
                dispute_drafts.append((order, dispute_outcome, updated_at, flow))

        orders = [d[0] for d in drafts]
        Order.objects.bulk_create(orders, batch_size=500)
        for order, created_at, updated_at, _ in drafts:
            order.created_at = created_at
            order.updated_at = updated_at
        Order.objects.bulk_update(orders, ['created_at', 'updated_at'], batch_size=500)

        self._seed_coupon_redemptions()
        self._seed_return_requests(return_drafts)
        self._seed_disputes(dispute_drafts)

        commissions = []
        for order, _, _, delivered_at in drafts:
            if order.status in HAS_COMMISSION_STATUSES:
                commission = Commission(order=order, **commission_for(order, commission_rate))
                commissions.append((commission, delivered_at))
        Commission.objects.bulk_create([c for c, _ in commissions], batch_size=500)
        for commission, delivered_at in commissions:
            commission.created_at = delivered_at
        Commission.objects.bulk_update([c for c, _ in commissions], ['created_at'], batch_size=500)

        product_reviews, seller_reviews = [], []
        for order, _, _, delivered_at in drafts:
            if order.status in CAN_REVIEW_STATUSES and random.random() < 0.6:
                self._maybe_review(order, delivered_at, product_reviews, seller_reviews)

        ProductReview.objects.bulk_create([r for r, _ in product_reviews], batch_size=500)
        SellerReview.objects.bulk_create([r for r, _ in seller_reviews], batch_size=500)
        for review, review_date in product_reviews + seller_reviews:
            review.created_at = review_date
        ProductReview.objects.bulk_update([r for r, _ in product_reviews], ['created_at'], batch_size=500)
        SellerReview.objects.bulk_update([r for r, _ in seller_reviews], ['created_at'], batch_size=500)

        ProductVariant.objects.bulk_update(list(touched_variants.values()), ['quantity'], batch_size=500)

    def _seed_return_requests(self, return_drafts):
        if not return_drafts:
            return

        self.stdout.write('Gerando solicitações de devolução...')
        requests = [
            ReturnRequest(order=order, reason_category=flow['reason_category'], description=flow['description'])
            for order, flow in return_drafts
        ]
        ReturnRequest.objects.bulk_create(requests, batch_size=500)
        for request, (_, flow) in zip(requests, return_drafts):
            request.created_at = flow['requested_at']
        ReturnRequest.objects.bulk_update(requests, ['created_at'], batch_size=500)

    def _seed_disputes(self, dispute_drafts):
        if not dispute_drafts:
            return

        self.stdout.write('Gerando disputas...')
        staff = User.objects.filter(is_staff=True).first()
        disputes, messages = [], []

        for order, outcome, updated_at, flow in dispute_drafts:
            seller = order.product.seller
            if flow['buyer_opened']:
                opened_by, other = order.buyer, seller
                category = flow['reason_category'] if flow['reason_category'] in self._dispute_categories else 'Outro'
                reason = random.choice(BUYER_ESCALATION_TEXTS)
            else:
                opened_by, other = seller, order.buyer
                category, reason = random.choice(SELLER_DISPUTE_REASONS)

            created_at = flow['dispute_at']
            resolved_at = None if outcome == 'OPEN' else updated_at

            dispute = Dispute(
                order=order,
                opened_by=opened_by,
                reason_category=category,
                reason=reason,
                status=outcome,
                resolved_by=staff if resolved_at else None,
                resolved_at=resolved_at,
                resolution_notes=random.choice(RESOLUTION_NOTES) if resolved_at else '',
            )
            dispute.seed_date = created_at
            disputes.append(dispute)

            last_message_at = resolved_at or self._now
            for i in range(random.randint(0, 3)):
                messages.append((
                    DisputeMessage(dispute=dispute, author=other if i % 2 == 0 else opened_by, message=random.choice(DISPUTE_REPLIES)),
                    random_between(created_at, last_message_at),
                ))

        Dispute.objects.bulk_create(disputes, batch_size=500)
        for dispute in disputes:
            dispute.created_at = dispute.seed_date
        Dispute.objects.bulk_update(disputes, ['created_at'], batch_size=500)

        DisputeMessage.objects.bulk_create([m for m, _ in messages], batch_size=500)
        for message, sent_at in messages:
            message.created_at = sent_at
        DisputeMessage.objects.bulk_update([m for m, _ in messages], ['created_at'], batch_size=500)

    def _review_date(self, delivered_at):
        return min(self._now, delivered_at + timedelta(days=random.randint(1, 14), hours=random.randint(0, 23)))

    def _maybe_review(self, order, delivered_at, product_reviews, seller_reviews):
        rating = lambda: Decimal(random.choice([str(x / 2) for x in range(1, 11)]))

        product_key = (order.product_id, order.buyer_id)
        if product_key not in self._reviewed_products:
            self._reviewed_products.add(product_key)
            nota = rating()
            review = ProductReview(
                product=order.product,
                reviewer=order.buyer,
                rating=nota,
                comment=comment_for(nota),
            )
            product_reviews.append((review, self._review_date(delivered_at)))

        seller_key = (order.product.seller_id, order.buyer_id)
        if seller_key not in self._reviewed_sellers:
            self._reviewed_sellers.add(seller_key)
            nota = rating()
            review = SellerReview(
                seller=order.product.seller,
                reviewer=order.buyer,
                rating=nota,
                comment=comment_for(nota),
            )
            seller_reviews.append((review, self._review_date(delivered_at)))

    def _seed_carts(self, products, buyers):
        published = [p for p in products if p.published and p.seed_variants]
        if not published or not buyers:
            return

        self.stdout.write('Gerando carrinhos...')
        for buyer in random.sample(buyers, k=max(1, len(buyers) // 4)):
            cart, _ = Cart.objects.get_or_create(user=buyer)
            for product in random.sample(published, k=min(3, len(published))):
                if product.seller == buyer:
                    continue
                variant = random.choice(product.seed_variants)
                if variant.quantity < 1:
                    continue
                CartItem.objects.get_or_create(
                    cart=cart, variant=variant,
                    defaults={'product': product, 'quantity': random.randint(1, min(2, variant.quantity))},
                )

    def _seed_auctions(self, categories, sellers, buyers, count):
        if not count or not buyers:
            return 0

        self.stdout.write('Gerando leilões...')
        for _ in range(count):
            category = random.choices(categories, weights=CATEGORY_WEIGHTS)[0]
            seller = random.choice(sellers)
            title, _ = self._generate_title(category)
            duration = random.choice(AUCTION_DURATIONS)

            ended = random.random() < AUCTION_ENDED_SHARE
            if ended:
                ends_at = self._now - timedelta(hours=random.randint(1, 72))
            else:
                ends_at = self._now + timedelta(minutes=random.randint(20, duration * 24 * 60 - 30))
            starts_at = ends_at - timedelta(days=duration)

            start = Decimal(random.randrange(10, 300))
            reserve = buy_now = None
            if random.random() < 0.3:
                reserve = (start * Decimal(str(random.uniform(1.5, 3)))).quantize(Decimal('1'))
            if random.random() < 0.35:
                base = max(start * Decimal('1.3'), reserve or Decimal('0'))
                buy_now = (base * Decimal(str(random.uniform(1.2, 1.8)))).quantize(Decimal('1'))

            product = Product.objects.create(
                category=category,
                seller=seller,
                title=title,
                description=' '.join(random.sample(DESCRIPTION_SENTENCES, 4)),
                condition=random.choices(['NEW', 'USED'], weights=[3, 7])[0],
                accepts_pickup=random.random() < 0.3,
            )
            Product.objects.filter(pk=product.pk).update(created_at=starts_at, updated_at=starts_at)
            auction = publish_auction(product, Auction(
                start_price=start, reserve_price=reserve, buy_now_price=buy_now, duration_days=duration,
            ), agora=starts_at)

            self._seed_bids(auction, buyers, starts_at, min(ends_at, self._now))
            if ended:
                close_auction(auction, agora=ends_at)
                if auction.order:
                    Order.objects.filter(pk=auction.order.pk).update(created_at=ends_at, updated_at=ends_at)
                elif auction.bid_count and random.random() < 0.6:
                    self._seed_second_chance(auction, seller)
            else:
                if auction.bid_count and random.random() < 0.12:
                    bidder = random.choice([b.bidder for b in auction.bids.filter(is_auto=False)])
                    retract_bids(auction.pk, bidder, random.choice(Bid.RETRACTION_CHOICES)[0])
                watchers = random.sample(buyers, k=random.randint(0, min(8, len(buyers))))
                AuctionWatch.objects.bulk_create(
                    [AuctionWatch(user=user, auction=auction) for user in watchers], ignore_conflicts=True,
                )

        return count

    def _seed_second_chance(self, auction, seller):
        candidatos = second_chance_candidates(auction)
        if not candidatos:
            return
        offer, _ = send_second_chance(auction.pk, seller, candidatos[0]['bidder'].pk, random.choice([1, 3, 5]))
        if offer and random.random() < 0.5:
            respond_second_chance(offer.pk, offer.bidder, aceitar=random.random() < 0.7)

    def _seed_bids(self, auction, buyers, inicio, fim):
        lances = random.choices([0, 1, 2, 3, 5, 8, 12], weights=[15, 10, 15, 20, 20, 12, 8])[0]
        if not lances:
            return

        participantes = random.sample(buyers, k=min(len(buyers), random.randint(1, 6)))
        valor_de_mercado = auction.start_price * Decimal(str(random.uniform(1.2, 3.5)))
        for momento in sorted(random_between(inicio, fim) for _ in range(lances)):
            participante = random.choice(participantes)
            if participante.pk == auction.leader_id:
                continue
            minimo = minimum_bid(auction)
            if minimo > valor_de_mercado:
                break
            valor = minimo + increment_for(minimo) * random.randint(0, 12)
            apply_bid(auction, participante, valor, momento)

    def _seed_trades(self, products, sellers, count):
        alvos = [p for p in products if p.accepts_trade and p.published]
        if not count or not alvos or len(sellers) < 2:
            return 0

        self.stdout.write('Gerando propostas de troca...')
        criadas = 0
        for _ in range(count * 4):
            if criadas >= count:
                break
            alvo = random.choice(alvos)
            proponente = random.choice(sellers)
            variantes = target_variants(alvo)
            if proponente.pk == alvo.seller_id or not variantes:
                continue
            inventario = tradeable_variants(proponente)
            if not inventario:
                continue

            variante = random.choice(variantes)
            itens = random.sample(inventario, k=min(len(inventario), random.choice([1, 1, 1, 2, 2, 3])))
            volta, pagador = self._trade_cash(variante.price, sum(v.price for v in itens))
            proposal, erro = propose_trade(
                alvo.pk, proponente, variante.pk, [v.pk for v in itens], volta, pagador, random.choice(TRADE_MESSAGES),
            )
            if erro:
                continue
            criadas += 1
            self._advance_trade(proposal, [v.pk for v in itens])

        expire_trades()
        return criadas

    def _trade_cash(self, preco_alvo, preco_itens):
        diferenca = preco_alvo - preco_itens
        if abs(diferenca) < 10 or random.random() < 0.3:
            return Decimal('0'), ''
        volta = (abs(diferenca) * Decimal(str(random.uniform(0.5, 1)))).quantize(Decimal('1'), rounding=ROUND_DOWN)
        return volta, PROPOSER if diferenca > 0 else OWNER

    def _advance_trade(self, proposal, itens):
        desfecho = random.choices([d for d, _ in TRADE_OUTCOMES], weights=[w for _, w in TRADE_OUTCOMES])[0]
        if desfecho in ('pendente', 'contraproposta'):
            inicio = self._now - timedelta(hours=random.randint(2, 40))
        else:
            inicio = self._now - timedelta(days=random.randint(3, 90), hours=random.randint(0, 23))

        if desfecho == 'contraproposta' or (desfecho == 'aceita' and random.random() < 0.4):
            self._counter_trade(proposal, itens)
            proposal.refresh_from_db()

        if desfecho == 'aceita':
            accept_trade(proposal.pk, proposal.awaiting_user)
        elif desfecho == 'recusada':
            decline_trade(proposal.pk, proposal.owner, random.choice(DECLINE_MESSAGES))
        elif desfecho == 'retirada':
            withdraw_trade(proposal.pk, proposal.proposer)

        self._backdate_trade(proposal.pk, inicio)

    def _counter_trade(self, proposal, itens):
        if proposal.cash_payer == OWNER:
            volta = (proposal.cash_amount / 2).quantize(Decimal('1'), rounding=ROUND_DOWN)
            pagador = OWNER
        else:
            volta = min(proposal.cash_amount + random.choice([10, 15, 20, 30]), proposal.variant.price - 1)
            pagador = PROPOSER
        counter_trade(
            proposal.pk, proposal.owner, itens, volta, pagador,
            random.choice(['Consegue colocar um pouco mais de volta?', 'Fecho se ajustar a volta.', '']),
        )

    def _backdate_trade(self, pk, inicio):
        proposal = TradeProposal.objects.get(pk=pk)
        limite = self._now - timedelta(minutes=5)
        eventos = list(proposal.events.order_by('created_at', 'pk'))
        momento = inicio
        for evento in eventos:
            evento.created_at = min(momento, limite)
            momento += timedelta(hours=random.randint(1, 30))
        TradeEvent.objects.bulk_update(eventos, ['created_at'])

        fim = eventos[-1].created_at
        campos = {'created_at': inicio, 'expires_at': fim + timedelta(days=PlatformConfig.load().trade_response_days)}
        if proposal.status != 'PENDING':
            campos['closed_at'] = fim
        TradeProposal.objects.filter(pk=pk).update(**campos)

        if proposal.status == 'ACCEPTED':
            self._progress_trade_orders(list(proposal.orders.all()), fim)

    def _progress_trade_orders(self, pedidos, fechada):
        dias = (self._now - fechada).days
        if dias > 20:
            status = 'COMPLETED'
        elif dias > 6:
            status = 'SHIPPED'
        elif any(p.amount_charged for p in pedidos) and random.random() < 0.5:
            status = 'PENDING'
        else:
            status = 'PAID'

        primeiro_pagante = next((p for p in pedidos if p.amount_charged), None)
        for pedido in pedidos:
            pedido.status = status
            pedido.created_at = fechada
            pedido.updated_at = fechada + timedelta(days=min(dias, 10))
            pedido.trade_paid = bool(pedido.amount_charged) and (
                status != 'PENDING' or (pedido is primeiro_pagante and random.random() < 0.5)
            )
            if status == 'SHIPPED':
                pedido.tracking_code = generate_tracking_code()
        Order.objects.bulk_update(pedidos, ['status', 'created_at', 'updated_at', 'tracking_code', 'trade_paid'])

        if status != 'COMPLETED':
            return
        taxa = PlatformConfig.get_commission_rate()
        comissoes = [Commission(order=p, **commission_for(p, taxa)) for p in pedidos if p.total_price]
        Commission.objects.bulk_create(comissoes)
        for comissao in comissoes:
            comissao.created_at = fechada + timedelta(days=8)
        Commission.objects.bulk_update(comissoes, ['created_at'])
        ProductVariant.objects.filter(pk__in=[p.variant_id for p in pedidos], quantity__gt=0).update(quantity=F('quantity') - 1)