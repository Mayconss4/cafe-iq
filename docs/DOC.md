# DOC.md — Documentação Completa CaféIQ

## Índice

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Instalação e Execução](#instalação-e-execução)
4. [Serviços](#serviços)
5. [Endpoints e Uso](#endpoints-e-uso)
6. [Configuração](#configuração)
7. [Fluxos de Dados](#fluxos-de-dados)
8. [Troubleshooting](#troubleshooting)

---

## Visão geral

CaféIQ é um assistente inteligente para o mercado de café, implementado como sistema de microsserviços distribuídos. O sistema:

- Responde perguntas sobre cotações, clima e notícias do mercado cafeeiro
- Combina busca vetorial (RAG) com ferramentas externas (MCP) para contexto em tempo real
- Coleta dados assincronamente via RabbitMQ
- Expõe API unificada via API Gateway
- Oferece painel de controle administrativo

**Stack tecnológico:**
- Backend: Python (FastAPI) + JavaScript (Node.js/Express)
- Banco vetorial: ChromaDB
- LLM: Ollama (llama3)
- Message broker: RabbitMQ
- Orquestração: Docker Compose

---

## Arquitetura

### Diagrama de componentes

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
       │ POST /chat       │ POST /mcp/tool       │ GET /health
       ▼                  ▼                      ▼
┌──────────────┐  ┌──────────────┐   ┌──────────────────────┐
│ servico-rag  │  │ servico-mcp  │   │ servico-controlador  │
│    :8001     │  │    :8002     │   │       :3001          │
│              │  │              │   │                      │
│ LangChain +  │  │ Ferramentas: │   │ Status + logs +      │
│ ChromaDB +   │  │ • cotacao    │   │ trigger ingestão     │
│ Ollama       │  │ • clima      │   │                      │
└──────┬───────┘  │ • noticias   │   └──────────────────────┘
       │          └──────────────┘
       │ (interno) enriquece contexto
       └──────────────────────────────► servico-mcp /invoke
```

### Componentes de infraestrutura

```
┌─────────────────────────────────────────┐
│  ChromaDB :8000 (banco vetorial)        │
│  volume: chroma-data                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  Ollama :11434 (serviço LLM)            │
│  • llama3 (geração)                     │
│  • nomic-embed-text (embeddings)        │
│  volume: ollama-data                    │
└─────────────────────────────────────────┘

┌─────────────────────────────────────────┐
│  RabbitMQ :5672 / :15672 (painel)       │
│  fila: cafeiq.ingestao                  │
│  usuário: cafeiq / cafeiq123            │
│  volume: rabbitmq-data                  │
└─────────────────────────────────────────┘

                    ▼
          servico-scrapper
          (publica a cada 60s)
                    │
                    └──► RabbitMQ ──► servico-rag (consumer)
```

---

## Instalação e Execução

### Requisitos

| Ferramenta | Versão mínima |
|---|---|
| Docker Desktop | 24.x |
| Docker Compose | 2.x (plugin) |
| curl / curl.exe | qualquer |

### Passos

#### 1. Clonar repositório

```bash
git clone <url-do-repositorio>
cd cafe-iq
```

#### 2. Subir containers

```bash
docker compose up --build
```

Aguarde até ver:
```
cafeiq-api-gateway     | api-gateway listening on port 3000
cafeiq-servico-rag     | INFO:     Application startup complete.
cafeiq-servico-mcp     | INFO:     Application startup complete.
cafeiq-servico-scrapper | INFO:   Application startup complete.
cafeiq-servico-controlador | INFO:   Application startup complete.
```

#### 3. Puxar modelos Ollama

Em outro terminal (após step 2):

```bash
# Modelo LLM para geração de respostas (4.7 GB)
docker exec cafeiq-ollama ollama pull llama3

# Modelo para embeddings (274 MB)
docker exec cafeiq-ollama ollama pull nomic-embed-text
```

#### 4. Abrir interface web

Abra `index.html` no navegador ou acesse via API.

### Windows: Notas importantes

No PowerShell, `curl` é um alias de `Invoke-WebRequest`. Use `curl.exe`:

```bash
# Linux
curl -s -X POST http://localhost:3001/forcar-ingestao

# Powershell
curl.exe -s -X POST http://localhost:3001/forcar-ingestao
```

Para formatar JSON no PowerShell (sem `jq`):

```powershell
curl.exe -s http://localhost:3001/status | ConvertFrom-Json
```

---

## Serviços

### 1. API Gateway

**Responsabilidade**: Roteamento centralizado de requisições do cliente

- **Linguagem**: JavaScript (Node.js + Express)
- **Porta**: 3000
- **Arquivo**: [api-gateway.md](./api-gateway.md)

**Endpoints principais:**
- `POST /chat` → `servico-rag` (responde pergunta)
- `POST /mcp/tool` → `servico-mcp` (invoca ferramenta)
- `GET /health` → verifica saúde de todos os serviços

---

### 2. Serviço MCP

**Responsabilidade**: Exposição de ferramentas externas para dados em tempo real

- **Linguagem**: Python (FastAPI)
- **Porta**: 8002
- **Arquivo**: [servico-mcp.md](./servico-mcp.md)

**Ferramentas disponíveis:**
- `cotacao_cafe`: cotação simulada (ICE e B3)
- `clima`: condições meteorológicas simuladas
- `noticias`: manchetes de notícias simuladas

---

### 3. Serviço RAG

**Responsabilidade**: Responder perguntas combinando busca vetorial, contexto MCP e LLM

- **Linguagem**: Python (FastAPI + LangChain)
- **Porta**: 8001
- **Arquivo**: [servico-rag.md](./servico-rag.md)

**Funcionalidades:**
- Enriquecimento de contexto com dados MCP em tempo real
- Busca vetorial em ChromaDB
- Geração de respostas via Ollama
- Consumer RabbitMQ para ingestão assíncrona

---

### 4. Serviço Scrapper

**Responsabilidade**: Coleta periódica de dados simulados e publicação em RabbitMQ

- **Linguagem**: Python (FastAPI)
- **Porta**: 8003
- **Arquivo**: [servico-scrapper.md](./servico-scrapper.md)

**Dados coletados a cada ciclo:**
- 2 notícias
- 1 clima (Lavras-MG)
- 1 cotação

**Intervalo**: 60 segundos (configurável)

---

### 5. Serviço Controlador

**Responsabilidade**: Painel administrativo com status e disparo manual de ingestão

- **Linguagem**: JavaScript (Node.js + Express)
- **Porta**: 3001
- **Arquivo**: [servico-controlador.md](./servico-controlador.md)

**Funcionalidades:**
- Monitoramento consolidado de saúde
- Disparo manual de coleta
- Ring buffer de 20 logs recentes

---

## Endpoints e Uso

### Pergunta ao assistente

```bash
curl.exe -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual é a cotação atual do café arábica?"}'
```

**Resposta:**
```json
{
  "resposta": "A cotação atual...",
  "fontes": ["scrapper/cotacao", "scrapper/noticia"]
}
```

### Invocar ferramenta MCP diretamente

```bash
# Cotação
curl.exe -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "cotacao_cafe", "params": {}}'

# Clima
curl.exe -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "clima", "params": {"cidade": "Varginha"}}'

# Notícias
curl.exe -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "noticias", "params": {}}'
```

### Forçar coleta manualmente

```bash
curl.exe -s -X POST http://localhost:3001/forcar-ingestao
```

### Verificar saúde do sistema

```bash
# Via Gateway
curl.exe -s http://localhost:3000/health

# Via Controlador
curl.exe -s http://localhost:3001/status

# Logs do Controlador
curl.exe -s http://localhost:3001/logs
```

### Indexar documento manualmente

```bash
curl.exe -s -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{"texto": "Safra 2025 atinge recordes.", "fonte": "conab"}'
```

### Listar ferramentas disponíveis

```bash
curl.exe -s http://localhost:8002/tools
```

---

## Configuração

### Variáveis de ambiente

#### servico-rag

```bash
OLLAMA_BASE_URL=http://ollama:11434
CHROMA_HOST=chromadb
CHROMA_PORT=8000
COLLECTION_NAME=cafeiq
LLM_MODEL=llama3
EMBED_MODEL=nomic-embed-text
RETRIEVER_K=4
MCP_URL=http://servico-mcp:8002
RABBITMQ_HOST=event-bus
RABBITMQ_PORT=5672
RABBITMQ_USER=cafeiq
RABBITMQ_PASS=cafeiq123
QUEUE_NAME=cafeiq.ingestao
CONSUMER_RETRY_DELAY=5
```

#### servico-scrapper

```bash
RABBITMQ_HOST=event-bus
RABBITMQ_PORT=5672
RABBITMQ_USER=cafeiq
RABBITMQ_PASS=cafeiq123
QUEUE_NAME=cafeiq.ingestao
COLLECT_INTERVAL=60
```

#### api-gateway

```bash
PORT=3000
RAG_URL=http://servico-rag:8001
MCP_URL=http://servico-mcp:8002
CONTROLADOR_URL=http://servico-controlador:3001
```

#### servico-controlador

```bash
PORT=3001
GATEWAY_URL=http://api-gateway:3000
SCRAPPER_URL=http://servico-scrapper:8003
```

---

## Fluxos de dados

### Fluxo síncrono: Resposta a pergunta

```
1. Cliente
   └─ POST /chat {"pergunta": "..."}
      │
      ▼
2. api-gateway
   └─ POST /query
      │
      ▼
3. servico-rag
   ├─ 1. mcp_enricher.fetch_enrichments()
   │      └─ Detecta keywords
   │         └─ Chama servico-mcp para dados em tempo real
   │
   ├─ 2. get_vectorstore().as_retriever(k=4)
   │      └─ Busca no ChromaDB
   │
   ├─ 3. Monta prompt com:
   │      ├─ [Dados em tempo real] ← resultado MCP
   │      ├─ [Base de conhecimento] ← docs ChromaDB
   │      └─ Pergunta: ...
   │
   ├─ 4. Ollama (llama3)
   │      └─ Gera resposta
   │
   └─ 5. Retorna {"resposta": "...", "fontes": [...]}
      │
      ▼
4. api-gateway
   └─ Encaminha resposta
      │
      ▼
5. Cliente
   └─ Recebe resposta
```

### Fluxo assíncrono: Ingestão de dados

```
1. servico-scrapper (a cada 60s ou manual)
   ├─ collectors.run_cycle()
   │  ├─ collect_noticias() → 2 notícias
   │  ├─ collect_clima() → 1 clima
   │  └─ collect_cotacao() → 1 cotação
   │
   └─ publisher.publish_many(messages)
      └─ RabbitMQ (fila: cafeiq.ingestao)
         │
         ▼
2. servico-rag (consumer em thread)
   ├─ _on_message()
   ├─ Mapeia mensagem → (texto, fonte)
   ├─ ingest_document(texto, fonte)
   │  └─ ChromaDB (indexa com embedding nomic-embed-text)
   └─ basic_ack() ← sucesso
      ou basic_nack(requeue=False) ← falha permanente
```

---

## Troubleshooting

### Erro: "model 'nomic-embed-text' not found"

**Causa**: Modelo não foi puxado do Ollama

**Solução**:
```bash
docker exec cafeiq-ollama ollama pull nomic-embed-text
```

### Erro: "connection refused" ao chamar serviço

**Causa**: Serviço não está rodando ou porta está bloqueada

**Solução**:
```bash
# Verificar status dos containers
docker compose ps

# Verificar logs
docker compose logs cafeiq-servico-rag

# Reiniciar serviço
docker compose restart cafeiq-servico-rag
```

### Curl não funciona no PowerShell

**Causa**: `curl` é alias de `Invoke-WebRequest` no PowerShell

**Solução**: Use `curl.exe` explicitamente
```powershell
curl.exe -s http://localhost:3000/health
```

### RabbitMQ painel acessível

- URL: http://localhost:15672
- Usuário: `cafeiq`
- Senha: `cafeiq123`

### ChromaDB painel acessível

- URL: http://localhost:8000

### Limpar dados e recomeçar

```bash
# Parar containers
docker compose down

# Remover volumes (limpa dados persistidos)
docker volume rm cafe-iq_chroma-data cafe-iq_ollama-data cafe-iq_rabbitmq-data

# Subir novamente
docker compose up --build
```

### Consumo de disco alto

Os modelos Ollama ocupam ~5 GB. Se precisar liberar espaço:

```bash
# Ver volume Ollama
docker volume inspect cafe-iq_ollama-data

# Remover (vai refazer download ao subir)
docker volume rm cafe-iq_ollama-data
```

---

## Estrutura de arquivos

```
cafe-iq/
├── index.html                      # Interface web
├── docker-compose.yml              # Orquestração
├── README.md                       # Visão geral
├── docs/
│   ├── DOC.md                      # Este arquivo (documentação geral)
│   ├── documentacao_completa.md    # Documentação anterior (referência)
│   ├── api-gateway.md              # Documentação API Gateway
│   ├── servico-mcp.md              # Documentação Serviço MCP
│   ├── servico-rag.md              # Documentação Serviço RAG
│   ├── servico-scrapper.md         # Documentação Serviço Scrapper
│   ├── servico-controlador.md      # Documentação Serviço Controlador
│   └── arquitetura.md              # Justificativas arquiteturais
├── api-gateway/
│   ├── Dockerfile
│   ├── package.json
│   ├── package-lock.json
│   └── src/
│       └── index.js
├── servico-mcp/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── registry.py
│       └── tools/
│           ├── __init__.py
│           ├── cotacao_cafe.py
│           ├── clima.py
│           └── noticias.py
├── servico-rag/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── rag.py
│       ├── mcp_enricher.py
│       ├── consumer.py
├── servico-scrapper/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── collectors.py
│       └── publisher.py
└── servico-controlador/
    ├── Dockerfile
    ├── package.json
    ├── package-lock.json
    └── src/
        └── index.js
```

---

## Próximos passos

1. **Substituir mocks por APIs reais**:
   - Cotação: ICE WebAPI ou B3 API
   - Clima: OpenWeatherMap ou INMET API
   - Notícias: NewsAPI ou API customizada

2. **Melhorar validação**:
   - Validar entrada de usuário
   - Limitar taxa de requisições (rate limiting)
   - Autenticação/autorização

3. **Produção**:
   - Usar orchestração Kubernetes
   - Setup de CI/CD
   - Monitoramento com Prometheus + Grafana
   - Backup automático de dados

---

## Referências

- **FastAPI**: https://fastapi.tiangolo.com/
- **LangChain**: https://python.langchain.com/
- **ChromaDB**: https://docs.trychroma.com/
- **Ollama**: https://ollama.ai/
- **RabbitMQ**: https://www.rabbitmq.com/
- **Express**: https://expressjs.com/

---

**Última atualização**: 2025-06-16

Para dúvidas sobre um serviço específico, consulte o arquivo `docs/servico-*.md` correspondente.
