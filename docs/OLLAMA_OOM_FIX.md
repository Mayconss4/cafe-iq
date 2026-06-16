# Solução: Ollama llama-server Process Killed (Out-Of-Memory)

## Problema
Quando o serviço RAG tenta gerar respostas usando o modelo `llama3`, o servidor Ollama retorna erro 500:
```json
{"error":"llama-server process has terminated: signal: killed"}
```

## Diagnóstico
1. **Embeddings funcionam**: O modelo `nomic-embed-text` (274 MB) executa sem problemas
2. **Completions falham**: Chamadas para `/v1/completions` com `llama3` retornam HTTP 500
3. **Container foi OOMKilled**: `docker inspect cafeiq-ollama` mostra `"OOMKilled":true`
4. **Causa**: O modelo `llama3` (4.7 GB) requer muita memória RAM para executar e o Docker está matando o processo

## Solução (3 opções)

### **Opção 1: Aumentar memória alocada para Docker Desktop (RECOMENDADO)**

Docker Desktop por padrão aloca apenas 2-4 GB de RAM. O modelo llama3 necessita de mais espaço.

#### Windows (Docker Desktop):
1. Abra **Docker Desktop Settings** (clique no ícone na bandeja)
2. Vá para **Resources** → **Memory**
3. Aumente para **8 GB ou mais** (mínimo 12 GB recomendado para llama3)
4. Clique em **Apply & Restart**

Verifique após reiniciar:
```powershell
docker system info | Select-String "Memory"
```

---

### **Opção 2: Reduzir o tamanho do contexto do llama3**

Modifique o serviço RAG para usar contexto menor e melhorar performance:

**Arquivo**: [servico-rag/app/rag.py](../servico-rag/app/rag.py)

```python
# Linha ~64: Adicione parâmetros de otimização
llm = Ollama(
    base_url=OLLAMA_BASE_URL, 
    model=LLM_MODEL,
    num_ctx=1024,  # Reduz contexto de 2048 para 1024 tokens
    num_threads=4,  # Limita threads
)
```

**Arquivo**: [servico-rag/app/config.py](../servico-rag/app/config.py)

```python
# Adicione variáveis de configuração
OLLAMA_CONTEXT_SIZE = int(os.getenv("OLLAMA_CONTEXT_SIZE", "1024"))
OLLAMA_THREADS = int(os.getenv("OLLAMA_THREADS", "4"))
```

Depois reinicie:
```powershell
docker-compose restart servico-rag
```

---

### **Opção 3: Usar modelo menor em vez de llama3**

Se não conseguir aumentar memória, use um modelo mais leve:

Edite [docker-compose.yml](../docker-compose.yml) ou execute:

```powershell
# Remova llama3 e instale modelo menor
docker exec cafeiq-ollama ollama rm llama3
docker exec cafeiq-ollama ollama pull mistral  # ou neural-chat, phi, etc
```

Depois atualize [servico-rag/app/config.py](../servico-rag/app/config.py):
```python
LLM_MODEL = os.getenv("LLM_MODEL", "mistral")  # em vez de "llama3"
```

---

## Verificação Após Correção

### 1. Confirme memória do Docker
```powershell
docker stats --no-stream --format "table {{.MemUsage}}" cafeiq-ollama
```
Deve mostrar > 6 GB disponíveis.

### 2. Teste completions
```powershell
$req = @{
    model = "llama3"
    prompt = "Olá, como você está?"
    max_tokens = 50
} | ConvertTo-Json

Invoke-RestMethod -Uri http://localhost:11434/v1/completions `
  -Method Post -ContentType 'application/json' -Body $req | Format-List
```

### 3. Teste via API Gateway
```powershell
curl.exe -X POST http://localhost:3000/chat `
  -H "Content-Type: application/json" `
  -d '{"pergunta":"Como você está?"}'
```

---

## Referências
- [Ollama Documentation](https://github.com/ollama/ollama)
- [Docker Desktop Memory Settings](https://docs.docker.com/desktop/settings/windows/#resources)
- [Model Comparison](https://ollama.ai/library)
