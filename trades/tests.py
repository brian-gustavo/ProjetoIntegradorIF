from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from auctions.models import Auction
from auctions.services import publish as publish_auction
from catalog.models import Category, Product, ProductVariant
from orders.models import Commission, Order, PlatformConfig
from orders.views import _create_mp_preference, _finalize_delivery
from .models import OWNER, PROPOSER, TradeProposal
from .services import (
    accept, awaiting_count, cancel, counter, decline, expire_trades, inbox, mark_paid, propose, tradeable_variants, withdraw,
)

class TradeTestCase(TestCase):
    def setUp(self):
        self.ana = User.objects.create_user('ana', password='senha12345')
        self.bruno = User.objects.create_user('bruno', password='senha12345')
        self.carla = User.objects.create_user('carla', password='senha12345')
        self.category = Category.objects.create(name='Games', slug='games')
        PlatformConfig.objects.create(trade_fee=Decimal('0.00'))
        self.alvo = self.make_product(self.ana, 'Zelda', '200.00', accepts_trade=True)
        self.alvo_variant = self.alvo.variants.get()
        self.jogo = self.make_product(self.bruno, 'Mario', '150.00').variants.get()
        self.controle = self.make_product(self.bruno, 'Controle', '80.00').variants.get()

    def make_product(self, seller, title, price, quantity=1, **kwargs):
        product = Product.objects.create(
            category=self.category, seller=seller, title=title, description='-', published=True, **kwargs,
        )
        ProductVariant.objects.create(product=product, name='Padrão', price=Decimal(price), quantity=quantity)
        return product

    def propose(self, items=None, cash='0', payer='', user=None, product=None):
        product = product or self.alvo
        return propose(
            product.pk, user or self.bruno, product.variants.first().pk,
            [v.pk for v in (items or [self.jogo])], Decimal(cash), payer,
        )

class ProposeTests(TradeTestCase):
    def test_creates_pending_proposal_awaiting_owner(self):
        proposal, erro = self.propose(items=[self.jogo, self.controle], cash='20.00', payer=PROPOSER)
        self.assertIsNone(erro)
        self.assertEqual(proposal.status, 'PENDING')
        self.assertEqual(proposal.awaiting, OWNER)
        self.assertEqual(proposal.owner, self.ana)
        self.assertEqual(proposal.items.count(), 2)
        self.assertEqual(proposal.events.get().kind, 'PROPOSED')
        self.assertEqual(awaiting_count(self.ana), 1)
        self.assertEqual(awaiting_count(self.bruno), 0)

    def test_requires_listing_accepting_trades(self):
        outro = self.make_product(self.ana, 'Metroid', '100.00')
        _, erro = self.propose(product=outro)
        self.assertIn('não aceita', erro)

    def test_auction_never_accepts_trades(self):
        product = Product.objects.create(category=self.category, seller=self.ana, title='Raro', description='-', accepts_trade=True)
        publish_auction(product, Auction(start_price=Decimal('10.00'), duration_days=7))
        _, erro = self.propose(product=product)
        self.assertIn('não aceita', erro)

    def test_cannot_propose_on_own_listing(self):
        meu = self.make_product(self.ana, 'Pokémon', '90.00').variants.get()
        _, erro = propose(self.alvo.pk, self.ana, self.alvo_variant.pk, [meu.pk], Decimal('0'), '')
        self.assertIn('próprio anúncio', erro)

    def test_items_must_belong_to_proposer(self):
        da_carla = self.make_product(self.carla, 'Sonic', '50.00').variants.get()
        _, erro = self.propose(items=[da_carla])
        self.assertIn('não está mais disponível', erro)

    def test_requires_at_least_one_item(self):
        _, erro = propose(self.alvo.pk, self.bruno, self.alvo_variant.pk, [], Decimal('0'), '')
        self.assertIn('pelo menos um item', erro)

    def test_only_one_open_proposal_per_listing(self):
        self.propose()
        _, erro = self.propose(items=[self.controle])
        self.assertIn('já tem uma proposta', erro)

    def test_cash_from_proposer_must_be_below_listing_price(self):
        _, erro = self.propose(cash='200.00', payer=PROPOSER)
        self.assertIn('menor que o valor do anúncio', erro)

    def test_cash_from_owner_must_be_below_offered_value(self):
        _, erro = self.propose(cash='150.00', payer=OWNER)
        self.assertIn('valor de referência dos itens oferecidos', erro)

    def test_cash_requires_payer(self):
        _, erro = self.propose(cash='10.00', payer='')
        self.assertIn('quem paga', erro)

    def test_items_committed_to_accepted_trade_are_not_tradeable(self):
        proposal, _ = self.propose()
        accept(proposal.pk, self.ana)
        self.assertNotIn(self.jogo.pk, [v.pk for v in tradeable_variants(self.bruno)])

