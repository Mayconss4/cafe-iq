# SYSTEM SPECIFICATION - CaféIQ

**Objetivo**: Especificação completa e estruturada do sistema CaféIQ para uso como prompt para IA entender arquitetura e esquemas.

---

## 1. VISÃO GERAL DO SISTEMA

**Nome do Sistema**: CaféIQ  
**Tipo**: Assistente inteligente distribuído em microsserviços  
**Domínio**: Mercado de café (cotações, clima, notícias)  
**Estilo Arquitetural**: Event-Driven Microservices + RAG (Retrieval-Augmented Generation)

**Características principais**:
- Responde perguntas combinando busca vetorial, dados em tempo real e LLM
- Coleta dados assincronamente via RabbitMQ
- Mantém base de conhecimento vetorizada em ChromaDB
- Oferece painel administrativo para monitoramento

---

## 2. COMPONENTES DO SISTEMA

### 2.1 API Gateway (:3000)

**Tecnologia**: Node.js + Express  
**Responsabilidade**: Roteamento centralizado e ponto de entrada único

**Endpoints**:
```
POST /chat
  Input:  {"pergunta": "string"}
  Output: {"resposta": "string", "fontes": ["string"]}
  Roteia para: servico-rag:8001/query

POST /mcp/tool
  Input:  {"tool": "string", "params": {}}
  Output: {qualquer} (variável conforme ferramenta)
  Roteia para: servico-mcp:8002/invoke

GET /health
  Output: {"status": "healthy|unhealthy", "services": {}}
  Verifica: Saúde de todos os serviços
```

**Responsabilidades internas**:
- Validação de entrada
- Rate limiting (opcional)
- Logging centralizado
- Tratamento de erros HTTP

---

### 2.2 Serviço MCP (:8002)

**Tecnologia**: Python + FastAPI  
**Responsabilidade**: Provisão de ferramentas externas (Model Context Protocol)

**Ferramentas disponíveis**:

#### Tool: cotacao_cafe
```
Endpoint: POST /invoke
Input:  {"tool": "cotacao_cafe", "params": {}}
Output: {
  "tipo": "cotacao",
  "produto": "cafe_arabica",
  "preco_usc_lb": 245.50 (float),
  "coletado_em": "2025-06-16T10:30:45.123456",
  "fonte": "mock" (string: "mock" | "ice" | "b3")
}
Dados**: Simulados. Futuramente: API real (ICE WebAPI, B3 API)
```

#### Tool: clima
```
Endpoint: POST /invoke
Input:  {"tool": "clima", "params": {"cidade": "string"}}
Output: {
  "tipo": "clima",
  "cidade": "Lavras-MG" (string),
  "temperatura_c": 25.3 (float),
  "umidade_pct": 72 (int),
  "condicao": "Parcialmente nublado" (enum: "Ensolarado", "Parcialmente nublado", "Nublado", "Chuva leve"),
  "coletado_em": "2025-06-16T10:30:45.123456",
  "fonte": "mock"
}
Dados**: Simulados. Futuramente: OpenWeatherMap API, INMET API
```

#### Tool: noticias
```
Endpoint: POST /invoke
Input:  {"tool": "noticias", "params": {}}
Output: {
  "tipo": "noticia",
  "titulo": "string" (ex: "Safra 2025 supera expectativas"),
  "coletado_em": "2025-06-16T10:30:45.123456",
  "fonte": "mock"
}
Dados**: Lista de 2 manchetes aleatórias de pool pré-definido. Futuramente: NewsAPI, scraping
```

**Endpoint adicional**:
```
GET /tools
Output: {"tools": ["cotacao_cafe", "clima", "noticias"]}
```

---

### 2.3 Serviço RAG (:8001)

**Tecnologia**: Python + FastAPI + LangChain  
**Responsabilidade**: Processamento de perguntas + indexação de documentos

