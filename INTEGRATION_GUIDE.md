# FastAPI ↔ Worker Integration Guide

## Overview

This guide shows how the **Worker service** (Node.js/TypeScript) integrates with the **FastAPI Ollama service** (Python) for AI model inference.

## Architecture

```
Worker (TypeScript)
  ↓ HTTP calls
FastAPI (Python) - Pure Model Service
  ↓ HTTP calls
Ollama (GPU Server)
```

## Worker Configuration

The Worker service is configured to call FastAPI via the `OLLAMA_HOST` environment variable:

```typescript
// worker/src/core/config.ts
ollamaHost: process.env.OLLAMA_HOST || process.env.OLLAMA_BASE_URL || 'http://localhost:11434'
```

### Environment Setup

**Local Development:**
```bash
# Worker .env
OLLAMA_HOST=http://localhost:8000  # FastAPI service
```

**Production:**
```bash
# Worker .env
OLLAMA_HOST=https://ollama.ctrlchecks.ai  # FastAPI via reverse proxy
```

## API Endpoints Used by Worker

### 1. Chat Completions (`/api/chat`)

**Worker Usage:**
```typescript
// worker/src/services/ai/ollama-manager.ts
async generate(prompt: string, options: OllamaGenerationOptions) {
  // Calls FastAPI /api/chat endpoint
  const response = await fetch(`${this.endpoint}/api/chat`, {
    method: 'POST',
    body: JSON.stringify({
      model: options.model,
      messages: [{ role: 'user', content: prompt }],
      stream: false
    })
  });
}
```

**FastAPI Endpoint:**
- `POST /api/chat`
- Handles retry, circuit breaker, fallback
- Validates JSON responses
- Returns model response

### 2. Text Generation (`/api/generate`)

**Worker Usage:**
```typescript
// Similar to chat, but uses /api/generate
const response = await fetch(`${this.endpoint}/api/generate`, {
  method: 'POST',
  body: JSON.stringify({
    model: options.model,
    prompt: prompt,
    stream: false
  })
});
```

**FastAPI Endpoint:**
- `POST /api/generate`
- Same resilience features as `/api/chat`

### 3. List Models (`/api/tags`)

**Worker Usage:**
```typescript
// Check available models
const response = await fetch(`${this.endpoint}/api/tags`);
const { models } = await response.json();
```

**FastAPI Endpoint:**
- `GET /api/tags`
- Returns list of available Ollama models

### 4. Health Check (`/health`)

**Worker Usage:**
```typescript
// Check FastAPI service health
const response = await fetch(`${this.endpoint}/health`);
const health = await response.json();
// Returns: { status, ollama, gpu, models, ... }
```

**FastAPI Endpoint:**
- `GET /health`
- Returns service health, Ollama status, GPU info

## Current Worker Integration Points

### 1. OllamaManager (`worker/src/services/ai/ollama-manager.ts`)

**Primary integration point:**
- Manages all Ollama API calls
- Handles endpoint configuration
- Uses `config.ollamaHost` for FastAPI URL
- Supports both direct Ollama and FastAPI proxy

**Key Methods:**
```typescript
class OllamaManager {
  async generate(prompt: string, options: OllamaGenerationOptions)
  async ensureModelsLoaded(models: string[])
  private async directHttpFetch(endpoint: string, body: any)
}
```

### 2. OllamaOrchestrator (`worker/src/services/ai/ollama-orchestrator.ts`)

**High-level orchestration:**
- Routes AI requests to appropriate models
- Uses `OllamaManager` for actual API calls
- Handles caching and retry logic
- Tracks performance metrics

**Key Methods:**
```typescript
class OllamaOrchestrator {
  async processRequest(type: AIRequestType, input: any, options?: {...})
  private async executeWithRetry(model: string, type: AIRequestType, ...)
}
```

### 3. Workflow Builder (`worker/src/services/ai/workflow-builder.ts`)

**Workflow generation:**
- Uses `ollamaOrchestrator.processRequest()` for AI calls
- Generates workflows from prompts
- Calls FastAPI indirectly via OllamaOrchestrator

**Example:**
```typescript
const result = await ollamaOrchestrator.processRequest('workflow-generation', {
  prompt: fullPrompt,
  temperature: 0.2,
  maxTokens: 100,
});
```

## FastAPI Features Available to Worker

### 1. Automatic Fallback

If primary model (14B) fails:
- FastAPI automatically switches to fallback (7B)
- Worker receives response from fallback model
- No code changes needed in Worker

### 2. Retry Logic

FastAPI handles:
- Exponential backoff retry
- Network error recovery
- Timeout handling
- Worker doesn't need to implement retry

### 3. Circuit Breaker

FastAPI protects against:
- Cascading failures
- Service overload
- Returns 503 when circuit is open
- Worker should handle 503 gracefully

### 4. JSON Validation

FastAPI ensures:
- All responses are valid JSON
- Automatic correction of malformed JSON
- Worker receives clean JSON responses

