import random
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from faker import Faker

from accounts.models import UF_CHOICES, SellerReview
from catalog.models import Category, Product, ProductVariant, ProductReview
from orders.models import Order, Cart, CartItem, PlatformConfig, Commission, Dispute, DisputeMessage, generate_tracking_code

fake = Faker('pt_BR')

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
BUYER_DISPUTE_REASONS = [
    ('Produto com defeito', 'O produto chegou com defeito e o vendedor não aceitou a devolução.'),
    ('Produto diferente do anunciado', 'O item recebido é diferente do que estava no anúncio.'),
    ('Produto incompleto', 'O produto veio incompleto, faltando acessórios descritos no anúncio.'),
    ('Key ou código digital inválido', 'A key digital já tinha sido resgatada quando tentei ativar.'),
    ('Outro', 'O vendedor recusou a devolução sem justificativa.'),
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
    (20, [('SHIPPED', 15), ('READY_PICKUP', 5), ('DELIVERED', 35), ('RETURN_WINDOW', 15), ('RETURN_REQUESTED', 5), ('CANCELLED', 10), ('COMPLETED', 15)]),
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

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument('--sellers', type=int, default=25)
        parser.add_argument('--buyers', type=int, default=60)
        parser.add_argument('--products', type=int, default=250)
        parser.add_argument('--orders', type=int, default=400)
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
            self._seed_orders(products, buyers, options['orders'])
            self._seed_carts(products, buyers)

        self.stdout.write(self.style.SUCCESS(
            f"Banco povoado: {len(sellers)} vendedores, {len(buyers)} compradores, "
            f"{len(products)} produtos."
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
            user.profile.city = fake.city()
            user.profile.uf = random.choice(UF_CHOICES)[0]
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
            return f'{item} {fake.word().capitalize()} Pro', ['Padrão', 'Edição RGB']
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

            product = Product(
                category=category,
                seller=seller,
                title=title,
                description=fake.paragraph(nb_sentences=4),
                condition=random.choices(['NEW', 'USED'], weights=[7, 3])[0],
                accepts_pickup=random.random() < 0.3,
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

    def _order_timeline(self, status, created_at):
        now = self._now
        if status == 'PENDING':
            return created_at, None
        if status in RECENT_STATUSES or status == 'CANCELLED':
            return min(now, created_at + timedelta(hours=random.randint(1, 120))), None
        delivered_at = min(now, created_at + timedelta(days=random.randint(3, 12), hours=random.randint(0, 23)))
        updated_at = min(now, delivered_at + timedelta(hours=random.randint(0, 240)))
        return updated_at, delivered_at

    def _seed_orders(self, products, buyers, count):
        published = [p for p in products if p.published and p.seed_variants]
        if not published:
            return

        self.stdout.write('Gerando pedidos...')
        commission_rate = PlatformConfig.get_commission_rate()
        product_weights = [p.seed_weight for p in published]
        buyer_weights = [random.lognormvariate(0, 1.2) for _ in buyers]

        drafts = []
        dispute_drafts = []
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

            if status in STOCK_DECREMENTED_STATUSES:
                variant.quantity = max(variant.quantity - quantity, 0)
                touched_variants[variant.pk] = variant

            drafts.append((order, created_at, updated_at, delivered_at))
            if dispute_outcome:
                dispute_drafts.append((order, dispute_outcome, delivered_at, updated_at))

        orders = [d[0] for d in drafts]
        Order.objects.bulk_create(orders, batch_size=500)
        for order, created_at, updated_at, _ in drafts:
            order.created_at = created_at
            order.updated_at = updated_at
        Order.objects.bulk_update(orders, ['created_at', 'updated_at'], batch_size=500)

        self._seed_disputes(dispute_drafts)

        commissions = []
        for order, _, _, delivered_at in drafts:
            if order.status in HAS_COMMISSION_STATUSES:
                commission_amount = (order.total_price * commission_rate / Decimal('100')).quantize(Decimal('0.01'))
                commission = Commission(
                    order=order,
                    rate=commission_rate,
                    gross_amount=order.total_price,
                    commission_amount=commission_amount,
                    net_amount=order.total_price - commission_amount,
                )
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

    def _seed_disputes(self, dispute_drafts):
        if not dispute_drafts:
            return

        self.stdout.write('Gerando disputas...')
        staff = User.objects.filter(is_staff=True).first()
        disputes, messages = [], []

        for order, outcome, delivered_at, updated_at in dispute_drafts:
            seller = order.product.seller
            if outcome == 'RESOLVED_BUYER_REFUND' or random.random() < 0.7:
                opened_by, other = order.buyer, seller
                category, reason = random.choice(BUYER_DISPUTE_REASONS)
            else:
                opened_by, other = seller, order.buyer
                category, reason = random.choice(SELLER_DISPUTE_REASONS)

            if outcome == 'OPEN':
                created_at, resolved_at = updated_at, None
            else:
                resolved_at = updated_at
                created_at = random_between(delivered_at, resolved_at - timedelta(hours=12))

            dispute = Dispute(
                order=order,
                opened_by=opened_by,
                reason_category=category,
                reason=reason,
                status=outcome,
                resolved_by=staff if resolved_at else None,
                resolved_at=resolved_at,
                resolution_notes=fake.sentence() if resolved_at else '',
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
            review = ProductReview(
                product=order.product,
                reviewer=order.buyer,
                rating=rating(),
                comment=fake.sentence() if random.random() < 0.7 else '',
            )
            product_reviews.append((review, self._review_date(delivered_at)))

        seller_key = (order.product.seller_id, order.buyer_id)
        if seller_key not in self._reviewed_sellers:
            self._reviewed_sellers.add(seller_key)
            review = SellerReview(
                seller=order.product.seller,
                reviewer=order.buyer,
                rating=rating(),
                comment=fake.sentence() if random.random() < 0.7 else '',
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