# ProjetoIntegradorIF

Este é o software desenvolvido como projeto integrador do curso de Análise e Desenvolvimento de Sistemas (ADS) do IFSP-CJO, sendo que é empregada a linguagem de programação Python com o *framework* Django tanto para o back end quanto para o front end (utilizando SSR), além da plataforma Supabase para o banco de dados.

É um marketplace customer-to-customer (C2C) voltado para jogos, sejam eles físicos, digitais ou até mesmo de tabuleiro, em adição à quaisquer periféricos ou outros itens relacionados. Seu nome é MegaGame.

*Produtos a serem vendidos:* Jogos físicos, consoles, acessórios para consoles, jogos de tabuleiro, keys para jogos digitais, itens *in-game*, pôsteres, *action figures* e *bottons*

*Requisitos faltantes:*
- Criar manuais de uso para as páginas (serão embarcados no sistema)
- Consertar os problemas restantes da documentação e adicionar o que foi alterado após a última versão
- ADICIONAL, CASO DÊ TEMPO: Consertar e aprimorar os testes

*Correções:*
- Pesquisar sobre a API do MelhorEnvios para evitar o uso do rastreio simulado
- Fazer um tratamento mais abrangente e mais expositivo de erros (exemplo fornecido: falha de conexão com a API de pagamento)
- Inserir algumas stock images para serem usadas no seeding dos produtos (por exemplo, um mouse deve receber uma imagem de mouse)
- Integrar os cupons/gamificação/etc. aos dados de receita do site, para evitar prejuízo
- Estudar a questão do preço de venda mínimo (diferente do lance inicial) no leilão
- Considerar gastos externos (servidor, etc.) no setor financeiro-administrativo; seria ideal permitir adição manual de gastos pela staff
- Inserir um favicon.ico