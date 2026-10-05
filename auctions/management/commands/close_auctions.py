from django.core.management.base import BaseCommand

from auctions.models import Auction
from auctions.services import close_expired_auctions

class Command(BaseCommand):
    help = 'Encerra os leilões cujo prazo já terminou'

    def handle(self, *args, **options):
        antes = Auction.objects.filter(status='ACTIVE').count()
        close_expired_auctions()
        encerrados = antes - Auction.objects.filter(status='ACTIVE').count()
        self.stdout.write(self.style.SUCCESS(f'{encerrados} leilão(ões) encerrado(s).'))