# Serviço RAG

## Visão geral

Serviço de Retrieval-Augmented Generation que responde perguntas combinando busca vetorial em base de conhecimento com dados em tempo real do MCP e LLM via Ollama.

- **Linguagem**: Python
- **Framework**: FastAPI
- **Porta**: `8001`
- **Entrypoint**: `servico-rag/app/main.py`

## Dependências

```
fastapi==0.111.0
uvicorn[standard]==0.30.1
langchain==0.2.6
langchain-community==0.2.6
chromadb==0.5.3
pydantic==2.7.4
pika==1.3.2
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

### POST /query

Responde uma pergunta usando RAG.

**Requisição:**
```json
{
  "pergunta": "Qual é a cotação atual do café arábica?"
}
```

**Resposta:**
```json
{
  "resposta": "A cotação atual do café arábica está em torno de 223 USc/lb no mercado ICE...",
  "fontes": ["scrapper/cotacao", "scrapper/noticia"]
}
```

### POST /ingest

Indexa um documento manualmente no ChromaDB.

**Requisição:**
```json
{
  "texto": "A safra 2025 de café arábica deve atingir 12 milhões de sacas.",
  "fonte": "conab-2025"
}
```

**Resposta:**
```json
{
  "id": "abc123def456",
  "mensagem": "Documento indexado com sucesso."
}
```

## Configuração

Via variáveis de ambiente:

| Variável | Padrão | Descrição |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://ollama:11434` | URL do servidor Ollama |
| `CHROMA_HOST` | `chromadb` | Host do ChromaDB |
| `CHROMA_PORT` | `8000` | Porta do ChromaDB |
| `COLLECTION_NAME` | `cafeiq` | Nome da coleção no ChromaDB |
| `LLM_MODEL` | `llama3` | Modelo LLM para geração |
| `EMBED_MODEL` | `nomic-embed-text` | Modelo para embeddings |
| `RETRIEVER_K` | `4` | Número de documentos a recuperar |
| `MCP_URL` | `http://servico-mcp:8002` | URL do serviço MCP |
| `RABBITMQ_HOST` | `event-bus` | Host do RabbitMQ |
| `RABBITMQ_PORT` | `5672` | Porta do RabbitMQ |
| `RABBITMQ_USER` | `cafeiq` | Usuário RabbitMQ |
| `RABBITMQ_PASS` | `cafeiq123` | Senha RabbitMQ |
| `QUEUE_NAME` | `cafeiq.ingestao` | Nome da fila |
| `CONSUMER_RETRY_DELAY` | `5` | Delay em segundos para reconexão |

## Fluxo de resposta (POST /query)

1. **Enriquecimento MCP**: `mcp_enricher.fetch_enrichments(pergunta)`
   - Detecta palavras-chave na pergunta
   - Invoca ferramentas MCP relevantes (cotacao_cafe, clima, noticias)
   - Formata dados em tempo real como contexto

2. **Busca vetorial**: busca no ChromaDB
   - Converte pergunta em embedding via `EMBED_MODEL`
   - Recupera `RETRIEVER_K` documentos mais relevantes

3. **Montagem do prompt**:
   - Seção "[Dados em tempo real]" (se houver dados MCP)
   - Seção "[Base de conhecimento]" (documentos do ChromaDB)
   - Pergunta original

4. **Geração LLM**: invoca Ollama
   - Modelo: `LLM_MODEL`
   - Retorna texto da resposta

5. **Extração de fontes**: coleta `fonte` dos metadados dos documentos

## Fluxo de ingestão assíncrona

### Publisher (servico-scrapper)

1. Scrapper coleta dados cada `COLLECT_INTERVAL` segundos
2. Publica 4 mensagens em RabbitMQ (fila `cafeiq.ingestao`):
   - 2 notícias
   - 1 clima
   - 1 cotação

### Consumer (servico-rag)

