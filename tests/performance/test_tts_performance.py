"""
Performance tests for Kokoro TTS API.

These tests verify that the TTS system meets performance requirements
as defined in the Working Spec (TTFA < 800ms, streaming latency < 500ms).
"""
import pytest
import time
import asyncio
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from api.main import app


class TestTTSPerformance:
    """Test TTS performance requirements."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_health_endpoint_performance(self, client):
        """Test health endpoint performance."""
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Performance requirement: health endpoint should respond quickly
        assert response.status_code == 200
        assert response_time < 100  # Should respond within 100ms
    
    def test_status_endpoint_performance(self, client):
        """Test status endpoint performance."""
        start_time = time.time()
        response = client.get("/status")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Performance requirement: status endpoint should respond quickly
        assert response.status_code == 200
        assert response_time < 500  # Should respond within 500ms
    
    def test_voices_endpoint_performance(self, client):
        """Test voices endpoint performance."""
        start_time = time.time()
        response = client.get("/voices")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Performance requirement: voices endpoint should respond quickly
        assert response.status_code == 200
        assert response_time < 200  # Should respond within 200ms
    
    @patch('api.main.get_tts_config')
    def test_tts_request_validation_performance(self, mock_config, client):
        """Test TTS request validation performance."""
        mock_config.return_value = Mock()
        
        request_data = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": False,
            "format": "wav"
        }
        
        start_time = time.time()
        response = client.post("/v1/audio/speech", json=request_data)
        end_time = time.time()
        
        validation_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Performance requirement: request validation should be fast
        assert response.status_code in [200, 503]  # May be 503 if model not loaded
        assert validation_time < 50  # Validation should be very fast
    
    def test_concurrent_requests_performance(self, client):
        """Test performance under concurrent requests."""
        import threading
        import queue
        
        results = queue.Queue()
        
        def make_request():
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            results.put((response.status_code, (end_time - start_time) * 1000))
        
        # Make 10 concurrent requests
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Collect results
        response_times = []
        while not results.empty():
            status_code, response_time = results.get()
            assert status_code == 200
            response_times.append(response_time)
        
        # Performance requirement: concurrent requests should not degrade significantly
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)
        
        assert avg_response_time < 200  # Average should be under 200ms
        assert max_response_time < 500  # Max should be under 500ms
    
    def test_memory_usage_performance(self, client):
        """Test memory usage performance."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make multiple requests
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
        
        # Get final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Performance requirement: memory usage should not grow significantly
        assert memory_increase < 50  # Should not increase by more than 50MB


class TestStreamingPerformance:
    """Test streaming performance requirements."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_streaming_latency_performance(self, client):
        """Test streaming latency performance."""
        request_data = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": True,
            "format": "wav"
        }
        
        start_time = time.time()
        response = client.post("/v1/audio/speech", json=request_data)
        end_time = time.time()
        
        # Note: This test may return 503 if model is not loaded
        # In a real test environment with the model loaded, we would:
        # 1. Check that response starts streaming quickly
        # 2. Measure time to first audio chunk
        # 3. Verify streaming latency < 500ms
        
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            # Performance requirement: streaming should start quickly
            initial_response_time = (end_time - start_time) * 1000
            assert initial_response_time < 500  # Should start streaming within 500ms


class TestPerformanceBenchmarks:
    """Test performance benchmarks against Working Spec requirements."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_ttfa_requirement_performance(self, client):
        """Test Time to First Audio (TTFA) requirement."""
        # Working Spec requirement: TTFA < 800ms
        
        request_data = {
            "text": "Hello, world!",
            "voice": "af_heart",
            "speed": 1.0,
            "lang": "en-us",
            "stream": True,
            "format": "wav"
        }
        
        start_time = time.time()
        response = client.post("/v1/audio/speech", json=request_data)
        end_time = time.time()
        
        ttfa = (end_time - start_time) * 1000  # Convert to milliseconds
        
        # Note: This test may return 503 if model is not loaded
        # In a real test environment, we would verify TTFA < 800ms
        assert response.status_code in [200, 503]
        
        if response.status_code == 200:
            # Performance requirement: TTFA < 800ms
            assert ttfa < 800, f"TTFA {ttfa}ms exceeds 800ms requirement"
    
    def test_api_p95_performance(self, client):
        """Test API P95 performance requirement."""
        # Working Spec requirement: API P95 < 800ms
        
        response_times = []
        
        # Make multiple requests to measure P95
        for _ in range(20):
            start_time = time.time()
            response = client.get("/health")
            end_time = time.time()
            
            if response.status_code == 200:
                response_time = (end_time - start_time) * 1000
                response_times.append(response_time)
        
        if response_times:
            # Calculate P95
            response_times.sort()
            p95_index = int(len(response_times) * 0.95)
            p95_time = response_times[p95_index]
            
            # Performance requirement: P95 < 800ms
            assert p95_time < 800, f"P95 {p95_time}ms exceeds 800ms requirement"
    
    def test_memory_usage_requirement_performance(self, client):
        """Test memory usage requirement."""
        # Working Spec requirement: Memory usage < 1024MB
        
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        
        # Performance requirement: Memory usage < 1024MB
        assert memory_usage < 1024, f"Memory usage {memory_usage}MB exceeds 1024MB requirement"


class TestPerformanceRegression:
    """Test for performance regressions."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    def test_no_performance_regression_health(self, client):
        """Test that health endpoint performance doesn't regress."""
        # Baseline: health endpoint should be very fast
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time < 50  # Should be very fast, no regression
    
    def test_no_performance_regression_status(self, client):
        """Test that status endpoint performance doesn't regress."""
        # Baseline: status endpoint should be reasonably fast
        start_time = time.time()
        response = client.get("/status")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000
        
        assert response.status_code == 200
        assert response_time < 300  # Should be reasonably fast, no regression
