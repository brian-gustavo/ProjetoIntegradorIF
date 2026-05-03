from django.contrib.auth.models import User
from django.test import TestCase

from .models import Order
from catalog.models import Category, Product, Stock

class OrderTest(TestCase):
    def setUp(self):
        self.vendedor = User.objects.create_user(username='vendedor', password='seller890')
        self.comprador = User.objects.create_user(username='comprador', password='buyer890')
        category = Category.objects.create(name='Jogos', slug='jogos')
        self.product = Product.objects.create(
            title='GTA VI',
            description='Jogo novo',
            category=category,
            seller=self.vendedor,
            price=300,
            condition='NEW',
            location='SP',
        )
        Stock.objects.create(product=self.product, quantity=5)

    def test_realizar_pedido(self):
        self.client.login(username='comprador', password='buyer890')
        response = self.client.post(f'/pedidos/novo/{self.product.pk}/', {'quantity': 2})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(buyer=self.comprador).exists())

    def test_vendedor_nao_pode_comprar_proprio_produto(self):
        self.client.login(username='vendedor', password='seller890')
        self.client.post(f'/pedidos/novo/{self.product.pk}/', {'quantity': 1})
        self.assertFalse(Order.objects.exists())

    def test_estoque_decrementado_apos_pagamento(self):
        self.client.login(username='comprador', password='buyer890')
        self.client.post(f'/pedidos/novo/{self.product.pk}/', {'quantity': 2})
        order = Order.objects.get(buyer=self.comprador)
        self.client.post(f'/pedidos/{order.pk}/pagar/')
        self.product.stock.refresh_from_db()
        self.assertEqual(self.product.stock.quantity, 3)