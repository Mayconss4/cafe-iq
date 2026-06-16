# API Gateway

## Visão geral

O API Gateway é o ponto de entrada único para todas as requisições do cliente. Roteia chamadas para os serviços de backend (RAG, MCP e Controlador) e expõe um healthcheck consolidado.

- **Linguagem**: JavaScript (Node.js)
- **Framework**: Express
- **Porta**: `3000`
- **Entrypoint**: `api-gateway/src/index.js`

## Dependências

```json
{
  "dependencies": {
    "axios": "^1.7.2",
    "express": "^4.19.2"
  },
  "devDependencies": {
    "nodemon": "^3.1.4"
  }
}
```

## Endpoints

### POST /chat

Encaminha pergunta para o serviço RAG e retorna a resposta gerada.

**Requisição:**
```json
{
  "pergunta": "Qual é a cotação atual do café arábica?"
}
```

**Resposta:**
```json
{
  "resposta": "A cotação atual do café arábica está em torno de 224 USc/lb no mercado ICE...",
  "fontes": ["scrapper/cotacao", "scrapper/noticia"]
}
```

**Interno:** 
- Chama `POST http://servico-rag:8001/query`
- Status HTTP da resposta é preservado

### POST /mcp/tool

Invoca uma ferramenta MCP no serviço MCP.

**Requisição:**
```json
{
  "tool": "cotacao_cafe",
  "params": {}
}
```

**Resposta:**
```json
{
  "tool": "cotacao_cafe",
  "resultado": {
    "data": "2025-06-16",
    "ICE_arabica_usc_lb": 223.45,
    "B3_arabica_brl_saca60kg": 1087.30,
    "fonte": "mock — substituir por API ICE/B3"
  }
}
```

**Interno:**
- Chama `POST http://servico-mcp:8002/invoke`
- Validação de ferramentas é feita no serviço MCP

### GET /health

Verifica saúde dos serviços de backend.

**Resposta (sucesso):**
```json
{
  "gateway": "ok",
  "services": [
    {
      "name": "rag",
      "status": "ok",
      "latencyMs": 45
    },
    {
      "name": "mcp",
      "status": "ok",
      "latencyMs": 23
    },
    {
      "name": "controlador",
      "status": "ok",
      "latencyMs": 15
    }
  ]
}
```

**Resposta (falha parcial, HTTP 207):**
```json
{
  "gateway": "ok",
  "services": [
    {
      "name": "rag",
      "status": "ok",
      "latencyMs": 42
    },
    {
      "name": "mcp",
      "status": "unreachable",
      "error": "connect ECONNREFUSED"
    },
    {
      "name": "controlador",
      "status": "ok",
      "latencyMs": 18
    }
  ]
}
```

- Faz requisições paralelas a todos os serviços
- Retorna HTTP 200 se todos estiverem ok
- Retorna HTTP 207 se houver falha parcial
- Timeout de 3 segundos por serviço

## Middleware

### CORS

Permite requisições de qualquer origem (Fix 1). Headers permitidos:
- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

Responde com 204 para preflight OPTIONS.

### Logging

Loga cada requisição com:
- Método HTTP
- Caminho
- Status HTTP
- Latência em ms

Exemplo:
```
GET /health 200 12ms
POST /chat 200 342ms
POST /mcp/tool 404 45ms
```

### Bodyparser

Automaticamente parseia JSON no corpo das requisições.

## Configuração

Via variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `PORT` | `3000` | Porta do gateway |
| `RAG_URL` | `http://servico-rag:8001` | URL do serviço RAG |
| `MCP_URL` | `http://servico-mcp:8002` | URL do serviço MCP |
| `CONTROLADOR_URL` | `http://servico-controlador:3001` | URL do serviço Controlador |

## Tratamento de erros

### Erro do serviço remoto

Se o serviço remoto retorna um erro, ele é encaminhado diretamente:

```javascript
res.status(err.response.status).json(err.response.data);
```

### Serviço inacessível (502)

Se a conexão falhar (timeout, conexão recusada, etc.):

```json
{
  "error": "Bad Gateway",
  "detail": "connect ECONNREFUSED"
}
```

## Como testar

### Verificar saúde

```bash
curl -s http://localhost:3000/health | jq
```

### Fazer uma pergunta

```bash
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual é o preço do café?"}' | jq
```

### Invocar ferramenta MCP

```bash
curl -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "cotacao_cafe", "params": {}}' | jq
```

## Notas técnicas

- Não valida o corpo da requisição; a validação é feita nos serviços remotos
- Não cachea respostas
- Conexões são mantidas abertas pelo `axios` (keep-alive)
- Em caso de erro, a resposta é status 502 (Bad Gateway) padrão HTTP
