# Projecto Nexxus

Primeira versão utilizável do NEXXUS Logística sobre o Core Comum + Core Logística.

## Estrutura

- Core Comum
- Core Logística
- Nexxus Logística

## Fluxo utilizável

**Demanda → Planeamento → Preparação → Execução → Exceção/Replaneamento → Resultado/Evidência → Medição.**

Uma demanda pode ser **dividida** por várias operações (quando excede a capacidade de um único
recurso), e uma operação pode **consolidar** várias demandas de clientes diferentes numa só viagem.
Ver secção "Cardinalidade Demanda ↔ Operação" abaixo.

## Protótipo

A aplicação web está em `app.py` e usa `nexxus_logistica.py` como fonte de verdade do domínio.

```bash
python app.py
```

Depois abrir `http://localhost:8000`.

## Estado

- Modelo de domínio alinhado com o Core Logística MVP.
- Etapas e exceções são objetos próprios.
- Operação usa o estado Preparada antes da execução.
- Planos suportam versão para replaneamento.
- Interface web utiliza o domínio real, sem segunda máquina de estados.
- Demanda avança corretamente `validated → planned → in_execution → completed` durante o uso da aplicação web.
- Cliente, descrição, condições e observações são campos próprios da Demanda e aparecem na página da operação.
- Exceção regista tipo, gravidade e descrição reais introduzidos pelo operador (antes eram valores fixos).
- GitHub Actions: PASS — validado adicionalmente com um teste de regressão que chama `create_replanned_plan` (a função real usada pelo `app.py`), não apenas a construção manual de um `Plan`.

## Cardinalidade Demanda ↔ Operação (divisão e consolidação)

A auditoria do Core Logística como Nível 2 identificou que o modelo assumia implicitamente
**1 Demanda : 1 Plano : 1 Operação : 1 Recurso**, o que não cobre dois casos comuns em logística
real:

- **Divisão** — uma demanda grande (ex.: 30t) excede a capacidade de um único recurso e precisa de
  duas ou mais operações (dois veículos, duas viagens).
- **Consolidação** — várias demandas de clientes diferentes são transportadas juntas numa única
  operação (um camião, uma rota, várias entregas).

A correção introduziu `DemandAllocation` (demand_id + quantidade) como uma **lista** em `Plan` e em
`Operation`, em vez de um único `demand_id`. Cada `Demand` passa a controlar quanto da sua
quantidade total já foi alocada a algum plano (`allocated_quantity` / `remaining_quantity`) e quanto
já foi efetivamente entregue (`delivered_quantity` / `fully_delivered`). Isto permite:

- planear apenas uma parte de uma demanda (`create_plan(demand, resource, plan_id, quantities={...})`),
  deixando o resto disponível para uma operação futura;
- planear várias demandas juntas (`create_plan([d1, d2, d3], resource, plan_id)`), desde que
  partilhem a mesma unidade de medida e o recurso tenha capacidade para a soma;
- uma demanda só passa a `completed` quando **toda** a sua quantidade tiver sido entregue — o que
  pode exigir mais do que uma operação concluída.

Na aplicação web, isto aparece como duas rotas novas:

- `/plan-demand` — planear (total ou parcialmente) uma demanda, a partir da sua própria página
  (`/demand?id=...`);
- `/consolidate` — selecionar duas ou mais demandas com quantidade por planear e criar uma operação
  conjunta.

`PLANS` e `OPERATIONS` deixaram de ser indexados por `demand_id` (o que impunha 1:1 na própria
estrutura de dados) e passaram a ser indexados pela sua própria id (`plan_id` / `operation_id`); a
página de uma demanda lista todas as operações que a cobrem, e a página de uma operação lista todas
as demandas que ela transporta.

## Catálogo de recursos, etapas dinâmicas e eventos com localização/quantidade

- **Catálogo de recursos** (`/resources`): recursos são adicionados uma vez e reutilizados em vários
  planos, em vez de cada plano criar um recurso novo a partir de texto livre.
