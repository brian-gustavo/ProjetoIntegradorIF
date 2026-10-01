from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.graphics.charts.barcharts import HorizontalBarChart
from reportlab.graphics.charts.linecharts import HorizontalLineChart
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from catalog.templatetags.catalog_extras import brl

VERDE = colors.HexColor('#22c55e')
PRETO = colors.HexColor('#0a0a0a')
CINZA = colors.HexColor('#737373')
CINZA_CLARO = colors.HexColor('#f4f4f4')
CINZA_BORDA = colors.HexColor('#d1d1d1')

LARGURA_UTIL = A4[0] - 4 * cm

estilos = getSampleStyleSheet()
TITULO = ParagraphStyle('Titulo', parent=estilos['Title'], fontName='Helvetica-Bold', fontSize=20, textColor=PRETO, alignment=0, spaceAfter=4)
SUBTITULO = ParagraphStyle('Subtitulo', parent=estilos['Normal'], fontSize=9, textColor=CINZA, leading=13)
SECAO = ParagraphStyle('Secao', parent=estilos['Heading2'], fontName='Helvetica-Bold', fontSize=13, textColor=PRETO, spaceBefore=18, spaceAfter=8)
NOTA = ParagraphStyle('Nota', parent=estilos['Normal'], fontSize=8, textColor=CINZA, leading=11, spaceAfter=6)
CELULA = ParagraphStyle('Celula', parent=estilos['Normal'], fontSize=8.5, leading=11)
CELULA_DIREITA = ParagraphStyle('CelulaDireita', parent=CELULA, alignment=TA_RIGHT)

def _reais(valor):
    return f'R$ {brl(valor)}'

def _pct(valor, casas=1):
    return f'{valor:.{casas}f}%'.replace('.', ',')

def _variacao(valor, sufixo='%', inverso=False):
    if valor is None:
        return '—'
    sinal = '+' if valor >= 0 else '-'
    cor = '#16a34a' if (valor >= 0) != inverso else '#ef4444'
    texto = f'{sinal}{abs(valor):.1f}'.replace('.', ',') + sufixo
    return Paragraph(f'<font color="{cor}">{texto}</font>', CELULA_DIREITA)

def _tabela(cabecalho, linhas, larguras, alinhar_direita=(), destacar_ultima=False):
    tabela = Table([cabecalho] + linhas, colWidths=larguras, repeatRows=1)
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), PRETO),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8.5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LINEBELOW', (0, 1), (-1, -1), 0.5, CINZA_BORDA),
        ('BOX', (0, 0), (-1, -1), 1, PRETO),
    ]
    for coluna in alinhar_direita:
        estilo.append(('ALIGN', (coluna, 0), (coluna, -1), 'RIGHT'))
    if destacar_ultima:
        estilo += [
            ('BACKGROUND', (0, -1), (-1, -1), CINZA_CLARO),
            ('TEXTCOLOR', (0, -1), (-1, -1), CINZA),
        ]
    tabela.setStyle(TableStyle(estilo))
    return tabela

