# Troubleshooting Guide - Café IQ Project

## Issue #1: Ollama llama-server Process Killed (OOM)

**Status**: ✓ DIAGNOSED

**Error Message**:
```
Ollama call failed with status code 500. Details: {"error":"llama-server process has terminated: signal: killed"}
```

**Root Cause**: 
Out-Of-Memory error when llama3 model (4.7 GB) attempts to load during completion inference.
Docker Desktop container memory limit exceeded.

**Solution**:
See [docs/OLLAMA_OOM_FIX.md](docs/OLLAMA_OOM_FIX.md) for:
1. Increase Docker Desktop memory (recommended)
2. Reduce llama3 context size  
3. Use smaller model (mistral, neural-chat, phi)

**How to Verify Fix**:
```powershell
# Test embeddings (should work)
curl.exe -X POST http://localhost:11434/v1/embeddings `
  -H "Content-Type: application/json" `
  -d '{"model":"nomic-embed-text","input":"test"}'

# Test completions (will fail if OOM not fixed)
curl.exe -X POST http://localhost:11434/v1/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"llama3","prompt":"Test","max_tokens":10}'
```

---

## Issue #2: Windows PowerShell curl Alias (RESOLVED)

**Error**: `curl` command treated as PowerShell alias instead of curl.exe

**Solution**: Use `curl.exe` explicitly in all commands

---

## Issue #3: Model Not Found "nomic-embed-text" (RESOLVED)

**Cause**: Model not downloaded to container

**Solution**: Pull models on first startup
```powershell
docker exec cafeiq-ollama ollama pull nomic-embed-text
docker exec cafeiq-ollama ollama pull llama3
```

---

## Quick Debugging Commands

### Health Check
```powershell
docker ps --filter "name=cafeiq"
docker logs --tail 50 cafeiq-ollama
docker exec cafeiq-ollama ollama list
```

### Memory Inspection
```powershell
docker stats --no-stream cafeiq-ollama
docker inspect cafeiq-ollama --format '{{json .State}}'
```

### API Testing
```powershell
# List available models
curl.exe http://localhost:11434/v1/models

# Test embeddings
curl.exe -X POST http://localhost:11434/v1/embeddings `
  -H "Content-Type: application/json" `
  -d '{"model":"nomic-embed-text:latest","input":"test"}'

# Test completions
curl.exe -X POST http://localhost:11434/v1/completions `
  -H "Content-Type: application/json" `
  -d '{"model":"llama3:latest","prompt":"Test","max_tokens":10}'
```
