# ProjetoIntegradorIF

Este é o software desenvolvido como projeto integrador do curso de Análise e Desenvolvimento de Sistemas (ADS) do IFSP-CJO, sendo que é empregada a linguagem de programação Python com o *framework* Django para o back e o front-end (utilizando SSR), além da plataforma Supabase para o banco de dados.

É um marketplace customer-to-customer (C2C) voltado para jogos, sejam eles físicos, digitais ou até mesmo de tabuleiro, em adição à quaisquer periféricos ou outros itens relacionados. Seu nome é MegaGame.

*Produtos a serem vendidos:* Jogos físicos, consoles, acessórios para consoles, jogos de tabuleiro, keys para jogos digitais, itens *in-game*, pôsteres, *action figures* e *buttons*

*Requisitos faltantes:*
- Implementar a edição de produtos/avaliações/etc.
    - Considerar um limite de edições em certas áreas (mudar a avaliação apenas uma vez, por exemplo)
    - Adicionar a opção de mudar a quantidade de um item que esteja no carrinho
    - Adicionar a opção de tirar um anúncio do ar após sua publicação

*Ideias pro segundo semestre:*
- Implementar aspectos secundários (gamificação, cupons de desconto, etc.)
- Implementar uma API de pagamento real (provavelmente Stripe)
- Estudar a possibilidade de permitir trocas na plataforma
- Estudar a melhor forma de povoar o banco para testes em larga escala (arquivo CSV?)
- Implementar os filtros de busca na pesquisa (localização, média de avaliação, preço...)
- Considerar mudanças para eventuais clientes internacionais (localização, preço, etc.)
- Implementar um sistema de disputa (talvez usar escrow também?)
- Permitir o uso de transportadoras além dos Correios