class NegotiationTests(TradeTestCase):
    def test_counter_flips_turn_and_extends_deadline(self):
        proposal, _ = self.propose()
        antes = proposal.expires_at
        resultado, erro = counter(proposal.pk, self.ana, [self.jogo.pk], Decimal('30.00'), PROPOSER)
        self.assertIsNone(erro)
        self.assertEqual(resultado.awaiting, PROPOSER)
        self.assertEqual(resultado.rounds, 2)
        self.assertGreaterEqual(resultado.expires_at, antes)
        self.assertEqual(awaiting_count(self.bruno), 1)

    def test_counter_must_change_terms(self):
        proposal, _ = self.propose()
        _, erro = counter(proposal.pk, self.ana, [self.jogo.pk], Decimal('0'), '')
        self.assertIn('precisa mudar', erro)

    def test_only_awaited_party_can_respond(self):
        proposal, _ = self.propose()
        _, erro = accept(proposal.pk, self.bruno)
        self.assertIn('não está aguardando', erro)
        _, erro = counter(proposal.pk, self.bruno, [self.controle.pk], Decimal('0'), '')
        self.assertIn('não está aguardando', erro)
        _, erro = accept(proposal.pk, self.carla)
        self.assertIn('não está aguardando', erro)

    def test_author_withdraws_but_awaited_party_declines(self):
        proposal, _ = self.propose()
        _, erro = withdraw(proposal.pk, self.ana)
        self.assertIsNotNone(erro)
        resultado, erro = withdraw(proposal.pk, self.bruno)
        self.assertIsNone(erro)
        self.assertEqual(resultado.status, 'WITHDRAWN')

    def test_decline_keeps_message(self):
        proposal, _ = self.propose()
        resultado, _ = decline(proposal.pk, self.ana, 'Já troquei')
        self.assertEqual(resultado.status, 'DECLINED')
        self.assertEqual(resultado.events.last().message, 'Já troquei')

    def test_expiration(self):
        proposal, _ = self.propose()
        TradeProposal.objects.filter(pk=proposal.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
        expire_trades()
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'EXPIRED')
        self.assertTrue(proposal.events.filter(kind='EXPIRED', author__isnull=True).exists())
        _, erro = accept(proposal.pk, self.ana)
        self.assertIsNotNone(erro)

