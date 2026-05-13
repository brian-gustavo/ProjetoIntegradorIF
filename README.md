# ProjetoIntegradorIF

Este é o software desenvolvido como projeto integrador do curso de Análise e Desenvolvimento de Sistemas (ADS) do IFSP-CJO, sendo que é empregada a linguagem de programação Python com o *framework* Django para o back e o front-end (utilizando SSR), além da plataforma Supabase para o banco de dados.

É um marketplace customer-to-customer (C2C) voltado para jogos, sejam eles físicos, digitais ou até mesmo de tabuleiro, em adição à quaisquer periféricos ou outros itens relacionados. Seu nome é MegaGame.

*Produtos a serem vendidos:* Jogos físicos, consoles, acessórios para consoles, jogos de tabuleiro, keys para jogos digitais, itens *in-game*, pôsteres, *action figures* e *buttons*

*Requisitos faltantes:*
- Implementar os filtros de busca na pesquisa (localização, média de avaliação, preço...)
- Inserir a parte financeira do admin (implementar a comissão sobre as vendas, etc.)
    - Refletir a comissão no *dashboard* do vendedor (para mostrar o lucro real)
- Aprimorar a questão de estoque (possível variabilidade entre produtos, intermediar a compra e o fluxo de envio do produto, etc.)
    - Assegurar que o estoque só deve dar baixa após o produto ser entregue
    - Revisar o *dashboard* quanto ao produto com mais vendas (deve ser por unidade ou por lote comprado?)
- Detalhar melhor o fluxo de envio do produto (ao invés de criação do pedido -> pagamento -> confirmação de entrega, deve ser no mínimo criação do pedido -> pagamento -> verificação no estoque -> preparação do produto -> envio -> trajeto -> confirmação de entrega)
    - Considerar a criação de uma opção para cancelar um pedido (aproveitando que existe a opção no banco)
    - Tentar fazer um detalhamento na parte de trajeto (rastreio, previsão de entrega...)
    - Assegurar que a confirmação de entrega deve vir do comprador, não do vendedor
- Implementar a edição de anúncios/avaliações/etc.
    - Considerar um limite de edições (mudar a avaliação apenas uma vez, por exemplo)
    - Deve haver uma opção de mudar a quantidade de um item que esteja no carrinho
- Inserir um limite de MB em imagens inseridas pelos usuários
- Mudar o autocomplete para detectar a partir de três ou quatro letras
- Fazer a validação da quantidade quando o usuário for adicionar algo ao carrinho (atualmente, pode-se inserir manualmente um número que seja maior que o estoque e o sistema não valida isso)

*Ideias pro segundo semestre:*
- Implementar aspectos secundários (gamificação, cupons de desconto, etc.)
- Implementar uma API de pagamento real (provavelmente Stripe)
- Estudar a possibilidade de permitir trocas na plataforma
- Estudar a melhor forma de povoar o banco para testes em larga escala (arquivo CSV?)