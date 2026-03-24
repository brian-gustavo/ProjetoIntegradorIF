from django.apps import AppConfig

class AccountsConfig(AppConfig):
    DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
    
    name = 'accounts'
    verbose_name = 'Contas'