class AcceptTests(TradeTestCase):
    def test_accept_without_cash_creates_paid_orders_for_both_sides(self):
        proposal, _ = self.propose(items=[self.jogo, self.controle])
        resultado, erro = accept(proposal.pk, self.ana)
        self.assertIsNone(erro)
        self.assertEqual(resultado.status, 'ACCEPTED')
        pedidos = Order.objects.filter(trade=proposal)
        self.assertEqual(pedidos.count(), 3)
        self.assertTrue(all(p.status == 'PAID' and p.total_price == 0 for p in pedidos))
        self.assertEqual(pedidos.get(product=self.alvo).buyer, self.bruno)
        self.assertEqual(set(pedidos.exclude(product=self.alvo).values_list('buyer', flat=True)), {self.ana.pk})

    def test_cash_goes_to_order_bought_by_payer(self):
        proposal, _ = self.propose(cash='40.00', payer=PROPOSER)
        accept(proposal.pk, self.ana)
        pedidos = Order.objects.filter(trade=proposal)
        self.assertTrue(all(p.status == 'PENDING' for p in pedidos))
        self.assertEqual(pedidos.get(buyer=self.bruno).total_price, Decimal('40.00'))
        self.assertEqual(pedidos.get(buyer=self.ana).total_price, Decimal('0.00'))

    def test_owner_paid_cash_attached_to_single_order(self):
        proposal, _ = self.propose(items=[self.jogo, self.controle], cash='20.00', payer=OWNER)
        accept(proposal.pk, self.ana)
        da_ana = Order.objects.filter(trade=proposal, buyer=self.ana)
        self.assertEqual(sum(p.total_price for p in da_ana), Decimal('20.00'))
        self.assertEqual(da_ana.filter(total_price__gt=0).count(), 1)

    def test_paying_cash_releases_every_order(self):
        proposal, _ = self.propose(cash='40.00', payer=PROPOSER)
        accept(proposal.pk, self.ana)
        volta = Order.objects.get(trade=proposal, buyer=self.bruno)
        mark_paid([str(volta.pk)])
        self.assertFalse(Order.objects.filter(trade=proposal, status='PENDING').exists())

    def test_accept_fails_when_item_became_unavailable(self):
        proposal, _ = self.propose()
        ProductVariant.objects.filter(pk=self.jogo.pk).update(quantity=0)
        _, erro = accept(proposal.pk, self.ana)
        self.assertIn('Mario', erro)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'PENDING')

    def test_proposer_accepts_counter(self):
        proposal, _ = self.propose()
        counter(proposal.pk, self.ana, [self.jogo.pk, self.controle.pk], Decimal('0'), '')
        resultado, erro = accept(proposal.pk, self.bruno)
        self.assertIsNone(erro)
        self.assertEqual(Order.objects.filter(trade=resultado).count(), 3)

    def test_cancel_before_shipping_cancels_all_orders(self):
        proposal, _ = self.propose()
        accept(proposal.pk, self.ana)
        resultado, erro = cancel(proposal.pk, self.bruno)
        self.assertIsNone(erro)
        self.assertEqual(resultado.status, 'CANCELLED')
        self.assertFalse(Order.objects.filter(trade=proposal).exclude(status='CANCELLED').exists())

    def test_cannot_cancel_after_shipping(self):
        proposal, _ = self.propose()
        accept(proposal.pk, self.ana)
        Order.objects.filter(trade=proposal, buyer=self.bruno).update(status='SHIPPED')
        _, erro = cancel(proposal.pk, self.ana)
        self.assertIsNotNone(erro)

    def test_zero_value_delivery_skips_commission(self):
        proposal, _ = self.propose(cash='40.00', payer=PROPOSER)
        accept(proposal.pk, self.ana)
        Order.objects.filter(trade=proposal).update(status='SHIPPED')
        for pedido in Order.objects.filter(trade=proposal):
            _finalize_delivery(pedido)
        self.assertEqual(Commission.objects.count(), 1)
        self.assertEqual(Commission.objects.get().gross_amount, Decimal('40.00'))
        self.alvo_variant.refresh_from_db()
        self.assertEqual(self.alvo_variant.quantity, 0)

    def test_inbox_groups(self):
        aceita, _ = self.propose()
        accept(aceita.pk, self.ana)
        outro = self.make_product(self.carla, 'Kirby', '60.00', accepts_trade=True)
        self.propose(product=outro, items=[self.controle])
        dados = inbox(self.bruno)
        self.assertEqual([p.pk for p in dados['andamento']], [aceita.pk])
        self.assertEqual(len(dados['aguardando']), 1)
        self.assertEqual(dados['sua_vez'], [])

