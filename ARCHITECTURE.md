# FastAPI Ollama Service - Architecture

## Overview

**FastAPI Ollama Service** is a **pure model service** that provides a REST API interface to Ollama instances running on GPU servers. It handles AI model inference only - no business logic.

## Core Principle

> **FastAPI = Pure Model Service**  
> **Worker = All Business Logic**

This separation allows:
- ✅ FastAPI to remain stable (only model calls)
- ✅ Worker to iterate quickly (local development)
- ✅ Easier testing and debugging
- ✅ No need to deploy to GPU for logic changes

## Service Responsibilities

### ✅ What FastAPI Does

1. **Model Proxy**
   - `/api/chat` - Chat completions
   - `/api/generate` - Text generation
   - `/api/tags` - List available models
   - `/api/create` - Create new models

2. **Resilience Features**
   - Retry with exponential backoff
   - Circuit breaker (trip after 5 failures)
   - Automatic fallback to smaller models (7B if 14B fails)
   - JSON validation and correction
   - Request size limits
   - Rate limiting

3. **Monitoring**
   - `/health` - Health check with GPU monitoring
   - `/metrics` - Prometheus metrics
   - GPU memory monitoring (VRAM pressure detection)
   - Request tracing with request IDs

4. **GPU Optimization**
   - Request queue (mutex) to prevent parallel heavy calls
   - VRAM pressure detection
   - Automatic model selection based on GPU state

### ❌ What FastAPI Does NOT Do

- ❌ Workflow generation logic
- ❌ Intent extraction
- ❌ Task planning
- ❌ Node selection
- ❌ Property inference
- ❌ Workflow validation
- ❌ Business logic of any kind

All of the above is handled by the **Worker service** (Node.js/TypeScript).

## API Endpoints

### Model Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/chat` | POST | Chat with Ollama models |
| `/api/generate` | POST | Generate text completions |
| `/api/tags` | GET | List available models |
| `/api/create` | POST | Create new model from Modelfile |

### Health & Monitoring

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check with Ollama and GPU status |
| `/metrics` | GET | Prometheus-formatted metrics |

### Legacy Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/run` | POST | Legacy direct LLM prompt |
| `/process` | POST | Legacy task-based processing |
| `/chatbot` | POST | Proxy to Worker service |

## Configuration

Environment variables (see `env.example`):

```bash
# Ollama
OLLAMA_URL=http://localhost:11434

# Models
MODEL_PRIMARY=qwen2.5:14b-instruct-q4_K_M
MODEL_FALLBACK=qwen2.5:7b-instruct-q4_K_M
MODEL_CODER=qwen2.5-coder:7b-instruct-q4_K_M
MODEL_TIMEOUT=60
MODEL_MAX_RETRIES=3

# Circuit Breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=60.0

# Request Limits
MAX_REQUEST_SIZE_MB=10
RATE_LIMIT_PER_MINUTE=100
```

## Architecture Flow

```
Frontend
   ↓
Worker (Node.js/TypeScript)
   ├─ Workflow Generation Logic
   ├─ Intent Extraction
   ├─ Planning
   ├─ Node Selection
   └─ Validation
   ↓
FastAPI (Python) - Pure Model Service
   ├─ /api/chat
   ├─ /api/generate
   └─ Resilience (retry, circuit breaker, fallback)
   ↓
Ollama (GPU Server)
   └─ Qwen2.5 Models
```

## Key Features

### 1. Automatic Fallback

If primary model (14B) fails or VRAM pressure is high:
- Automatically switches to fallback model (7B)
- Logs the fallback event
- Returns response from fallback model

### 2. JSON Validation

All model responses are:
- Validated for JSON syntax
- Corrected if malformed (with retry)
- Logged if correction fails

### 3. Circuit Breaker

Protects against cascading failures:
- Opens after 5 consecutive failures
- Blocks requests for 60 seconds
- Automatically attempts recovery

### 4. GPU Monitoring

- Monitors VRAM usage via `nvidia-smi`
- Detects high VRAM pressure (>85%)
- Automatically selects smaller models when needed

### 5. Request Tracing

Every request gets:
- Unique request ID
- Structured JSON logging
- Latency tracking
- Model usage metrics

## File Structure

```
Fast_API_Ollama/
├── main.py                 # Main FastAPI app
├── circuit_breaker.py      # Circuit breaker implementation
├── metrics.py              # Prometheus metrics
├── json_validator.py       # JSON validation and correction
├── gpu_monitor.py          # GPU memory monitoring
├── retry_utils.py          # Retry with exponential backoff
├── requirements.txt        # Python dependencies
├── env.example            # Environment variable template
├── ARCHITECTURE.md        # This file
└── WORKFLOW_COMPILER_MIGRATION.md  # Migration guide
```

## Deployment

FastAPI runs on port 8000 (configurable via `PORT` env var).

For production deployment, see:
- `DEPLOY_COMMANDS.txt` - Deployment instructions
- `nginx-ollama-complete.conf` - Nginx reverse proxy config

## Testing

```bash
# Health check
curl http://localhost:8000/health

# List models
curl http://localhost:8000/api/tags

# Chat
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:14b-instruct-q4_K_M",
    "messages": [{"role": "user", "content": "Hello"}],
    "stream": false
  }'
```

## Notes

- FastAPI is **stateless** - no database, no session storage
- All business logic is in Worker service
- FastAPI only proxies to Ollama with resilience features
- Changes to workflow logic should be made in Worker, not FastAPI
