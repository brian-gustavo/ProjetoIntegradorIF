from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from catalog.models import Category, Product
from orders.models import Order
from .forms import AuctionForm
from .models import Auction, Bid, SecondChanceOffer
from .services import (
    buy_now, can_relist, cancel_unpaid, close_expired_auctions, end_early, increment_for, place_bid, publish, relist,
    respond_second_chance, retract_bids, second_chance_candidates, send_second_chance,
)

class AuctionTestCase(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user('vendedor', password='senha12345')
        self.ana = User.objects.create_user('ana', password='senha12345')
        self.bruno = User.objects.create_user('bruno', password='senha12345')
        self.carla = User.objects.create_user('carla', password='senha12345')
        self.category = Category.objects.create(name='Consoles', slug='consoles')

    def make_auction(self, start='100.00', **kwargs):
        product = Product.objects.create(category=self.category, seller=self.seller, title='Console retrô', description='-')
        dados = {'start_price': Decimal(start), 'duration_days': 7}
        dados.update({k: Decimal(v) if isinstance(v, str) else v for k, v in kwargs.items()})
        return publish(product, Auction(**dados))

    def bid(self, auction, user, amount):
        resultado, erro = place_bid(auction.pk, user, Decimal(amount))
        auction.refresh_from_db()
        return resultado, erro

    def expire(self, auction):
        Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        close_expired_auctions()
        auction.refresh_from_db()

class ProxyBiddingTests(AuctionTestCase):
    def test_first_bid_keeps_start_price(self):
        auction = self.make_auction()
        resultado, erro = self.bid(auction, self.ana, '150.00')
        self.assertIsNone(erro)
        self.assertTrue(resultado['lider'])
        self.assertEqual(auction.current_price, Decimal('100.00'))
        self.assertEqual(auction.leader, self.ana)
        self.assertEqual(auction.product.variants.get().price, Decimal('100.00'))

    def test_lower_bid_is_outbid_by_proxy(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        resultado, _ = self.bid(auction, self.bruno, '120.00')
        self.assertFalse(resultado['lider'])
        self.assertEqual(auction.leader, self.ana)
        self.assertEqual(auction.current_price, Decimal('122.50'))
        self.assertTrue(auction.bids.filter(bidder=self.ana, is_auto=True, amount=Decimal('122.50')).exists())
        self.assertEqual(auction.bid_count, 3)

    def test_higher_bid_takes_lead_one_increment_above(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        resultado, _ = self.bid(auction, self.bruno, '200.00')
        self.assertTrue(resultado['lider'])
        self.assertEqual(auction.leader, self.bruno)
        self.assertEqual(auction.current_price, Decimal('152.50'))

    def test_price_capped_at_leader_max(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        self.bid(auction, self.bruno, '149.50')
        self.assertEqual(auction.current_price, Decimal('150.00'))
        self.assertEqual(auction.leader, self.ana)

    def test_tie_goes_to_earliest_bid(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        _, erro = self.bid(auction, self.bruno, '150.00')
        self.assertIsNone(erro)
        self.assertEqual(auction.leader, self.ana)
        self.assertEqual(auction.current_price, Decimal('150.00'))

    def test_minimum_bid_enforced(self):
        auction = self.make_auction()
        _, erro = self.bid(auction, self.ana, '99.99')
        self.assertIn('100,00', erro)
        self.bid(auction, self.ana, '150.00')
        self.bid(auction, self.bruno, '120.00')
        _, erro = self.bid(auction, self.carla, '123.00')
        self.assertIn('125,00', erro)

    def test_leader_can_only_raise_max(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        self.bid(auction, self.bruno, '120.00')
        _, erro = self.bid(auction, self.ana, '140.00')
        self.assertIn('150,00', erro)
        resultado, erro = self.bid(auction, self.ana, '300.00')
        self.assertIsNone(erro)
        self.assertTrue(resultado['aumentou'])
        self.assertEqual(auction.current_price, Decimal('122.50'))

    def test_seller_and_staff_cannot_bid(self):
        auction = self.make_auction()
        _, erro = self.bid(auction, self.seller, '150.00')
        self.assertIsNotNone(erro)
        staff = User.objects.create_user('equipe', password='senha12345', is_staff=True)
        _, erro = self.bid(auction, staff, '150.00')
        self.assertIsNotNone(erro)

    def test_increment_table(self):
        self.assertEqual(increment_for(Decimal('0.50')), Decimal('0.05'))
        self.assertEqual(increment_for(Decimal('24.99')), Decimal('0.50'))
        self.assertEqual(increment_for(Decimal('25.00')), Decimal('1.00'))
        self.assertEqual(increment_for(Decimal('6000.00')), Decimal('100.00'))

class ReserveAndBuyNowTests(AuctionTestCase):
    def test_reserve_jumps_price_when_met(self):
        auction = self.make_auction(reserve_price='300.00')
        self.bid(auction, self.ana, '200.00')
        self.assertEqual(auction.current_price, Decimal('100.00'))
        self.assertFalse(auction.reserve_met)
        self.bid(auction, self.ana, '350.00')
        self.assertEqual(auction.current_price, Decimal('300.00'))
        self.assertTrue(auction.reserve_met)

    def test_unsold_when_reserve_not_met(self):
        auction = self.make_auction(reserve_price='300.00')
        self.bid(auction, self.ana, '200.00')
        self.expire(auction)
        self.assertEqual(auction.status, 'UNSOLD')
        self.assertIsNone(auction.order)
        self.assertFalse(auction.product.published)

    def test_buy_now_disappears_after_first_bid(self):
        auction = self.make_auction(buy_now_price='200.00')
        self.assertTrue(auction.buy_now_available)
        self.bid(auction, self.ana, '110.00')
        self.assertFalse(auction.buy_now_available)
        order, erro = buy_now(auction.pk, self.bruno)
        self.assertIsNone(order)
        self.assertIsNotNone(erro)

    def test_buy_now_stays_until_reserve_met(self):
        auction = self.make_auction(reserve_price='150.00', buy_now_price='200.00')
        self.bid(auction, self.ana, '120.00')
        self.assertTrue(auction.buy_now_available)
        self.bid(auction, self.bruno, '160.00')
        self.assertFalse(auction.buy_now_available)

    def test_buy_now_creates_order(self):
        auction = self.make_auction(buy_now_price='200.00')
        order, erro = buy_now(auction.pk, self.ana)
        self.assertIsNone(erro)
        auction.refresh_from_db()
        self.assertEqual(auction.status, 'SOLD')
        self.assertTrue(auction.bought_now)
        self.assertEqual(order.total_price, Decimal('200.00'))
        self.assertEqual(order.variant.price, Decimal('200.00'))
        self.assertEqual(order.status, 'PENDING')

    def test_form_rules(self):
        form = AuctionForm({'start_price': '100', 'duration_days': 7, 'reserve_price': '90', 'buy_now_price': '120'})
        self.assertFalse(form.is_valid())
        self.assertIn('reserve_price', form.errors)
        self.assertIn('buy_now_price', form.errors)
        form = AuctionForm({'start_price': '100', 'duration_days': 7, 'reserve_price': '150', 'buy_now_price': '140'})
        self.assertFalse(form.is_valid())
        self.assertIn('buy_now_price', form.errors)
        form = AuctionForm({'start_price': '100', 'duration_days': 7, 'reserve_price': '150', 'buy_now_price': '180'})
        self.assertTrue(form.is_valid())

class ClosingTests(AuctionTestCase):
    def test_winner_gets_pending_order(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        self.bid(auction, self.bruno, '130.00')
        self.expire(auction)
        self.assertEqual(auction.status, 'SOLD')
        self.assertEqual(auction.winner, self.ana)
        self.assertEqual(auction.order.buyer, self.ana)
        self.assertEqual(auction.order.total_price, Decimal('132.50'))
        self.assertIsNotNone(auction.payment_due_at)

    def test_bidding_after_end_is_rejected(self):
        auction = self.make_auction()
        Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() - timedelta(seconds=1))
        _, erro = place_bid(auction.pk, self.ana, Decimal('150.00'))
        self.assertIsNotNone(erro)

    def test_end_early_rules(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() + timedelta(hours=5))
        _, erro = end_early(auction.pk, self.seller)
        self.assertIsNotNone(erro)
        Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() + timedelta(days=2))
        encerrado, erro = end_early(auction.pk, self.seller)
        self.assertIsNone(erro)
        self.assertEqual(encerrado.status, 'SOLD')
        self.assertTrue(encerrado.ended_early)

    def test_relist_clones_listing(self):
        auction = self.make_auction(reserve_price='300.00')
        self.expire(auction)
        novo = relist(auction)
        self.assertNotEqual(novo.pk, auction.product_id)
        self.assertEqual(novo.auction.reserve_price, Decimal('300.00'))
        self.assertEqual(novo.auction.status, 'ACTIVE')
        self.assertTrue(novo.published)

class AuctionViewTests(AuctionTestCase):
    def test_product_page_and_bid_flow(self):
        auction = self.make_auction(buy_now_price='200.00')
        url = reverse('product_detail', args=[auction.product_id])
        self.assertContains(self.client.get(url), 'Entre para dar um lance')

        self.client.login(username='ana', password='senha12345')
        self.assertContains(self.client.get(url), 'Comprar agora por R$ 200,00')
        self.client.post(reverse('place_bid', args=[auction.product_id]), {'amount': '150,00'})
        resposta = self.client.get(url)
        self.assertContains(resposta, 'Você é o maior lance.')
        self.assertNotContains(resposta, 'Comprar agora por')

        self.client.login(username='bruno', password='senha12345')
        self.client.post(reverse('place_bid', args=[auction.product_id]), {'amount': '120'})
        self.assertContains(self.client.get(url), 'Você foi superado.')

        historico = self.client.get(reverse('bid_history', args=[auction.product_id]))
        self.assertContains(historico, 'a***a')
        self.assertContains(historico, 'Lance automático')
        self.assertNotContains(historico, '150,00')

    def test_auction_listing_pages(self):
        auction = self.make_auction()
        self.assertContains(self.client.get(reverse('home')), 'Leilões terminando em breve')
        self.assertContains(self.client.get(reverse('auction_list')), 'Console retrô')
        self.assertContains(self.client.get(reverse('home'), {'q': 'Console', 'formato': 'leilao'}), 'Console retrô')
        self.assertNotContains(self.client.get(reverse('home'), {'q': 'Console', 'formato': 'imediata'}), 'product-card-title">Console')

        self.client.login(username='ana', password='senha12345')
        self.bid(auction, self.ana, '150.00')
        self.assertContains(self.client.get(reverse('my_bids')), 'Você é o maior lance')
        self.client.post(reverse('toggle_watch', args=[auction.product_id]))
        self.assertContains(self.client.get(reverse('my_bids'), {'aba': 'acompanhando'}), 'Console retrô')

    def test_cart_rejects_auction(self):
        auction = self.make_auction()
        self.client.login(username='ana', password='senha12345')
        self.client.post(reverse('add_to_cart', args=[auction.product_id]), {'variant_id': auction.product.variants.get().pk, 'quantity': 1})
        self.assertFalse(self.ana.cart.items.exists() if hasattr(self.ana, 'cart') else False)

    def test_create_auction_flow(self):
        self.client.login(username='vendedor', password='senha12345')
        resposta = self.client.post(reverse('create_product'), {
            'title': 'Cartucho raro', 'category': self.category.pk, 'description': '-', 'condition': 'USED', 'formato': 'leilao',
        })
        product = Product.objects.get(title='Cartucho raro')
        self.assertRedirects(resposta, reverse('setup_auction', args=[product.pk]))
        self.client.post(reverse('setup_auction', args=[product.pk]), {'start_price': '50', 'duration_days': 3})
        product.refresh_from_db()
        self.assertTrue(product.published)
        self.assertEqual(product.auction.current_price, Decimal('50.00'))
        self.assertEqual(product.variants.get().quantity, 1)

        edicao = self.client.get(reverse('edit_product', args=[product.pk]))
        self.assertContains(edicao, 'Preço de reserva')
        self.client.post(reverse('edit_product', args=[product.pk]), {
            'title': 'Cartucho raro', 'category': self.category.pk, 'description': '-', 'condition': 'USED',
            'start_price': '60', 'duration_days': 5,
        })
        product.auction.refresh_from_db()
        self.assertEqual(product.auction.current_price, Decimal('60.00'))
        self.assertEqual(product.auction.ends_at - product.auction.starts_at, timedelta(days=5))

    def test_winner_sees_payment(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        self.expire(auction)
        self.client.login(username='ana', password='senha12345')
        self.assertContains(self.client.get(reverse('product_detail', args=[auction.product_id])), 'Você arrematou este item!')
        self.assertContains(self.client.get(reverse('my_orders')), 'arrematou este item em leilão')
        self.client.login(username='vendedor', password='senha12345')
        self.assertContains(self.client.get(reverse('my_products')), 'Leilão vendido')

class RetractionTests(AuctionTestCase):
    def test_retraction_recalculates_price(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        self.bid(auction, self.bruno, '400.00')
        self.bid(auction, self.carla, '200.00')
        self.assertEqual(auction.leader, self.bruno)
        self.assertEqual(auction.current_price, Decimal('202.50'))

        resultado, erro = retract_bids(auction.pk, self.bruno, 'TYPO')
        auction.refresh_from_db()
        self.assertIsNone(erro)
        self.assertEqual(resultado['quantidade'], 1)
        self.assertEqual(auction.leader, self.carla)
        self.assertEqual(auction.current_price, Decimal('152.50'))
        self.assertFalse(auction.bids.filter(bidder=self.bruno, is_auto=True).exists())
        self.assertEqual(auction.bid_count, auction.bids.filter(retracted_at__isnull=True).count())

    def test_retracting_all_bids_reopens_buy_now(self):
        auction = self.make_auction(buy_now_price='200.00')
        self.bid(auction, self.ana, '120.00')
        self.bid(auction, self.ana, '130.00')
        retract_bids(auction.pk, self.ana, 'SELLER')
        auction.refresh_from_db()
        self.assertEqual(auction.bid_count, 0)
        self.assertIsNone(auction.leader)
        self.assertTrue(auction.buy_now_available)

    def test_late_retraction_only_last_hour_bid(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '120.00')
        Bid.objects.filter(auction=auction).update(created_at=timezone.now() - timedelta(hours=2))
        Auction.objects.filter(pk=auction.pk).update(ends_at=timezone.now() + timedelta(hours=5))
        _, erro = retract_bids(auction.pk, self.ana, 'TYPO')
        self.assertIsNotNone(erro)

        self.bid(auction, self.ana, '180.00')
        resultado, erro = retract_bids(auction.pk, self.ana, 'TYPO')
        auction.refresh_from_db()
        self.assertIsNone(erro)
        self.assertEqual(resultado['quantidade'], 1)
        self.assertEqual(auction.leader, self.ana)
        self.assertEqual(auction.bids.filter(bidder=self.ana, retracted_at__isnull=True).get().amount, Decimal('120.00'))

    def test_invalid_reason_rejected(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '120.00')
        _, erro = retract_bids(auction.pk, self.ana, 'QUALQUER')
        self.assertIsNotNone(erro)

    def test_retraction_view_and_history(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '150.00')
        self.client.login(username='ana', password='senha12345')
        url = reverse('retract_bid', args=[auction.product_id])
        self.assertContains(self.client.get(url), 'todos os seus lances')
        self.client.post(url, {'motivo': 'DESCRIPTION'})
        historico = self.client.get(reverse('bid_history', args=[auction.product_id]))
        self.assertContains(historico, 'Lances retirados')
        self.assertContains(historico, 'A descrição do item mudou significativamente')

class SecondChanceTests(AuctionTestCase):
    def unpaid_auction(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '200.00')
        self.bid(auction, self.carla, '120.00')
        self.bid(auction, self.bruno, '150.00')
        self.expire(auction)
        Auction.objects.filter(pk=auction.pk).update(payment_due_at=timezone.now() - timedelta(minutes=1))
        auction.refresh_from_db()
        cancel_unpaid(auction)
        auction.refresh_from_db()
        return auction

    def test_blocked_while_sale_in_progress(self):
        auction = self.make_auction()
        self.bid(auction, self.ana, '200.00')
        self.bid(auction, self.bruno, '150.00')
        self.expire(auction)
        _, erro = send_second_chance(auction.pk, self.seller, self.bruno.pk, 3)
        self.assertIsNotNone(erro)

    def test_offer_to_next_bidder_at_their_max(self):
        auction = self.unpaid_auction()
        candidatos = second_chance_candidates(auction)
        self.assertEqual([c['bidder'] for c in candidatos], [self.bruno, self.carla])
        self.assertEqual(candidatos[0]['preco'], Decimal('150.00'))

        offer, erro = send_second_chance(auction.pk, self.seller, self.bruno.pk, 3)
        self.assertIsNone(erro)
        self.assertFalse(can_relist(auction))
        _, erro = send_second_chance(auction.pk, self.seller, self.carla.pk, 3)
        self.assertIsNotNone(erro)

        offer, erro = respond_second_chance(offer.pk, self.bruno, True)
        self.assertIsNone(erro)
        auction.refresh_from_db()
        self.assertEqual(auction.winner, self.bruno)
        self.assertEqual(auction.order.total_price, Decimal('150.00'))
        self.assertEqual(auction.order.variant.price, Decimal('150.00'))
        self.assertEqual(offer.order, auction.order)

    def test_unpaid_buyers_never_reoffered(self):
        auction = self.unpaid_auction()
        offer, _ = send_second_chance(auction.pk, self.seller, self.bruno.pk, 3)
        respond_second_chance(offer.pk, self.bruno, True)
        Auction.objects.filter(pk=auction.pk).update(payment_due_at=timezone.now() - timedelta(minutes=1))
        auction.refresh_from_db()
        cancel_unpaid(auction)
        auction.refresh_from_db()
        self.assertEqual([c['bidder'] for c in second_chance_candidates(auction)], [self.carla])

    def test_reserve_not_met_allows_offer_to_leader(self):
        auction = self.make_auction(reserve_price='300.00')
        self.bid(auction, self.ana, '250.00')
        self.expire(auction)
        offer, erro = send_second_chance(auction.pk, self.seller, self.ana.pk, 1)
        self.assertIsNone(erro)
        self.assertEqual(offer.price, Decimal('250.00'))

    def test_expired_and_declined_offers(self):
        auction = self.unpaid_auction()
        offer, _ = send_second_chance(auction.pk, self.seller, self.bruno.pk, 1)
        SecondChanceOffer.objects.filter(pk=offer.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        close_expired_auctions()
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'EXPIRED')
        _, erro = respond_second_chance(offer.pk, self.bruno, True)
        self.assertIsNotNone(erro)

        offer, _ = send_second_chance(auction.pk, self.seller, self.carla.pk, 1)
        respond_second_chance(offer.pk, self.carla, False)
        offer.refresh_from_db()
        self.assertEqual(offer.status, 'DECLINED')
        self.assertTrue(can_relist(auction))

    def test_views(self):
        auction = self.unpaid_auction()
        self.client.login(username='vendedor', password='senha12345')
        self.assertContains(self.client.get(reverse('product_detail', args=[auction.product_id])), 'Enviar oferta de segunda chance')
        self.client.post(reverse('second_chance', args=[auction.product_id]), {'bidder': self.bruno.pk, 'duration_days': 3})
        offer = SecondChanceOffer.objects.get()

        self.client.login(username='bruno', password='senha12345')
        self.assertContains(self.client.get(reverse('product_detail', args=[auction.product_id])), 'oferta de segunda chance')
        self.assertContains(self.client.get(reverse('my_bids'), {'aba': 'ofertas'}), 'Aguardando sua resposta')
        resposta = self.client.post(reverse('respond_offer', args=[offer.pk]), {'acao': 'aceitar'})
        offer.refresh_from_db()
        self.assertRedirects(resposta, reverse('resume_payment', args=[offer.order_id]), fetch_redirect_response=False)
        self.assertContains(self.client.get(reverse('my_orders')), 'oferta de segunda chance')

class DashboardTests(AuctionTestCase):
    def test_auction_metrics_and_pdf(self):
        vendido = self.make_auction()
        self.bid(vendido, self.ana, '200.00')
        self.bid(vendido, self.bruno, '150.00')
        self.expire(vendido)
        sem_lances = self.make_auction()
        self.expire(sem_lances)
        ativo = self.make_auction()
        self.bid(ativo, self.carla, '130.00')
        retract_bids(ativo.pk, self.carla, 'TYPO')

        User.objects.create_user('equipe', password='senha12345', is_staff=True)
        self.client.login(username='equipe', password='senha12345')
        resposta = self.client.get(reverse('admin_dashboard'))
        leiloes = resposta.context['leiloes']
        self.assertEqual(leiloes['encerrados'], 2)
        self.assertEqual(leiloes['vendidos'], 1)
        self.assertEqual(leiloes['taxa_venda'], 50.0)
        self.assertEqual(leiloes['retirados'], 1)
        self.assertEqual(leiloes['ativos_agora'], 1)
        self.assertAlmostEqual(leiloes['valorizacao_media'], 52.5)
        self.assertContains(resposta, 'Sem venda: nenhum lance')

        pdf = self.client.get(reverse('admin_dashboard_pdf'))
        self.assertEqual(pdf['Content-Type'], 'application/pdf')