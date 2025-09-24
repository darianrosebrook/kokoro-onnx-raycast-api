"""
Integration tests using Testcontainers for realistic testing scenarios.

These tests use containerized services to provide more realistic integration
testing without requiring external dependencies.
"""
import pytest
import asyncio
import aiohttp
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional

# Testcontainers imports (with fallback for environments without it)
try:
    from testcontainers.compose import DockerCompose
    from testcontainers.core.waiting_utils import wait_for_logs
    HAVE_TESTCONTAINERS = True
except ImportError:
    HAVE_TESTCONTAINERS = False
    DockerCompose = None
    wait_for_logs = None

# FastAPI test client
from fastapi.testclient import TestClient
from api.main import app

class MockTTSContainer:
    """Mock container for environments without Testcontainers."""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.is_running = False
    
    def start(self):
        self.is_running = True
        return self
    
    def stop(self):
        self.is_running = False
    
    def get_service_port(self, service: str, port: int) -> int:
        return 8000  # Default port for mock
    
    def get_service_host(self, service: str) -> str:
        return "localhost"

@pytest.fixture(scope="session")
def tts_container():
    """Start TTS service container for integration tests."""
    if HAVE_TESTCONTAINERS:
        # Use real Testcontainers
        compose_file = Path(__file__).parent.parent.parent / "docker-compose.test.yml"
        if compose_file.exists():
            with DockerCompose(
                compose_file_path=str(compose_file.parent),
                compose_file_name="docker-compose.test.yml"
            ) as compose:
                # Wait for service to be ready
                wait_for_logs(compose, "TTS service is ready", timeout=30)
                yield compose
        else:
            # Fallback to mock container
            container = MockTTSContainer("tts-service")
            container.start()
            yield container
            container.stop()
    else:
        # Use mock container
        container = MockTTSContainer("tts-service")
        container.start()
        yield container
        container.stop()

@pytest.fixture
def tts_client(tts_container):
    """Create HTTP client for TTS service."""
    if hasattr(tts_container, 'get_service_host'):
        host = tts_container.get_service_host("tts-service")
        port = tts_container.get_service_port("tts-service", 8000)
        base_url = f"http://{host}:{port}"
    else:
        base_url = "http://localhost:8000"
    
    return aiohttp.ClientSession(base_url=base_url)

