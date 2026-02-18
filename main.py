import os
import uuid
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pydantic_settings import BaseSettings
import httpx
import json
import time
import logging
import asyncio
from typing import Optional
from contextlib import asynccontextmanager

# Import new modules
from circuit_breaker import CircuitBreaker
from metrics import metrics
from json_validator import validate_and_fix_json, ensure_json_response
from gpu_monitor import get_gpu_memory_info, check_vram_pressure
from retry_utils import retry_with_backoff

# Configure structured JSON logging
logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "name": "%(name)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger(__name__)

# Define lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting CtrlChecks AI Backend - Pure Model Service")
    
    yield
    
    # Shutdown
    logger.info("Shutting down CtrlChecks AI Backend")


class Settings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    port: int = 8000
    allowed_origins: str = "*"
    timeout_seconds: float = 60.0  # Reduced to 60s default
    worker_url: str = "http://localhost:3001"
    
    # Model configuration
    model_primary: str = "qwen2.5:14b-instruct-q4_K_M"
    model_fallback: str = "qwen2.5:7b-instruct-q4_K_M"
    model_coder: str = "qwen2.5-coder:7b-instruct-q4_K_M"
    model_timeout: int = 60
    model_max_retries: int = 3
    
    # Circuit breaker
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0
    
    # Request limits
    max_request_size_mb: int = 10
    rate_limit_per_minute: int = 100
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

# Initialize circuit breaker
circuit_breaker = CircuitBreaker(
    failure_threshold=settings.circuit_breaker_failure_threshold,
    recovery_timeout=settings.circuit_breaker_recovery_timeout
)

# Request queue for GPU optimization (simple mutex)
request_lock = asyncio.Lock()

# OpenAPI tags metadata
tags_metadata = [
    {
        "name": "health",
        "description": "Health check endpoints to verify service and Ollama connectivity.",
    },
    {
        "name": "models",
        "description": "Operations for listing and managing Ollama models.",
    },
    {
        "name": "chat",
        "description": "Chat with Ollama models using conversational interface.",
    },
    {
        "name": "generate",
        "description": "Generate text completions using Ollama models.",
    },
    {
        "name": "legacy",
        "description": "Legacy endpoints for backward compatibility.",
    },
]

app = FastAPI(
    title="CtrlChecks AI Backend",
    description="""
    FastAPI proxy service for Ollama models - Pure Model Service.
    
    This service provides a REST API interface to interact with Ollama instances running on GPU servers.
    It handles model management, chat interactions, and text generation with resilience features.
    
    ## Features
    
    * **Model Management**: List and query available Ollama models
    * **Chat Interface**: Conversational AI interactions with retry and fallback
    * **Text Generation**: Direct text completion with JSON validation
    * **Health Monitoring**: Service and Ollama connectivity checks with GPU monitoring
    * **Resilience**: Circuit breaker, retry logic, and automatic fallback to smaller models
    
    ## Architecture
    
    This is a **pure model service** - it only handles AI model inference.
    All workflow generation logic is handled by the Worker service (Node.js/TypeScript).
    
    ## Authentication
    
    Currently, this service does not require authentication for local development.
    For production, consider adding API key authentication.
    """,
    version="1.0.0",
    openapi_tags=tags_metadata,
    lifespan=lifespan,
    contact={
        "name": "CtrlChecks Support",
        "url": "https://ctrlchecks.ai",
    },
    license_info={
        "name": "Proprietary",
    },
)

# -------------------------------------------------
# CORS CONFIG
# -------------------------------------------------
origins = settings.allowed_origins.split(",") if settings.allowed_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Note: Workflow compiler logic is in Worker service, not here
# FastAPI is a pure model service - only handles Ollama proxy calls

# -------------------------------------------------
# CONSTANTS
# -------------------------------------------------
OLLAMA_URL = settings.ollama_url.rstrip("/")
WORKER_URL = settings.worker_url.rstrip("/")

# -------------------------------------------------
# REQUEST MODELS
# -------------------------------------------------
class RunRequest(BaseModel):
    prompt: str
    model: str = "llama3.1:8b"  # Production model for general tasks
    timeout: int = 180

