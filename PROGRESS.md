# Projecto Nexxus — Estado

## Concluído
- Primeiro vertical slice funcional (Demanda → Plano → Operação → Execução → Resultado/Medição).
- Modelo de domínio alinhado com o Core Logística MVP: Etapa e Exceção como objetos próprios,
  Operação com estado Preparada, Plano com versão.
- `app.py` unificado com `nexxus_logistica.py` — deixou de existir uma segunda máquina de estados.
- Corrigido bug crítico em `create_replanned_plan` que impedia qualquer replaneamento na aplicação web
  (rebentava com "Demand must be validated before planning"). Ver README, secção "Correção — replaneamento",
  e Notion → Nexxus Logística, secção 12.
- Corrigidos campos da Demanda (`client`, `description`, `conditions`, `notes`) que antes eram
  sobrepostos de forma incorreta ou desapareciam da interface após a criação.
- Corrigido registo de Exceção: tipo, gravidade e descrição são agora introduzidos pelo operador,
  em vez de valores fixos ("media" / "impacto operacional" para todas as exceções).
- Demanda avança corretamente de estado durante o uso da aplicação web (antes ficava presa em "planned").
- Corrigido caso limite: replanear sem exceção pendente já não rebenta com 500 (IndexError não tratado);
  devolve agora um 400 tratado.
- Adicionada suite de testes de integração (`test_app.py`) que corre pedidos HTTP reais contra `app.py`,
  cobrindo o fluxo completo com exceção e replaneamento — é a camada onde o bug acima vivia sem detecção.
- Suite de testes total: 10 (5 domínio + 5 integração).
- Documentação (README, PROGRESS, Notion) sincronizada com o estado real e validado do código.

## Próximo objetivo
- Persistência em ficheiro (hoje tudo está em memória e perde-se ao reiniciar o processo).
- Avaliar se `Capacidade` deve tornar-se objeto próprio (hoje é atributo do Recurso — simplificação
  consciente do MVP, documentada no Notion, secção 11.2).
