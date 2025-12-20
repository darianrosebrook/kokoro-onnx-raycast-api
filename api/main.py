"""
Kokoro TTS API v2 - Main Application

Minimal FastAPI server for Kokoro TTS.
~200 lines replacing 26,000+ lines of the original implementation.
"""

import logging
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from .config import HOST, PORT, DEFAULT_VOICE, DEFAULT_SPEED, MIN_SPEED, MAX_SPEED
from .tts import initialize_model, get_model, get_voices, generate_audio, is_model_ready
from .streaming import stream_audio_chunks, get_audio_duration

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Request/Response models
class TTSRequest(BaseModel):
    """TTS request - accepts both 'input' (OpenAI) and 'text' (legacy) fields."""
    model: str = Field(default="kokoro-v1.0", description="Model ID (ignored, only one model)")
    input: Optional[str] = Field(default=None, description="Text to synthesize (OpenAI format)")
    text: Optional[str] = Field(default=None, description="Text to synthesize (legacy format)")
    voice: str = Field(default=DEFAULT_VOICE, description="Voice ID")
    speed: float = Field(default=DEFAULT_SPEED, ge=MIN_SPEED, le=MAX_SPEED, description="Speed multiplier")
    response_format: str = Field(default="pcm", description="Audio format (pcm or wav)")
    stream: bool = Field(default=True, description="Whether to stream the response")
    
    @model_validator(mode='after')
    def validate_text_input(self):
        """Ensure either 'input' or 'text' is provided, normalize to 'input'."""
        if self.input is None and self.text is None:
            raise ValueError("Either 'input' or 'text' must be provided")
        
        # Use 'text' as fallback if 'input' is not provided
        if self.input is None:
            self.input = self.text
        
        # Validate length
        if len(self.input) < 1:
            raise ValueError("Text cannot be empty")
        if len(self.input) > 10000:
            raise ValueError("Text too long (max 10000 characters)")
        
        return self


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    model_loaded: bool
    uptime_seconds: float


class VoicesResponse(BaseModel):
    """Available voices response."""
    voices: list[str]


class StatusResponse(BaseModel):
    """Server status response."""
    status: str
    model_loaded: bool
    model_path: str
    voices_count: int
    uptime_seconds: float


# Server state
_start_time: float = 0
_init_time: float = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - initialize model on startup."""
    global _start_time, _init_time
    
    _start_time = time.time()
    
    logger.info("Starting Kokoro TTS API v2...")
    
    try:
        _init_time = initialize_model()
        logger.info(f"Server ready on {HOST}:{PORT}")
    except Exception as e:
        logger.error(f"Failed to initialize model: {e}")
        raise
    
    yield
    
    logger.info("Shutting down...")


# Create FastAPI app
app = FastAPI(
    title="Kokoro TTS API",
    version="2.0.0",
    description="Minimal, high-performance TTS API using Kokoro ONNX",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok" if is_model_ready() else "initializing",
        model_loaded=is_model_ready(),
        uptime_seconds=time.time() - _start_time,
    )


@app.get("/voices", response_model=VoicesResponse)
async def list_voices():
    """List available voices."""
    if not is_model_ready():
        raise HTTPException(status_code=503, detail="Model not ready")
    
    return VoicesResponse(voices=get_voices())


@app.get("/status", response_model=StatusResponse)
async def get_status():
    """Get server status."""
    from .config import MODEL_PATH
    
    return StatusResponse(
        status="ok" if is_model_ready() else "initializing",
        model_loaded=is_model_ready(),
        model_path=str(MODEL_PATH),
        voices_count=len(get_voices()) if is_model_ready() else 0,
        uptime_seconds=time.time() - _start_time,
    )


@app.post("/v1/audio/speech")
async def create_speech(request: TTSRequest):
    """
    Generate speech from text (OpenAI-compatible endpoint).
    
    Accepts both 'input' (OpenAI format) and 'text' (legacy format).
    Streams audio chunks as they're generated for low latency.
    """
    if not is_model_ready():
        raise HTTPException(status_code=503, detail="Model not ready")
    
    if not request.input.strip():
        raise HTTPException(status_code=400, detail="Input text cannot be empty")
    
    logger.info(f"TTS request: voice={request.voice}, speed={request.speed}, "
                f"text='{request.input[:50]}...' ({len(request.input)} chars)")
    
    try:
        # Generate audio
        start_time = time.perf_counter()
        audio, sample_rate, gen_time = generate_audio(
            text=request.input,
            voice=request.voice,
            speed=request.speed,
        )
        
        # Calculate metrics
        audio_duration = get_audio_duration(audio)
        rtf = gen_time / audio_duration if audio_duration > 0 else 0
        
        logger.info(f"Generated {audio_duration:.2f}s audio in {gen_time:.2f}s (RTF: {rtf:.3f})")
        
        # Determine content type and whether to include WAV header
        include_wav = request.response_format == "wav"
        content_type = "audio/wav" if include_wav else "audio/pcm"
        
        # Stream the audio
        return StreamingResponse(
            stream_audio_chunks(audio, include_wav_header=include_wav),
            media_type=content_type,
            headers={
                "X-Audio-Duration": str(audio_duration),
                "X-Generation-Time": str(gen_time),
                "X-RTF": str(rtf),
            },
        )
        
    except Exception as e:
        logger.error(f"TTS generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Compatibility endpoint (same as /v1/audio/speech)
@app.post("/audio/speech")
async def create_speech_compat(request: TTSRequest):
    """Compatibility endpoint - redirects to /v1/audio/speech."""
    return await create_speech(request)


def main():
    """Run the server."""
    import uvicorn
    
    logger.info(f"Starting server on {HOST}:{PORT}")
    uvicorn.run(
        "api.main:app",
        host=HOST,
        port=PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