**Arquitetura interna**:
```
RAG (Retrieval-Augmented Generation) =
  Retrieval:  Busca documentos no ChromaDB
  + Augmentation: Enriquece com dados MCP em tempo real
  + Generation: Ollama gera resposta contextualizada
```

#### Endpoint: POST /query
```
Input: {
  "pergunta": "Qual é a cotação do café?" (string)
}

Processing:
  1. mcp_enricher.fetch_enrichments(pergunta)
     ├─ Detecta keywords: ["cotação", "preço", "clima", "notícia"]
     └─ Para cada keyword, chama servico-mcp correspondente
        └─ Retorna {keyword: resultado_mcp}

  2. vectorstore.as_retriever(k=4).get_relevant_documents(pergunta)
     ├─ Query no ChromaDB com embedding
     └─ Retorna até 4 documentos mais similares

  3. monta_prompt(pergunta, docs, enrichments)
     ├─ Template:
     │  """
     │  [DADOS EM TEMPO REAL]
     │  {enrichments}
     │  
     │  [BASE DE CONHECIMENTO]
     │  {docs}
     │  
     │  Pergunta: {pergunta}
     │  """
     └─ Passa para LLM

  4. ollama.invoke(prompt)
     └─ llama3 gera resposta

Output: {
  "resposta": "A cotação atual do café arábica é $245.50/lb..." (string),
  "fontes": ["mcp/cotacao_cafe", "chroma/doc_3", "chroma/doc_7"] (list)
}
```

#### Endpoint: POST /ingest
```
Input: {
  "texto": "Safra 2025 atingiu 12 milhões de sacas." (string),
  "fonte": "conab-2025" (string)
}

Processing:
  1. rag.ingest_document(texto, fonte)
  2. Gera embedding com nomic-embed-text
  3. Armazena em ChromaDB com metadados

Output: {
  "status": "success|error",
  "message": "Documento indexado com sucesso"
}
```

#### Componente interno: Consumer RabbitMQ
```
Função: Consome mensagens de fila cafeiq.ingestao continuamente

Loop:
  1. Aguarda mensagem em fila
  2. Se chegou mensagem:
     ├─ Extrai {"texto": "...", "fonte": "..."}
     ├─ Chama POST /ingest internamente
     ├─ Se sucesso: basic_ack()
     └─ Se falha: basic_nack(requeue=False)
  3. Volta ao passo 1

Rodas em**: Thread separada (não bloqueia API)
```

**Configuração** (via variáveis de ambiente):
```
OLLAMA_BASE_URL = "http://ollama:11434"
CHROMA_HOST = "chromadb"
CHROMA_PORT = 8000
COLLECTION_NAME = "cafeiq"
LLM_MODEL = "llama3"
EMBED_MODEL = "nomic-embed-text"
RETRIEVER_K = 4
MCP_URL = "http://servico-mcp:8002"
RABBITMQ_HOST = "event-bus"
RABBITMQ_PORT = 5672
RABBITMQ_USER = "cafeiq"
RABBITMQ_PASS = "cafeiq123"
QUEUE_NAME = "cafeiq.ingestao"
```

---

### 2.4 Serviço Scrapper (:8003)

**Tecnologia**: Python + FastAPI  
**Responsabilidade**: Coleta periódica de dados e publicação em RabbitMQ

#### Função: run_cycle() — Executada a cada 60s (configurável)
```python
def run_cycle():
  mensagens = []
  
  # Coleta 2 notícias aleatórias
  mensagens.extend(collect_noticias())  # → 2 mensagens tipo "noticia"
  
  # Coleta 1 clima (localização fixa: Lavras-MG)
  mensagens.append(collect_clima())     # → 1 mensagem tipo "clima"
  
  # Coleta 1 cotação
  mensagens.append(collect_cotacao())   # → 1 mensagem tipo "cotacao"
  
  return mensagens  # Total: 4 mensagens
```

