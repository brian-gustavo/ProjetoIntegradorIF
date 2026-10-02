import random
from datetime import timedelta
from django.utils import timezone

DELIVERED_STATUSES = {
    'DELIVERED', 'RETURN_WINDOW', 'RETURN_REQUESTED', 'DISPUTE_OPEN',
    'RETURN_ACCEPTED', 'RETURNED', 'CANCELLED_NO_RETURN', 'COMPLETED',
}
TRACKABLE_STATUSES = DELIVERED_STATUSES | {'SHIPPED'}

CAPITAIS = {
    'AC': 'Rio Branco', 'AL': 'Maceió', 'AP': 'Macapá', 'AM': 'Manaus', 'BA': 'Salvador',
    'CE': 'Fortaleza', 'DF': 'Brasília', 'ES': 'Vitória', 'GO': 'Goiânia', 'MA': 'São Luís',
    'MT': 'Cuiabá', 'MS': 'Campo Grande', 'MG': 'Belo Horizonte', 'PA': 'Belém', 'PB': 'João Pessoa',
    'PR': 'Curitiba', 'PE': 'Recife', 'PI': 'Teresina', 'RJ': 'Rio de Janeiro', 'RN': 'Natal',
    'RS': 'Porto Alegre', 'RO': 'Porto Velho', 'RR': 'Boa Vista', 'SC': 'Florianópolis', 'SP': 'São Paulo',
    'SE': 'Aracaju', 'TO': 'Palmas',
}

CIDADES_PADRAO = [
    ('Campinas', 'SP'), ('Ribeirão Preto', 'SP'), ('Niterói', 'RJ'), ('Juiz de Fora', 'MG'),
    ('Londrina', 'PR'), ('Joinville', 'SC'), ('Caxias do Sul', 'RS'), ('Feira de Santana', 'BA'),
    ('Uberlândia', 'MG'), ('Campina Grande', 'PB'), ('Anápolis', 'GO'), ('Caruaru', 'PE'),
]

POSTADO, COLETA, TRANSFERENCIA, DISTRIBUICAO, SAIU, ENTREGUE = 0, 9, 28, 52, 70, 76
DURACAO_TOTAL = timedelta(hours=ENTREGUE)
PRAZO_POSTAGEM = timedelta(hours=24)

def _local(user):
    profile = getattr(user, 'profile', None)
    if profile and profile.city and profile.uf:
        return profile.city, profile.uf
    return CIDADES_PADRAO[user.pk % len(CIDADES_PADRAO)]

def _fmt(cidade, uf):
    return f'{cidade.upper()} - {uf}'

def _etapas(origem, destino):
    hub_origem = (CAPITAIS[origem[1]], origem[1])
    hub_destino = (CAPITAIS[destino[1]], destino[1])

    etapas = [
        (POSTADO, 'package', 'Objeto postado', [_fmt(*origem)]),
        (COLETA, 'truck', 'Objeto em transferência - por favor aguarde', [
            f'de Agência dos Correios, {_fmt(*origem)}',
            f'para Unidade de Tratamento, {_fmt(*hub_origem)}',
        ]),
    ]
    if hub_origem != hub_destino:
        etapas.append((TRANSFERENCIA, 'truck', 'Objeto em transferência - por favor aguarde', [
            f'de Unidade de Tratamento, {_fmt(*hub_origem)}',
            f'para Unidade de Tratamento, {_fmt(*hub_destino)}',
        ]))
    etapas += [
        (DISTRIBUICAO, 'truck', 'Objeto em transferência - por favor aguarde', [
            f'de Unidade de Tratamento, {_fmt(*hub_destino)}',
            f'para Unidade de Distribuição, {_fmt(*destino)}',
        ]),
        (SAIU, 'pin', 'Objeto saiu para entrega ao destinatário', [_fmt(*destino)]),
        (ENTREGUE, 'check', 'Objeto entregue ao destinatário', [_fmt(*destino)]),
    ]
    return etapas

def simulate_tracking(order):
    if order.pickup or not order.tracking_code or order.status not in TRACKABLE_STATUSES:
        return None

    rng = random.Random(order.pk)
    entregue = order.status in DELIVERED_STATUSES
    agora = timezone.now()

    if entregue:
        fim = order.updated_at if order.status == 'DELIVERED' else min(order.updated_at, order.created_at + PRAZO_POSTAGEM + DURACAO_TOTAL)
        postado_em = max(order.created_at, fim - DURACAO_TOTAL)
        escala = (fim - postado_em) / DURACAO_TOTAL
    else:
        fim = None
        postado_em = order.updated_at
        escala = 1

    eventos = []
    for horas, icone, titulo, linhas in _etapas(_local(order.product.seller), _local(order.buyer)):
        if horas == ENTREGUE and not entregue:
            continue
        if horas == ENTREGUE:
            momento = fim
        else:
            jitter = timedelta(minutes=rng.randint(0, 45)) if horas else timedelta(0)
            momento = postado_em + (timedelta(hours=horas) + jitter) * escala
        if momento > agora:
            break
        eventos.append({'titulo': titulo, 'linhas': linhas, 'momento': momento, 'icone': icone})

    return {
        'codigo': order.tracking_code,
        'entregue': entregue,
        'entregue_em': fim,
        'previsao': timezone.localtime(postado_em + DURACAO_TOTAL + timedelta(days=1)).date() if not entregue else None,
        'eventos': list(reversed(eventos)),
    }