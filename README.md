# CafeIQ

CafeIQ e um assistente inteligente especializado no mercado de cafe, construido como sistema distribuido de microsservicos. O sistema combina recuperacao aumentada por geracao (RAG), ferramentas de contexto em tempo real via Model Context Protocol (MCP) e coleta assincrona de dados de mercado para responder perguntas sobre cotacoes, clima nas regioes produtoras e noticias do setor cafeeiro.

---

## Sumario

1. [Arquitetura do Sistema](#arquitetura-do-sistema)
2. [Fluxos de Operacao](#fluxos-de-operacao)
3. [Decisoes de Design](#decisoes-de-design)
4. [Mecanismos de Resiliencia](#mecanismos-de-resiliencia)
5. [Servicos](#servicos)
6. [Infraestrutura de Suporte](#infraestrutura-de-suporte)
7. [Instalacao e Execucao](#instalacao-e-execucao)
8. [Referencia de API](#referencia-de-api)
9. [Variaveis de Ambiente](#variaveis-de-ambiente)
10. [Estrutura do Repositorio](#estrutura-do-repositorio)

---

## Arquitetura do Sistema

### Visao geral

O CafeIQ organiza seus componentes em duas camadas distintas: a camada de borda, composta pelo API Gateway que atende o cliente web, e a camada interna, onde vivem os servicos de processamento de linguagem, ferramentas externas e coleta de dados. A comunicacao entre essas camadas obedece a dois padroes complementares: HTTP sincrono para interacoes que exigem resposta imediata ao usuario, e mensageria assincrona via RabbitMQ para o pipeline de ingestao de dados em background.

```
  Cliente Web (index.html)
         |
         | HTTP :3000
         v
  +--------------------+
  |    api-gateway     |  Node.js / Express
  |    porta 3000      |  unico ponto de entrada
  +--------------------+
         |
    +----+----+----+
    |         |    |
    v         v    v
+----------+ +----------+ +--------------------+
|serv-rag  | |serv-mcp  | |serv-controlador    |
|:8001     | |:8002     | |:3001               |
|FastAPI   | |FastAPI   | |Node.js / Express   |
|LangChain | |requests  | |painel admin        |
|ChromaDB  | |wttr.in   | +--------------------+
|Ollama    | |AlphaVant.|
+----+-----+ +----------+
     |
     | indexa embeddings
     v
+----------+     +----------+     +----------+
| ChromaDB |     | Ollama   |     | RabbitMQ |
| :8000    |     | :11434   |     | :5672    |
| vetor DB |     | LLM/emb. |     | event bus|
+----------+     +----------+     +----+-----+
                                       |
                                  publica msgs
                                       |
                              +--------+--------+
                              | serv-scrapper   |
                              | :8003           |
                              | FastAPI         |
                              | Google News RSS |
                              | wttr.in         |
                              | Alpha Vantage   |
                              +-----------------+
```

### Componentes e responsabilidades

| Componente | Tecnologia | Responsabilidade principal |
|---|---|---|
| api-gateway | Node.js 20, Express 4 | Ponto unico de entrada, roteamento e CORS |
| servico-rag | Python 3.11, FastAPI, LangChain | RAG, embeddings, consulta ao LLM |
| servico-mcp | Python 3.11, FastAPI | Ferramentas de contexto em tempo real |
| servico-scrapper | Python 3.11, FastAPI | Coleta periodica de dados de mercado |
| servico-controlador | Node.js 20, Express 4 | Painel administrativo e observabilidade |
| ChromaDB 0.5.3 | Docker (imagem oficial) | Banco vetorial persistente |
| Ollama | Docker (imagem oficial) | Servidor de modelos LLM e de embeddings |
| RabbitMQ 3 | Docker (imagem oficial) | Broker de mensagens para ingestao assincrona |

### Rede interna

Todos os servicos compartilham a rede Docker `cafeiq-net` do tipo bridge. A comunicacao interna ocorre por nome de servico (DNS interno do Docker), sem exposicao de portas ao host, exceto onde explicitamente mapeado. Essa topologia garante que o cliente web nunca alcance servicos internos diretamente.

---

## Fluxos de Operacao

### Fluxo sincrono: resposta a uma pergunta

Este fluxo e iniciado quando o usuario envia uma pergunta pela interface web. Cada etapa bloqueia ate receber a resposta da etapa seguinte.

```
  Browser
    |
    | POST /chat {"pergunta": "..."}
    v
  api-gateway
    |
    | POST servico-rag:8001/query
    v
  servico-rag: mcp_enricher.py
    |
    | 1. Analisa keywords na pergunta
    |    "preco", "cotacao"  --> tool: cotacao_cafe
    |    "clima", "chuva"    --> tool: clima
    |    "noticia", "mercado"--> tool: noticias
    |
    | 2. POST servico-mcp:8002/invoke  (timeout 5s, falha silenciosa)
    |    resultado: texto estruturado com dado em tempo real
    |
  servico-rag: rag.py
    |
    | 3. Busca vetorial no ChromaDB
    |    retriever.invoke(pergunta)  k=4 documentos mais relevantes
    |    embeddings: nomic-embed-text via Ollama
    |
    | 4. Monta prompt com duas secoes de contexto:
    |    [Dados em tempo real]   <-- resultado MCP (se houver)
    |    [Base de conhecimento]  <-- documentos do ChromaDB
    |    Pergunta: ...
    |
    | 5. Ollama (llama3) gera resposta
    |
    | 6. Extrai metadados "fonte" dos source_documents
    v
  resposta: {"resposta": "...", "fontes": ["scrapper/cotacao", ...]}
    |
    v
  Browser
```

**Latencia esperada:** a chamada ao LLM domina o tempo total. Em hardware com CPU, respostas tipicamente levam entre 15 e 60 segundos. Com GPU disponivel para o container Ollama, esse tempo cai significativamente.

### Fluxo assincrono: ingestao de dados

Este fluxo e completamente independente do usuario. Ele opera em background e alimenta a base de conhecimento do ChromaDB continuamente.

```
  servico-scrapper (thread de coleta, intervalo configuravel via COLLECT_INTERVAL, padrao 60s)
    |
    | collect_noticias()  --> Google News RSS (ate 3 manchetes)
    | collect_clima()     --> wttr.in (temperatura, umidade, condicao)
    | collect_cotacao()   --> Alpha Vantage ICO (USc/lb, mensal)
    |
    | fallback automatico para cada coletor em caso de falha da API externa
    |
    | Publisher.publish_many(messages)
    v
  RabbitMQ
    fila: cafeiq.ingestao  (durable=True, delivery_mode=Persistent)
    |
    v
  servico-rag: consumer.py (thread daemon, basic_qos prefetch_count=1)
    |
    | _build_ingest_args(msg)
    |   tipo "noticia"  --> texto = titulo,      fonte = "scrapper/noticia"
    |   tipo "clima"    --> texto = descricao,   fonte = "scrapper/clima"
    |   tipo "cotacao"  --> texto = preco + data, fonte = "scrapper/cotacao"
    |
    | ingest_document(texto, fonte)
    |   Document(page_content, metadata)
    |   vectorstore.add_documents([doc])
    |   embedding gerado por nomic-embed-text
    v
  ChromaDB: colecao "cafeiq"
    documentos persistidos em volume Docker "chroma-data"
```

**Garantias de entrega:** a fila e declarada com `durable=True` e as mensagens publicadas com `delivery_mode=Persistent`. Se o `servico-rag` reiniciar, as mensagens aguardam na fila ate o consumer reconectar. Erros de ingestao resultam em `basic_nack(requeue=False)` para evitar loops infinitos de reprocessamento.

### Fluxo de coleta manual

O `servico-controlador` permite disparar a coleta fora do intervalo agendado:

```
  POST servico-controlador:3001/forcar-ingestao
    |
    | axios.post servico-scrapper:8003/coletar-agora
    v
  servico-scrapper: _manual_trigger.set()
    |
    | threading.Event desbloqueia o wait() do loop
    v
  ciclo imediato de coleta e publicacao no RabbitMQ
```

---

## Decisoes de Design

### API Gateway como ponto unico de entrada

Todo o trafego do cliente web passa obrigatoriamente pelo `api-gateway` na porta 3000. O browser nao acessa os servicos internos diretamente.

Esse padrao garante que a rede `cafeiq-net` permaneca isolada do host, que politicas transversais como CORS e logging sejam implementadas uma unica vez, e que o cliente web nao precise conhecer a topologia interna. O gateway encaminha erros HTTP dos servicos downstream com o status code original, preservando a semantica REST.

### RabbitMQ para desacoplamento temporal

A escolha de mensageria assincrona em vez de chamadas HTTP diretas do scrapper para o RAG tem tres consequencias praticas: o scrapper nao bloqueia esperando o embedding ser computado (operacao de alta latencia), mensagens nao sao perdidas se o consumidor estiver indisponivel no momento da publicacao, e o sistema tolera falhas parciais sem cascata.

### RAG com enriquecimento MCP

A combinacao de recuperacao vetorial (ChromaDB) com dados em tempo real (MCP) resolve dois problemas distintos. O ChromaDB fornece contexto historico e documental acumulado ao longo do tempo. O MCP fornece dados pontuais e altamente voliteis, como cotacoes e clima, que seriam imediatamente obsoletos se indexados no vector store. O prompt final combina as duas fontes de contexto em secoes distintas, deixando o LLM ciente da procedencia de cada informacao.

### Deteccao de ferramentas por palavras-chave

O `mcp_enricher.py` usa correspondencia de palavras-chave em vez de classificacao por modelo para decidir quais ferramentas invocar. Essa abordagem e deterministica, de latencia zero adicional e nao requer modelo auxiliar. O custo e menor cobertura em linguagem ambigua, que e aceitavel para o dominio restrito do mercado de cafe.

### Stacks heterogeneas por afinidade

Servicos de IA (RAG, MCP, scrapper) usam Python porque o ecossistema de inteligencia artificial em Python (LangChain, ChromaDB, pika) e mais maduro e bem documentado. Servicos de roteamento e orquestracao (gateway, controlador) usam Node.js porque proxies HTTP leves e alta concorrencia de I/O sao pontos fortes do runtime. O Docker elimina conflitos entre as duas stacks.

---

## Mecanismos de Resiliencia

| Cenario de falha | Comportamento implementado |
|---|---|
| servico-mcp indisponivel durante uma query | `mcp_enricher.py` captura a excecao com timeout de 5s, loga `WARNING` e retorna string vazia. O RAG prossegue com apenas os documentos do ChromaDB. |
| RabbitMQ indisponivel na inicializacao | `_consume_loop()` em `consumer.py` executa `time.sleep(CONSUMER_RETRY_DELAY)` e tenta reconectar indefinidamente. |
| RabbitMQ cai durante operacao | `AMQPConnectionError` capturada no loop do consumer e do publisher. Reconexao automatica no proximo ciclo. |
| Servico interno nao responde no health check | `Promise.allSettled` no gateway garante que a falha de um servico nao cancela a verificacao dos demais. O endpoint retorna HTTP 207 com o servico marcado como `unreachable`. |
| Falha ao indexar uma mensagem no ChromaDB | `basic_nack(requeue=False)` descarta a mensagem sem gerar loop infinito. O erro e registrado em log. |
| API externa de cotacao ou clima indisponivel | Cada coletor no `collectors.py` e cada ferramenta MCP possui bloco `try/except` com fallback para dados simulados, garantindo que o pipeline nao quebre. |

---

## Servicos

### api-gateway

**Tecnologia:** Node.js 20, Express 4.19, Axios 1.7

**Responsabilidade:** unico ponto de entrada para o cliente web. Roteie requisicoes para os servicos internos, aplicando CORS, logging de latencia e tratamento de erros de forma centralizada.

**Porta exposta:** 3000

**Rotas:**

| Metodo | Rota | Comportamento |
|---|---|---|
| POST | /chat | Encaminha `req.body` para `servico-rag:8001/query` e retorna a resposta sem modificacao. |
| POST | /mcp/tool | Encaminha `req.body` para `servico-mcp:8002/invoke` e retorna o resultado da ferramenta. |
| GET | /health | Executa health checks em paralelo (Promise.allSettled) para RAG, MCP e controlador com timeout de 3s cada. Retorna HTTP 200 se todos ok, 207 se algum falhou. |

**Politicas aplicadas:**

- CORS permissivo (`Access-Control-Allow-Origin: *`) para suportar clientes servidos por `file://` ou outras origens.
- Logging de latencia em todos os requests via middleware `res.end` wrapper.
- Propagacao fiel de erros HTTP: se o servico downstream retornar 502, o gateway retorna 502 com o mesmo corpo.

**Variaveis de ambiente:**

| Variavel | Padrao | Descricao |
|---|---|---|
| PORT | 3000 | Porta de escuta |
| RAG_URL | http://servico-rag:8001 | Endereco do servico-rag |
| MCP_URL | http://servico-mcp:8002 | Endereco do servico-mcp |
| CONTROLADOR_URL | http://servico-controlador:3001 | Endereco do controlador |

**Dependencias em tempo de execucao:** servico-rag (startup), servico-mcp (startup), servico-controlador (startup), event-bus (health).

---

### servico-rag

**Tecnologia:** Python 3.11, FastAPI 0.111, LangChain 0.2.6, LangChain-Community 0.2.6, ChromaDB 0.5.3 (client), Pika 1.3.2

**Responsabilidade:** nucleo de inteligencia do sistema. Coordena o pipeline de RAG: enriquece a pergunta com dados em tempo real via MCP, recupera documentos relevantes do ChromaDB, monta o prompt e invoca o LLM via Ollama. Tambem opera como consumidor assincrono do RabbitMQ para indexar documentos no vector store.

**Porta exposta:** 8001

**Rotas:**

| Metodo | Rota | Comportamento |
|---|---|---|
| GET | /health | Retorna `{"status": "ok"}`. |
| POST | /query | Recebe `{"pergunta": "..."}`, executa o pipeline RAG completo e retorna `{"resposta": "...", "fontes": [...]}`. |
| POST | /ingest | Recebe `{"texto": "...", "fonte": "..."}`, cria um `Document` LangChain e indexa no ChromaDB via `vectorstore.add_documents`. Retorna o ID do documento gerado. |

**Pipeline de consulta (`rag.py`):**

1. `get_vectorstore()` cria um cliente `chromadb.HttpClient` e instancia `Chroma` com `OllamaEmbeddings(model="nomic-embed-text")`.
2. `retriever.invoke(pergunta)` executa busca por similaridade cossenoidal com `k=4` (configuravel via `RETRIEVER_K`).
3. O prompt e montado a partir do template em `_PROMPT_TEMPLATE`, concatenando a secao de dados em tempo real (se houver) e a secao de base de conhecimento.
4. `Ollama(model="llama3").invoke(prompt)` gera a resposta em texto.
5. Os metadados `fonte` dos `source_documents` sao deduplicados e retornados como lista.

**Enriquecimento MCP (`mcp_enricher.py`):**

O modulo analisa a pergunta por correspondencia de palavras-chave e dispara as ferramentas MCP pertinentes antes da busca vetorial. As regras sao:

- Palavras como "preco", "cotacao", "ice": invoca `cotacao_cafe`.
- Palavras como "clima", "temperatura", "chuva": invoca `clima` com `cidade=Lavras`.
- Palavras como "noticia", "mercado": invoca `noticias`.

Cada chamada ao MCP usa `urllib.request` com timeout de 5 segundos. Falhas sao capturadas silenciosamente, e o pipeline continua sem o enriquecimento.

**Consumer assincrono (`consumer.py`):**

Na inicializacao do FastAPI (evento `lifespan`), uma thread daemon e criada para consumir a fila `cafeiq.ingestao`. O consumer opera com `prefetch_count=1` para processar uma mensagem por vez e evitar sobrecarga no ChromaDB. Reconexao automatica ao RabbitMQ com intervalo configuravel via `CONSUMER_RETRY_DELAY`.

Mapeamento de mensagens para documentos:

| Tipo de mensagem | Texto indexado | Fonte |
|---|---|---|
| noticia | titulo da noticia | scrapper/noticia |
| clima | descricao textual de temperatura, umidade e condicao | scrapper/clima |
| cotacao | preco em USc/lb com data de referencia | scrapper/cotacao |

**Variaveis de ambiente:**

| Variavel | Padrao | Descricao |
|---|---|---|
| OLLAMA_BASE_URL | http://ollama:11434 | Endereco do servidor Ollama |
| LLM_MODEL | llama3 | Modelo de geracao de texto |
| EMBED_MODEL | nomic-embed-text | Modelo de embeddings |
| CHROMA_HOST | chromadb | Host do ChromaDB |
| CHROMA_PORT | 8000 | Porta do ChromaDB |
| COLLECTION_NAME | cafeiq | Nome da colecao vetorial |
| RETRIEVER_K | 4 | Numero de documentos recuperados por query |
| MCP_URL | http://servico-mcp:8002 | Endereco do servico-mcp |
| RABBITMQ_HOST | event-bus | Host do broker |
| RABBITMQ_PORT | 5672 | Porta AMQP |
| RABBITMQ_USER | cafeiq | Usuario do RabbitMQ |
| RABBITMQ_PASS | cafeiq123 | Senha do RabbitMQ |
| QUEUE_NAME | cafeiq.ingestao | Nome da fila de ingestao |
| CONSUMER_RETRY_DELAY | 5 | Segundos entre tentativas de reconexao |

---

### servico-mcp

**Tecnologia:** Python 3.11, FastAPI 0.111, Requests 2.32

**Responsabilidade:** provedor de ferramentas de contexto em tempo real. Implementa o padrao Model Context Protocol (MCP), expondo uma interface uniforme de invocacao de ferramentas que podem ser chamadas por qualquer servico interno. Cada ferramenta busca dados de uma API externa e retorna resultado estruturado.

**Porta exposta:** 8002

**Rotas:**

| Metodo | Rota | Comportamento |
|---|---|---|
| GET | /health | Retorna `{"status": "ok"}`. |
| GET | /tools | Lista todas as ferramentas registradas com nome, descricao e parametros esperados. |
| POST | /invoke | Recebe `{"tool": "nome", "params": {...}}`, localiza o handler no registry e executa. Retorna `{"tool": "nome", "resultado": {...}}`. |

**Ferramentas registradas (`registry.py`):**

Cada ferramenta e um modulo em `app/tools/` com uma funcao `run(params: dict) -> dict | list`. O registro associa o nome da ferramenta ao handler e aos metadados expostos em `/tools`.

**cotacao_cafe**

Consulta a API Alpha Vantage com a funcao `COFFEE` e a chave `demo`, que retorna o preco mensal de cafe ICO (International Coffee Organization) em centavos de dolar por libra-peso (USc/lb). O resultado inclui a data de referencia da ultima observacao mensal e o preco equivalente em BRL por saca de 60 kg, calculado com taxa de cambio aproximada de R$ 5,20/USD e fator de conversao de 132,277 lb/saca.

Em caso de falha na API, retorna valores simulados com variacao aleatorial em torno de uma base fixa, sinalizados pelo campo `"fonte": "fallback"`.

**clima**

Consulta `wttr.in/{cidade}?format=j1`, retornando temperatura em Celsius, umidade relativa e descricao textual das condicoes atmosfericas para a cidade solicitada. Aceita qualquer nome de cidade como parametro. Em caso de falha, retorna valores simulados com `"fonte": "fallback"`.

**noticias**

Consulta o feed RSS do Google News filtrado para o termo "cafe arabica mercado" com idioma pt-BR. Extrai os tres primeiros itens do feed, retornando titulo, link e data de publicacao. Em caso de falha no feed, retorna manchetes de uma lista local de fallback.

---

### servico-scrapper

**Tecnologia:** Python 3.11, FastAPI 0.111, Requests 2.32, Pika 1.3.2

**Responsabilidade:** coleta periodica de dados do mercado de cafe em fontes externas e publicacao no broker de mensagens. Opera em loop continuo em uma thread dedicada, publicando mensagens JSON na fila `cafeiq.ingestao` a cada ciclo.

**Porta exposta:** 8003

**Rotas:**

| Metodo | Rota | Comportamento |
|---|---|---|
| GET | /health | Retorna `{"status": "ok"}`. |
| POST | /coletar-agora | Define um `threading.Event` que interrompe o `wait()` do loop e dispara um ciclo imediato de coleta. |

**Coleta de dados (`collectors.py`):**

Cada ciclo produz até 5 mensagens: ate 3 noticias, 1 registro de clima e 1 registro de cotacao.

**Coleta de noticias:** GET no feed RSS do Google News com query `cafe arabica mercado` em portugues. Extrai os tres primeiros itens via `xml.etree.ElementTree`. Fallback: amostra aleatoria de uma lista local de titulos representativos.

**Coleta de clima:** GET em `https://wttr.in/Lavras,MG?format=j1`. Extrai `temp_C`, `humidity` e `weatherDesc[0].value` do campo `current_condition[0]`. Fallback: valores aleatorios com condicao "Indisponivel".

**Coleta de cotacao:** GET na API Alpha Vantage (`function=COFFEE&interval=monthly&apikey=demo`). Extrai o campo `data[0].value` (preco em USc/lb) e a data de referencia mensal. Fallback: valor aleatorio entre 200 e 300 USc/lb.

**Publisher (`publisher.py`):**

Usa `pika.BlockingConnection` com reconexao automatica via lista de delays `[5, 10, 30]` segundos. Mensagens sao publicadas com `delivery_mode=Persistent` e `content_type=application/json`. Falhas em mensagens individuais nao interrompem a publicacao das demais.

**Loop de coleta (`main.py`):**

```
while True:
    mensagens = run_cycle()
    publisher.publish_many(mensagens)
    acionado = _manual_trigger.wait(timeout=COLLECT_INTERVAL)
    _manual_trigger.clear()
```

O uso de `threading.Event.wait()` em vez de `time.sleep()` permite que o endpoint `/coletar-agora` acorde o loop imediatamente sem polling.

**Variaveis de ambiente:**

| Variavel | Padrao | Descricao |
|---|---|---|
| RABBITMQ_HOST | event-bus | Host do broker |
| RABBITMQ_PORT | 5672 | Porta AMQP |
| RABBITMQ_USER | cafeiq | Usuario |
| RABBITMQ_PASS | cafeiq123 | Senha |
| QUEUE_NAME | cafeiq.ingestao | Fila de destino |
| COLLECT_INTERVAL | 60 | Intervalo entre ciclos em segundos |

---

### servico-controlador

**Tecnologia:** Node.js 20, Express 4.19, Axios 1.7

**Responsabilidade:** painel administrativo do sistema. Agrega o estado de saude via gateway, permite disparar coletas manuais no scrapper e mantem um buffer circular dos ultimos eventos registrados.

**Porta exposta:** 3001

**Rotas:**

| Metodo | Rota | Comportamento |
|---|---|---|
| GET | /health | Retorna `{"status": "ok"}`. Usado pelo gateway no health check consolidado. |
| GET | /status | Consulta `api-gateway:3000/health` com timeout de 5s e retorna o resultado enriquecido com o campo `"origem": "api-gateway"`. |
| POST | /forcar-ingestao | Encaminha `POST /coletar-agora` para o scrapper, acionando um ciclo imediato de coleta. |
| GET | /logs | Retorna as ultimas 20 entradas do buffer de log em memoria, em ordem cronologica inversa. |

**Buffer de logs:**

Implementado como array FIFO com capacidade maxima de 20 entradas. Todo request recebido pelo controlador gera uma entrada com timestamp ISO 8601, nivel (`info` ou `error`), mensagem e latencia em milissegundos. O buffer e mantido em memoria e nao sobrevive a reinicializacoes do servico. Para auditoria persistente, recomenda-se redirecionar os logs do container para um sistema externo.

**Variaveis de ambiente:**

| Variavel | Padrao | Descricao |
|---|---|---|
| PORT | 3001 | Porta de escuta |
| GATEWAY_URL | http://api-gateway:3000 | Endereco do gateway |
| SCRAPPER_URL | http://servico-scrapper:8003 | Endereco do scrapper |

---

## Infraestrutura de Suporte

### RabbitMQ 3 (Management)

Broker de mensagens AMQP responsavel pela comunicacao assincrona entre o scrapper e o RAG. A fila `cafeiq.ingestao` e declarada como `durable=True` pelos proprios clientes, garantindo que sobreviva a reinicializacoes do broker.

| Recurso | Valor |
|---|---|
| Porta AMQP | 5672 |
| Porta Management UI | 15672 |
| Usuario padrao | cafeiq |
| Senha padrao | cafeiq123 |
| Volume de persistencia | rabbitmq-data |

A interface de gerenciamento esta disponivel em `http://localhost:15672` e permite inspecionar filas, mensagens enfileiradas, conexoes ativas e metricas de throughput.

### ChromaDB 0.5.3

Banco de dados vetorial que armazena os embeddings dos documentos indexados pelo pipeline de ingestao. O servico-rag se conecta via `chromadb.HttpClient` e opera sobre a colecao `cafeiq`.

| Recurso | Valor |
|---|---|
| Porta HTTP | 8000 |
| Colecao utilizada | cafeiq |
| Volume de persistencia | chroma-data |
| Funcao de embedding | nomic-embed-text (via Ollama) |

### Ollama

Servidor de modelos de linguagem e de embeddings que opera inteiramente dentro do Docker. Dois modelos sao necessarios e devem ser baixados apos o primeiro `docker compose up`.

| Modelo | Tamanho | Funcao |
|---|---|---|
| llama3 | 4,7 GB | Geracao de respostas em linguagem natural |
| nomic-embed-text | 274 MB | Geracao de embeddings para busca vetorial |

| Recurso | Valor |
|---|---|
| Porta HTTP | 11434 |
| Volume de persistencia | ollama-data |

Os modelos sao persistidos no volume `ollama-data` e nao precisam ser baixados novamente nas execucoes subsequentes, a menos que o volume seja removido com `docker compose down -v`.

---

## Instalacao e Execucao

### Pre-requisitos

| Ferramenta | Versao minima | Observacao |
|---|---|---|
| Docker Engine | 24.x | Docker Desktop inclui o Compose plugin |
| Docker Compose | 2.x (plugin) | Usar `docker compose` (sem hifem) |
| Git | qualquer | Para clonar o repositorio |

O Ollama roda dentro do Docker. Nao e necessario instala-lo na maquina host.

### Primeira execucao

**1. Clonar o repositorio**

```bash
git clone <url-do-repositorio>
cd cafe-iq
```

**2. Construir as imagens e subir os containers**

```bash
docker compose up --build -d
```

O build das imagens Python e Node pode levar de 5 a 15 minutos na primeira vez, dependendo da conexao. Use `docker compose logs -f` para acompanhar os logs.

O sistema esta pronto quando os seguintes logs aparecerem:

```
cafeiq-api-gateway           | api-gateway listening on port 3000
cafeiq-servico-rag           | INFO:     Application startup complete.
cafeiq-servico-mcp           | INFO:     Application startup complete.
cafeiq-servico-scrapper      | INFO:     Application startup complete.
cafeiq-servico-controlador   | [INFO] servico-controlador escutando na porta 3001
```

**3. Baixar os modelos do Ollama (obrigatorio apenas na primeira vez)**

```bash
docker exec cafeiq-ollama ollama pull llama3
docker exec cafeiq-ollama ollama pull nomic-embed-text
```

Aguarde os dois downloads completarem antes de usar o sistema. O modelo `llama3` tem aproximadamente 4,7 GB.

**4. Verificar o estado do sistema**

```bash
curl -s http://localhost:3000/health | jq
```

Resposta esperada:

```json
{
  "gateway": "ok",
  "services": [
    {"name": "rag",         "status": "ok", "latencyMs": 12},
    {"name": "mcp",         "status": "ok", "latencyMs": 5},
    {"name": "controlador", "status": "ok", "latencyMs": 8}
  ]
}
```

**5. Abrir a interface web**

Abra o arquivo `index.html` diretamente no navegador (duplo clique ou arraste para a janela do navegador). A interface se comunica com o gateway em `http://localhost:3000`.

### Execucoes subsequentes

```bash
docker compose up -d
```

Sem `--build`. As imagens e os modelos do Ollama ja existem nos volumes. O sistema sobe em menos de 30 segundos.

### Parar o sistema

```bash
# Para containers, preserva volumes (dados do ChromaDB, Ollama e RabbitMQ)
docker compose stop

# Remove containers e volumes (reset completo, exige novo download dos modelos)
docker compose down -v
```

---

## Referencia de API

### API Gateway (porta 3000)

**POST /chat**

Envia uma pergunta ao assistente e recebe a resposta gerada pelo LLM com as fontes utilizadas.

Corpo da requisicao:
```json
{"pergunta": "Qual e a cotacao do cafe arabica hoje?"}
```

Resposta:
```json
{
  "resposta": "A cotacao do cafe arabica (ICO) em maio de 2026 estava em torno de 317 USc/lb...",
  "fontes": ["scrapper/cotacao", "scrapper/noticia"]
}
```

**POST /mcp/tool**

Invoca uma ferramenta MCP diretamente, sem passar pelo pipeline RAG.

Corpo da requisicao:
```json
{"tool": "cotacao_cafe", "params": {}}
```

Resposta:
```json
{
  "tool": "cotacao_cafe",
  "resultado": {
    "data": "2026-06-16",
    "referencia_mensal": "2026-05-01",
    "ICE_arabica_usc_lb": 317.53,
    "B3_arabica_brl_saca60kg": 2184.13,
    "fonte": "alphavantage/ICO (COFFEE)"
  }
}
```

**GET /health**

Verifica a disponibilidade de todos os servicos internos.

Resposta (HTTP 200 se todos ok, 207 se algum falhou):
```json
{
  "gateway": "ok",
  "services": [
    {"name": "rag", "status": "ok", "latencyMs": 6},
    {"name": "mcp", "status": "ok", "latencyMs": 4},
    {"name": "controlador", "status": "ok", "latencyMs": 3}
  ]
}
```

### servico-rag (porta 8001)

**POST /ingest**

Indexa um documento arbitrario no ChromaDB.

```bash
curl -s -X POST http://localhost:8001/ingest \
  -H "Content-Type: application/json" \
  -d '{"texto": "A safra 2025 atingiu 68 milhoes de sacas.", "fonte": "conab-2025"}' | jq
```

### servico-mcp (porta 8002)

**GET /tools**

Lista todas as ferramentas disponíveis com seus parametros.

**POST /invoke**

Ferramentas disponiveis e parametros:

| Ferramenta | Parametros | Fonte dos dados |
|---|---|---|
| cotacao_cafe | nenhum | Alpha Vantage ICO (COFFEE function) |
| clima | `{"cidade": "Nome da cidade"}` | wttr.in |
| noticias | nenhum | Google News RSS |

### servico-controlador (porta 3001)

**GET /status**

Retorna o estado consolidado do sistema consultando o gateway.

**POST /forcar-ingestao**

Dispara um ciclo imediato de coleta no scrapper.

**GET /logs**

Retorna as ultimas 20 entradas do log administrativo.

```json
{
  "total": 5,
  "logs": [
    {
      "timestamp": "2026-06-16T23:41:02.000Z",
      "level": "info",
      "message": "POST /forcar-ingestao -> 200",
      "ms": 43
    }
  ]
}
```

---

## Variaveis de Ambiente

Todas as variaveis possuem valores padrao que funcionam sem configuracao adicional no ambiente Docker Compose. Para producao, substitua credenciais e URLs conforme necessario.

| Servico | Variavel | Padrao |
|---|---|---|
| api-gateway | PORT | 3000 |
| api-gateway | RAG_URL | http://servico-rag:8001 |
| api-gateway | MCP_URL | http://servico-mcp:8002 |
| api-gateway | CONTROLADOR_URL | http://servico-controlador:3001 |
| servico-rag | OLLAMA_BASE_URL | http://ollama:11434 |
| servico-rag | LLM_MODEL | llama3 |
| servico-rag | EMBED_MODEL | nomic-embed-text |
| servico-rag | CHROMA_HOST | chromadb |
| servico-rag | CHROMA_PORT | 8000 |
| servico-rag | COLLECTION_NAME | cafeiq |
| servico-rag | RETRIEVER_K | 4 |
| servico-rag | MCP_URL | http://servico-mcp:8002 |
| servico-rag | RABBITMQ_HOST | event-bus |
| servico-rag | RABBITMQ_USER | cafeiq |
| servico-rag | RABBITMQ_PASS | cafeiq123 |
| servico-rag | QUEUE_NAME | cafeiq.ingestao |
| servico-rag | CONSUMER_RETRY_DELAY | 5 |
| servico-scrapper | RABBITMQ_HOST | event-bus |
| servico-scrapper | RABBITMQ_USER | cafeiq |
| servico-scrapper | RABBITMQ_PASS | cafeiq123 |
| servico-scrapper | QUEUE_NAME | cafeiq.ingestao |
| servico-scrapper | COLLECT_INTERVAL | 60 |
| servico-controlador | PORT | 3001 |
| servico-controlador | GATEWAY_URL | http://api-gateway:3000 |
| servico-controlador | SCRAPPER_URL | http://servico-scrapper:8003 |

---

## Estrutura do Repositorio

```
cafe-iq/
|
|-- index.html                        # Interface web (HTML, CSS e JS sem framework)
|-- docker-compose.yml                # Orquestracao de todos os servicos
|-- README.md
|
|-- docs/
|   |-- arquitetura.md                # Justificativas arquiteturais e mapeamento GCC129
|
|-- api-gateway/
|   |-- Dockerfile
|   |-- package.json                  # Express 4, Axios 1.7
|   |-- src/
|       |-- index.js                  # Rotas, CORS, logging, health check paralelo
|
|-- servico-rag/
|   |-- Dockerfile
|   |-- requirements.txt              # FastAPI, LangChain, ChromaDB, Pika
|   |-- app/
|       |-- main.py                   # FastAPI, lifespan (inicia consumer thread)
|       |-- rag.py                    # Pipeline RAG: embeddings, retrieval, LLM
|       |-- mcp_enricher.py           # Deteccao de ferramentas e chamadas ao MCP
|       |-- consumer.py               # Consumer RabbitMQ com reconexao automatica
|       |-- config.py                 # Variaveis de ambiente com valores padrao
|
|-- servico-mcp/
|   |-- Dockerfile
|   |-- requirements.txt              # FastAPI, Requests
|   |-- app/
|       |-- main.py                   # FastAPI: /tools e /invoke
|       |-- registry.py               # Registro de ferramentas e metadados
|       |-- tools/
|           |-- cotacao_cafe.py       # Alpha Vantage ICO: cotacao em USc/lb
|           |-- clima.py              # wttr.in: temperatura, umidade, condicao
|           |-- noticias.py           # Google News RSS: manchetes recentes
|
|-- servico-scrapper/
|   |-- Dockerfile
|   |-- requirements.txt              # FastAPI, Requests, Pika
|   |-- app/
|       |-- main.py                   # FastAPI, loop de coleta com threading.Event
|       |-- collectors.py             # Coleta de noticias, clima e cotacao
|       |-- publisher.py              # Publicacao AMQP com reconexao e retry
|       |-- config.py                 # Variaveis de ambiente com valores padrao
|
|-- servico-controlador/
    |-- Dockerfile
    |-- package.json                  # Express 4, Axios 1.7
    |-- src/
        |-- index.js                  # /status, /forcar-ingestao, /logs, buffer circular
```

---

## Portas Expostas

| Servico | Porta | Acesso recomendado |
|---|---|---|
| api-gateway | 3000 | Ponto de entrada para o cliente web e testes de API |
| servico-rag | 8001 | Ingestao manual de documentos via /ingest |
| servico-mcp | 8002 | Testes diretos de ferramentas via /invoke |
| servico-scrapper | 8003 | Trigger manual via /coletar-agora |
| servico-controlador | 3001 | Painel administrativo |
| ChromaDB | 8000 | Acesso interno (nao exposto ao usuario final) |
| Ollama | 11434 | Acesso interno (nao exposto ao usuario final) |
| RabbitMQ AMQP | 5672 | Acesso interno |
| RabbitMQ Management | 15672 | Painel web: http://localhost:15672 (cafeiq / cafeiq123) |