#### Estrutura de mensagem publicada
```json
{
  "tipo": "noticia" | "clima" | "cotacao",
  "titulo": "string" (apenas para notícia),
  "cidade": "string" (apenas para clima),
  "produto": "cafe_arabica" (apenas para cotação),
  "temperatura_c": 25.3 (apenas para clima),
  "umidade_pct": 72 (apenas para clima),
  "condicao": "Ensolarado" (apenas para clima),
  "preco_usc_lb": 245.50 (apenas para cotação),
  "coletado_em": "ISO 8601 timestamp",
  "fonte": "mock"
}
```

#### Endpoint: POST /coletar-agora
```
Trigger manual da coleta (sem aguardar 60s)

Input: {} (vazio)
Output: {
  "status": "success",
  "mensagens_publicadas": 4
}
```

**Configuração** (via variáveis de ambiente):
```
RABBITMQ_HOST = "event-bus"
RABBITMQ_PORT = 5672
RABBITMQ_USER = "cafeiq"
RABBITMQ_PASS = "cafeiq123"
QUEUE_NAME = "cafeiq.ingestao"
COLLECT_INTERVAL = 60 (segundos)
```

---

### 2.5 Serviço Controlador (:3001)

**Tecnologia**: Node.js + Express  
**Responsabilidade**: Painel administrativo e monitoramento

#### Endpoint: GET /status
```
Output: {
  "gateway": {"status": "healthy|unhealthy", "latency_ms": 5},
  "rag": {"status": "healthy|unhealthy", "latency_ms": 12},
  "mcp": {"status": "healthy|unhealthy", "latency_ms": 8},
  "scrapper": {"status": "healthy|unhealthy", "latency_ms": 10},
  "rabbitmq": {"status": "healthy|unhealthy"},
  "chromadb": {"status": "healthy|unhealthy"},
  "ollama": {"status": "healthy|unhealthy"},
  "system_status": "operational|degraded|down"
}
```

#### Endpoint: GET /logs
```
Output: {
  "logs": [
    {
      "timestamp": "ISO 8601",
      "level": "INFO|WARN|ERROR",
      "service": "string",
      "message": "string"
    }
  ]
}
Ring buffer**: Últimas 20 mensagens
```

#### Endpoint: POST /forcar-ingestao
```
Trigger manual no scrapper

Output: {
  "status": "success|error",
  "message": "Coleta acionada"
}

Internamente chama: POST servico-scrapper:8003/coletar-agora
```

---

## 3. COMPONENTES DE INFRAESTRUTURA

### 3.1 Ollama (:11434)

**Função**: Motor de LLM e embeddings  
**Tipo**: Serviço HTTP externo (roda em container Docker)

**Modelos utilizados**:

#### llama3 (Model Context: generation)
```
Endpoint: POST /api/generate
Input: {
  "model": "llama3",
  "prompt": "string",
  "stream": false
}
Output: {
  "response": "string",
  "model": "llama3",
  "created_at": "timestamp"
}
Tamanho**: ~4.7 GB
Tempo resposta**: ~2-5 segundos (depende de hardware)
```

#### nomic-embed-text (Model Context: embeddings)
```
Endpoint: POST /api/embeddings
Input: {
  "model": "nomic-embed-text",
  "prompt": "string"
}
Output: {
  "embedding": [float, float, ...] (dimensionalidade: 768),
  "model": "nomic-embed-text"
}
Tamanho**: ~274 MB
Tempo resposta**: ~50-200ms
```

---

### 3.2 ChromaDB (:8000)

**Função**: Banco de dados vetorial (vector store)  
**Tipo**: Serviço HTTP (container Docker)

**Operações**:

#### Add/Index
```
Internamente via LangChain:
  vectorstore.add_texts(
    texts=["documento 1", "documento 2"],
    metadatas=[{"fonte": "conab"}, {"fonte": "conab"}],
    embedding_function=OllamaEmbeddings(...)
  )

Resultado:
  ├─ Gera embedding para cada documento
  ├─ Armazena embedding + metadados
  └─ Indexa para busca rápida
```

