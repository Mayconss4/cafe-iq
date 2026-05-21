# Arquitetura do CaféIQ — Justificativas e Mapeamento GCC129

## 1. Visão arquitetural

O CaféIQ é um sistema distribuído composto por cinco microsserviços que se comunicam por dois canais distintos: HTTP síncrono (para interações em tempo real com o usuário) e mensageria assíncrona via RabbitMQ (para ingestão contínua de dados em background).

```
                    ┌─────────────┐
                    │  index.html │  (cliente estático)
                    └──────┬──────┘
                           │ HTTP
              ┌────────────▼────────────┐
              │       api-gateway       │  ← único ponto de entrada
              └───┬──────────┬──────────┘
                  │          │
          ┌───────▼──┐  ┌────▼──────────────┐
          │serv-rag  │  │   serv-mcp        │
          │(RAG+LLM) │◄─┤ (ferramentas MCP) │
          └───┬──────┘  └───────────────────┘
              │ indexa
    ┌─────────▼──────────────────────────┐
    │         RabbitMQ (event-bus)       │
    └─────────▲──────────────────────────┘
              │ publica
    ┌─────────┴──────────┐
    │  serv-scrapper     │
    │  (coleta a cada    │
    │   60s ou on-demand)│
    └────────────────────┘

    ┌────────────────────┐
    │  serv-controlador  │  ← painel admin (fora do fluxo principal)
    └────────────────────┘
```

---

## 2. Justificativas arquiteturais

### 2.1 API Gateway como único ponto de entrada

**Decisão:** todo o tráfego do cliente web passa obrigatoriamente pelo `api-gateway` na porta 3000. O browser nunca acessa os serviços internos diretamente.

**Por quê:**
- **Segurança de superfície:** a rede `cafeiq-net` é interna ao Docker; apenas o gateway tem porta mapeada para o host. Os serviços internos ficam isolados da internet.
- **Ponto único de políticas:** log de requisições, CORS, autenticação futura e rate limiting são implementados uma vez no gateway, não replicados em cada serviço.
- **Desacoplamento:** o cliente web não precisa conhecer endereços, portas ou protocolos dos serviços internos. A API pública pode evoluir sem quebrar o frontend.
- **Proxy transparente:** o gateway encaminha erros HTTP dos serviços downstream com o código original, preservando semântica REST sem camada extra de abstração.

**Alternativa descartada:** expor cada serviço diretamente ao browser. Exigiria CORS configurado em cada serviço, acoplaria o frontend à topologia interna e dificultaria monitoramento centralizado.

---

### 2.2 Event Bus (RabbitMQ) para ingestão assíncrona

**Decisão:** o `servico-scrapper` publica mensagens JSON na fila `cafeiq.ingestao`; o `servico-rag` as consome em thread separada e indexa no ChromaDB.

**Por quê:**
- **Desacoplamento temporal:** o scrapper não precisa esperar que o RAG processe cada documento. Se o RAG estiver sobrecarregado, as mensagens ficam enfileiradas sem perda de dados.
- **Resiliência:** se o `servico-rag` reiniciar, a fila retém as mensagens (persistência `durable=True`, `delivery_mode=Persistent`). A retomada é automática ao reconectar.
- **Escalabilidade futura:** múltiplos consumidores podem ser adicionados ao grupo sem alterar o scrapper (fan-out ou work queue).
- **Separação de responsabilidades:** o scrapper é responsável apenas por coletar e publicar; quem decide o que fazer com os dados é o consumidor. Novos serviços podem assinar a mesma fila sem modificar o scrapper.

**Alternativa descartada:** chamada HTTP direta do scrapper para `servico-rag/ingest`. Cria acoplamento forte, perde mensagens se o RAG estiver fora no momento da coleta, e força o scrapper a aguardar a resposta do embedding (operação lenta).

---

### 2.3 RAG (Retrieval-Augmented Generation)

**Decisão:** antes de chamar o LLM, o `servico-rag` busca os documentos mais relevantes no ChromaDB e os inclui no prompt.

**Por quê:**
- **Conhecimento atualizado sem retreinamento:** documentos indexados pelo scrapper ficam disponíveis para o LLM imediatamente, sem necessidade de fine-tuning. O modelo base (llama3) permanece fixo; o conhecimento de domínio está no vector store.
- **Grounding (redução de alucinações):** o LLM responde com base em documentos reais recuperados, não apenas no que aprendeu no pré-treino. O prompt explicita "use as informações abaixo", instruindo o modelo a ancorar a resposta no contexto fornecido.
- **Rastreabilidade:** os `source_documents` retornados permitem mostrar ao usuário de onde veio a informação (campo `fontes` na resposta).
- **Separação embeddings/LLM:** `nomic-embed-text` é especializado em representação semântica; `llama3` é especializado em geração. Usar modelos especializados para cada tarefa é mais eficiente do que um único modelo.

**Alternativa descartada:** chamar o LLM diretamente com a pergunta. O modelo não teria conhecimento sobre o mercado de café atual, preços ou safras recentes — apenas conhecimento genérico do pré-treino.

---

### 2.4 MCP (Model Context Protocol) para enriquecimento em tempo real

**Decisão:** antes de chamar o LLM, o `servico-rag` consulta o `servico-mcp` para obter dados estruturados em tempo real (cotação, clima, notícias) quando a pergunta é relevante.

