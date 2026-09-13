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
- GitHub Actions: PASS.

O protótipo mantém o foco na execução real do fluxo, sem introduzir infraestrutura ou arquitetura desnecessária nesta fase.