class ProcessRequest(BaseModel):
    task: str
    input: str = None
    image: str = None  # Base64 encoded image for image processing tasks
    model: str = "llama3.1:8b"  # Production model for general tasks
    timeout: int = 180
    sentence_count: int = 5  # For story generation
    steps: int = 2  # For text-to-image (not supported, but kept for compatibility)
    guidance_scale: float = 1.0  # For text-to-image (not supported, but kept for compatibility)

# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.get(
    "/",
    tags=["health"],
    summary="Service Information",
    description="Get information about the service and available endpoints.",
    response_description="Service information and endpoint list",
)
def root():
    """
    Get service information and available endpoints.
    
    Returns basic information about the service and a list of all available endpoints.
    """
    return {
        "service": "CtrlChecks AI Backend",
        "status": "running",
        "version": "1.0.0",
        "ollama_url": OLLAMA_URL,
        "endpoints": {
            "/": "Root - Service information",
            "/health": "Health check - Verify service and Ollama connectivity",
            "/api/tags": "List models - Get available Ollama models",
            "/api/create": "Create model - Create new Ollama model from Modelfile",
            "/api/chat": "Chat - Conversational AI interface",
            "/api/generate": "Generate - Text completion",
            "/run": "Legacy - Direct LLM prompt",
            "/process": "Legacy - Task-based processing",
            "/chatbot": "Proxy - Chatbot endpoint (forwards to worker service)",
        },
        "docs": {
            "swagger": "/docs",
            "redoc": "/redoc",
            "openapi": "/openapi.json",
        }
    }

@app.get(
    "/health",
    tags=["health"],
    summary="Health Check",
    description="Check service health, Ollama connectivity, model availability, and GPU status.",
    response_description="Health status including Ollama connection, models, and GPU memory",
)
async def health():
    """Enhanced health check with GPU monitoring"""
    health_data = {
        "status": "healthy",
        "timestamp": time.time(),
        "service": "CtrlChecks AI Backend",
        "version": "1.0.0"
    }
    
    # Check Ollama connectivity
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                models_data = response.json()
                available_models = [m.get("name", "") for m in models_data.get("models", [])]
                health_data["ollama"] = "running"
                health_data["models"] = available_models
                
                # Check if primary model is loaded
                primary_loaded = any(settings.model_primary in m or m.startswith(settings.model_primary.split(":")[0]) for m in available_models)
                health_data["primary_model_loaded"] = primary_loaded
                health_data["primary_model"] = settings.model_primary
            else:
                health_data["ollama"] = "down"
    except Exception as e:
        health_data["ollama"] = "down"
        health_data["ollama_error"] = str(e)
    
    # Check GPU memory
    gpu_info = get_gpu_memory_info()
    if gpu_info:
        health_data["gpu"] = gpu_info
        health_data["gpu_available"] = True
        # Check VRAM pressure
        health_data["vram_pressure"] = check_vram_pressure(90.0)
    else:
        health_data["gpu_available"] = False
    
    # Circuit breaker status
    health_data["circuit_breaker"] = circuit_breaker.get_state()
    
    # Determine overall status
    if health_data.get("ollama") != "running":
        health_data["status"] = "degraded"
    if health_data.get("vram_pressure"):
        health_data["status"] = "degraded"
        health_data["warning"] = "High VRAM usage detected"
    
    return health_data


@app.get(
    "/metrics",
    tags=["health"],
    summary="Prometheus Metrics",
    description="Export metrics in Prometheus format",
)
async def get_metrics():
    """Prometheus metrics endpoint"""
    return Response(
        content=metrics.get_prometheus_format(),
        media_type="text/plain"
    )

