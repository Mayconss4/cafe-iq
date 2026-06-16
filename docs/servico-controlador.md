# Serviço Controlador

## Visão geral

Serviço de painel administrativo que monitora o status do sistema e permite disparo manual de ingestão. Funciona como interface de controle centralizada.

- **Linguagem**: JavaScript (Node.js)
- **Framework**: Express
- **Porta**: `3001`
- **Entrypoint**: `servico-controlador/src/index.js`

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

### GET /health

Status do controlador.

**Resposta:**
```json
{
  "status": "ok"
}
```

### GET /status

Consulta saúde consolidada do sistema via api-gateway.

**Resposta:**
```json
{
  "origem": "api-gateway",
  "gateway": "ok",
  "services": [
    {
      "name": "rag",
      "status": "ok",
      "latencyMs": 42
    },
    {
      "name": "mcp",
      "status": "ok",
      "latencyMs": 25
    },
    {
      "name": "controlador",
      "status": "ok",
      "latencyMs": 18
    }
  ]
}
```

**Resposta (falha ao contactar gateway, HTTP 502):**
```json
{
  "error": "Não foi possível contatar o api-gateway.",
  "detail": "connect ECONNREFUSED"
}
```

### POST /forcar-ingestao

Dispara coleta manual no serviço scrapper.

**Resposta (sucesso):**
```json
{
  "mensagem": "Coleta manual disparada.",
  "ok": true
}
```

**Resposta (falha ao contactar scrapper, HTTP 502):**
```json
{
  "error": "Não foi possível contatar o servico-scrapper.",
  "detail": "socket hang up"
}
```

### GET /logs

Retorna os últimos 20 logs em memória (ring buffer).

**Resposta:**
```json
{
  "total": 15,
  "logs": [
    {
      "timestamp": "2025-06-16T14:32:45.123Z",
      "level": "info",
      "message": "GET /status → 200",
      "ms": 45
    },
    {
      "timestamp": "2025-06-16T14:32:40.456Z",
      "level": "info",
      "message": "POST /forcar-ingestao → 200",
      "ms": 2341
    },
    {
      "timestamp": "2025-06-16T14:32:39.789Z",
      "level": "error",
      "message": "GET /status falhou: connect ECONNREFUSED"
    }
  ]
}
```

Logs aparecem em **ordem reversa** (mais recentes primeiro).

## Configuração

Via variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `PORT` | `3001` | Porta do controlador |
| `GATEWAY_URL` | `http://api-gateway:3000` | URL do api-gateway |
| `SCRAPPER_URL` | `http://servico-scrapper:8003` | URL do scrapper |

## Middleware

### Logging

Registra todas as requisições em ring buffer (máximo 20 entradas):

- Timestamp ISO
- Nível (info/error)
- Mensagem
- Latência em ms
- Metadados customizados

Exemplo de log:
```
[INFO] GET /status → 207 (ms: 89)
[ERROR] POST /forcar-ingestao falhou: connect ECONNREFUSED
```

### Bodyparser

Parse automático de JSON no corpo.

## Estrutura do código

### Ring buffer de logs

```javascript
const MAX_LOGS = 20;
const _logs = [];

function addLog(level, message, meta = {}) {
  const entry = { 
    timestamp: new Date().toISOString(), 
    level, 
    message, 
    ...meta 
  };
  _logs.push(entry);
  if (_logs.length > MAX_LOGS) _logs.shift();
  console.log(`[${entry.level.toUpperCase()}] ${entry.message}`);
}
```

- Armazena até 20 logs
- Quando atinge limite, remove o mais antigo
- Cada log é também impresso no console

### Middleware de timing

```javascript
app.use((req, _res, next) => {
  req._startTime = Date.now();
  next();
});

app.use((req, res, next) => {
  const original = res.end.bind(res);
  res.end = (...args) => {
    addLog('info', `${req.method} ${req.path} → ${res.statusCode}`, {
      ms: Date.now() - req._startTime,
    });
    return original(...args);
  };
  next();
});
```

- Calcula latência de cada requisição
- Loga após resposta ser enviada

## Como testar

### Verificar saúde

```bash
curl -s http://localhost:3001/health | jq
```

### Consultar status do sistema

```bash
curl -s http://localhost:3001/status | jq
```

### Forçar coleta manual

```bash
curl -s -X POST http://localhost:3001/forcar-ingestao | jq
```

### Ver logs

```bash
curl -s http://localhost:3001/logs | jq
```

## Tratamento de erros

### Erro ao contactar Gateway

Se GET `/status` falhar:

```json
{
  "error": "Não foi possível contatar o api-gateway.",
  "detail": "connect ECONNREFUSED"
}
```

Status HTTP: 502 (Bad Gateway)

Esse erro é também logado:
```
[ERROR] GET /status falhou: connect ECONNREFUSED
```

### Erro ao contactar Scrapper

Se POST `/forcar-ingestao` falhar:

```json
{
  "error": "Não foi possível contatar o servico-scrapper.",
  "detail": "socket hang up"
}
```

Status HTTP: 502

Logado como:
```
[ERROR] POST /forcar-ingestao falhou: socket hang up
```

## Casos de uso

### Monitorar status do sistema

```bash
# Verificar se todos os serviços estão saudáveis
curl -s http://localhost:3001/status | jq '.services[] | select(.status != "ok")'
```

### Disparar coleta manualmente

```bash
# Forçar ingestão de dados imediatamente
curl -s -X POST http://localhost:3001/forcar-ingestao
```

### Verificar logs recentes

```bash
# Ver últimos erros
curl -s http://localhost:3001/logs | jq '.logs[] | select(.level == "error")'
```

## Notas técnicas

- Ring buffer reside em memória (perdido ao restart do container)
- Logging é síncrono (não afeta performance significativamente)
- Timeout de 5 segundos para chamadas ao Gateway e Scrapper
- Não valida corpo das requisições
- Não faz cache de respostas