class TradeFeeTests(TradeTestCase):
    def setUp(self):
        super().setUp()
        PlatformConfig.objects.update(trade_fee=Decimal('5.01'), commission_rate=Decimal('10.00'))

    def test_fee_is_split_between_sides(self):
        proposal, _ = self.propose(items=[self.jogo, self.controle])
        accept(proposal.pk, self.ana)
        do_bruno = Order.objects.get(trade=proposal, buyer=self.bruno)
        da_ana = Order.objects.filter(trade=proposal, buyer=self.ana)
        self.assertEqual(do_bruno.trade_fee, Decimal('2.51'))
        self.assertEqual(sum(p.trade_fee for p in da_ana), Decimal('2.50'))
        self.assertEqual(da_ana.filter(trade_fee__gt=0).count(), 1)
        self.assertTrue(all(p.status == 'PENDING' for p in Order.objects.filter(trade=proposal)))

    def test_orders_released_only_after_both_sides_pay(self):
        proposal, _ = self.propose(cash='40.00', payer=PROPOSER)
        accept(proposal.pk, self.ana)
        do_bruno = Order.objects.get(trade=proposal, buyer=self.bruno)
        da_ana = Order.objects.get(trade=proposal, buyer=self.ana)

        mark_paid([str(do_bruno.pk)])
        self.assertFalse(Order.objects.filter(trade=proposal).exclude(status='PENDING').exists())
        do_bruno.refresh_from_db()
        self.assertTrue(do_bruno.trade_paid)

        mark_paid([str(da_ana.pk)])
        self.assertFalse(Order.objects.filter(trade=proposal, status='PENDING').exists())

    def test_mp_preference_charges_cash_plus_fee(self):
        from unittest import mock
        proposal, _ = self.propose(cash='40.00', payer=PROPOSER)
        accept(proposal.pk, self.ana)
        pedido = Order.objects.get(trade=proposal, buyer=self.bruno)
        resposta = mock.Mock(status_code=201, json=lambda: {})
        with mock.patch('orders.views.requests.post', return_value=resposta) as post:
            _create_mp_preference(self.ana, [pedido], mock.Mock(access_token='x'), mock.Mock(build_absolute_uri=lambda u: u))
        corpo = post.call_args.kwargs['json']
        self.assertEqual(corpo['items'][0]['unit_price'], 42.51)
        self.assertEqual(corpo['marketplace_fee'], 6.51)

    def test_paid_part_cannot_be_paid_again(self):
        proposal, _ = self.propose()
        accept(proposal.pk, self.ana)
        pedido = Order.objects.get(trade=proposal, buyer=self.bruno)
        mark_paid([str(pedido.pk)])
        self.client.login(username='bruno', password='senha12345')
        resposta = self.client.get(reverse('resume_payment', args=[pedido.pk]))
        self.assertRedirects(resposta, reverse('trade_detail', args=[proposal.pk]))

    def test_zero_cash_trade_still_skips_commission_but_records_fee(self):
        proposal, _ = self.propose()
        accept(proposal.pk, self.ana)
        mark_paid(list(Order.objects.filter(trade=proposal).values_list('pk', flat=True)))
        for pedido in Order.objects.filter(trade=proposal):
            _finalize_delivery(pedido)
        self.assertFalse(Commission.objects.exists())

class TradeViewTests(TradeTestCase):
    def test_full_flow_through_views(self):
        self.client.login(username='bruno', password='senha12345')
        resposta = self.client.get(reverse('propose_trade', args=[self.alvo.pk]))
        self.assertContains(resposta, 'Mario')

        resposta = self.client.post(reverse('propose_trade', args=[self.alvo.pk]), {
            'variant': self.alvo_variant.pk, 'items': [self.jogo.pk], 'volta': 'eu', 'cash_amount': '25,50', 'message': 'Topa?',
        })
        proposal = TradeProposal.objects.get()
        self.assertRedirects(resposta, reverse('trade_detail', args=[proposal.pk]))
        self.assertEqual(proposal.cash_amount, Decimal('25.50'))
        self.assertEqual(proposal.cash_payer, PROPOSER)

        self.client.login(username='ana', password='senha12345')
        self.assertContains(self.client.get(reverse('trade_detail', args=[proposal.pk])), 'aguarda a sua resposta')
        resposta = self.client.post(reverse('counter_trade', args=[proposal.pk]), {
            'items': [self.jogo.pk, self.controle.pk], 'volta': 'nenhuma',
        })
        self.assertRedirects(resposta, reverse('trade_detail', args=[proposal.pk]))

        self.client.login(username='bruno', password='senha12345')
        self.client.post(reverse('trade_action', args=[proposal.pk]), {'acao': 'aceitar'})
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, 'ACCEPTED')
        self.assertContains(self.client.get(reverse('my_orders')), 'Troca #')
        self.assertContains(self.client.get(reverse('my_trades') + '?aba=andamento'), 'Zelda')

    def test_order_cancel_redirects_to_trade(self):
        proposal, _ = self.propose()
        accept(proposal.pk, self.ana)
        pedido = Order.objects.get(trade=proposal, buyer=self.bruno)
        self.client.login(username='bruno', password='senha12345')
        resposta = self.client.get(reverse('cancel_order_buyer', args=[pedido.pk]))
        self.assertRedirects(resposta, reverse('trade_detail', args=[proposal.pk]))
        pedido.refresh_from_db()
        self.assertEqual(pedido.status, 'PAID')

    def test_outsider_cannot_see_trade(self):
        proposal, _ = self.propose()
        self.client.login(username='carla', password='senha12345')
        self.assertRedirects(self.client.get(reverse('trade_detail', args=[proposal.pk])), reverse('home'))

    def test_pages_render(self):
        self.propose()
        self.client.login(username='ana', password='senha12345')
        for url in (reverse('trade_list'), reverse('product_detail', args=[self.alvo.pk]), reverse('home'), reverse('my_trades')):
            self.assertEqual(self.client.get(url).status_code, 200)
        self.assertContains(self.client.get(reverse('trade_list')), 'Zelda')
