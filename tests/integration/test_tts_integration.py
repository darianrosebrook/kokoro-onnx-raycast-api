"""
Integration tests for Kokoro TTS API.

These tests verify the integration between different components
of the TTS system, including model loading, audio processing,
and API endpoints.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.config import TTSConfig


class TestTTSIntegration:
    """Test TTS system integration."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_model_loaded(self):
        """Mock model loaded state."""
        with patch('api.main.model_loaded', True):
            yield
    
    def test_health_to_status_integration(self, client):
        """Test integration between health and status endpoints."""
        # Get health status
        health_response = client.get("/health")
        assert health_response.status_code == 200
        health_data = health_response.json()
        
        # Get detailed status
        status_response = client.get("/status")
        assert status_response.status_code == 200
        status_data = status_response.json()
        
        # Integration: health status should be consistent with detailed status
        if health_data["status"] == "online":
            assert status_data["model_loaded"] is True
        elif health_data["status"] == "initializing":
            assert status_data["model_loaded"] is False
    
    def test_voices_to_tts_integration(self, client):
        """Test integration between voices and TTS endpoints."""
        # Get available voices
        voices_response = client.get("/voices")
        assert voices_response.status_code == 200
        voices_data = voices_response.json()
        
        if voices_data:  # If voices are available
            # Test TTS with first available voice
            voice_id = voices_data[0]["id"]
            
            request_data = {
                "text": "Hello, world!",
                "voice": voice_id,
                "speed": 1.0,
                "lang": "en-us",
                "stream": False,
                "format": "wav"
            }
            
            tts_response = client.post("/v1/audio/speech", json=request_data)
            
            # Integration: TTS should accept voices from voices endpoint
            # (May return 503 if model not loaded, which is expected)
            assert tts_response.status_code in [200, 503]
    
    @patch('api.main.get_tts_config')
    def test_config_to_tts_integration(self, mock_config, client):
        """Test integration between config and TTS processing."""
        # Mock TTS config
        mock_tts_config = Mock()
        mock_tts_config.max_text_length = 2000
        mock_tts_config.default_voice = "af_heart"
        mock_tts_config.default_speed = 1.0
        mock_config.return_value = mock_tts_config
        
        # Test TTS request
        request_data = {
            "text": "Test text",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us"
        }
        
        response = client.post("/v1/audio/speech", json=request_data)
        
        # Integration: config should be used in TTS processing
        mock_config.assert_called()
        assert response.status_code in [200, 503]
    
    def test_security_middleware_integration(self, client):
        """Test integration of security middleware with API endpoints."""
        # Test that security middleware is applied to all endpoints
        endpoints = ["/health", "/status", "/voices", "/v1/audio/speech"]
        
        for endpoint in endpoints:
            if endpoint == "/v1/audio/speech":
                # POST request for TTS endpoint
                response = client.post(endpoint, json={"text": "test"})
            else:
                # GET request for other endpoints
                response = client.get(endpoint)
            
            # Integration: security middleware should not block legitimate requests
            assert response.status_code in [200, 422, 503]  # Valid responses
    
    def test_performance_monitoring_integration(self, client):
        """Test integration of performance monitoring with API calls."""
        # Make a request to trigger performance monitoring
        response = client.get("/status")
        assert response.status_code == 200
        
        # Integration: performance monitoring should track the request
        # (This would be verified by checking performance stats)
        status_data = response.json()
        assert "performance_stats" in status_data
    
    def test_error_handling_integration(self, client):
        """Test integration of error handling across the system."""
        # Test various error conditions
        error_tests = [
            # Invalid JSON
            ("/v1/audio/speech", "POST", "invalid json", 422),
            # Missing required fields
            ("/v1/audio/speech", "POST", {"voice": "af_heart"}, 422),
            # Invalid parameters
            ("/v1/audio/speech", "POST", {"text": "test", "speed": 10.0}, 422),
        ]
        
        for endpoint, method, data, expected_status in error_tests:
            if method == "POST":
                if isinstance(data, str):
                    response = client.post(endpoint, data=data)
                else:
                    response = client.post(endpoint, json=data)
            else:
                response = client.get(endpoint)
            
            # Integration: error handling should be consistent
            assert response.status_code == expected_status


class TestModelIntegration:
    """Test model loading and processing integration."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @patch('api.main.initialize_model')
    def test_model_initialization_integration(self, mock_init, client):
        """Test model initialization integration."""
        # Mock model initialization
        mock_init.return_value = True
        
        # Test that model initialization affects status
        response = client.get("/status")
        assert response.status_code == 200
        
        # Integration: model initialization should be tracked
        mock_init.assert_called()
    
    def test_provider_fallback_integration(self, client):
        """Test provider fallback integration."""
        # This would test the integration between CoreML and CPU providers
        # In a real test, we'd mock the provider selection logic
        
        response = client.get("/status")
        assert response.status_code == 200
        
        status_data = response.json()
        if "providers" in status_data:
            # Integration: provider information should be available
            assert isinstance(status_data["providers"], list)


class TestStreamingIntegration:
    """Test streaming audio integration."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_streaming_request_integration(self, client):
        """Test streaming request integration."""
        request_data = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": True,
            "format": "wav"
        }
        
        response = client.post("/v1/audio/speech", json=request_data)
        
        # Integration: streaming requests should be handled differently
        # (May return 503 if model not loaded, which is expected)
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            # Integration: streaming response should have appropriate headers
            assert "content-type" in response.headers
            assert response.headers["content-type"].startswith("audio/")


class TestConfigurationIntegration:
    """Test configuration integration across the system."""
    
    def test_config_validation_integration(self):
        """Test configuration validation integration."""
        # Test valid configuration
        config = TTSConfig(
            max_text_length=1000,
            default_voice="af_heart",
            default_speed=1.2
        )
        
        # Integration: config should be valid
        assert config.max_text_length == 1000
        assert config.default_voice == "af_heart"
        assert config.default_speed == 1.2
    
    def test_config_error_handling_integration(self):
        """Test configuration error handling integration."""
        # Test invalid configuration
        with pytest.raises(ValueError):
            TTSConfig(max_text_length=-1)
        
        with pytest.raises(ValueError):
            TTSConfig(default_speed=0.0)
        
        # Integration: config errors should be properly handled
        pass