# -------------------------------------------------
# OLLAMA PROXY ENDPOINTS
# -------------------------------------------------
@app.get(
    "/api/tags",
    tags=["models"],
    summary="List Available Models",
    description="Get a list of all available Ollama models installed on the server.",
    response_description="List of models with metadata",
)
async def list_models_proxy():
    """
    List all available Ollama models.
    
    This endpoint proxies the Ollama `/api/tags` endpoint to retrieve
    a list of all models that are currently available for use.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ollama proxy error: {str(e)}")

@app.get("/models")
async def list_models_alias():
    return await list_models_proxy()

class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str = "llama3.1:8b"  # Production model for general tasks
    messages: list[ChatMessage]
    stream: bool = False
    options: dict | None = None


async def _call_ollama_chat(body: dict, request_id: str, use_fallback: bool = False) -> dict:
    """Internal function to call Ollama chat API with retry and fallback"""
    # Select model with fallback support
    requested_model = body.get('model', settings.model_primary)
    
    # If VRAM pressure, prefer smaller model
    if check_vram_pressure(85.0) and not use_fallback:
        if requested_model == settings.model_primary:
            logger.info(f"[{request_id}] VRAM pressure detected, using fallback model")
            body = body.copy()
            body['model'] = settings.model_fallback
            use_fallback = True
    
    # Use fallback if primary fails
    if use_fallback and requested_model == settings.model_primary:
        body = body.copy()
        body['model'] = settings.model_fallback
        logger.info(f"[{request_id}] Using fallback model: {settings.model_fallback}")
    
    timeout = settings.model_timeout
    
    async def _make_request():
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/chat", json=body)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp
    
    # Retry with exponential backoff
    try:
        resp = await retry_with_backoff(
            _make_request,
            max_retries=settings.model_max_retries,
            base_delay=1.0,
            max_delay=10.0,
            exceptions=(httpx.TimeoutException, httpx.NetworkError, HTTPException)
        )
    except Exception as e:
        # Try fallback model if primary failed
        if not use_fallback and requested_model == settings.model_primary:
            logger.warning(f"[{request_id}] Primary model failed, trying fallback")
            return await _call_ollama_chat(body, request_id, use_fallback=True)
        raise
    
    # Parse and validate JSON response
    response_text = resp.text.strip()
    parsed_json, is_valid = validate_and_fix_json(response_text)
    
    if not is_valid:
        logger.warning(f"[{request_id}] Invalid JSON response, attempting correction")
        # Try correction prompt if JSON is invalid
        correction_prompt = {
            "role": "system",
            "content": "You must respond with valid JSON only. Fix any JSON syntax errors."
        }
        if body.get('messages'):
            body['messages'].insert(0, correction_prompt)
            # Retry once with correction
            resp = await _make_request()
            response_text = resp.text.strip()
            parsed_json, is_valid = validate_and_fix_json(response_text)
    
    if is_valid:
        return parsed_json
    else:
        # Last resort: return error with raw response
        logger.error(f"[{request_id}] Failed to parse JSON after correction")
        return {
            "error": "Invalid JSON response",
            "raw_response": response_text[:500],
            "model": body.get('model')
        }


@app.post(
    "/api/chat",
    tags=["chat"],
    summary="Chat with Model",
    description="Send a chat message to an Ollama model with retry, JSON validation, and fallback.",
    response_description="Model response with message content",
)
async def chat_proxy(request: Request):
    """
    Enhanced chat endpoint with:
    - Retry with exponential backoff
    - JSON validation and correction
    - Circuit breaker protection
    - GPU-aware model selection
    - Automatic fallback to 7B model
    - Request ID tracing
    - Metrics tracking
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Check request size
    content_length = request.headers.get('content-length')
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > settings.max_request_size_mb:
            raise HTTPException(
                status_code=413,
                detail=f"Request too large: {size_mb:.2f}MB (max: {settings.max_request_size_mb}MB)"
            )
    
    try:
        body = await request.json()
        
        # Log request with structured logging
        logger.info(json.dumps({
            "request_id": request_id,
            "endpoint": "/api/chat",
            "model": body.get('model', 'default'),
            "message_count": len(body.get('messages', [])),
            "stream": body.get('stream', False)
        }))
        
        # Ensure stream is False (we don't support streaming in this refactor)
        body['stream'] = False
        
        # Check circuit breaker state
        cb_state = circuit_breaker.get_state()
        if cb_state['state'] == 'open':
            raise HTTPException(status_code=503, detail="Service temporarily unavailable: Circuit breaker is OPEN")
        
        # Use request lock for GPU optimization (simple mutex)
        async with request_lock:
            try:
                result = await _call_ollama_chat(body, request_id)
                # Record success for circuit breaker
                circuit_breaker._on_success()
            except Exception as e:
                metrics.increment_counter("chat_requests_failed", labels={"model": body.get('model', 'unknown')})
                # Record failure for circuit breaker
                circuit_breaker._on_failure()
                raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
        
        # Track metrics
        latency_ms = (time.time() - start_time) * 1000
        metrics.increment_counter("chat_requests_total", labels={"model": body.get('model', 'unknown')})
        metrics.record_histogram("chat_latency_ms", latency_ms, labels={"model": body.get('model', 'unknown')})
        
        logger.info(json.dumps({
            "request_id": request_id,
            "status": "success",
            "latency_ms": round(latency_ms, 2),
            "model": result.get('model', body.get('model'))
        }))
        
        return result
        
    except httpx.TimeoutException:
        metrics.increment_counter("chat_requests_timeout")
        raise HTTPException(status_code=504, detail="Request timeout")
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_counter("chat_requests_error")
        logger.error(json.dumps({
            "request_id": request_id,
            "error": str(e),
            "error_type": type(e).__name__
        }), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

async def _call_ollama_generate(body: dict, request_id: str, use_fallback: bool = False) -> dict:
    """Internal function to call Ollama generate API with retry and fallback"""
    requested_model = body.get('model', settings.model_primary)
    
    # If VRAM pressure, prefer smaller model
    if check_vram_pressure(85.0) and not use_fallback:
        if requested_model == settings.model_primary:
            logger.info(f"[{request_id}] VRAM pressure detected, using fallback model")
            body = body.copy()
            body['model'] = settings.model_fallback
            use_fallback = True
    
    # Use fallback if primary fails
    if use_fallback and requested_model == settings.model_primary:
        body = body.copy()
        body['model'] = settings.model_fallback
        logger.info(f"[{request_id}] Using fallback model: {settings.model_fallback}")
    
    timeout = settings.model_timeout
    
    async def _make_request():
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=body)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            return resp
    
    # Retry with exponential backoff
    try:
        resp = await retry_with_backoff(
            _make_request,
            max_retries=settings.model_max_retries,
            base_delay=1.0,
            max_delay=10.0,
            exceptions=(httpx.TimeoutException, httpx.NetworkError, HTTPException)
        )
    except Exception as e:
        # Try fallback model if primary failed
        if not use_fallback and requested_model == settings.model_primary:
            logger.warning(f"[{request_id}] Primary model failed, trying fallback")
            return await _call_ollama_generate(body, request_id, use_fallback=True)
        raise
    
    # Parse and validate JSON response
    response_text = resp.text.strip()
    parsed_json, is_valid = validate_and_fix_json(response_text)
    
    if is_valid:
        return parsed_json
    else:
        logger.error(f"[{request_id}] Failed to parse JSON")
        return {
            "error": "Invalid JSON response",
            "raw_response": response_text[:500],
            "model": body.get('model')
        }