def _grafico_serie(serie):
    desenho = Drawing(LARGURA_UTIL, 170)
    grafico = HorizontalLineChart()
    grafico.x, grafico.y = 45, 35
    grafico.width, grafico.height = LARGURA_UTIL - 60, 120
    grafico.data = [serie['valores']]

    passo = max(1, len(serie['labels']) // 12)
    grafico.categoryAxis.categoryNames = [
        label if i % passo == 0 else '' for i, label in enumerate(serie['labels'])
    ]
    grafico.categoryAxis.labels.fontSize = 7
    grafico.categoryAxis.labels.fontName = 'Helvetica'
    grafico.valueAxis.labels.fontName = 'Helvetica'
    grafico.categoryAxis.labels.angle = 45
    grafico.categoryAxis.labels.boxAnchor = 'ne'
    grafico.valueAxis.valueMin = 0
    grafico.valueAxis.labels.fontSize = 7
    grafico.valueAxis.labelTextFormat = lambda v: brl(v).split(',')[0]
    grafico.lines[0].strokeColor = VERDE
    grafico.lines[0].strokeWidth = 2
    desenho.add(grafico)
    return desenho

def _grafico_categorias(categorias):
    altura = 30 + 18 * len(categorias)
    desenho = Drawing(LARGURA_UTIL, altura)
    grafico = HorizontalBarChart()
    grafico.x, grafico.y = 110, 15
    grafico.width, grafico.height = LARGURA_UTIL - 130, altura - 25
    grafico.data = [[float(c['gmv']) for c in reversed(categorias)]]
    grafico.categoryAxis.categoryNames = [c['categoria'] for c in reversed(categorias)]
    grafico.categoryAxis.labels.fontSize = 8
    grafico.categoryAxis.labels.fontName = 'Helvetica'
    grafico.valueAxis.labels.fontName = 'Helvetica'
    grafico.valueAxis.valueMin = 0
    grafico.valueAxis.labels.fontSize = 7
    grafico.valueAxis.labelTextFormat = lambda v: brl(v).split(',')[0]
    grafico.bars[0].fillColor = VERDE
    grafico.bars[0].strokeColor = None
    desenho.add(grafico)
    return desenho

def _rodape(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 7.5)
    canvas.setFillColor(CINZA)
    canvas.drawString(2 * cm, 1.2 * cm, 'MegaGame — Relatório administrativo')
    canvas.drawRightString(A4[0] - 2 * cm, 1.2 * cm, f'Página {doc.page}')
    canvas.restoreState()

def _secao_visao_geral(d):
    linhas = [
        ['GMV', _reais(d['gmv_atual']), _variacao(d['gmv_variacao'])],
        ['Comissão', _reais(d['comissao_periodo']), _variacao(d['comissao_variacao'])],
        ['Pedidos concluídos', str(d['pedidos_periodo']), _variacao(d['pedidos_variacao'])],
        ['Ticket médio', _reais(d['ticket_medio']), _variacao(d['ticket_medio_variacao'])],
    ]
    elementos = [
        Paragraph('Visão geral do período', SECAO),
        _tabela(['Indicador', 'Valor', 'Variação'], linhas, [LARGURA_UTIL * 0.5, LARGURA_UTIL * 0.3, LARGURA_UTIL * 0.2], (1, 2)),
    ]
    if d['serie']['valores']:
        elementos += [Spacer(1, 10), Paragraph('GMV ao longo do período', NOTA), _grafico_serie(d['serie'])]

    historico = [
        ['Vendas concluídas (unidades)', str(d['total_vendas'])],
        ['Total transacionado', _reais(d['total_transacionado'])],
        ['Total em comissões', _reais(d['total_comissao'])],
    ]
    elementos += [
        Paragraph('Histórico acumulado da plataforma', SECAO),
        _tabela(['Indicador', 'Valor'], historico, [LARGURA_UTIL * 0.7, LARGURA_UTIL * 0.3], (1,)),
    ]
    return elementos

def _secao_ranking(d):
    ranking = d['ranking']
    elementos = [Paragraph('Ranking de vendedores', SECAO)]
    c = ranking['concentracao']
    if not c:
        return elementos + [Paragraph('Nenhuma venda concluída no período.', NOTA)]

    resumo = [
        ['Vendedores com vendas', str(c['ativos']), '—'],
        ['Participação do líder', _pct(c['top1']), '—'],
        ['Participação do top 5', _pct(c['top5']), _variacao(c['top5_diferenca'], ' p.p.', inverso=True)],
        [f'Top 20% dos vendedores ({c["pareto_n"]})', _pct(c['pareto']), _variacao(c['pareto_diferenca'], ' p.p.', inverso=True)],
        [f'Índice HHI (concentração {c["nivel"]})', f'{c["hhi"]:.0f}',
         f'{c["hhi_anterior"]:.0f} no anterior' if c['hhi_anterior'] is not None else '—'],
    ]
    elementos.append(_tabela(['Concentração de receita', 'Valor', 'Variação'], resumo,
                             [LARGURA_UTIL * 0.5, LARGURA_UTIL * 0.25, LARGURA_UTIL * 0.25], (1, 2)))
    elementos.append(Spacer(1, 10))

    linhas = [
        [str(v['posicao']), Paragraph(escape(v['vendedor']), CELULA), str(v['pedidos']), _reais(v['gmv']),
         _reais(v['comissao']), _reais(v['ticket_medio']), _pct(v['participacao']), _pct(v['acumulado'])]
        for v in ranking['linhas']
    ]
    demais = ranking['demais']
    if demais:
        linhas.append(['', f'Demais {demais["quantidade"]}', str(demais['pedidos']), _reais(demais['gmv']),
                       _reais(demais['comissao']), '—', _pct(demais['participacao']), '100,0%'])

    larguras = [0.05, 0.19, 0.09, 0.15, 0.13, 0.13, 0.13, 0.13]
    elementos.append(_tabela(
        ['#', 'Vendedor', 'Pedidos', 'GMV', 'Comissão', 'Ticket', 'Particip.', 'Acum.'],
        linhas, [LARGURA_UTIL * l for l in larguras], (2, 3, 4, 5, 6, 7), destacar_ultima=bool(demais),
    ))
    return elementos

def _secao_categorias(d):
    categorias = d['categorias']
    elementos = [Paragraph('Vendas por categoria', SECAO)]
    if not categorias:
        return elementos + [Paragraph('Nenhuma venda concluída no período.', NOTA)]

    linhas = [
        [c['categoria'], str(c['pedidos']), _reais(c['gmv']), _reais(c['ticket_medio']),
         _pct(c['participacao']), _variacao(c['variacao'])]
        for c in categorias
    ]
    larguras = [0.28, 0.1, 0.18, 0.16, 0.13, 0.15]
    return [KeepTogether(elementos + [_grafico_categorias(categorias)]), Spacer(1, 10), _tabela(
        ['Categoria', 'Pedidos', 'GMV', 'Ticket médio', 'Particip.', 'Variação'],
        linhas, [LARGURA_UTIL * l for l in larguras], (1, 2, 3, 4, 5),
    )]

def _secao_saude(d):
    s = d['saude']
    linhas = [
        ['Taxa de cancelamento', f'{_pct(s["taxa_cancelamento"])} ({s["cancelados"]})', _variacao(s['taxa_cancelamento_diferenca'], ' p.p.', inverso=True)],
        ['Taxa de devolução', f'{_pct(s["taxa_devolucao"])} ({s["devolucoes"]})', _variacao(s['taxa_devolucao_diferenca'], ' p.p.', inverso=True)],
        ['Taxa de disputa', f'{_pct(s["taxa_disputa"])} ({s["disputas"]})', _variacao(s['taxa_disputa_diferenca'], ' p.p.', inverso=True)],
        ['Disputas em aberto agora', str(d['disputas_abertas_agora']), '—'],
        ['Disputas resolvidas no período', str(s['disputas_resolvidas']), '—'],
    ]
    if s['disputas_resolvidas']:
        linhas += [
            ['Tempo médio de resolução', f'{s["tempo_medio_resolucao"]:.1f} dias'.replace('.', ','), '—'],
            ['Resolvidas a favor do comprador', f'{_pct(s["pct_favor_comprador"], 0)} ({s["favor_comprador"]} × {s["favor_vendedor"]})', '—'],
        ]

    elementos = [
        Paragraph('Saúde operacional', SECAO),
        Paragraph(f'Taxas calculadas sobre os {s["pedidos"]} pedidos criados no período (exceto os que ainda aguardam pagamento).', NOTA),
        _tabela(['Indicador', 'Valor', 'Variação'], linhas, [LARGURA_UTIL * 0.5, LARGURA_UTIL * 0.3, LARGURA_UTIL * 0.2], (1, 2)),
    ]

    if s['motivos']:
        motivos = [[Paragraph(escape(m['motivo']), CELULA), str(m['disputas']), _pct(m['participacao'])] for m in s['motivos']]
        elementos += [
            Spacer(1, 10),
            _tabela(['Motivo das disputas abertas no período', 'Disputas', 'Particip.'], motivos,
                    [LARGURA_UTIL * 0.6, LARGURA_UTIL * 0.2, LARGURA_UTIL * 0.2], (1, 2)),
        ]
    return elementos

def _secao_compradores(d):
    c = d['compradores']
    linhas = [
        ['Novos', str(c['novos']['compradores']), _reais(c['novos']['gmv']), _reais(c['novos']['gmv_por_comprador']), _variacao(c['novos_variacao'])],
        ['Recorrentes', str(c['recorrentes']['compradores']), _reais(c['recorrentes']['gmv']), _reais(c['recorrentes']['gmv_por_comprador']), _variacao(c['recorrentes_variacao'])],
        ['Total', str(c['ativos']), _reais(c['novos']['gmv'] + c['recorrentes']['gmv']), '—', '—'],
    ]
    larguras = [0.2, 0.17, 0.23, 0.23, 0.17]
    return [KeepTogether([
        Paragraph('Compradores novos vs. recorrentes', SECAO),
        Paragraph('"Novo" é o comprador cuja primeira compra concluída na plataforma aconteceu dentro do período.', NOTA),
        _tabela(['Grupo', 'Compradores', 'GMV', 'GMV/comprador', 'Variação'], linhas,
                [LARGURA_UTIL * l for l in larguras], (1, 2, 3, 4), destacar_ultima=True),
        Spacer(1, 6),
        Paragraph(
            f'Taxa de recorrência: <b>{_pct(c["pct_recorrentes"])}</b> dos compradores, '
            f'responsáveis por <b>{_pct(c["pct_gmv_recorrentes"])}</b> do GMV.', CELULA,
        ),
    ])]

def _secao_configuracoes(d):
    config = d['config']
    linhas = [
        ['Taxa de comissão', _pct(config.commission_rate, 2)],
        ['Prazo para solicitar devolução após a entrega', f'{config.return_window_days} dias'],
        ['Prazo para contestar cancelamento sem devolução', f'{config.dispute_window_days} dias'],
        ['Vendedores exibidos no ranking', str(config.ranking_size)],
        ['Motivos de disputa', Paragraph('<br/>'.join(escape(m) for m in config.dispute_reason_list()), CELULA)],
    ]
    return [KeepTogether([
        Paragraph('Configurações vigentes', SECAO),
        _tabela(['Configuração', 'Valor'], linhas, [LARGURA_UTIL * 0.55, LARGURA_UTIL * 0.45]),
    ])]

def build_admin_report_pdf(data, periodo):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title='Relatório administrativo — MegaGame', author='MegaGame',
    )

    agora = timezone.localtime()
    elementos = [
        Paragraph('MegaGame — Relatório administrativo', TITULO),
        Paragraph(
            f'Período: {periodo["inicio"]:%d/%m/%Y} a {periodo["fim"]:%d/%m/%Y} ({periodo["dias"]} dias) · '
            f'comparado a {periodo["inicio_anterior"]:%d/%m/%Y} a {periodo["fim_anterior"]:%d/%m/%Y}<br/>'
            f'Gerado em {agora:%d/%m/%Y às %H:%M}', SUBTITULO,
        ),
    ]
    for secao in (_secao_visao_geral, _secao_ranking, _secao_categorias, _secao_saude, _secao_compradores, _secao_configuracoes):
        elementos += secao(data)

    doc.build(elementos, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
