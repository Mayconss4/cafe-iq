# Serviço MCP - Diagramas de Classe

## Visão geral

O `servico-mcp` oferece ferramentas de domínio para o sistema e expõe:
- `GET /health`
- `GET /tools`
- `POST /invoke`

É responsável por retornar dados simulados de cotação, clima e notícias.

## Componentes principais

- `main.py`
  - `InvokeRequest`
  - `POST /invoke`
- `registry.py`
  - `TOOLS`
  - `tool_metadata()`
- `tools/cotacao_cafe.py`
  - `run(params)`
- `tools/clima.py`
  - `run(params)`
- `tools/noticias.py`
  - `run(params)`

## Diagrama de classes

```mermaid
classDiagram
    class InvokeRequest {
        +tool: str
        +params: dict
    }
    class McpService {
        +GET /health()
        +GET /tools()
        +POST /invoke(req)
    }
    class ToolRegistry {
        +TOOLS: dict
        +tool_metadata()
    }
    class CotacaoCafe {
        +run(params): dict
    }
    class Clima {
        +run(params): dict
    }
    class Noticias {
        +run(params): list[dict]
    }

    McpService --> ToolRegistry : consulta ferramentas
    McpService --> CotacaoCafe : chama handler
    McpService --> Clima : chama handler
    McpService --> Noticias : chama handler
```

## Descrição dos relacionamentos

- `InvokeRequest` modela requisições recebidas pelo endpoint `/invoke`.
- `ToolRegistry` mantém o mapeamento de ferramentas e metadados.
- Cada ferramenta (`CotacaoCafe`, `Clima`, `Noticias`) implementa um `run(params)` que retorna o resultado.
- `McpService` delega execução de ferramentas ao `ToolRegistry`.
