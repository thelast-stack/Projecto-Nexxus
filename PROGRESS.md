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
- Suite de testes total: 16 (6 domínio + 10 integração/persistência/catálogo/etapas/eventos).
- Documentação (README, PROGRESS, Notion — secções 12 a 15) sincronizada com o estado real e
  validado do código.

## Estado face ao MVP definido no Notion
Os 13 objetos mínimos (secção 3.1), os 6 blocos funcionais (secção 4), o cenário de validação de
15 passos (secção 7) e as 11 perguntas de critério de funcionalidade (secção 8) estão cobertos e
validados por HTTP real. Sem lacunas conhecidas face ao MVP documentado.

## Próximo objetivo
Fase de MVP considerada concluída. Simplificações conscientes que permanecem, fora do MVP mínimo
(secção 11.2 do Notion): Resultado/Evidência e Medição como campos simples, sem reserva concorrente
de recursos entre operações simultâneas, sem autenticação. Próximas prioridades ficam em aberto —
por exemplo, autenticação básica ou consulta de histórico de operações concluídas.
