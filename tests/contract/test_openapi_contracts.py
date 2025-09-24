"""
OpenAPI contract tests for Kokoro TTS API.

These tests validate that the API implementation conforms to the OpenAPI specification
and maintains backward compatibility.
"""
import pytest
import json
import yaml
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app

# Load OpenAPI schema
SCHEMA_PATH = Path(__file__).parent.parent.parent / "contracts" / "kokoro-tts-api.yaml"

def load_openapi_schema():
    """Load the OpenAPI schema from YAML file."""
    if not SCHEMA_PATH.exists():
        pytest.skip("OpenAPI schema not found")
    
    with open(SCHEMA_PATH, 'r') as f:
        return yaml.safe_load(f)

@pytest.fixture
def openapi_schema():
    """Load OpenAPI schema for testing."""
    return load_openapi_schema()

@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)

class TestOpenAPIContractCompliance:
    """Test OpenAPI contract compliance."""
    
    def test_health_endpoint_contract(self, client, openapi_schema):
        """Test health endpoint matches OpenAPI spec."""
        response = client.get("/health")
        
        assert response.status_code == 200
        
        # Validate response structure
        data = response.json()
        assert "status" in data
        assert data["status"] in ["online", "initializing"]
        
        # Validate against OpenAPI schema
        health_schema = openapi_schema["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
        assert data["status"] in health_schema["properties"]["status"]["enum"]
    
    def test_status_endpoint_contract(self, client, openapi_schema):
        """Test status endpoint matches OpenAPI spec."""
        response = client.get("/status")
        
        assert response.status_code == 200
        
        # Validate response structure
        data = response.json()
        required_fields = [
            "model_loaded",
            "providers", 
            "performance_stats",
            "hardware_acceleration"
        ]
        
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Validate data types
        assert isinstance(data["model_loaded"], bool)
        assert isinstance(data["providers"], list)
        assert isinstance(data["performance_stats"], dict)
        assert isinstance(data["hardware_acceleration"], dict)
    
    def test_voices_endpoint_contract(self, client, openapi_schema):
        """Test voices endpoint matches OpenAPI spec."""
        response = client.get("/voices")
        
        assert response.status_code == 200
        
        # Validate response structure
        data = response.json()
        assert isinstance(data, list)
        
        if data:  # If voices are available
            voice = data[0]
            required_voice_fields = ["id", "name", "language"]
            for field in required_voice_fields:
                assert field in voice, f"Missing required voice field: {field}"
    
    def test_tts_speech_endpoint_contract(self, client, openapi_schema):
        """Test TTS speech endpoint matches OpenAPI spec."""
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
        
        # Should return 200 (success) or 503 (model not loaded)
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            # Validate response headers
            assert "content-type" in response.headers
            assert response.headers["content-type"].startswith("audio/")
            
            # Check for required headers
            if "X-Request-ID" in response.headers:
                assert response.headers["X-Request-ID"] is not None
    
    def test_tts_request_validation_contract(self, client, openapi_schema):
        """Test TTS request validation matches OpenAPI spec."""
        # Test missing required field
        invalid_request = {
            "voice": "af_heart",
            "speed": 1.0
            # Missing 'text' field
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        assert response.status_code == 422
        
        # Validate error response structure
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], list)
    
    def test_tts_parameter_validation_contract(self, client, openapi_schema):
        """Test TTS parameter validation matches OpenAPI spec."""
        # Test speed out of range
        invalid_request = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 10.0,  # Too fast (max is 4.0)
            "lang": "en-us"
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        assert response.status_code == 422
    
    def test_tts_text_length_validation_contract(self, client, openapi_schema):
        """Test TTS text length validation matches OpenAPI spec."""
        # Test text too long (max is 4500 characters)
        long_text = "x" * 5000
        
        invalid_request = {
            "text": long_text,
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us"
        }
        
        response = client.post("/v1/audio/speech", json=invalid_request)
        assert response.status_code == 422
    
    def test_error_response_format_contract(self, client, openapi_schema):
        """Test error response format matches OpenAPI spec."""
        # Test 404 for non-existent endpoint
        response = client.get("/nonexistent")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
    
    def test_cors_headers_contract(self, client, openapi_schema):
        """Test CORS headers contract compliance."""
        # Test preflight request
        response = client.options("/v1/audio/speech")
        
        # Should return 200 for preflight
        assert response.status_code == 200
        
        # Should include CORS headers
        cors_headers = [
            "access-control-allow-origin",
            "access-control-allow-methods",
            "access-control-allow-headers"
        ]
        
        for header in cors_headers:
            if header in response.headers:
                assert response.headers[header] is not None

class TestOpenAPISchemaValidation:
    """Test OpenAPI schema validation."""
    
    def test_schema_is_valid_yaml(self, openapi_schema):
        """Test that the OpenAPI schema is valid YAML."""
        assert openapi_schema is not None
        assert "openapi" in openapi_schema
        assert openapi_schema["openapi"].startswith("3.0")
    
    def test_schema_has_required_fields(self, openapi_schema):
        """Test that the OpenAPI schema has required fields."""
        required_fields = ["openapi", "info", "paths"]
        
        for field in required_fields:
            assert field in openapi_schema, f"Missing required field: {field}"
    
    def test_schema_info_complete(self, openapi_schema):
        """Test that the schema info section is complete."""
        info = openapi_schema["info"]
        required_info_fields = ["title", "description", "version"]
        
        for field in required_info_fields:
            assert field in info, f"Missing info field: {field}"
    
    def test_schema_paths_defined(self, openapi_schema):
        """Test that all required paths are defined."""
        paths = openapi_schema["paths"]
        required_paths = [
            "/health",
            "/status", 
            "/voices",
            "/v1/audio/speech"
        ]
        
        for path in required_paths:
            assert path in paths, f"Missing required path: {path}"
    
    def test_schema_components_defined(self, openapi_schema):
        """Test that required components are defined."""
        if "components" in openapi_schema:
            components = openapi_schema["components"]
            
            if "schemas" in components:
                schemas = components["schemas"]
                required_schemas = ["ErrorResponse", "ValidationError"]
                
                for schema in required_schemas:
                    assert schema in schemas, f"Missing required schema: {schema}"

class TestBackwardCompatibility:
    """Test backward compatibility of API changes."""
    
    def test_v1_endpoints_accessible(self, client):
        """Test that v1 endpoints are accessible."""
        response = client.get("/v1/audio/speech")
        
        # Should return 405 Method Not Allowed, not 404 Not Found
        assert response.status_code == 405
    
    def test_health_endpoint_stable(self, client):
        """Test that health endpoint response format is stable."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        
        # Ensure response format hasn't changed
        assert "status" in data
        assert isinstance(data["status"], str)
    
    def test_status_endpoint_stable(self, client):
        """Test that status endpoint response format is stable."""
        response = client.get("/status")
        
        assert response.status_code == 200
        data = response.json()
        
        # Ensure core fields are present
        core_fields = ["model_loaded", "providers"]
        for field in core_fields:
            assert field in data, f"Core field {field} missing from status response"
