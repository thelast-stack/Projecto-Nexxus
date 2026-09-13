# Projecto Nexxus — Estado

## Concluído
- Primeiro vertical slice funcional (Demanda → Plano → Operação → Execução → Resultado/Medição).
- Modelo de domínio alinhado com o Core Logística MVP: Etapa e Exceção como objetos próprios,
  Operação com estado Preparada, Plano com versão.
- `app.py` unificado com `nexxus_logistica.py` — deixou de existir uma segunda máquina de estados.
- Corrigido bug crítico em `create_replanned_plan` que impedia qualquer replaneamento na aplicação web
  (rebentava com "Demand must be validated before planning"). Ver README, secção "Correção — replaneamento".
- Corrigidos campos da Demanda (`client`, `description`, `conditions`, `notes`) que antes eram
  sobrepostos de forma incorreta ou desapareciam da interface após a criação.
- Corrigido registo de Exceção: tipo, gravidade e descrição são agora introduzidos pelo operador,
  em vez de valores fixos ("media" / "impacto operacional" para todas as exceções).
- Demanda avança corretamente de estado durante o uso da aplicação web (antes ficava presa em "planned").
- Suite de testes ampliada para 5 testes, incluindo um teste de regressão dedicado ao bug do replaneamento.

## Próximo objetivo
- Persistência em ficheiro (hoje tudo está em memória e perde-se ao reiniciar o processo).
- Avaliar se `Capacidade` deve tornar-se objeto próprio (hoje é atributo do Recurso — simplificação
  consciente do MVP, documentada no Notion).
