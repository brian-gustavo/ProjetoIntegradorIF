import random
from decimal import Decimal
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from faker import Faker

from accounts.models import UF_CHOICES, SellerReview
from catalog.models import Category, Product, ProductVariant, ProductReview
from orders.models import Order, Cart, CartItem, PlatformConfig, Commission, generate_tracking_code

fake = Faker('pt_BR')

CATEGORIES = [
    ('Consoles', 'consoles'),
    ('Games', 'games'),
    ('Periféricos', 'perifericos'),
    ('Keys', 'keys'),
    ('Jogos de Tabuleiro', 'jogos-de-tabuleiro'),
    ('Itens In-Game', 'itens-in-game'),
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
COLLECTIBLE_VARIANTS = ['Padrão', 'Edição Especial', 'Edição Colecionador']

STATUS_WEIGHTS = [
    ('PENDING', 8), ('PAID', 8), ('CONFIRMED', 5), ('PREPARING', 5),
    ('SHIPPED', 6), ('READY_PICKUP', 3), ('DELIVERED', 10), ('RETURN_WINDOW', 6),
    ('RETURN_REQUESTED', 3), ('RETURN_ACCEPTED', 2), ('RETURNED', 3),
    ('CANCELLED_NO_RETURN', 2), ('COMPLETED', 25), ('CANCELLED', 6),
]

STOCK_DECREMENTED_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED',
    'CANCELLED_NO_RETURN', 'COMPLETED',
}
HAS_COMMISSION_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED', 'COMPLETED',
}
CAN_REVIEW_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'RETURN_ACCEPTED',
    'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED',
}
TRACKING_ELIGIBLE_STATUSES = {
    'SHIPPED', 'READY_PICKUP', 'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED',
    'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED',
}


class Command(BaseCommand):
    help = 'Povoa o banco de dados com dados fictícios para testes'

    def add_arguments(self, parser):
        parser.add_argument('--sellers', type=int, default=25)
        parser.add_argument('--buyers', type=int, default=60)
        parser.add_argument('--products', type=int, default=250)
        parser.add_argument('--orders', type=int, default=400)
        parser.add_argument('--flush', action='store_true')

    def handle(self, *args, **options):
        if options['flush']:
            self._flush()

        self._reviewed_products = set()
        self._reviewed_sellers = set()

        with transaction.atomic():
            PlatformConfig.objects.get_or_create(pk=1, defaults={'commission_rate': Decimal('10.00')})
            categories = self._seed_categories()
            sellers = self._seed_users('vendedor', options['sellers'])
            buyers = self._seed_users('comprador', options['buyers'])
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

    def _seed_users(self, prefix, count):
        users = []
        for i in range(count):
            username = f'{prefix}{i + 1}'
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': f'{username}@teste.com'},
            )
            if created:
                user.set_password('senha123')
                user.save()
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
        products = []
        for _ in range(count):
            category = random.choice(categories)
            seller = random.choice(sellers)
            title, variant_pool = self._generate_title(category)
            is_draft = random.random() < 0.05

            product = Product.objects.create(
                category=category,
                seller=seller,
                title=title,
                description=fake.paragraph(nb_sentences=4),
                condition=random.choices(['NEW', 'USED'], weights=[7, 3])[0],
                accepts_pickup=random.random() < 0.3,
                published=not is_draft and random.random() < 0.9,
                deleted=False,
            )

            if not is_draft:
                variant_count = random.randint(1, min(4, len(variant_pool)))
                for variant_name in random.sample(variant_pool, variant_count):
                    ProductVariant.objects.create(
                        product=product,
                        name=variant_name,
                        price=Decimal(random.randrange(2000, 45000)) / 100,
                        quantity=random.randint(0, 30),
                    )

            products.append(product)
        return products

    def _seed_orders(self, products, buyers, count):
        published = [p for p in products if p.published and p.variants.exists()]
        if not published:
            return

        commission_rate = PlatformConfig.get_commission_rate()
        statuses, weights = zip(*STATUS_WEIGHTS)

        for _ in range(count):
            product = random.choice(published)
            eligible_buyers = [b for b in buyers if b != product.seller]
            if not eligible_buyers:
                continue
            buyer = random.choice(eligible_buyers)
            variant = random.choice(list(product.variants.all()))
            status = random.choices(statuses, weights=weights)[0]

            if status in STOCK_DECREMENTED_STATUSES and variant.quantity < 1:
                status = 'PENDING'

            quantity = random.randint(1, min(3, max(variant.quantity, 1)))
            total_price = (variant.price * quantity).quantize(Decimal('0.01'))
            pickup = product.accepts_pickup and random.random() < 0.2

            order = Order.objects.create(
                buyer=buyer,
                product=product,
                variant=variant,
                quantity=quantity,
                total_price=total_price,
                status=status,
                pickup=pickup,
            )

            if not pickup and status in TRACKING_ELIGIBLE_STATUSES:
                order.tracking_code = generate_tracking_code()
                order.save()

            if status in STOCK_DECREMENTED_STATUSES:
                variant.quantity = max(variant.quantity - quantity, 0)
                variant.save()

            if status in HAS_COMMISSION_STATUSES:
                commission_amount = (total_price * commission_rate / Decimal('100')).quantize(Decimal('0.01'))
                Commission.objects.create(
                    order=order,
                    rate=commission_rate,
                    gross_amount=total_price,
                    commission_amount=commission_amount,
                    net_amount=total_price - commission_amount,
                )

            if status in CAN_REVIEW_STATUSES and random.random() < 0.6:
                self._maybe_review(order)

    def _maybe_review(self, order):
        rating = lambda: Decimal(random.choice([str(x / 2) for x in range(1, 11)]))

        product_key = (order.product_id, order.buyer_id)
        if product_key not in self._reviewed_products:
            self._reviewed_products.add(product_key)
            ProductReview.objects.create(
                product=order.product,
                reviewer=order.buyer,
                rating=rating(),
                comment=fake.sentence() if random.random() < 0.7 else '',
            )

        seller_key = (order.product.seller_id, order.buyer_id)
        if seller_key not in self._reviewed_sellers:
            self._reviewed_sellers.add(seller_key)
            SellerReview.objects.create(
                seller=order.product.seller,
                reviewer=order.buyer,
                rating=rating(),
                comment=fake.sentence() if random.random() < 0.7 else '',
            )

    def _seed_carts(self, products, buyers):
        published = [p for p in products if p.published and p.variants.exists()]
        if not published or not buyers:
            return

        for buyer in random.sample(buyers, k=max(1, len(buyers) // 4)):
            cart, _ = Cart.objects.get_or_create(user=buyer)
            for product in random.sample(published, k=min(3, len(published))):
                if product.seller == buyer:
                    continue
                variant = random.choice(list(product.variants.all()))
                if variant.quantity < 1:
                    continue
                CartItem.objects.get_or_create(
                    cart=cart, variant=variant,
                    defaults={'product': product, 'quantity': random.randint(1, min(2, variant.quantity))},
                )