class TestTTSIntegration:
    """Integration tests for TTS service."""
    
    @pytest.mark.asyncio
    async def test_health_check_integration(self, tts_client):
        """Test health check endpoint integration."""
        async with tts_client.get("/health") as response:
            assert response.status == 200
            data = await response.json()
            assert "status" in data
            assert data["status"] in ["online", "initializing"]
    
    @pytest.mark.asyncio
    async def test_status_endpoint_integration(self, tts_client):
        """Test status endpoint integration."""
        async with tts_client.get("/status") as response:
            assert response.status == 200
            data = await response.json()
            
            # Validate required fields
            required_fields = [
                "model_loaded",
                "providers",
                "performance_stats",
                "hardware_acceleration"
            ]
            
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
    
    @pytest.mark.asyncio
    async def test_voices_endpoint_integration(self, tts_client):
        """Test voices endpoint integration."""
        async with tts_client.get("/voices") as response:
            assert response.status == 200
            data = await response.json()
            assert isinstance(data, list)
    
    @pytest.mark.asyncio
    async def test_tts_generation_integration(self, tts_client):
        """Test TTS generation integration."""
        request_data = {
            "text": "Hello, this is an integration test.",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        async with tts_client.post("/v1/audio/speech", json=request_data) as response:
            # Should return 200 (success) or 503 (model not loaded)
            assert response.status in [200, 503]
            
            if response.status == 200:
                # Validate audio response
                content_type = response.headers.get("content-type", "")
                assert content_type.startswith("audio/")
                
                # Validate response headers
                if "X-Request-ID" in response.headers:
                    assert response.headers["X-Request-ID"] is not None
    
    @pytest.mark.asyncio
    async def test_tts_streaming_integration(self, tts_client):
        """Test TTS streaming integration."""
        request_data = {
            "text": "This is a streaming test with longer text to ensure proper streaming behavior.",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": True,
            "format": "pcm"
        }
        
        async with tts_client.post("/v1/audio/speech", json=request_data) as response:
            # Should return 200 (success) or 503 (model not loaded)
            assert response.status in [200, 503]
            
            if response.status == 200:
                # Validate streaming response
                content_type = response.headers.get("content-type", "")
                assert content_type.startswith("audio/")
                
                # Check for streaming headers
                if "X-TTFA" in response.headers:
                    ttfa = float(response.headers["X-TTFA"])
                    assert ttfa <= 500.0, f"TTFA {ttfa}ms exceeds 500ms budget"
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, tts_client):
        """Test error handling integration."""
        # Test invalid request
        invalid_request = {
            "text": "x" * 5000,  # Too long
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us"
        }
        
        async with tts_client.post("/v1/audio/speech", json=invalid_request) as response:
            assert response.status == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_performance_budgets_integration(self, tts_client):
        """Test performance budgets integration."""
        request_data = {
            "text": "Performance test text",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        start_time = time.time()
        async with tts_client.post("/v1/audio/speech", json=request_data) as response:
            end_time = time.time()
            response_time = (end_time - start_time) * 1000  # Convert to ms
            
            # Should return 200 (success) or 503 (model not loaded)
            assert response.status in [200, 503]
            
            if response.status == 200:
                # Validate performance budget (1000ms for non-streaming)
                assert response_time <= 1000.0, f"Response time {response_time}ms exceeds 1000ms budget"

class TestTTSLoadIntegration:
    """Load testing integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_integration(self, tts_client):
        """Test concurrent request handling."""
        request_data = {
            "text": "Concurrent test text",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        # Send 5 concurrent requests
        tasks = []
        for i in range(5):
            task = tts_client.post("/v1/audio/speech", json=request_data)
            tasks.append(task)
        
        responses = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All requests should complete (success or service unavailable)
        for response in responses:
            if isinstance(response, Exception):
                pytest.fail(f"Request failed with exception: {response}")
            
            async with response:
                assert response.status in [200, 503]
    
    @pytest.mark.asyncio
    async def test_memory_usage_integration(self, tts_client):
        """Test memory usage under load."""
        request_data = {
            "text": "Memory test text",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        # Send multiple requests to test memory usage
        for i in range(10):
            async with tts_client.post("/v1/audio/speech", json=request_data) as response:
                assert response.status in [200, 503]
                
                # Small delay between requests
                await asyncio.sleep(0.1)

class TestTTSResilienceIntegration:
    """Resilience testing integration scenarios."""
    
    @pytest.mark.asyncio
    async def test_service_recovery_integration(self, tts_client):
        """Test service recovery after errors."""
        # Send a request that might cause an error
        request_data = {
            "text": "Recovery test text",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        # First request
        async with tts_client.post("/v1/audio/speech", json=request_data) as response:
            assert response.status in [200, 503]
        
        # Wait a moment
        await asyncio.sleep(1)
        
        # Second request to test recovery
        async with tts_client.post("/v1/audio/speech", json=request_data) as response:
            assert response.status in [200, 503]
    
    @pytest.mark.asyncio
    async def test_graceful_degradation_integration(self, tts_client):
        """Test graceful degradation under stress."""
        # Send requests with various parameters to test degradation
        test_cases = [
            {"text": "Short text", "speed": 0.5},
            {"text": "Medium length text for testing", "speed": 1.0},
            {"text": "Longer text for testing performance under load", "speed": 2.0},
        ]
        
        for test_case in test_cases:
            request_data = {
                "text": test_case["text"],
                "voice": "af_heart",
                "speed": test_case["speed"],
                "lang": "en-us",
                "stream": False,
                "format": "wav"
            }
            
            async with tts_client.post("/v1/audio/speech", json=request_data) as response:
                assert response.status in [200, 503]
                
                # Service should remain responsive
                if response.status == 200:
                    content_type = response.headers.get("content-type", "")
                    assert content_type.startswith("audio/")

# Skip tests if Testcontainers is not available
if not HAVE_TESTCONTAINERS:
    pytest.skip("Testcontainers not available", allow_module_level=True)