**Por quê:**
- **Dados que o RAG não cobre bem:** cotações e clima mudam a cada minuto. Indexar dados tão voláteis no ChromaDB geraria desatualização imediata. O MCP fornece o valor do momento, sem passar pelo pipeline de ingestão.
- **Separação de fontes de contexto:** o RAG fornece contexto histórico/documental (base de conhecimento acumulada); o MCP fornece contexto estruturado e puntual (dados de API). Combinar os dois no prompt resulta em respostas mais completas.
- **Extensibilidade:** adicionar uma nova ferramenta ao MCP (ex: previsão de safra, câmbio) requer apenas criar um módulo em `app/tools/` e registrá-lo em `registry.py`, sem alterar o gateway, o RAG ou o scrapper.
- **Failsafe:** a chamada ao MCP tem timeout de 5s e falha silenciosa (`log.warning`). Se o MCP estiver fora, o RAG continua respondendo apenas com os documentos do ChromaDB.

**Alternativa descartada:** integrar as APIs diretamente no servico-rag. Violaria o princípio de responsabilidade única e dificultaria reutilizar as ferramentas por outros serviços futuros (ex: um agente autônomo).

---

### 2.5 Microsserviços heterogêneos (Python + Node.js)

**Decisão:** serviços de IA (RAG, MCP, scrapper) em Python; serviços de roteamento/orquestração (gateway, controlador) em Node.js.

**Por quê:**
- **Python** tem o ecossistema de IA mais maduro (LangChain, ChromaDB client, pika). Implementar RAG em Node exigiria wrappers ou reimplementações.
- **Node.js/Express** é ideal para proxies HTTP leves e alta concorrência I/O, que é exatamente o papel do gateway e do controlador.
- **Docker** abstrai a heterogeneidade: cada serviço tem seu próprio ambiente, sem conflito de dependências entre runtimes.

---

## 3. Mapeamento ao trabalho GCC129

### Requisito: Comunicação síncrona entre serviços

| Componente | Implementação | Localização |
|---|---|---|
| Cliente → Gateway | `fetch()` nativo (POST /chat, GET /health) | `index.html` |
| Gateway → RAG | `axios.post` para `servico-rag:8001/query` | `api-gateway/src/index.js` |
| Gateway → MCP | `axios.post` para `servico-mcp:8002/invoke` | `api-gateway/src/index.js` |
| RAG → MCP | `urllib.request` para `servico-mcp:8002/invoke` | `servico-rag/app/mcp_enricher.py` |
| Controlador → Gateway | `axios.get` para `api-gateway:3000/health` | `servico-controlador/src/index.js` |
| Controlador → Scrapper | `axios.post` para `servico-scrapper:8003/coletar-agora` | `servico-controlador/src/index.js` |

### Requisito: Comunicação assíncrona via mensageria

| Componente | Papel | Localização |
|---|---|---|
| RabbitMQ | Broker (fila `cafeiq.ingestao`, durable) | `docker-compose.yml` (imagem oficial) |
| Produtor | `servico-scrapper` publica 4 msg/ciclo via `pika.BlockingConnection` | `servico-scrapper/app/publisher.py` |
| Consumidor | `servico-rag` consome em thread daemon, chama `ingest_document()` | `servico-rag/app/consumer.py` |

### Requisito: Persistência de dados

| Dado | Tecnologia | Justificativa |
|---|---|---|
| Embeddings e documentos | ChromaDB (volume Docker `chroma-data`) | banco vetorial nativo para busca semântica |
| Modelos LLM | Ollama (volume Docker `ollama-data`) | evita re-download a cada restart |
| Mensagens em trânsito | RabbitMQ (volume Docker `rabbitmq-data`) | mensagens sobrevivem a restart do broker |
| Logs administrativos | Array em memória (últimos 20) | `servico-controlador/src/index.js` — escopo de sessão, não requer persistência |

### Requisito: Containerização

| Aspecto | Implementação |
|---|---|
| Isolamento | Cada serviço tem seu `Dockerfile` próprio |
| Rede interna | Bridge `cafeiq-net` — serviços se comunicam por nome (DNS interno) |
| Serviços de infraestrutura | RabbitMQ, ChromaDB e Ollama usam imagens oficiais |
| Orquestração | `docker-compose.yml` com `depends_on` e `restart: unless-stopped` |

### Requisito: Interface com o usuário

| Aspecto | Implementação |
|---|---|
| Arquivo | `index.html` (HTML + CSS + JS puro, sem framework) |
| Chat | `fetch POST /chat` → exibe resposta do LLM com fontes |
| Monitoramento | `fetch GET /health` a cada 10s → painel lateral com latência por serviço |
| UX | Tema café, textarea auto-grow, Enter para enviar, indicador de digitação |

### Requisito: Painel administrativo / observabilidade

| Rota | Função |
|---|---|
| `GET /status` | Consulta `api-gateway/health` e exibe estado consolidado |
| `POST /forcar-ingestao` | Aciona ciclo imediato no scrapper via `threading.Event` |
| `GET /logs` | Retorna últimas 20 entradas do buffer de log em memória |

---

## 4. Decisões de resiliência

| Cenário | Comportamento implementado |
|---|---|
| MCP fora do ar | `mcp_enricher.py` captura exceção, loga `warning`, retorna string vazia — RAG responde sem enriquecimento |
| RabbitMQ fora na inicialização | Consumer tenta reconectar a cada 5s indefinidamente (loop `while True` com `time.sleep`) |
| RabbitMQ cai em runtime | `pika.exceptions.AMQPConnectionError` capturada, reconexão automática no próximo ciclo |
| Serviço interno não responde no `/health` | `Promise.allSettled` no gateway — retorna `207` com o serviço marcado como `unreachable`, sem derrubar o health check dos demais |
| Falha de ingest de mensagem | `basic_nack(requeue=False)` — mensagem descartada sem loop infinito; erro logado |