#### Search
```
Internamente via LangChain:
  docs = vectorstore.similarity_search(
    query="Qual é a cotação?",
    k=4
  )

Resultado: Lista de (documento, score_similaridade)
```

**Collection**: "cafeiq" (fixa)  
**Volume Docker**: chroma-data (persistido entre reinicializações)

---

### 3.3 RabbitMQ (:5672, painel :15672)

**Função**: Message broker para arquitetura event-driven  
**Tipo**: Serviço TCP + HTTP (container Docker)

**Fila**: cafeiq.ingestao
```
Tipo**: Durable queue
Consumidores**: servico-rag (consumer thread)
Produtores**: servico-scrapper (a cada 60s)
TTL**: Sem expiração (mensagens persistem)
```

**Credenciais**:
```
Username: cafeiq
Password: cafeiq123
Painel web**: http://localhost:15672
```

**Padrão de mensagem**:
```
{
  "tipo": "noticia|clima|cotacao",
  ... (conforme tipo)
}
```

---

## 4. FLUXOS DE DADOS

### 4.1 Fluxo Síncrono: Pergunta do Usuário

```
Ator: Usuário no navegador
Ação: Digita pergunta e clica "Enviar"

┌─────────────────────────────────────────────────────────────┐
│ Sequência de operações:                                     │
│                                                              │
│ 1. Browser (index.html)                                     │
│    └─ POST /chat {"pergunta": "Qual é a cotação do café?"}  │
│                                                              │
│ 2. API Gateway (:3000)                                      │
│    └─ POST servico-rag:8001/query                           │
│       └─ Aguarda resposta                                   │
│                                                              │
│ 3. Serviço RAG (:8001)                                      │
│    ├─ mcp_enricher.fetch_enrichments("Qual é a cotação...") │
│    │  └─ Detecta keywords: ["cotação", "preço"]             │
│    │  └─ POST servico-mcp:8002/invoke {"tool":"cotacao..."}│
│    │  └─ Retorna {"preco_usc_lb": 245.50, ...}             │
│    │                                                         │
│    ├─ vectorstore.similarity_search(pergunta, k=4)         │
│    │  └─ Retorna 4 documentos similares                    │
│    │                                                         │
│    ├─ monta_prompt(pergunta, docs, enrichments)            │
│    │  └─ Combina dados MCP + ChromaDB + pergunta           │
│    │                                                         │
│    └─ ollama.invoke(prompt)                                │
│       └─ llama3 gera resposta                              │
│       └─ Retorna {"resposta": "..."}                       │
│                                                              │
│ 4. API Gateway (:3000)                                      │
│    └─ Encaminha resposta para browser                       │
│                                                              │
│ 5. Browser                                                  │
│    └─ Exibe resposta ao usuário                            │
│                                                              │
│ Tempo total: ~2-5 segundos                                 │
└─────────────────────────────────────────────────────────────┘
```

**Diagrama de sequência** (ASCII):
```
User    Gateway    RAG    MCP    ChromaDB    Ollama
 │         │        │      │         │         │
 ├─POST /chat       │      │         │         │
 │──────────────>   │      │         │         │
 │         │   POST /query │      │         │
 │         ├─────────────> │      │         │
 │         │        │   GET enrichments     │
 │         │        ├─────────────>│         │
 │         │        │<─────────────┤         │
 │         │        │   search_docs         │
 │         │        ├──────────────────────>│
 │         │        │<──────────────────────┤
 │         │        │   invoke(prompt)      │
 │         │        ├─────────────────────────────>
 │         │        │<─────────────────────────────
 │         │<─ resposta ─┤      │         │
 │<──resposta ┤         │      │         │
```

---

### 4.2 Fluxo Assíncrono: Coleta e Ingestão de Dados

