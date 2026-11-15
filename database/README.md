# Database Model
Este diretório contém todos os arquivos relacionados ao modelo de banco de dados do projeto Finance Data Platform.
O objetivo é manter documentado o schema, registrar decisões de design e facilitar a manutenção futura.

## Arquivos incluídos

- model.mwb — modelo visual criado no MySQL Workbench.

- model.png — Modelo visual (Caso não queria abrir o Workbench)

- schema.sql — script contendo apenas a estrutura do banco (dump sem dados).


## Arquitetura do Banco de Dados

A modelagem atual é composta por:

1. User

Representa o dono da carteira.
Neste MVP, o User não possui senha, pois:

o CRUD é inicialmente acadêmico e não exposto a usuários reais;

a autenticação ficará em outro módulo no futuro;

evita complexidade desnecessária nessa fase do projeto.

2. Wallet

Cada usuário pode ter uma ou mais carteiras, permitindo investimentos separados por estratégia.

Cardinalidade:

Um User → N Wallet (1:N)

3. Asset

Tabela de ativos cadastrados no sistema.
Inclui ações, FIIs, ETFs etc.

4. Wallet_Transaction

Histórico de transações da carteira.

Essa tabela elimina o problema da duplicidade que ocorreria se uma carteira tivesse apenas um registro por ativo.
Aqui, cada compra/venda é registrada individualmente, mantendo:

- quantidade
- preço médio da operação
- data da trade
- tipo (BUY/SELL)

Cardinalidade:

Uma Wallet → N Wallet_Transaction

Um Asset → N Wallet_Transaction
(Relacionamento N:N resolvido via tabela própria)

## Decisões importantes de modelagem
### ON DELETE CASCADE

Foi aplicado para que exclusões mantenham o banco limpo automaticamente:

- apagar um usuário apaga suas carteiras

- apagar uma carteira apaga suas transações

- apagar um ativo apaga suas transações relacionadas

### ON UPDATE NO ACTION

Mantido por simplicidade e segurança, já que IDs nunca devem ser alterados após criados.