# Serviço MCP

## Visão geral

Serviço que expõe ferramentas externas (Model Context Protocol tools) para consulta de dados em tempo real sobre o mercado de café: cotação, clima e notícias.

- **Linguagem**: Python
- **Framework**: FastAPI
- **Porta**: `8002`
- **Entrypoint**: `servico-mcp/app/main.py`

## Dependências

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic==2.7.4
```

## Endpoints

### GET /health

Status do serviço.

**Resposta:**
```json
{
  "status": "ok"
}
```

### GET /tools

Lista todas as ferramentas disponíveis com metadados.

**Resposta:**
```json
{
  "tools": [
    {
      "nome": "cotacao_cafe",
      "descricao": "Retorna cotação simulada do café arábica (ICE e B3).",
      "params": []
    },
    {
      "nome": "clima",
      "descricao": "Retorna condições climáticas simuladas para uma cidade produtora.",
      "params": [
        {
          "nome": "cidade",
          "tipo": "string",
          "obrigatorio": true
        }
      ]
    },
    {
      "nome": "noticias",
      "descricao": "Retorna 3 manchetes recentes simuladas sobre o mercado de café.",
      "params": []
    }
  ]
}
```

### POST /invoke

Executa uma ferramenta com parâmetros.

**Requisição:**
```json
{
  "tool": "cotacao_cafe",
  "params": {}
}
```

**Resposta (sucesso):**
```json
{
  "tool": "cotacao_cafe",
  "resultado": {
    "data": "2025-06-16",
    "ICE_arabica_usc_lb": 221.75,
    "B3_arabica_brl_saca60kg": 1089.45,
    "fonte": "mock — substituir por API ICE/B3"
  }
}
```

**Resposta (ferramenta não encontrada, HTTP 404):**
```json
{
  "detail": "Ferramenta 'cotacao_invalida' não encontrada. Disponíveis: ['cotacao_cafe', 'clima', 'noticias']"
}
```

**Resposta (erro interno, HTTP 500):**
```json
{
  "detail": "Descrição do erro interno"
}
```

## Ferramentas

### cotacao_cafe

Retorna cotação simulada de café arábica em dois mercados.

- **Arquivo**: `app/tools/cotacao_cafe.py`
- **Parâmetros**: nenhum
- **Resposta**:
  - `data`: data em ISO format
  - `ICE_arabica_usc_lb`: preço em US cents por libra (cotação ICE)
  - `B3_arabica_brl_saca60kg`: preço em BRL por saca de 60kg (cotação B3)
  - `fonte`: nota indicando que é mock

**Exemplo de uso:**
```bash
curl -s -X POST http://localhost:8002/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool": "cotacao_cafe", "params": {}}' | jq
```

### clima

Retorna condições climáticas simuladas para uma cidade produtora de café.

- **Arquivo**: `app/tools/clima.py`
- **Parâmetros**:
  - `cidade` (obrigatório): nome da cidade
- **Resposta**:
  - `cidade`: nome da cidade informada
  - `temperatura_c`: temperatura em Celsius
  - `umidade_pct`: umidade relativa em percentual (0-100)
  - `condicao`: condição do tempo (Ensolarado, Nublado, Chuva leve, etc.)
  - `fonte`: nota indicando que é mock

**Cidades suportadas:**
- Patrocinio
- Araguari
- Guaxupe
- Varginha
- Mococa
- Lavras (padrão do scrapper)

Se a cidade não estiver mapeada, usa valores genéricos.

**Exemplo de uso:**
```bash
curl -s -X POST http://localhost:8002/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool": "clima", "params": {"cidade": "Varginha"}}' | jq
```

### noticias

Retorna 3 manchetes de notícias simuladas sobre o mercado de café.

- **Arquivo**: `app/tools/noticias.py`
- **Parâmetros**: nenhum
- **Resposta**: array de objetos com:
  - `titulo`: texto da manchete
  - `data`: data em ISO format (retroativa)
  - `fonte`: nota indicando que é mock

**Exemplo de uso:**
```bash
curl -s -X POST http://localhost:8002/invoke \
  -H "Content-Type: application/json" \
  -d '{"tool": "noticias", "params": {}}' | jq
```

## Estrutura do código

### app/registry.py

Define o registro global de ferramentas:

```python
TOOLS: dict[str, dict] = {
    "nome_ferramenta": {
        "handler": funcao_handler,
        "descricao": "Descrição da ferramenta",
        "params": [...]
    }
}

def tool_metadata() -> list[dict]:
    # Retorna lista de metadados das ferramentas
```

### app/main.py

Define a aplicação FastAPI:

- `GET /health`: retorna status
- `GET /tools`: chama `tool_metadata()`
- `POST /invoke`: busca ferramenta em `TOOLS`, valida parâmetros e executa

### app/tools/

Cada arquivo define uma ferramenta:
- `cotacao_cafe.py`: `run(_params: dict) -> dict`
- `clima.py`: `run(params: dict) -> dict`
- `noticias.py`: `run(_params: dict) -> list[dict]`

## Validação e erros

- **Ferramenta não encontrada (404)**: se `req.tool` não existir em `TOOLS`
- **Erro na execução (500)**: se a função `handler` lançar exceção
- **Parâmetros inválidos (500)**: erros de validação Pydantic são capturados

## Como estender

Para adicionar uma nova ferramenta:

1. Crie um arquivo em `app/tools/nova_ferramenta.py`:
```python
def run(params: dict) -> dict:
    # seu código
    return { "resultado": ... }
```

2. Importe em `app/registry.py`:
```python
from app.tools import nova_ferramenta

TOOLS["nova_ferramenta"] = {
    "handler": nova_ferramenta.run,
    "descricao": "...",
    "params": [...]
}
```

3. Reinicie o serviço

## Notas técnicas

- Todas as ferramentas retornam dados simulados (mock)
- Para uso em produção, substituir pelas APIs reais (ICE, weather API, etc.)
- O serviço não tem estado persistente
- Não há limite de rate limiting
- Logging é realizado via uvicorn
