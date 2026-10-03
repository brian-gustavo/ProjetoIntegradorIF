from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product, ProductVariant
from orders.models import Cart, CartItem, Commission, Order
from orders.views import _finalize_delivery
from rewards.models import CoinTransaction
from rewards.services import balance
from .forms import CouponForm
from .models import Coupon, CouponRedemption
from .services import build_quote, redeem_code

class CouponTestCase(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('comprador', password='senha12345')
        self.seller = User.objects.create_user('loja1', password='senha12345')
        self.other_seller = User.objects.create_user('loja2', password='senha12345')
        self.jogos = Category.objects.create(name='Jogos', slug='jogos')
        self.consoles = Category.objects.create(name='Consoles', slug='consoles')
        self.game = self.make_variant(self.seller, self.jogos, 'Zelda', '200.00')
        self.console = self.make_variant(self.other_seller, self.consoles, 'Switch', '100.00')

    def make_variant(self, seller, category, title, price):
        product = Product.objects.create(category=category, seller=seller, title=title, description='-', published=True)
        return ProductVariant.objects.create(product=product, name='Padrão', price=Decimal(price), quantity=10)

    def coupon(self, code, seller=None, **kwargs):
        dados = {'kind': 'PERCENT', 'value': Decimal('10')}
        dados.update(kwargs)
        return Coupon.objects.create(code=code, seller=seller, **dados)

    def fill_cart(self, *variants, user=None):
        cart, _ = Cart.objects.get_or_create(user=user or self.buyer)
        cart.items.all().delete()
        for variant in variants:
            CartItem.objects.create(cart=cart, product=variant.product, variant=variant, quantity=1)
        return list(cart.items.select_related('product__seller', 'product__category', 'variant'))

    def quote(self, *variants, user=None, escolhas=None):
        return build_quote(user or self.buyer, self.fill_cart(*variants, user=user), escolhas)

    def checkout(self, *variants, user=None, data=None):
        user = user or self.buyer
        self.fill_cart(*variants, user=user)
        self.client.force_login(user)
        antes = set(Order.objects.values_list('pk', flat=True))
        self.client.post(reverse('checkout'), data or {})
        return list(Order.objects.exclude(pk__in=antes).order_by('pk'))

    def option(self, quote, code):
        opcoes = quote['plataforma']['opcoes'] + [o for loja in quote['lojas'] for o in loja['opcoes']]
        return next(o for o in opcoes if o['cupom'].code == code)

class DiscountRulesTests(CouponTestCase):
    def test_percent_discount_respects_cap(self):
        self.coupon('LOJA20', self.seller, value=Decimal('20'), max_discount=Decimal('30'))
        quote = self.quote(self.game)
        self.assertEqual(quote['desconto_lojas'], Decimal('30.00'))

    def test_best_store_coupon_is_selected_automatically(self):
        self.coupon('LOJA10', self.seller)
        self.coupon('LOJA25', self.seller, kind='FIXED', value=Decimal('25'), min_order_value=Decimal('150'))
        quote = self.quote(self.game)
        self.assertEqual(quote['lojas'][0]['escolhida']['cupom'].code, 'LOJA25')
        self.assertEqual(quote['total'], Decimal('175.00'))

    def test_minimum_order_shows_missing_amount(self):
        self.coupon('LOJA300', self.seller, kind='FIXED', value=Decimal('30'), min_order_value=Decimal('300'))
        opcao = self.option(self.quote(self.game), 'LOJA300')
        self.assertEqual(opcao['motivo'], 'Faltam R$ 100,00 para usar este cupom')
        self.assertEqual(opcao['desconto'], 0)

    def test_store_coupon_only_applies_to_its_store(self):
        self.coupon('LOJA10', self.seller)
        quote = self.quote(self.game, self.console)
        pedidos = {p.product.seller_id: p for p in quote['pedidos']}
        self.assertEqual(pedidos[self.seller.pk].seller_coupon_discount, Decimal('20.00'))
        self.assertEqual(pedidos[self.other_seller.pk].seller_coupon_discount, Decimal('0'))

    def test_category_restriction(self):
        self.coupon('CONSOLE', value=Decimal('5'), category=self.consoles)
        quote = self.quote(self.game, self.console)
        self.assertEqual(quote['desconto_plataforma'], Decimal('5.00'))
        self.assertEqual(self.option(self.quote(self.game), 'CONSOLE')['motivo'], 'Válido apenas para Consoles')

    def test_expired_and_scheduled_coupons_are_hidden(self):
        agora = timezone.now()
        self.coupon('VELHO', ends_at=agora - timedelta(days=1), starts_at=agora - timedelta(days=5))
        self.coupon('FUTURO', starts_at=agora + timedelta(days=1))
        self.assertEqual(self.quote(self.game)['plataforma']['opcoes'], [])

class PlatformCouponTests(CouponTestCase):
    def test_platform_coupon_is_split_between_orders(self):
        self.coupon('MEGA10')
        quote = self.quote(self.game, self.console)
        descontos = sorted(p.platform_coupon_discount for p in quote['pedidos'])
        self.assertEqual(descontos, [Decimal('10.00'), Decimal('20.00')])

    def test_platform_coupon_uses_price_after_store_coupon(self):
        self.coupon('LOJA50', self.seller, kind='FIXED', value=Decimal('50'), min_order_value=Decimal('100'))
        self.coupon('MEGA10')
        quote = self.quote(self.game)
        self.assertEqual(quote['desconto_lojas'], Decimal('50.00'))
        self.assertEqual(quote['desconto_plataforma'], Decimal('15.00'))
        self.assertEqual(quote['total'], Decimal('135.00'))

    def test_platform_coupon_never_exceeds_commission(self):
        self.coupon('MEGA30', value=Decimal('30'))
        opcao = self.option(self.quote(self.game), 'MEGA30')
        self.assertEqual(opcao['desconto'], Decimal('20.00'))
        self.assertTrue(opcao['limitado'])

    def test_coins_only_use_commission_left_by_coupon(self):
        CoinTransaction.objects.create(user=self.buyer, kind='ADJUST', amount=5000, description='Teste')
        self.coupon('MEGA5', value=Decimal('5'))
        quote = self.quote(self.game)
        self.assertEqual(quote['moedas']['usaveis'], 1000)

        self.coupon('MEGA10', value=Decimal('10'))
        self.assertEqual(self.quote(self.game)['moedas']['usaveis'], 0)

class EligibilityTests(CouponTestCase):
    def test_private_coupon_requires_code(self):
        self.coupon('SEGREDO', is_public=False)
        self.assertEqual(self.quote(self.game)['plataforma']['opcoes'], [])

        coupon, erro = redeem_code(self.buyer, ' segredo ')
        self.assertIsNone(erro)
        self.assertEqual(coupon.code, 'SEGREDO')
        self.assertEqual(self.quote(self.game)['desconto_plataforma'], Decimal('20.00'))

    def test_unknown_code(self):
        coupon, erro = redeem_code(self.buyer, 'NAOEXISTE')
        self.assertIsNone(coupon)
        self.assertIn('não encontrado', erro)

    def test_first_purchase_only(self):
        self.coupon('BEMVINDO', first_purchase_only=True)
        self.assertEqual(self.quote(self.game)['desconto_plataforma'], Decimal('20.00'))

        Order.objects.create(buyer=self.buyer, product=self.console.product, variant=self.console, total_price=Decimal('100'), status='COMPLETED')
        self.assertEqual(self.option(self.quote(self.game), 'BEMVINDO')['motivo'], 'Exclusivo para a primeira compra na MegaGame')

    def test_first_purchase_in_store(self):
        self.coupon('NOVOCLIENTE', self.seller, first_purchase_only=True)
        Order.objects.create(buyer=self.buyer, product=self.console.product, variant=self.console, total_price=Decimal('100'), status='COMPLETED')
        self.assertEqual(self.quote(self.game)['desconto_lojas'], Decimal('20.00'))

    def test_per_user_limit(self):
        self.coupon('MEGA10')
        self.checkout(self.game)
        self.assertEqual(self.option(self.quote(self.game), 'MEGA10')['motivo'], 'Você já usou este cupom')

    def test_usage_limit_is_released_when_order_is_cancelled(self):
        self.coupon('ULTIMO', usage_limit=1)
        pedido = self.checkout(self.game)[0]

        outro = User.objects.create_user('outro', password='senha12345')
        self.assertEqual(self.option(self.quote(self.game, user=outro), 'ULTIMO')['motivo'], 'Cupom esgotado')

        pedido.status = 'CANCELLED'
        pedido.save()
        self.assertEqual(self.quote(self.game, user=outro)['desconto_plataforma'], Decimal('20.00'))

class CheckoutTests(CouponTestCase):
    def test_checkout_saves_discounts_and_redemptions(self):
        self.coupon('LOJA10', self.seller)
        self.coupon('MEGA5', value=Decimal('5'))
        pedido = self.checkout(self.game)[0]

        self.assertEqual(pedido.seller_coupon_discount, Decimal('20.00'))
        self.assertEqual(pedido.platform_coupon_discount, Decimal('9.00'))
        self.assertEqual(pedido.amount_paid, Decimal('171.00'))
        self.assertEqual(pedido.seller_coupon.coupon.code, 'LOJA10')
        self.assertEqual(pedido.platform_coupon.coupon.code, 'MEGA5')
        self.assertEqual(CouponRedemption.objects.count(), 2)

    def test_opting_out_of_coupon(self):
        cupom = self.coupon('LOJA10', self.seller)
        pedido = self.checkout(self.game, data={f'cupom_loja_{self.seller.pk}': ''})[0]
        self.assertEqual(pedido.seller_coupon_discount, Decimal('0'))
        self.assertFalse(cupom.redemptions.exists())

    def test_changed_total_blocks_confirmation(self):
        self.coupon('LOJA10', self.seller)
        pedidos = self.checkout(self.game, data={'action': 'confirmar', 'total_esperado': '200.00'})
        self.assertEqual(pedidos, [])
        self.assertTrue(CartItem.objects.filter(cart__user=self.buyer).exists())

    def test_unavailable_chosen_coupon_blocks_confirmation(self):
        cupom = self.coupon('LOJA10', self.seller)
        cupom.active = False
        cupom.save()
        pedidos = self.checkout(self.game, data={f'cupom_loja_{self.seller.pk}': str(cupom.pk)})
        self.assertEqual(pedidos, [])

    def test_commission_uses_price_after_store_coupon(self):
        self.coupon('LOJA10', self.seller)
        self.coupon('MEGA5', value=Decimal('5'))
        pedido = self.checkout(self.game)[0]
        pedido.status = 'SHIPPED'
        pedido.save()
        _finalize_delivery(pedido)

        comissao = Commission.objects.get(order=pedido)
        self.assertEqual(comissao.gross_amount, Decimal('180.00'))
        self.assertEqual(comissao.commission_amount, Decimal('18.00'))
        self.assertEqual(comissao.net_amount, Decimal('162.00'))

    def test_coupon_and_coins_together(self):
        CoinTransaction.objects.create(user=self.buyer, kind='ADJUST', amount=5000, description='Teste')
        self.coupon('MEGA5', value=Decimal('5'))
        pedido = self.checkout(self.game, data={'use_coins': '1'})[0]
        self.assertEqual(pedido.platform_coupon_discount, Decimal('10.00'))
        self.assertEqual(pedido.coins_discount, Decimal('10.00'))
        self.assertEqual(balance(self.buyer), 4000)

    def test_code_from_store_outside_cart_is_saved(self):
        self.coupon('LOJA2', self.other_seller, is_public=False)
        self.fill_cart(self.game)
        self.client.force_login(self.buyer)
        resposta = self.client.post(reverse('checkout'), {'action': 'codigo', 'codigo': 'loja2'})
        self.assertContains(resposta, 'não está no seu carrinho')
        self.assertTrue(self.buyer.saved_coupons.filter(coupon__code='LOJA2').exists())
        self.assertFalse(Order.objects.exists())

class CouponFormTests(CouponTestCase):
    def form(self, seller=None, **dados):
        base = {'kind': 'PERCENT', 'value': '10', 'min_order_value': '0', 'per_user_limit': '1',
                'starts_at': timezone.localtime().strftime('%Y-%m-%dT%H:%M'), 'is_public': 'on'}
        base.update(dados)
        return CouponForm(base, seller=seller)

    def test_platform_percent_cannot_exceed_commission(self):
        self.assertFalse(self.form(value='15').is_valid())
        self.assertTrue(self.form(value='10').is_valid())
        self.assertTrue(self.form(seller=self.seller, value='15').is_valid())

    def test_platform_fixed_requires_minimum_order(self):
        form = self.form(kind='FIXED', value='20', min_order_value='150')
        self.assertFalse(form.is_valid())
        self.assertIn('R$ 200,00', form.errors['min_order_value'][0])
        self.assertTrue(self.form(kind='FIXED', value='20', min_order_value='200').is_valid())

    def test_code_is_generated_and_normalized(self):
        form = self.form(seller=self.seller)
        self.assertTrue(form.is_valid())
        self.assertTrue(form.cleaned_data['code'].startswith('LOJA1'))

        form = self.form(code='bem vindo')
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['code'], 'BEMVINDO')