```
Ator: Sistema (automático a cada 60s)
Ação: Coleta dados e indexa

┌──────────────────────────────────────────────────────┐
│ Sequência de operações:                              │
│                                                       │
│ T=0s   Serviço Scrapper                              │
│        └─ run_cycle() executado                      │
│           ├─ collect_noticias() → 2 msgs             │
│           ├─ collect_clima() → 1 msg                 │
│           ├─ collect_cotacao() → 1 msg               │
│           └─ Total: 4 mensagens                      │
│                                                       │
│ T=0s+  Scrapper → RabbitMQ                           │
│        └─ Publica 4 mensagens na fila                │
│                                                       │
│ T=0s++ Serviço RAG (consumer thread)                 │
│        └─ Escuta fila (conexão permanente)           │
│        ├─ Recebe mensagem 1 (notícia)                │
│        │  └─ ingest_document(texto, fonte)           │
│        │  └─ Gera embedding nomic-embed-text         │
│        │  └─ Armazena em ChromaDB                    │
│        │  └─ basic_ack() ← sucesso                   │
│        │                                              │
│        ├─ Recebe mensagem 2 (notícia)                │
│        │  └─ [idem]                                  │
│        │                                              │
│        ├─ Recebe mensagem 3 (clima)                  │
│        │  └─ [idem]                                  │
│        │                                              │
│        └─ Recebe mensagem 4 (cotação)                │
│           └─ [idem]                                  │
│                                                       │
│ Resultado: ChromaDB agora tem 4 novos documentos    │
│            com embeddings indexados                  │
│                                                       │
│ T=60s  Ciclo se repete                              │
└──────────────────────────────────────────────────────┘
```

**Diagrama de sequência** (ASCII):
```
Scrapper    RabbitMQ    RAG (consumer)    ChromaDB    Ollama (embed)
   │            │             │              │            │
   ├─ run_cycle             │              │            │
   │ [coleta]
   │
   ├─ publish_many           │              │            │
   │────────────────────────>│              │            │
   │            │   _on_message             │            │
   │            ├───────────────────────>   │            │
   │            │            │   ingest_doc │            │
   │            │            ├──────────────────────────>│
   │            │            │   <─ embedding ─ [vector]
   │            │            │<───────────────────────────┤
   │            │            │   add_to_collection       │
   │            │            ├──────────────────────────>│
   │            │            │<──────────────────────────┤
   │            │   ack()     │              │            │
   │            │<────────────┤              │            │
```

---

## 5. ESTRUTURA DE DADOS

### 5.1 Mensagem de Fila RabbitMQ

```
Base (todos os tipos):
{
  "tipo": "noticia" | "clima" | "cotacao",
  "coletado_em": "2025-06-16T10:30:45.123456Z" (ISO 8601),
  "fonte": "mock" (string)
}

Tipo: noticia
{
  "tipo": "noticia",
  "titulo": "Safra 2025 supera expectativas",
  "coletado_em": "...",
  "fonte": "mock"
}

Tipo: clima
{
  "tipo": "clima",
  "cidade": "Lavras-MG",
  "temperatura_c": 25.3,
  "umidade_pct": 72,
  "condicao": "Ensolarado",
  "coletado_em": "...",
  "fonte": "mock"
}

Tipo: cotacao
{
  "tipo": "cotacao",
  "produto": "cafe_arabica",
  "preco_usc_lb": 245.50,
  "coletado_em": "...",
  "fonte": "mock"
}
```

### 5.2 Documento em ChromaDB

```
Armazenado como:
{
  "id": "uuid_gerado_automaticamente",
  "text": "Safra 2025 de café arábica no Sul...",
  "embedding": [0.123, -0.456, ...] (768 dimensões),
  "metadata": {
    "fonte": "scrapper/noticia",
    "tipo": "noticia",
    "coletado_em": "2025-06-16T10:30:45.123456Z"
  }
}
```

### 5.3 Resposta da Query RAG