### 5. GPU Optimization

FastAPI manages:
- Request queue (prevents parallel heavy calls)
- VRAM pressure detection
- Automatic model selection based on GPU state
- Worker doesn't need GPU awareness

## Error Handling in Worker

### Handle FastAPI Errors

```typescript
try {
  const response = await ollamaManager.generate(prompt, options);
  // Success
} catch (error) {
  if (error.status === 503) {
    // Circuit breaker is open - service temporarily unavailable
    console.error('FastAPI circuit breaker is open');
  } else if (error.status === 504) {
    // Request timeout
    console.error('FastAPI request timeout');
  } else {
    // Other errors
    console.error('FastAPI error:', error);
  }
}
```

### Health Check Before Critical Operations

```typescript
async function checkFastAPIHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${config.ollamaHost}/health`);
    const health = await response.json();
    return health.status === 'healthy' && health.ollama === 'running';
  } catch {
    return false;
  }
}

// Use before workflow generation
if (!await checkFastAPIHealth()) {
  throw new Error('FastAPI service is not available');
}
```

## Testing Integration

### Local Testing

1. **Start FastAPI:**
```bash
cd Fast_API_Ollama
python -m uvicorn main:app --reload --port 8000
```

2. **Start Worker:**
```bash
cd worker
npm run dev
# Set OLLAMA_HOST=http://localhost:8000
```

3. **Test Health:**
```bash
curl http://localhost:8000/health
```

4. **Test from Worker:**
```bash
# Worker will call FastAPI automatically via ollamaManager
# Check Worker logs for FastAPI calls
```

### Production Testing

1. **Verify FastAPI is accessible:**
```bash
curl https://ollama.ctrlchecks.ai/health
```

2. **Check Worker configuration:**
```bash
# Ensure OLLAMA_HOST=https://ollama.ctrlchecks.ai
```

3. **Monitor logs:**
- FastAPI logs: Check for request IDs and latency
- Worker logs: Check for successful FastAPI calls

## Best Practices

### 1. Use OllamaOrchestrator for AI Calls

✅ **Good:**
```typescript
const result = await ollamaOrchestrator.processRequest('workflow-generation', {
  prompt: prompt,
  temperature: 0.2
});
```

❌ **Avoid:**
```typescript
// Don't call FastAPI directly - use OllamaManager/OllamaOrchestrator
const response = await fetch(`${config.ollamaHost}/api/chat`, ...);
```

### 2. Handle Circuit Breaker Errors

```typescript
try {
  const result = await ollamaOrchestrator.processRequest(...);
} catch (error) {
  if (error.message.includes('Circuit breaker')) {
    // Retry after delay or use fallback
    await new Promise(resolve => setTimeout(resolve, 5000));
    // Retry or use alternative approach
  }
}
```

### 3. Monitor FastAPI Health

```typescript
// Before critical operations
const health = await fetch(`${config.ollamaHost}/health`).then(r => r.json());
if (health.status !== 'healthy') {
  // Log warning or use fallback
}
```

### 4. Use Appropriate Models

FastAPI supports:
- `qwen2.5:14b-instruct-q4_K_M` (primary)
- `qwen2.5:7b-instruct-q4_K_M` (fallback)
- `qwen2.5-coder:7b-instruct-q4_K_M` (coder)

Worker should use these models for consistency.

## Troubleshooting

### Worker can't connect to FastAPI

1. **Check FastAPI is running:**
```bash
curl http://localhost:8000/health
```

2. **Check Worker config:**
```bash
# Verify OLLAMA_HOST is set correctly
echo $OLLAMA_HOST
```

3. **Check network:**
```bash
# From Worker machine
ping ollama.ctrlchecks.ai
```

### FastAPI returns 503 (Circuit Breaker)

1. **Check FastAPI health:**
```bash
curl http://localhost:8000/health
# Look for circuit_breaker state
```

2. **Wait for recovery:**
- Circuit breaker recovers after 60 seconds
- Or restart FastAPI service

### Slow responses

1. **Check GPU status:**
```bash
curl http://localhost:8000/health
# Look for gpu.vram_pressure
```

2. **Check FastAPI metrics:**
```bash
curl http://localhost:8000/metrics
# Look for latency metrics
```

3. **Check model loading:**
- First request is slower (model loading)
- Subsequent requests should be faster

## Summary

- ✅ Worker calls FastAPI via `OLLAMA_HOST` environment variable
- ✅ FastAPI provides `/api/chat`, `/api/generate`, `/api/tags`, `/health`
- ✅ FastAPI handles resilience (retry, circuit breaker, fallback)
- ✅ Worker uses `OllamaManager` and `OllamaOrchestrator` for AI calls
- ✅ No direct FastAPI calls needed - use existing Worker services
- ✅ FastAPI is pure model service - no business logic

**Integration is already working!** The Worker service is already configured to use FastAPI for all AI model calls.
