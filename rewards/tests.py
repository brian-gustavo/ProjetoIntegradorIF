from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product, ProductReview, ProductVariant
from orders.models import Cart, CartItem, Commission, Order
from .models import CoinTransaction
from .services import balance, checkin_status, do_checkin, level_info, sync_wallet

class RewardsTestCase(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user('comprador', password='senha12345')
        self.seller = User.objects.create_user('vendedor', password='senha12345')
        categoria = Category.objects.create(name='Jogos', slug='jogos')
        self.product = Product.objects.create(
            category=categoria, seller=self.seller, title='Zelda', description='-', published=True,
        )
        self.variant = ProductVariant.objects.create(product=self.product, name='Switch', price=Decimal('200.00'), quantity=10)

    def make_order(self, status, total=Decimal('200.00'), **kwargs):
        return Order.objects.create(
            buyer=self.buyer, product=self.product, variant=self.variant,
            total_price=total, status=status, **kwargs,
        )

    def give(self, amount):
        CoinTransaction.objects.create(user=self.buyer, kind='ADJUST', amount=amount, description='Teste')

class CashbackTests(RewardsTestCase):
    def test_completed_order_earns_cashback_once(self):
        self.make_order('COMPLETED')
        sync_wallet(self.buyer)
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 200)
        self.assertEqual(CoinTransaction.objects.filter(kind='PURCHASE').count(), 1)

    def test_delivered_order_waits_for_return_window(self):
        order = self.make_order('DELIVERED')
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 0)

        Order.objects.filter(pk=order.pk).update(updated_at=timezone.now() - timedelta(days=8))
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 200)

    def test_cashback_ignores_coin_discount(self):
        self.make_order('COMPLETED', coins_used=1000, coins_discount=Decimal('10.00'))
        sync_wallet(self.buyer)
        self.assertEqual(CoinTransaction.objects.get(kind='PURCHASE').amount, 190)

    def test_level_multiplier(self):
        self.make_order('COMPLETED', total=Decimal('600.00'))
        sync_wallet(self.buyer)
        self.assertEqual(level_info(self.buyer)['atual']['nome'], 'Prata')

        self.make_order('COMPLETED', total=Decimal('100.00'))
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 600 + 125)

class RedemptionTests(RewardsTestCase):
    def checkout(self, use_coins=True):
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product, variant=self.variant, quantity=1)
        self.client.force_login(self.buyer)
        self.client.post(reverse('checkout'), {'use_coins': '1'} if use_coins else {})
        return Order.objects.latest('pk')

    def test_redemption_is_capped_by_commission(self):
        self.give(5000)
        order = self.checkout()
        self.assertEqual(order.coins_used, 2000)
        self.assertEqual(order.coins_discount, Decimal('20.00'))
        self.assertEqual(balance(self.buyer), 3000)

    def test_redemption_limited_by_balance(self):
        self.give(150)
        order = self.checkout()
        self.assertEqual(order.coins_discount, Decimal('1.50'))
        self.assertEqual(balance(self.buyer), 0)

    def test_opt_out(self):
        self.give(150)
        order = self.checkout(use_coins=False)
        self.assertEqual(order.coins_used, 0)
        self.assertEqual(balance(self.buyer), 150)

    def test_cancelled_order_refunds_coins(self):
        self.give(500)
        order = self.checkout()
        order.status = 'CANCELLED'
        order.save()
        sync_wallet(self.buyer)
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 500)

    def test_cancelled_no_return_refunds_only_after_contest_window(self):
        self.give(500)
        order = self.checkout()
        order.status = 'CANCELLED_NO_RETURN'
        order.save()
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 0)

        Order.objects.filter(pk=order.pk).update(updated_at=timezone.now() - timedelta(days=8))
        sync_wallet(self.buyer)
        self.assertEqual(balance(self.buyer), 500)

