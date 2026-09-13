# Projecto Nexxus — Estado

## Concluído
- Primeiro vertical slice funcional (Demanda → Plano → Operação → Execução → Resultado/Medição).
- Modelo de domínio alinhado com o Core Logística MVP: Etapa e Exceção como objetos próprios,
  Operação com estado Preparada, Plano com versão.
- `app.py` unificado com `nexxus_logistica.py` — deixou de existir uma segunda máquina de estados.
- Corrigido bug crítico em `create_replanned_plan` que impedia qualquer replaneamento na aplicação web.
  Ver README e Notion → Nexxus Logística, secção 12.
- Corrigidos campos da Demanda (`client`, `description`, `conditions`, `notes`) e do registo de
  Exceção (tipo/gravidade/descrição reais em vez de valores fixos).
- Corrigido caso limite: replanear sem exceção pendente já não rebenta com 500; devolve 400 tratado.
- Suite de testes de integração (`test_app.py`) a correr pedidos HTTP reais contra `app.py`.
- **Persistência em SQLite** (`storage.py`): o estado deixou de estar só em memória. Reiniciar o
  processo do servidor já não apaga demandas/operações em curso. Validado com um reinício real
  do processo via linha de comandos e com um teste dedicado que recarrega os dados directamente
  da base de dados.
- Suite de testes total: 11 (5 domínio + 6 integração/persistência).
- Documentação (README, PROGRESS, Notion) sincronizada com o estado real e validado do código.

## Próximo objetivo
- Avaliar se `Capacidade` deve tornar-se objeto próprio (hoje é atributo do Recurso — simplificação
  consciente do MVP, documentada no Notion, secção 11.2). É a última simplificação por resolver.