1. Inicia em thread de background ao startup
2. Consome mensagens da fila
3. Converte mensagem para texto indexável:
   - `noticia`: usa `titulo` como texto
   - `clima`: monta string com cidade, temperatura, umidade, condição
   - `cotacao`: monta string com produto, preço, data

4. Indexa no ChromaDB com `fonte` como metadado

5. Em sucesso: `basic_ack` (reconhece a mensagem)

6. Em erro persistente: `basic_nack(requeue=False)` (não recoloca na fila)

7. Em erro de conexão: reconecta com atraso

## Estrutura do código

### app/config.py

Centraliza configurações via variáveis de ambiente.

### app/rag.py

Funções principais:

- `_embeddings()`: retorna objeto `OllamaEmbeddings`
- `_chroma_client()`: retorna cliente HTTP do ChromaDB
- `get_vectorstore()`: retorna objeto `Chroma` para operações
- `answer_question(pergunta, extra_context)`: pergunta → resposta
  - Recupera docs via `retriever`
  - Monta prompt com contexto
  - Invoca LLM
  - Retorna resposta e documentos
- `ingest_document(texto, fonte)`: indexa documento e retorna ID

### app/mcp_enricher.py

Detecta palavras-chave e enriquece contexto:

- `_detect_tools(pergunta)`: retorna lista de ferramentas a invocar
- `_call_mcp(tool, params)`: faz POST para `MCP_URL/invoke`
- `_format_result(tool, result)`: formata resultado em texto legível
- `fetch_enrichments(pergunta)`: retorna string com todos os enriquecimentos

Regras de palavras-chave:

| Ferramenta | Palavras-chave |
|---|---|
| `cotacao_cafe` | preço, preco, cotação, cotacao, ice |
| `clima` | clima, tempo, chuva, temperatura |
| `noticias` | notícia, noticia, mercado |

### app/consumer.py

Consumer RabbitMQ:

- `_build_ingest_args(msg)`: converte mensagem em (texto, fonte)
- `_on_message(channel, method, properties, body)`: callback de mensagem
  - Parseia JSON
  - Extrai (texto, fonte)
  - Indexa no ChromaDB
  - Reconhece ou nega a mensagem
- `_consume_loop()`: loop bloqueante com reconexão automática
- `start_consumer_thread()`: inicia thread daemon

### app/main.py

Aplicação FastAPI:

- Inicia consumer thread no lifespan
- Expõe endpoints /health, /query, /ingest

## Prompt template

```
Você é um assistente especializado no mercado de café.
Responda de forma precisa e objetiva usando as informações abaixo.
Se não tiver a informação necessária, diga claramente que não sabe.

{context}

Pergunta: {question}
Resposta:
```

O `{context}` é preenchido com dados em tempo real + base de conhecimento.

## Como testar

### Verificar saúde

```bash
curl -s http://localhost:8001/health | jq
```

### Fazer uma pergunta

```bash
curl -s -X POST http://localhost:8001/query \
  -H "Content-Type: application/json" \
  -d '{"pergunta": "Qual é o preço do café?"}' | jq
```

### Indexar um documento

```bash
curl -s -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{"texto": "Safra 2025 atinge recordes.", "fonte": "conab"}' | jq
```

## Tratamento de erros

- **Erro ao conectar ao Ollama (502)**: "error": "Não foi possível contatar o Ollama"
- **Erro ao conectar ao MCP (aviso silencioso)**: enriquecimento é pulado, resposta usa apenas base de conhecimento
- **Erro ao indexar (consumer)**: mensagem é negada sem requeue; errado é logado

## Notas técnicas

- Documentos indexados persistem no volume `chroma-data` do Docker
- Embeddings são calculados via modelo `nomic-embed-text`
- O modelo LLM deve estar puxado no Ollama: `docker exec cafeiq-ollama ollama pull llama3`
- Recupera `RETRIEVER_K=4` documentos por padrão; ajuste via variável de ambiente
- O consumer reconecta ao RabbitMQ a cada `CONSUMER_RETRY_DELAY=5` segundos em caso de falha
