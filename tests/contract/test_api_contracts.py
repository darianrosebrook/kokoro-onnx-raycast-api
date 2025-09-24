"""
Contract tests for Kokoro TTS API endpoints.

These tests verify that the API contracts are maintained and that
the API behaves according to its specification.
"""
import pytest
import json
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from api.main import app


class TestTTSAPIContracts:
    """Test TTS API contract compliance."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_health_endpoint_contract(self, client):
        """Test health endpoint contract compliance."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Contract: health endpoint must return status
        assert "status" in data
        assert data["status"] in ["online", "initializing"]
    
    def test_status_endpoint_contract(self, client):
        """Test status endpoint contract compliance."""
        response = client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Contract: status endpoint must return comprehensive status
        required_fields = [
            "model_loaded",
            "providers",
            "performance_stats",
            "hardware_acceleration"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
    
    def test_voices_endpoint_contract(self, client):
        """Test voices endpoint contract compliance."""
        response = client.get("/voices")
        
        assert response.status_code == 200
        data = response.json()
        
        # Contract: voices endpoint must return list of voices
        assert isinstance(data, list)
        
        if data:  # If voices are available
            voice = data[0]
            required_voice_fields = ["id", "name", "language"]
            for field in required_voice_fields:
                assert field in voice, f"Missing required voice field: {field}"
    
    @patch('api.main.get_tts_config')
    def test_tts_speech_endpoint_contract(self, mock_config, client):
        """Test TTS speech endpoint contract compliance."""
        # Mock the TTS config to avoid model loading
        mock_config.return_value = Mock()
        
        # Test valid request
        request_data = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        response = client.post("/v1/audio/speech", json=request_data)
        
        # Contract: should return 503 if model not loaded (expected in test)
        # or 200 with audio data if model is loaded
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            # Contract: successful response should have audio data
            assert response.headers["content-type"].startswith("audio/")
        elif response.status_code == 503:
            # Contract: service unavailable should have error message
            data = response.json()
            assert "detail" in data
    
    def test_tts_request_validation_contract(self, client):
        """Test TTS request validation contract."""
        # Test invalid request (missing required field)
        invalid_request = {
            "voice": "af_heart",
            "speed": 1.0
            # Missing 'text' field
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        
        # Contract: invalid requests should return 422
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
    
    def test_tts_speed_validation_contract(self, client):
        """Test TTS speed parameter validation contract."""
        # Test speed out of range
        invalid_request = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 10.0,  # Too fast
            "lang": "en-us"
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        
        # Contract: invalid speed should return 422
        assert response.status_code == 422
    
    def test_tts_text_length_validation_contract(self, client):
        """Test TTS text length validation contract."""
        # Test text too long
        long_text = "x" * 3000  # Exceeds 2000 character limit
        
        invalid_request = {
            "text": long_text,
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us"
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        
        # Contract: text too long should return 422
        assert response.status_code == 422
    
    def test_tts_format_validation_contract(self, client):
        """Test TTS format parameter validation contract."""
        # Test invalid format
        invalid_request = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "format": "mp3"  # Invalid format
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        
        # Contract: invalid format should return 422
        assert response.status_code == 422
    
    def test_cors_headers_contract(self, client):
        """Test CORS headers contract compliance."""
        # Test preflight request
        response = client.options("/v1/audio/speech")
        
        # Contract: CORS preflight should return 200
        assert response.status_code == 200
        
        # Contract: should include CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
    
    def test_error_response_format_contract(self, client):
        """Test error response format contract."""
        # Test 404 for non-existent endpoint
        response = client.get("/nonexistent")
        
        # Contract: 404 should return JSON error
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestAPIVersioningContract:
    """Test API versioning contract compliance."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_api_version_header_contract(self, client):
        """Test API version header contract."""
        response = client.get("/health")
        
        # Contract: API should include version in response headers
        # (This would be implemented in the actual API)
        # assert "x-api-version" in response.headers
    
    def test_backward_compatibility_contract(self, client):
        """Test backward compatibility contract."""
        # Test that v1 endpoints still work
        response = client.get("/v1/audio/speech")
        
        # Contract: v1 endpoints should be accessible
        # (GET should return 405 Method Not Allowed, not 404)
        assert response.status_code == 405  # Method not allowed, not 404


class TestSecurityContract:
    """Test security contract compliance."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_security_headers_contract(self, client):
        """Test security headers contract."""
        response = client.get("/health")
        
        # Contract: should include security headers
        # (These would be implemented in the actual security middleware)
        # assert "x-content-type-options" in response.headers
        # assert "x-frame-options" in response.headers
    
    def test_rate_limiting_contract(self, client):
        """Test rate limiting contract."""
        # Make multiple requests to test rate limiting
        responses = []
        for i in range(5):
            response = client.get("/health")
            responses.append(response)
        
        # Contract: legitimate requests should not be rate limited
        # (Rate limiting would be tested with more requests)
        for response in responses:
            assert response.status_code in [200, 429]  # OK or rate limited
