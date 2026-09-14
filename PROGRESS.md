# Projecto Nexxus — Estado

## Concluído
- Primeiro vertical slice funcional (Demanda → Plano → Operação → Execução → Resultado/Medição).
- Modelo de domínio alinhado com o Core Logística MVP: Etapa, Exceção e Capacidade como objetos
  próprios; Operação com estado Preparada; Plano com versão.
- `app.py` unificado com `nexxus_logistica.py` — deixou de existir uma segunda máquina de estados.
- Corrigido bug crítico em `create_replanned_plan` que impedia qualquer replaneamento na aplicação web.
- Corrigidos campos da Demanda e do registo de Exceção (tipo/gravidade/descrição reais).
- Persistência em SQLite (`storage.py`); carregamento resiliente a registos de versões antigas.
- Capacidade modelada como objeto próprio, com ciclo Reservada → Utilizada → Liberada.
- **Catálogo de recursos** (`/resources`), reutilizável entre planos, em vez de recurso ad-hoc por plano.
- **Etapas dinâmicas**: nomes de etapas definidos pelo operador no planeamento (com padrão de 3 se
  deixado em branco).
- **Eventos com localização e quantidade**, visíveis na linha do tempo da operação.
- **Cardinalidade Demanda ↔ Operação corrigida.** O modelo assumia implicitamente 1 Demanda : 1
  Plano : 1 Operação, o que não cobria divisão (uma demanda grande servida por várias operações) nem
  consolidação (várias demandas transportadas juntas numa operação). `Plan` e `Operation` passam a
  referenciar uma lista de `DemandAllocation` (demanda + quantidade); `Demand` ganhou
  `allocated_quantity`/`delivered_quantity` para saber quanto já foi planeado e quanto já foi
  entregue. `PLANS`/`OPERATIONS` deixaram de ser indexados por `demand_id` (o que impunha 1:1 na
  própria estrutura) e passaram a ser indexados pela sua própria id. Novas rotas web: `/plan-demand`
  (planear total ou parcialmente uma demanda) e `/consolidate` (agrupar várias demandas numa
  operação).
- Removido `Test_app.py`, duplicado obsoleto de `test_app.py` que só diferia na capitalização
  (frágil em checkouts case-insensitive; sem as funcionalidades de catálogo).
- Suite de testes total: 24 (11 domínio + 13 integração — incluindo os dois cenários de
  cardinalidade, ponta a ponta, via HTTP real).
- Todos os três cenários (fluxo original com replaneamento, divisão, consolidação) validados
  manualmente com `curl` do planeamento até `completed`, sem erros inesperados.
- Documentação (README, PROGRESS, Notion — secções 12 a 15) sincronizada com o estado real e
  validado do código.

## Estado face ao MVP definido no Notion
Os 13 objetos mínimos (secção 3.1), os 6 blocos funcionais (secção 4), o cenário de validação de
15 passos (secção 7) e as 11 perguntas de critério de funcionalidade (secção 8) estão cobertos e
validados por HTTP real. A auditoria do Core Logística como Nível 2 (Teste de Cobertura) identificou
a lacuna de cardinalidade Demanda↔Operação, já corrigida e validada nesta versão. Sem lacunas
conhecidas adicionais face ao MVP documentado.

## Próximo objetivo
Simplificações conscientes que permanecem, fora do MVP mínimo (secção 11.2 do Notion):
Resultado/Evidência e Medição como campos simples, sem reserva concorrente de recursos entre
operações simultâneas, sem autenticação. Próximas prioridades ficam em aberto — por exemplo,
autenticação básica, consulta de histórico de operações concluídas, ou revisitar a distinção entre
"Informação" e "Histórico" mencionada como ponto em aberto na secção 6 do Notion.