```
{
  "resposta": "A cotação atual do café arábica é $245.50/lb, conforme dados de mercado coletados em 2025-06-16. A safra 2025 no Sul de Minas superou expectativas, atingindo 12 milhões de sacas.",
  "fontes": [
    "mcp/cotacao_cafe",
    "chroma/doc_abc123",
    "chroma/doc_def456"
  ]
}
```

---

## 6. CONFIGURAÇÃO E DEPLOYMENT

### 6.1 Variáveis de Ambiente

**servico-rag**:
```
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

**servico-scrapper**:
```
RABBITMQ_HOST=event-bus
RABBITMQ_PORT=5672
RABBITMQ_USER=cafeiq
RABBITMQ_PASS=cafeiq123
QUEUE_NAME=cafeiq.ingestao
COLLECT_INTERVAL=60
```

**api-gateway**:
```
PORT=3000
RAG_URL=http://servico-rag:8001
MCP_URL=http://servico-mcp:8002
CONTROLADOR_URL=http://servico-controlador:3001
```

**servico-controlador**:
```
PORT=3001
GATEWAY_URL=http://api-gateway:3000
SCRAPPER_URL=http://servico-scrapper:8003
```

### 6.2 Portas Mapeadas

```
Serviço                Porta Interna    Porta Docker Host
api-gateway            3000             3000
servico-rag            8001             8001
servico-mcp            8002             8002
servico-scrapper       8003             8003
servico-controlador    3001             3001
ChromaDB               8000             8000
Ollama                 11434            11434
RabbitMQ (AMQP)        5672             5672
RabbitMQ (Web UI)      15672            15672
```

### 6.3 Volumes Docker (Persistência)

```
chroma-data       → ChromaDB vetorizado
ollama-data       → Modelos Ollama (llama3, nomic-embed-text)
rabbitmq-data     → Fila de mensagens
```

---

## 7. CASOS DE USO

### 7.1 Caso: Usuário pergunta sobre cotação

```
Input: "Qual é a cotação do café hoje?"

Expected Output:
{
  "resposta": "A cotação atual do café arábica é de $245.50/lb segundo dados ICE de hoje.",
  "fontes": ["mcp/cotacao_cafe"]
}

Fluxo:
1. mcp_enricher detecta "cotação"
2. Chama servico-mcp/invoke com tool "cotacao_cafe"
3. Busca documentos similares em ChromaDB (histórico de cotações)
4. Monta prompt com dados MCP + histórico
5. Ollama gera resposta
```

### 7.2 Caso: Administrador força coleta

```
Input: POST /forcar-ingestao

Expected Output:
{
  "status": "success",
  "mensagens_publicadas": 4
}

Fluxo:
1. Controlador recebe POST /forcar-ingestao
2. Chama servico-scrapper:8003/coletar-agora
3. Scrapper executa run_cycle() immediately
4. Publica 4 mensagens em RabbitMQ
5. RAG consumer recebe e indexa
```

### 7.3 Caso: Novo documento é indexado

```
Input: POST /ingest
{
  "texto": "Novas variedades resistentes à ferrugem ganham espaço.",
  "fonte": "conab-2025"
}

Fluxo:
1. RAG recebe requisição
2. Gera embedding do texto (nomic-embed-text via Ollama)
3. Armazena em ChromaDB com metadados
4. Próximas queries podem recuperar este documento
```

---

## 8. TRATAMENTO DE ERROS

### 8.1 Cenários de Falha

```
Cenário: Ollama indisponível
├─ RAG tenta invocar /api/generate
├─ Recebe timeout ou 500
├─ Retorna HTTP 502 (Bad Gateway)
└─ Cliente vê: "Serviço temporariamente indisponível"

Cenário: ChromaDB sem espaço
├─ RAG tenta add_texts()
├─ ChromaDB rejeita com erro de disco
├─ RAG loga erro e continua (pergunta pode falhar)
└─ Administrador vê no /logs

