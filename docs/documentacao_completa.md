# Documentação Completa — CaféIQ

## Visão geral

CaféIQ é um assistente inteligente para o mercado de café, composto por microsserviços distribuídos. O sistema combina:

- RAG (Retrieval-Augmented Generation) usando ChromaDB + Ollama
- Ferramentas MCP para consulta de dados em tempo real (cotação, clima, notícias)
- Coleta assíncrona de dados via RabbitMQ
- Uma interface HTTP unificada via API Gateway
- Um painel de controle para status e disparo manual de ingestão

---

## Arquitetura de alto nível

O sistema possui os seguintes componentes:

- `api-gateway`: roteia as solicitações do browser para os serviços de backend e expõe endpoints públicos.
- `servico-rag`: gera respostas usando busca vetorial e LLM, além de ingerir documentos no ChromaDB a partir de mensagens RabbitMQ.
- `servico-mcp`: expõe ferramentas de dados em tempo real como serviços especializados.
- `servico-scrapper`: coleta dados simulados periodicamente e publica mensagens no RabbitMQ.
- `servico-controlador`: painel administrativo que consulta o gateway e dispara ingestão manual.
- `ollama`: servidor de modelos LLM/embedding.
- `chromadb`: banco vetorial usado pelo serviço RAG.
- `event-bus` (RabbitMQ): barramento de mensagens para ingestão assíncrona.

---

## Serviços e responsabilidades

### api-gateway

- Linguagem: JavaScript (Node.js)
- Dependências: `express`, `axios`
- Entrypoint: `api-gateway/src/index.js`
- Portas: `3000`

#### Endpoints

- `POST /chat`
  - Encaminha corpo JSON para `servico-rag` em `/query`
  - Responde com JSON retornado pelo serviço RAG
- `POST /mcp/tool`
  - Encaminha corpo JSON para `servico-mcp` em `/invoke`
  - Responde com JSON retornado pelo serviço MCP
- `GET /health`
  - Verifica saúde de `servico-rag`, `servico-mcp` e `servico-controlador`
  - Retorna status 200 se todos estiverem ok ou 207 em caso de falha parcial

#### Observações

- Implementa CORS aberto para permitir chamadas do browser direto de `file://`
- Loga latência e status de cada requisição

---

### servico-mcp

- Linguagem: Python
- Framework: FastAPI
- Dependências: `fastapi`, `uvicorn`, `pydantic`
- Entrypoint: `servico-mcp/app/main.py`
- Portas: `8002`

#### Endpoints

- `GET /health`
  - Retorna `{ "status": "ok" }`
- `GET /tools`
  - Retorna metadados das ferramentas registradas
- `POST /invoke`
  - Recebe `tool` e `params`
  - Executa a função registrada em `app.registry.TOOLS`
  - Retorna `{"tool": ..., "resultado": ...}`

#### Ferramentas disponíveis

- `cotacao_cafe`
  - Retorna cotação simulada de café arábica
  - Implementado em `app/tools/cotacao_cafe.py`
- `clima`
  - Retorna condições climáticas simuladas para uma cidade
  - Implementado em `app/tools/clima.py`
- `noticias`
  - Retorna 3 manchetes de notícias simuladas sobre café
  - Implementado em `app/tools/noticias.py`

#### Notas técnicas

- A validação de parâmetro usa `pydantic.BaseModel` com `tool: str` e `params: dict`
- Se a ferramenta não existir, retorna 404 com mensagem amigável
- Em caso de erro interno, retorna 500

---

### servico-rag

- Linguagem: Python
- Framework: FastAPI
- Dependências: `fastapi`, `uvicorn`, `langchain`, `langchain-community`, `chromadb`, `pydantic`, `pika`
- Entrypoint: `servico-rag/app/main.py`
- Portas: `8001`

#### Endpoints

- `GET /health`
  - Retorna `{ "status": "ok" }`
- `POST /query`
  - Recebe `{ "pergunta": "..." }`
  - Enriqueces a pergunta com dados MCP relevantes
  - Executa busca vetorial e gera resposta via LLM
  - Retorna `{ "resposta": ..., "fontes": [...] }`
- `POST /ingest`
  - Recebe `{ "texto": "...", "fonte": "..." }`
  - Indexa documento no ChromaDB
  - Retorna `{ "id": ..., "mensagem": ... }`

#### Módulos principais

- `app/config.py`
  - Configura variáveis de ambiente para URLs, modelos e RabbitMQ
- `app/mcp_enricher.py`
  - Detecta palavras-chave na pergunta
  - Chama `servico-mcp` via HTTP e formata respostas contextuais
- `app/rag.py`
  - Cria vetor de embeddings via Ollama
  - Consulta ChromaDB
  - Prepara prompt com contexto e pergunta
  - Invoca Ollama para gerar a resposta
  - Adiciona documentos ao banco vetorial
