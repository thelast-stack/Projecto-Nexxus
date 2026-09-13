# Projecto Nexxus

Primeira versão utilizável do NEXXUS Logística sobre o Core Comum + Core Logística.

## Estrutura

- Core Comum
- Core Logística
- Nexxus Logística

## Fluxo utilizável

**Criar operação → validar → planear → iniciar execução → registar eventos → registar exceção → replanear → concluir → consultar resultado/evidência.**

## Protótipo

A aplicação web está em `app.py` e corre com Python standard library:

```bash
python app.py
```

Depois abrir `http://localhost:8000`.

O protótipo mantém o foco na execução da operação, sem introduzir infraestrutura ou arquitetura desnecessária nesta fase.