class ManagementTests(CouponTestCase):
    def test_seller_cannot_edit_other_store_coupon(self):
        cupom = self.coupon('LOJA2', self.other_seller)
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(reverse('edit_coupon', args=[cupom.pk])).status_code, 404)

    def test_seller_cannot_edit_platform_coupon(self):
        cupom = self.coupon('MEGA10')
        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(reverse('edit_coupon', args=[cupom.pk])).status_code, 404)

    def test_used_coupon_cannot_be_deleted(self):
        cupom = self.coupon('LOJA10', self.seller)
        self.checkout(self.game)
        self.client.force_login(self.seller)
        self.client.post(reverse('delete_coupon', args=[cupom.pk]))
        self.assertTrue(Coupon.objects.filter(pk=cupom.pk).exists())

    def test_pages_render(self):
        self.coupon('LOJA10', self.seller)
        self.coupon('MEGA10')
        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(reverse('my_coupons')), 'MEGA10')
        self.assertContains(self.client.get(reverse('product_detail', args=[self.game.product.pk])), '10% OFF')
        self.fill_cart(self.game)
        self.assertContains(self.client.get(reverse('checkout')), 'LOJA10')
        self.assertContains(self.client.get(reverse('cart_detail')), 'cupons disponíveis')

        self.client.force_login(self.seller)
        self.assertContains(self.client.get(reverse('manage_coupons')), 'LOJA10')
        self.assertEqual(self.client.get(reverse('create_coupon')).status_code, 200)

        staff = User.objects.create_user('staff', password='senha12345', is_staff=True)
        self.client.force_login(staff)
        resposta = self.client.get(reverse('manage_coupons'))
        self.assertContains(resposta, 'MEGA10')
        self.assertNotContains(resposta, 'LOJA10')
        self.assertEqual(self.client.get(reverse('admin_dashboard')).status_code, 200)
        self.assertEqual(self.client.get(reverse('admin_dashboard_pdf')).status_code, 200)