@app.post(
    "/api/generate",
    tags=["generate"],
    summary="Generate Text",
    description="Generate text completion with retry, JSON validation, and fallback.",
    response_description="Generated text response",
)
async def generate_proxy(request: Request):
    """
    Enhanced generate endpoint with same features as chat endpoint.
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    
    # Check request size
    content_length = request.headers.get('content-length')
    if content_length:
        size_mb = int(content_length) / (1024 * 1024)
        if size_mb > settings.max_request_size_mb:
            raise HTTPException(
                status_code=413,
                detail=f"Request too large: {size_mb:.2f}MB (max: {settings.max_request_size_mb}MB)"
            )
    
    try:
        body = await request.json()
        
        logger.info(json.dumps({
            "request_id": request_id,
            "endpoint": "/api/generate",
            "model": body.get('model', 'default'),
            "prompt_length": len(body.get('prompt', ''))
        }))
        
        body['stream'] = False
        
        # Check circuit breaker
        cb_state = circuit_breaker.get_state()
        if cb_state['state'] == 'open':
            raise HTTPException(status_code=503, detail="Service temporarily unavailable: Circuit breaker is OPEN")
        
        # Use request lock for GPU optimization
        async with request_lock:
            try:
                result = await _call_ollama_generate(body, request_id)
                circuit_breaker._on_success()
            except Exception as e:
                metrics.increment_counter("generate_requests_failed", labels={"model": body.get('model', 'unknown')})
                circuit_breaker._on_failure()
                raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")
        
        # Track metrics
        latency_ms = (time.time() - start_time) * 1000
        metrics.increment_counter("generate_requests_total", labels={"model": body.get('model', 'unknown')})
        metrics.record_histogram("generate_latency_ms", latency_ms, labels={"model": body.get('model', 'unknown')})
        
        logger.info(json.dumps({
            "request_id": request_id,
            "status": "success",
            "latency_ms": round(latency_ms, 2),
            "model": result.get('model', body.get('model'))
        }))
        
        return result
        
    except httpx.TimeoutException:
        metrics.increment_counter("generate_requests_timeout")
        raise HTTPException(status_code=504, detail="Request timeout")
    except HTTPException:
        raise
    except Exception as e:
        metrics.increment_counter("generate_requests_error")
        logger.error(json.dumps({
            "request_id": request_id,
            "error": str(e),
            "error_type": type(e).__name__
        }), exc_info=True)
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

@app.post(
    "/api/create",
    tags=["models"],
    summary="Create Model",
    description="Create a new Ollama model from a Modelfile.",
    response_description="Model creation status",
)
async def create_model_proxy(request: Request):
    """
    Create a new Ollama model from a Modelfile.
    
    This endpoint proxies the Ollama `/api/create` endpoint to create
    a new model with a custom Modelfile configuration.
    
    **Request Body:**
    - `name`: Model name (e.g., "ctrlchecks-workflow-builder")
    - `modelfile`: Modelfile content as a string
    - `stream`: Whether to stream the response (default: false)
    
    **Example:**
    ```json
    {
        "name": "ctrlchecks-workflow-builder",
        "modelfile": "FROM llama3.1:8b\\nSYSTEM \"You are a helpful assistant\"",
        "stream": false
    }
    ```
    """
    try:
        body = await request.json()
        print(f"Received create request for model: {body.get('name')}")
        
        # Set longer timeout for model creation (can take several minutes)
        timeout = 300.0  # 5 minutes
        
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/create", json=body)
            if resp.status_code != 200:
                error_detail = resp.text
                try:
                    error_json = resp.json()
                    error_detail = error_json.get("detail", error_json.get("error", error_detail))
                except:
                    pass
                raise HTTPException(status_code=resp.status_code, detail=error_detail)
            
            # Handle streaming and non-streaming responses
            if body.get("stream", False):
                # For streaming, return the raw response
                return resp.text
            else:
                # For non-streaming, return JSON
                try:
                    return resp.json()
                except:
                    return {"status": "success", "message": "Model creation completed"}
            
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout - model creation may take several minutes")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Create model proxy error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

# -------------------------------------------------
# LEGACY ENDPOINTS (for compatibility)
# -------------------------------------------------
@app.post("/run")
async def run(req: RunRequest):
    """Legacy endpoint - use /api/generate instead"""
    try:
        async with httpx.AsyncClient(timeout=req.timeout) as client:
            payload = {
                "model": req.model,
                "prompt": req.prompt,
                "stream": False
            }
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            
            result = resp.json()
            return {
                "success": True,
                "model": req.model,
                "response": result.get("response", ""),
                "latency": result.get("total_duration", 0) / 1_000_000_000  # Convert ns to seconds
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process")
async def process(req: ProcessRequest):
    """
    Task-based endpoint supporting both text and image processing.
    
    Supports:
    - Text tasks: summarize, translate, extract, sentiment, generate, qa, chat
    - Image tasks: image_caption, story, image_prompt (requires 'image' field)
    """
    try:
        start_time = time.time()
        
        # Image processing tasks require an image
        image_tasks = ["image_caption", "story", "image_prompt"]
        if req.task in image_tasks:
            if not req.image:
                raise HTTPException(status_code=400, detail=f"Image data required for task: {req.task}")
            
            # Vision models not supported - return error
            raise HTTPException(
                status_code=501, 
                detail="Image processing functionality has been removed. Multimodal features are no longer supported. Please use text-based models: llama3.1:8b (general) or qwen2.5-coder:7b (code)."
            )
            
            # Prepare image (remove data URL prefix if present)
            image_base64 = req.image
            if "," in image_base64:
                image_base64 = image_base64.split(",")[1]
            
            # Build prompt based on task
            if req.task == "image_caption":
                prompt = "Describe this image in a short, concise caption."
            elif req.task == "story":
                prompt = f"Describe this image in detail. Include what you see, the mood, colors, atmosphere, and any interesting details. Use {req.sentence_count or 5} sentences."
            elif req.task == "image_prompt":
                prompt = "Describe this image in detail for image generation. Include style, composition, colors, lighting, mood, and technical details. Format as a Stable Diffusion prompt with keywords."
            else:
                prompt = f"Analyze this image and provide information about: {req.task}"
            
            # Prepare messages for vision model
            messages = [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_base64]
                }
            ]
            
            # Call Ollama vision API
            async with httpx.AsyncClient(timeout=req.timeout) as client:
                payload = {
                    "model": vision_model,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 300 if req.task == "story" else 150
                    }
                }
                
                resp = await client.post(f"{OLLAMA_URL}/api/chat", json=payload)
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                
                result = resp.json()
                
                # Extract response from Ollama format
                if "message" in result and "content" in result["message"]:
                    output = result["message"]["content"]
                elif "response" in result:
                    output = result["response"]
                else:
                    output = str(result)
                
                # For image_prompt, enhance with keywords
                if req.task == "image_prompt":
                    output = f"{output}, ultra realistic, cinematic lighting, high detail, sharp focus, 4k, professional photography"
                
                processing_time = time.time() - start_time
                
                return {
                    "success": True,
                    "task": req.task,
                    "output": output.strip(),
                    "model_used": vision_model,
                    "processing_time": round(processing_time, 2)
                }
        
        # Text processing tasks
        else:
            if not req.input:
                raise HTTPException(status_code=400, detail=f"Input text required for task: {req.task}")
            
            # Build prompt from task
            prompt = f"""
