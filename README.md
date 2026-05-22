# CaféIQ

Assistente inteligente especializado no mercado de café, construído como sistema distribuído de microsserviços. Combina busca vetorial (RAG), integração com ferramentas externas (MCP) e coleta assíncrona de dados para responder perguntas sobre cotações, clima e notícias do setor cafeeiro.

---

## Arquitetura

### Visão geral dos componentes

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (index.html)                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP (porta 3000)
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         api-gateway :3000                       │
│            Único ponto de entrada para o cliente web            │
└──────┬──────────────────┬──────────────────────┬────────────────┘
       │ POST /query      │ POST /invoke         │ GET /health
       ▼                  ▼                      ▼
┌──────────────┐  ┌──────────────┐   ┌──────────────────────┐
│ servico-rag  │  │ servico-mcp  │   │ servico-controlador  │
│    :8001     │  │    :8002     │   │       :3001          │
│              │  │              │   │                      │
│ LangChain +  │  │ Ferramentas  │   │ Painel admin /status │
│ ChromaDB +   │  │ cotacao_cafe │   │ /forcar-ingestao     │
│ Ollama/llama3│  │ clima        │   │ /logs                │
└──────┬───────┘  │ noticias     │   └──────────────────────┘
       │          └──────────────┘
       │ (interno) enriquece contexto
       └──────────────────────────────► servico-mcp /invoke
```

### Fluxo síncrono — pergunta do usuário

```
Browser
  │  POST /chat {"pergunta": "qual o preço do café?"}
  ▼
api-gateway
  │  POST servico-rag:8001/query
  ▼
servico-rag
  ├─ 1. mcp_enricher detecta keyword "preço"
  │       └─ POST servico-mcp:8002/invoke {"tool":"cotacao_cafe"}
  │              └─ retorna cotação simulada (ICE/B3)
  │
  ├─ 2. Busca vetorial no ChromaDB (k=4 documentos relevantes)
  │
  ├─ 3. Monta prompt:
  │       [Dados em tempo real]  ← resultado MCP
  │       [Base de conhecimento] ← docs do ChromaDB
  │       Pergunta: ...
  │
  └─ 4. Ollama (llama3) gera resposta
         └─ retorna {"resposta": "...", "fontes": [...]}
```

### Fluxo assíncrono — ingestão de dados

```
servico-scrapper (a cada 60s ou POST /coletar-agora)
  │
  ├─ coleta: 2 notícias + clima Lavras-MG + cotação café
  │
  └─ publica 4 mensagens JSON em ──► RabbitMQ
                                      fila: cafeiq.ingestao
                                           │
                              ┌────────────┘
                              ▼
                     servico-rag (thread consumer)
                          │
                          └─ ingest_document() ──► ChromaDB
                                                  (embedding
                                                  nomic-embed-text)
```

---

## Pré-requisitos

| Ferramenta | Versão mínima | Instalação |
|---|---|---|
| Docker | 24.x | https://docs.docker.com/get-docker/ |
| Docker Compose | 2.x (plugin) | incluído no Docker Desktop |
| curl | qualquer | para testar os endpoints |

> O Ollama roda **dentro do Docker** (`cafeiq-ollama`). Não é necessário instalá-lo na máquina host.

---

## Subindo o sistema

### 1. Clonar e construir

```bash
git clone <url-do-repositorio>
cd cafe-iq
docker compose up --build
```

A primeira execução faz o build das imagens Python e Node. Aguarde até ver os logs:

```
cafeiq-api-gateway    | api-gateway listening on port 3000
cafeiq-servico-rag    | INFO:     Application startup complete.
cafeiq-servico-mcp    | INFO:     Application startup complete.
cafeiq-servico-scrapper | INFO:   Application startup complete.
```

### 2. Puxar os modelos do Ollama

Execute **após** o `docker compose up`, em outro terminal:

```bash
# Modelo de linguagem (geração de respostas)
docker exec cafeiq-ollama ollama pull llama3

# Modelo de embeddings (busca vetorial)
docker exec cafeiq-ollama ollama pull nomic-embed-text
```

> Os modelos ficam persistidos no volume `ollama-data`. O pull só é necessário na primeira vez.

### 3. Abrir a interface web

Abra o arquivo `index.html` diretamente no navegador:

```bash
xdg-open index.html        # Linux
open index.html            # macOS
# ou arraste o arquivo para o navegador
```

---

## Exemplos de uso

### Perguntar ao assistente (via API Gateway)

```bash
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual é a cotação atual do café arábica?"}' | jq
```

Resposta esperada:
```json
{
  "resposta": "A cotação atual do café arábica está em torno de 224 USc/lb no mercado ICE...",
  "fontes": ["scrapper/cotacao", "scrapper/noticia"]
}
```

### Invocar uma ferramenta MCP diretamente

```bash
# Cotação do café
curl -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "cotacao_cafe", "params": {}}' | jq

# Clima em cidade produtora
curl -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "clima", "params": {"cidade": "Varginha"}}' | jq

# Notícias recentes
curl -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "noticias", "params": {}}' | jq
```

### Indexar um documento manualmente

```bash
curl -s -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{"texto": "A safra 2025 de café arábica no Sul de Minas deve atingir 12 milhões de sacas, segundo a Conab.", "fonte": "conab-2025"}' | jq
```

### Status dos serviços

```bash
# Saúde consolidada (via gateway)
curl -s http://localhost:3000/health | jq

# Status via painel administrativo
curl -s http://localhost:3001/status | jq
```

### Forçar coleta imediata do scrapper

```bash
curl -s -X POST http://localhost:3001/forcar-ingestao | jq
```

### Listar ferramentas MCP disponíveis

```bash
curl -s http://localhost:8002/tools | jq
```

### Ver logs do controlador

```bash
curl -s http://localhost:3001/logs | jq
```

---

## Portas expostas

| Serviço | Porta | Descrição |
|---|---|---|
| api-gateway | 3000 | Ponto de entrada do cliente web |
| servico-rag | 8001 | RAG + ingestão |
| servico-mcp | 8002 | Ferramentas MCP |
| servico-scrapper | 8003 | Coleta e trigger manual |
| servico-controlador | 3001 | Painel administrativo |
| ChromaDB | 8000 | Banco vetorial (interno) |
| Ollama | 11434 | Servidor LLM (interno) |
| RabbitMQ | 5672 / 15672 | Event bus / painel web |

> Painel do RabbitMQ: http://localhost:15672 (usuário: `cafeiq`, senha: `cafeiq123`)

---

## Estrutura do repositório

```
cafe-iq/
├── index.html                  # Interface web (arquivo único)
├── docker-compose.yml
├── README.md
├── docs/
│   └── arquitetura.md          # Justificativas arquiteturais
├── api-gateway/                # Node.js/Express — proxy + roteamento
├── servico-rag/                # Python/FastAPI — RAG + consumer RabbitMQ
├── servico-mcp/                # Python/FastAPI — ferramentas MCP
├── servico-scrapper/           # Python/FastAPI — coleta periódica
└── servico-controlador/        # Node.js/Express — painel administrativo
```