- `app/consumer.py`
  - Consome a fila RabbitMQ `cafeiq.ingestao`
  - Converte mensagens em texto para indexação
  - Indexa notificações, clima e cotações

#### Fluxo RAG

1. `api-gateway` encaminha `POST /chat` para `servico-rag/query`
2. `servico-rag` usa `mcp_enricher.fetch_enrichments()` para coletar contexto em tempo real
3. `servico-rag` busca documentos relevantes no ChromaDB usando `RETRIEVER_K`
4. Monta prompt com contexto MCP + base de conhecimento
5. Invoca Ollama LLM (`llama3`) para gerar a resposta
6. Retorna `resposta` e `fontes`

#### Fluxo de ingestão assíncrona

- `servico-scrapper` publica mensagens em RabbitMQ
- `servico-rag` executa um consumer em thread de background
- Mensagens são convertidas em texto e indexadas no ChromaDB
- Eventos processados recebem `basic_ack`; falhas persistentes usam `basic_nack(requeue=False)`

#### Observações

- O serviço inicia o consumer RabbitMQ no lifespan do FastAPI
- A conexão ao RabbitMQ se reconecta com atraso em caso de falha
- O `source_documents` retornado pela busca é usado para extrair fontes

---

### servico-scrapper

- Linguagem: Python
- Framework: FastAPI
- Dependências: `fastapi`, `uvicorn`, `pika`, `pydantic`
- Entrypoint: `servico-scrapper/app/main.py`
- Portas: `8003`

#### Endpoints

- `GET /health`
  - Retorna `{ "status": "ok" }`
- `POST /coletar-agora`
  - Dispara coleta manual usando um evento interno
  - Retorna `{ "mensagem": "Coleta manual disparada.", "ok": true }`

#### Módulos principais

- `app/collectors.py`
  - Gera dados simulados de `noticia`, `clima` e `cotacao`
  - `run_cycle()` produz 4 mensagens por ciclo
- `app/publisher.py`
  - Conecta ao RabbitMQ e publica mensagens de forma persistente
  - Re-tenta conexão em caso de falha
- `app/main.py`
  - Inicia um thread de coleta contínua
  - Executa ciclo a cada `COLLECT_INTERVAL` segundos
  - Usa `_manual_trigger` para coletar imediatamente quando solicitado

#### Fluxo de coleta

1. Thread de coleta entra em loop infinito após startup
2. Chama `run_cycle()` para gerar 4 mensagens simuladas
3. Publica todas as mensagens em `cafeiq.ingestao`
4. Espera `COLLECT_INTERVAL` segundos ou recebe trigger manual

---

### servico-controlador

- Linguagem: JavaScript (Node.js)
- Dependências: `express`, `axios`
- Entrypoint: `servico-controlador/src/index.js`
- Portas: `3001`

#### Endpoints

- `GET /health`
  - Retorna `{ "status": "ok" }`
- `GET /status`
  - Consulta `api-gateway` em `/health`
  - Retorna informações consolidadas de saúde
- `POST /forcar-ingestao`
  - Encaminha requisição para `servico-scrapper/coletar-agora`
  - Retorna resposta do scrapper
- `GET /logs`
  - Retorna os últimos 20 logs em memória

#### Observações

- Mantém um ring buffer de logs em memória
- Loga todas as requisições recebidas
- Usado como painel administrativo leve

---

## Infraestrutura (Docker Compose)

O arquivo `docker-compose.yml` orquestra todos os serviços e containers necessários.

### Containers definidos

- `api-gateway` → expõe `3000`
- `servico-rag` → expõe `8001`
- `servico-mcp` → expõe `8002`
- `servico-scrapper` → expõe `8003`
- `servico-controlador` → expõe `3001`
- `ollama` → expõe `11434`
- `chromadb` → expõe `8000`
- `event-bus` (RabbitMQ) → expõe `5672` e `15672`

### Volumes

- `ollama-data`: persistência dos modelos Ollama
- `chroma-data`: persistência da base vetorial ChromaDB
- `rabbitmq-data`: persistência do RabbitMQ

### Rede

- `cafeiq-net`: rede bridge compartilhada entre serviços

### Dependências de inicialização

- `api-gateway` espera `event-bus`, `servico-rag`, `servico-mcp` e `servico-controlador`
- `servico-rag` espera `chromadb`, `ollama` e `event-bus`
- `servico-mcp` espera `event-bus`
- `servico-scrapper` espera `event-bus`
- `servico-controlador` espera `event-bus`

---

## Configurações e variáveis de ambiente

### servico-rag

