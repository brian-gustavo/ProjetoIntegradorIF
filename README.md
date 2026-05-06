# ProjetoIntegradorIF

Este é o software desenvolvido como projeto integrador do curso de Análise e Desenvolvimento de Sistemas (ADS) do IFSP-CJO, sendo que é empregada a linguagem de programação Python com o *framework* Django para o back e o front-end (utilizando SSR), além da plataforma Supabase para o banco de dados.

É um marketplace customer-to-customer (C2C) voltado para jogos, sejam eles físicos, digitais ou até mesmo de tabuleiro, em adição à quaisquer periféricos ou outros itens relacionados. Seu nome é MegaGame.

*Produtos a serem vendidos:* Jogos físicos, consoles, acessórios para consoles, jogos de tabuleiro, keys para jogos digitais, itens *in-game*, pôsteres, *action figures* e *buttons*

*Requisitos faltantes:*
- Fazer uma separação maior entre admin e usuário comum (o admin não deve ser capaz de publicar anúncios, por exemplo)
- Colocar autocomplete nas buscas
- Implementar um sistema de avaliação de produtos, além do sistema já existente de vendedores (e mostrar tudo no front-end)
- Inserir a parte financeira do admin (implementar a comissão sobre as vendas, etc.)
    - Refletir a comissão no *dashboard* do vendedor (para mostrar o lucro real)
- Aprimorar o usuário para inserir mais campos (localização é a prioridade, mas dá pra pensar em outros)
    - Tirar a localização dos produtos
    - Definir a especificidade da localização
- Aprimorar a questão de estoque (possível variabilidade entre produtos, intermediar a compra e o fluxo de envio do produto, etc.)
    - Estoque só deve dar baixa após o produto ser entregue
    - Revisar o *dashboard* quanto ao produto com mais vendas (deve ser por unidade ou por lote comprado?)
- Detalhar melhor o fluxo de envio do produto (ao invés de criação do pedido -> pagamento -> confirmação de entrega, deve ser no mínimo criação do pedido -> pagamento -> verificação no estoque -> preparação do produto -> envio -> trajeto -> confirmação de entrega)
    - Considerar a criação de uma opção para cancelar um pedido; se não for possível, remover "Cancelado" do banco de dados
    - Tentar fazer um detalhamento na parte de trajeto (rastreio, previsão de entrega...)
    - A confirmação de entrega deve vir do comprador, não do vendedor
- Ao criar um anúncio, deve-se poder inserir todas as imagens (dentro do limite definido) simultaneamente a partir de um único ponto
    - Especificar a moeda a ser usada (será o real)
- Pedir para o usuário confirmar ações que sejam potencialmente danosas (publicar um anúncio, fazer uma compra...)
- Implementar um carrinho
- Descobrir o porquê da fixture não estar funcionando (será essencial fazer testes em maior escala)
- Deixar a tela das categorias mais esteticamente agradável
- Considerar a possibilidade do usuário editar anúncios (mas apenas o que não for potencialmente danoso!)
- Estudar exemplos reais mais a fundo para tentar descobrir outras lacunas

*Ideias pro segundo semestre:*
- Implementar aspectos secundários (gamificação, cupons de desconto, etc.)
- Implementar uma API de pagamento real (provavelmente Stripe)
- Estudar a possibilidade de permitir trocas na plataforma