Cenário: RabbitMQ fila cheia
├─ Scrapper tenta publish_many()
├─ RabbitMQ rejeita mensagem
├─ Scrapper loga erro e tenta retry após CONSUMER_RETRY_DELAY
└─ Dados podem ser perdidos se retry falhar permanentemente

Cenário: MCP timeout em 30s
├─ Serviço RAG aguarda servico-mcp responder
├─ Se timeout, usa apenas ChromaDB para responder
├─ Qualidade reduzida mas sistema continua operacional
└─ Trata como "dados em tempo real indisponíveis"
```

### 8.2 Estratégias de Resiliência

```
1. Fallback em cascata:
   MCP (tempo real) → ChromaDB (histórico) → LLM puro

2. Retry com backoff:
   - RabbitMQ: exponential backoff
   - HTTP: max 3 tentativas

3. Circuit breaker:
   - Se Ollama falha 5x consecutivas, marca como "unhealthy"
   - Gateway retorna 503 Service Unavailable

4. Queue de prioridade:
   - Perguntas de usuário: prioridade alta
   - Coleta de dados: prioridade normal
```

---

## 9. MODELO DE DADOS - JSON SCHEMAS

### 9.1 Requisição de Chat

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ChatRequest",
  "type": "object",
  "required": ["pergunta"],
  "properties": {
    "pergunta": {
      "type": "string",
      "minLength": 1,
      "maxLength": 500,
      "description": "Pergunta do usuário sobre café"
    }
  }
}
```

### 9.2 Resposta de Chat

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ChatResponse",
  "type": "object",
  "required": ["resposta", "fontes"],
  "properties": {
    "resposta": {
      "type": "string",
      "description": "Resposta gerada pelo LLM"
    },
    "fontes": {
      "type": "array",
      "items": {
        "type": "string",
        "pattern": "^(mcp|chroma)/.*"
      },
      "description": "Fontes usadas para gerar resposta"
    }
  }
}
```

### 9.3 Requisição MCP Tool

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "MCPToolRequest",
  "type": "object",
  "required": ["tool"],
  "properties": {
    "tool": {
      "type": "string",
      "enum": ["cotacao_cafe", "clima", "noticias"],
      "description": "Nome da ferramenta MCP"
    },
    "params": {
      "type": "object",
      "description": "Parâmetros específicos da ferramenta"
    }
  }
}
```

---

## 10. MÉTRICAS E MONITORAMENTO

### 10.1 Métricas por Serviço

**API Gateway**:
- Requisições/min
- Latência p50/p95/p99
- Taxa de erro 4xx/5xx

**Serviço RAG**:
- Tempo de resposta query
- Taxa de hit em ChromaDB
- Tempo Ollama inference
- Tamanho fila RabbitMQ

**Serviço MCP**:
- Latência por tool
- Taxa de erro

**ChromaDB**:
- Documentos indexados
- Espaço em disco

**Ollama**:
- Tempo inference
- Memória utilizada
- Taxa OOM

**RabbitMQ**:
- Mensagens processadas/min
- Tamanho fila
- Taxa de rejeição

---

## 11. ROADMAP FUTURO

```
Curto prazo (1-2 meses):
├─ Integrar APIs reais (ICE, OpenWeatherMap, NewsAPI)
├─ Melhorar validação de entrada
└─ Implementar rate limiting

Médio prazo (2-4 meses):
├─ Autenticação/autorização
├─ Persistência de histórico de chats
├─ Feedback user (thumbs up/down)
└─ Análise de sentimento

Longo prazo (4+ meses):
├─ Kubernetes orchestration
├─ CI/CD pipeline
├─ Monitoramento Prometheus + Grafana
├─ Cache distribuído (Redis)
└─ Fine-tuning model em dados específicos café
```

---

**Documento atualizado em**: 2025-06-16  
**Versão**: 1.0  
**Autor**: Documentação do CaféIQ