- `OLLAMA_BASE_URL` (padrão `http://ollama:11434`)
- `CHROMA_HOST` (padrão `chromadb`)
- `CHROMA_PORT` (padrão `8000`)
- `COLLECTION_NAME` (padrão `cafeiq`)
- `LLM_MODEL` (padrão `llama3`)
- `EMBED_MODEL` (padrão `nomic-embed-text`)
- `RETRIEVER_K` (padrão `4`)
- `MCP_URL` (padrão `http://servico-mcp:8002`)
- `RABBITMQ_HOST` (padrão `event-bus`)
- `RABBITMQ_PORT` (padrão `5672`)
- `RABBITMQ_USER` (padrão `cafeiq`)
- `RABBITMQ_PASS` (padrão `cafeiq123`)
- `QUEUE_NAME` (padrão `cafeiq.ingestao`)
- `CONSUMER_RETRY_DELAY` (padrão `5`)

### servico-scrapper

- `RABBITMQ_HOST` (padrão `event-bus`)
- `RABBITMQ_PORT` (padrão `5672`)
- `RABBITMQ_USER` (padrão `cafeiq`)
- `RABBITMQ_PASS` (padrão `cafeiq123`)
- `QUEUE_NAME` (padrão `cafeiq.ingestao`)
- `COLLECT_INTERVAL` (padrão `60`)

### api-gateway

- `RAG_URL` (padrão `http://servico-rag:8001`)
- `MCP_URL` (padrão `http://servico-mcp:8002`)
- `CONTROLADOR_URL` (padrão `http://servico-controlador:3001`)

### servico-controlador

- `GATEWAY_URL` (padrão `http://api-gateway:3000`)
- `SCRAPPER_URL` (padrão `http://servico-scrapper:8003`)

---

## Como rodar o sistema

### Requisitos

- Docker Desktop com Compose v2
- `curl` ou `curl.exe` no Windows
- `jq` opcional para formatação JSON

### Passos

1. `git clone <url-do-repositorio>`
2. `cd cafe-iq`
3. `docker compose up --build`

### Após o build

Abra outro terminal e execute:

```bash
docker exec cafeiq-ollama ollama pull llama3
docker exec cafeiq-ollama ollama pull nomic-embed-text
```

### Notas para Windows

No PowerShell, use `curl.exe` em vez de `curl` para evitar o alias `Invoke-WebRequest`.

Para formatar JSON no PowerShell:

```powershell
curl.exe -s -X POST http://localhost:3001/forcar-ingestao | ConvertFrom-Json
```

---

## Endpoints principais

### API pública

- `POST http://localhost:3000/chat`
  - Corpo: `{ "pergunta": "..." }`
- `POST http://localhost:3000/mcp/tool`
  - Corpo: `{ "tool": "...", "params": {...} }`
- `GET http://localhost:3000/health`

### Serviço RAG

- `POST http://localhost:8001/query`
- `POST http://localhost:8001/ingest`
- `GET http://localhost:8001/health`

### Serviço MCP

- `GET http://localhost:8002/health`
- `GET http://localhost:8002/tools`
- `POST http://localhost:8002/invoke`

### Serviço Scrapper

- `GET http://localhost:8003/health`
- `POST http://localhost:8003/coletar-agora`

### Serviço Controlador

- `GET http://localhost:3001/health`
- `GET http://localhost:3001/status`
- `POST http://localhost:3001/forcar-ingestao`
- `GET http://localhost:3001/logs`

---

## Casos de uso

### Perguntar ao assistente

```bash
curl -s -X POST http://localhost:3000/chat \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual é a cotação atual do café arábica?"}'
```

### Invocar ferramenta MCP diretamente

```bash
curl -s -X POST http://localhost:3000/mcp/tool \
  -H "Content-Type: application/json" \
  -d '{"tool": "cotacao_cafe", "params": {}}'
```

### Forçar coleta manualmente

```bash
curl.exe -s -X POST http://localhost:3001/forcar-ingestao
```

---

## Observações e possíveis melhorias

- As ferramentas MCP são mocks e podem ser substituídas por APIs reais.
- O serviço RAG depende de `nomic-embed-text` e `llama3` no Ollama. Os modelos precisam ser puxados no container `cafeiq-ollama`.
- A validação e tratamento de erros podem ser ampliados para maior robustez.
- A interface web é um arquivo estático simples (`index.html`) e não está descrita aqui, mas funciona via gateway.

---

## Referência de arquivos

- `docker-compose.yml`
- `api-gateway/src/index.js`
- `servico-mcp/app/main.py`
- `servico-mcp/app/registry.py`
- `servico-mcp/app/tools/*.py`
- `servico-rag/app/main.py`
- `servico-rag/app/rag.py`
- `servico-rag/app/mcp_enricher.py`
- `servico-rag/app/consumer.py`
- `servico-scrapper/app/main.py`
- `servico-scrapper/app/collectors.py`
- `servico-scrapper/app/publisher.py`
- `servico-controlador/src/index.js`
