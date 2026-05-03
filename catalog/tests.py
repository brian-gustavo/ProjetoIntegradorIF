from django.contrib.auth.models import User
from django.test import TestCase

from .models import Category, Product, Stock

class ProductTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='vendedor', password='seller890')
        self.category = Category.objects.create(name='Jogos', slug='jogos')

    def test_criar_produto_autenticado(self):
        self.client.login(username='vendedor', password='seller890')
        response = self.client.post('/anuncios/novo/', {
            'title': 'GTA VI',
            'description': 'Jogo novo',
            'category': self.category.pk,
            'price': '300.00',
            'condition': 'NEW',
            'location': 'São Paulo/SP',
            'quantity': 1,
            'images-TOTAL_FORMS': '0',
            'images-INITIAL_FORMS': '0',
            'images-MIN_NUM_FORMS': '0',
            'images-MAX_NUM_FORMS': '5',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Product.objects.filter(title='GTA VI').exists())

    def test_criar_produto_sem_login(self):
        response = self.client.post('/anuncios/novo/', {})
        self.assertRedirects(response, '/accounts/login/?next=/anuncios/novo/')