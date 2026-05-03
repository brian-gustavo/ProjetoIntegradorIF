from django.contrib.auth.models import User
from django.test import TestCase

class RegisterTest(TestCase):
    def test_cadastro_valido(self):
        response = self.client.post('/accounts/register/', {
            'username': 'exemplo',
            'email': 'exemplo@gmail.com',
            'password1': 'loremipsum123',
            'password2': 'loremipsum123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='testuser').exists())

    def test_email_duplicado(self):
        User.objects.create_user(username='exemplo1', email='exemplodois@gmail.com', password='321loremipsum')
        response = self.client.post('/accounts/register/', {
            'username': 'exemplo2',
            'email': 'exemplodois@gmail.com',
            'password1': 'loremipsum456',
            'password2': 'loremipsum456',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email='exemplodois@gmail.com').count(), 1)