from django.apps import AppConfig

class RewardsConfig(AppConfig):
    DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

    name = 'rewards'
    verbose_name = 'MegaCoins'

    def ready(self):
        from . import signals  # noqa: F401