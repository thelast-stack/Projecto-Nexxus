# Projecto Nexxus — Estado

## Concluído
- Primeiro vertical slice funcional (Demanda → Plano → Operação → Execução → Resultado/Medição).
- Modelo de domínio alinhado com o Core Logística MVP: Etapa, Exceção e agora Capacidade como
  objetos próprios; Operação com estado Preparada; Plano com versão.
- `app.py` unificado com `nexxus_logistica.py` — deixou de existir uma segunda máquina de estados.
- Corrigido bug crítico em `create_replanned_plan` que impedia qualquer replaneamento na aplicação web.
- Corrigidos campos da Demanda (`client`, `description`, `conditions`, `notes`) e do registo de
  Exceção (tipo/gravidade/descrição reais em vez de valores fixos).
- Corrigido caso limite: replanear sem exceção pendente já não rebenta com 500; devolve 400 tratado.
- Suite de testes de integração (`test_app.py`) a correr pedidos HTTP reais contra `app.py`.
- Persistência em SQLite (`storage.py`): reiniciar o processo do servidor já não apaga o estado.
- **Capacidade modelada como objeto próprio** (`Capacity`), com ciclo Disponível → Reservada →
  Utilizada → Liberada, coordenado por `start_operation`/`complete_operation` e por
  `create_replanned_plan` (liberta a capacidade antiga, reserva e usa a nova no replaneamento).
  Era a última simplificação consciente do MVP documentada no Notion — está resolvida.
- Suite de testes total: 12 (6 domínio + 6 integração/persistência).
- Documentação (README, PROGRESS, Notion) sincronizada com o estado real e validado do código.

## Próximo objetivo
- Sem simplificações pendentes por resolver da lista original do MVP. Próximas prioridades ficam
  em aberto: por exemplo, autenticação básica, múltiplos recursos/etapas em paralelo, ou consulta
  de histórico completo de operações concluídas.