- **Etapas dinâmicas**: o planeamento permite definir os nomes das etapas (`create_operation` aceita
  `stage_names`); em branco, usa o padrão `pickup, transport, delivery`.
- **Eventos com localização e quantidade**: `Event` ganhou campos opcionais `location` e `quantity`,
  visíveis na linha do tempo da operação.

## Capacidade

Capacidade é um objeto próprio (`Capacity`), com o ciclo `Disponível → Reservada → Utilizada →
Liberada`. Reservada ao criar o plano, colocada em uso ao iniciar a operação, e liberada ao concluir
(ou, no replaneamento, liberada do plano anterior e reservada/colocada em uso de imediato no novo).
Antes, capacidade era apenas um atributo do Recurso — sem estado próprio. Ver `Capacity` em
`nexxus_logistica.py`.

## Persistência

O estado (demandas, recursos, planos, operações, medições) é guardado em `nexxus.db`, uma base de
dados SQLite local (biblioteca padrão do Python — nenhuma dependência ou infraestrutura nova). Cada
agregado é gravado como JSON numa tabela própria, carregado ao arrancar o servidor e atualizado a
cada ação. Reiniciar o processo já não apaga o trabalho em curso. Ver `storage.py`.

## Testes

- `test_nexxus_logistica.py` — testes do domínio: 11 testes (fluxo original com exceção e
  replaneamento, ciclo de vida da Capacidade, medição, **divisão de uma demanda por duas operações**,
  **consolidação de três demandas numa operação**, e as validações de erro de cada caso).
- `test_app.py` — testes de integração: 13 testes que correm pedidos HTTP reais contra `app.py`
  (servidor iniciado num thread, numa porta livre), cobrindo o fluxo completo com exceção e
  replaneamento, persistência (dados recarregados diretamente da base de dados, simulando um
  reinício do processo), catálogo de recursos, etapas/eventos personalizados, e **os dois cenários de
  cardinalidade (divisão e consolidação) via HTTP real, do planeamento até `completed`**. Usa um
  ficheiro SQLite temporário, isolado da base de dados real.

Total: 24 testes.

```bash
python -m pytest -v
```

## Correções aplicadas

**Cardinalidade Demanda ↔ Operação (divisão e consolidação).** Ver secção dedicada acima. Identificado
numa auditoria do Core Logística como Nível 2, validado com dois testes de domínio, dois testes de
integração HTTP, e execução manual com `curl` do planeamento até `completed` em ambos os cenários.

**Replaneamento.** Foi identificado e corrigido um bug em que `create_replanned_plan` chamava
`create_plan`, que por sua vez exigia `demand.state == VALIDATED`. Como o primeiro `create_plan` já
tinha avançado a demanda para `PLANNED`, qualquer replaneamento subsequente rebentava com
`ValueError: Demand must be validated before planning`. Isto tornava o passo de replaneamento
inutilizável na aplicação web, apesar de os testes anteriores passarem — porque construíam o `Plan`
replaneado manualmente em vez de chamar a função usada pelo `app.py`. `create_replanned_plan` tem
agora validação própria, independente do estado da demanda, e o teste
`test_replanning_does_not_require_demand_to_be_revalidated` cobre esta regressão.

Foi também corrigido um caso limite descoberto ao escrever os testes de integração: chamar `replan`
sem existir nenhuma exceção pendente rebentava com `IndexError` não tratado (500). Agora é validado
explicitamente e devolve um erro tratado (400).

**Limpeza:** removido `Test_app.py` (duplicado de `test_app.py` diferindo apenas na maiúscula
inicial, mais antigo e sem as funcionalidades de catálogo de recursos). Manter dois ficheiros que só
diferem na capitalização é frágil em checkouts de Windows/macOS (sistemas de ficheiros
case-insensitive) e não tem função aqui — apenas o `test_app.py` (minúsculas) é mantido.

O protótipo mantém o foco na execução real do fluxo, sem introduzir infraestrutura ou arquitetura
desnecessária nesta fase.