Task: {req.task}

Input:
{req.input}

Please provide the requested output.
"""
            
            async with httpx.AsyncClient(timeout=req.timeout) as client:
                payload = {
                    "model": req.model,
                    "prompt": prompt,
                    "stream": False
                }
                resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
                if resp.status_code != 200:
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                
                result = resp.json()
                processing_time = time.time() - start_time
                
                return {
                    "success": True,
                    "task": req.task,
                    "output": result.get("response", ""),
                    "model_used": req.model,
                    "processing_time": round(processing_time, 2)
                }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing task {req.task}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chatbot")
async def chatbot_proxy(request: Request):
    """
    Proxy endpoint for chatbot - forwards requests to worker service.
    This allows the frontend to call /chatbot on port 8000 (FastAPI)
    and it will be forwarded to the worker service on port 3001.
    """
    try:
        body = await request.json()
        logger.info(f"Proxying chatbot request to worker service at {WORKER_URL}/chatbot")
        
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{WORKER_URL}/chatbot",
                json=body,
                headers={
                    "Content-Type": "application/json",
                }
            )
            
            if resp.status_code != 200:
                logger.error(f"Worker service error: {resp.status_code} - {resp.text}")
                raise HTTPException(status_code=resp.status_code, detail=resp.text)
            
            return resp.json()
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Request timeout")
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to worker service at {WORKER_URL}. Please ensure the worker service is running."
        )
    except Exception as e:
        logger.error(f"Chatbot proxy error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Proxy error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting CtrlChecks AI Backend on port {settings.port}")
    logger.info(f"Ollama URL: {OLLAMA_URL}")
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