class CheckinTests(RewardsTestCase):
    def backdate_checkin(self, dias_atras, moedas=5):
        dia = timezone.localdate() - timedelta(days=dias_atras)
        t = CoinTransaction.objects.create(
            user=self.buyer, kind='CHECKIN', amount=moedas, reference=f'checkin:{dia.isoformat()}', description='-',
        )
        CoinTransaction.objects.filter(pk=t.pk).update(created_at=timezone.now() - timedelta(days=dias_atras))

    def test_once_per_day(self):
        self.assertEqual(do_checkin(self.buyer), 5)
        self.assertIsNone(do_checkin(self.buyer))
        self.assertEqual(balance(self.buyer), 5)

    def test_streak_advances_and_resets(self):
        for dias_atras in (3, 2, 1):
            self.backdate_checkin(dias_atras)
        status = checkin_status(self.buyer)
        self.assertEqual(status['sequencia'], 3)
        self.assertEqual(status['recompensa'], 10)

        CoinTransaction.objects.filter(kind='CHECKIN').delete()
        self.backdate_checkin(2)
        self.assertEqual(checkin_status(self.buyer)['sequencia'], 0)

    def test_seventh_day_bonus_and_new_cycle(self):
        for dias_atras in range(6, 0, -1):
            self.backdate_checkin(dias_atras)
        self.assertEqual(do_checkin(self.buyer), 50)
        status = checkin_status(self.buyer)
        self.assertTrue(all(d['feito'] for d in status['dias']))

class ReviewRewardTests(RewardsTestCase):
    def test_first_review_rewarded(self):
        ProductReview.objects.create(product=self.product, reviewer=self.buyer, rating=Decimal('5.0'))
        self.assertEqual(balance(self.buyer), 20)

class AdminDashboardTests(RewardsTestCase):
    def setUp(self):
        super().setUp()
        self.staff = User.objects.create_user('staff', password='senha12345', is_staff=True)
        self.give(5000)
        order = self.make_order('COMPLETED', coins_used=2000, coins_discount=Decimal('20.00'))
        Commission.objects.create(
            order=order, rate=Decimal('10.00'), gross_amount=Decimal('200.00'),
            commission_amount=Decimal('20.00'), net_amount=Decimal('180.00'),
        )
        CoinTransaction.objects.create(user=self.buyer, order=order, kind='REDEEM', amount=-2000, description='-')
        self.make_order('COMPLETED')
        sync_wallet(self.buyer)
        self.client.force_login(self.staff)

    def test_program_metrics(self):
        m = self.client.get(reverse('admin_dashboard')).context['moedas']
        self.assertEqual(m['descontos'], Decimal('20.00'))
        self.assertEqual(m['comissao_liquida'], Decimal('0.00'))
        self.assertEqual(m['pedidos_com_moedas'], 1)
        self.assertEqual(m['emitidas'], 5000 + 180 + 200)
        self.assertEqual(m['resgatadas_liquidas'], 2000)
        self.assertEqual(m['em_circulacao'], 5000 - 2000 + 180 + 200)

    def test_pdf_builds(self):
        resposta = self.client.get(reverse('admin_dashboard_pdf'))
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertTrue(resposta.content.startswith(b'%PDF'))

class PageTests(RewardsTestCase):
    def test_wallet_and_orders_render(self):
        self.make_order('COMPLETED')
        self.make_order('SHIPPED')
        self.client.force_login(self.buyer)

        resposta = self.client.get(reverse('wallet'))
        self.assertContains(resposta, 'Check-in diário')
        self.assertEqual(resposta.context['previstas'], 200)

        resposta = self.client.get(reverse('my_orders'))
        self.assertContains(resposta, 'MegaCoins recebidas')
        self.assertContains(resposta, 'MegaCoins previstas')

    def test_checkout_shows_coin_option(self):
        self.give(300)
        cart = Cart.objects.create(user=self.buyer)
        CartItem.objects.create(cart=cart, product=self.product, variant=self.variant, quantity=1)
        self.client.force_login(self.buyer)
        resposta = self.client.get(reverse('checkout'))
        self.assertContains(resposta, 'Usar <strong>300 MegaCoins</strong>')
        self.assertContains(resposta, 'R$ 197,00')

    def test_review_form_shows_reward_hint(self):
        self.make_order('COMPLETED')
        self.client.force_login(self.buyer)
        resposta = self.client.get(reverse('review_product', args=[self.product.pk]))
        self.assertContains(resposta, 'Ganhe <strong>20 MegaCoins</strong>')

    def test_checkin_view(self):
        self.client.force_login(self.buyer)
        self.client.post(reverse('coin_checkin'))
        self.assertEqual(balance(self.buyer), 5)