# Projecto Nexxus

Primeira versão utilizável do NEXXUS Logística sobre o Core Comum + Core Logística.

## Estrutura

- Core Comum
- Core Logística
- Nexxus Logística

## Fluxo utilizável

**Demanda → Planeamento → Preparação → Execução → Exceção/Replaneamento → Resultado/Evidência → Medição.**

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

## Persistência

O estado (demandas, recursos, planos, operações, medições) é guardado em `nexxus.db`, uma base de
dados SQLite local (biblioteca padrão do Python — nenhuma dependência ou infraestrutura nova). Cada
agregado é gravado como JSON numa tabela própria, carregado ao arrancar o servidor e atualizado a
cada ação. Reiniciar o processo já não apaga o trabalho em curso. Ver `storage.py`.

## Testes

- `test_nexxus_logistica.py` — testes do domínio (dataclasses, máquina de estados, medição).
- `test_app.py` — testes de integração: correm pedidos HTTP reais contra `app.py` (servidor iniciado
  num thread, numa porta livre), cobrindo o fluxo completo com exceção e replaneamento, e a persistência
  (dados recarregados diretamente da base de dados, simulando um reinício do processo). Este ficheiro
  existe porque o bug do replaneamento só era visível a correr o fluxo HTTP real — os testes de
  domínio isolados não o detectavam. Usa um ficheiro SQLite temporário, isolado da base de dados real.

```bash
python -m pytest -v
```

## Correção — replaneamento

Foi identificado e corrigido um bug em que `create_replanned_plan` chamava `create_plan`, que por sua vez exigia `demand.state == VALIDATED`. Como o primeiro `create_plan` já tinha avançado a demanda para `PLANNED`, qualquer replaneamento subsequente rebentava com `ValueError: Demand must be validated before planning`. Isto tornava o passo de replaneamento inutilizável na aplicação web, apesar de os testes anteriores passarem — porque construíam o `Plan` replaneado manualmente em vez de chamar a função usada pelo `app.py`. `create_replanned_plan` tem agora validação própria, independente do estado da demanda, e o teste `test_replanning_does_not_require_demand_to_be_revalidated` cobre esta regressão.

Foi também corrigido um caso limite descoberto ao escrever os testes de integração: chamar `replan`
sem existir nenhuma exceção pendente rebentava com `IndexError` não tratado (500). Agora é validado
explicitamente e devolve um erro tratado (400).

O protótipo mantém o foco na execução real do fluxo, sem introduzir infraestrutura ou arquitetura desnecessária nesta fase.
