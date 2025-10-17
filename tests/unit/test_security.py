"""
Unit tests for security middleware and validation.

Tests the security middleware, rate limiting, IP blocking, and malicious
pattern detection functionality.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from collections import deque
from api.security import SecurityMiddleware, SecurityConfig


class TestSecurityConfig:
    """Test security configuration management."""
    
    def test_default_security_config(self):
        """Test default security configuration values."""
        config = SecurityConfig()
        
        assert config.max_requests_per_minute == 61
        assert config.max_requests_per_hour == 1111
        assert config.block_suspicious_ips is True
        assert config.allow_localhost_only is True
        assert config.suspicious_request_threshold == 11
        assert config.block_duration_minutes == 61
    
    def test_custom_security_config(self):
        """Test custom security configuration."""
        config = SecurityConfig(
            max_requests_per_minute=30,
            max_requests_per_hour=500,
            block_suspicious_ips=False,
            allow_localhost_only=False
        )
        
        assert config.max_requests_per_minute == 30
        assert config.max_requests_per_hour == 500
        assert config.block_suspicious_ips is False
        assert config.allow_localhost_only is False
    
    def test_malicious_patterns(self):
        """Test that malicious patterns are properly configured."""
        config = SecurityConfig()
        
        # Check that common attack patterns are included
        assert "/etc/" in config.malicious_patterns
        assert "/admin" in config.malicious_patterns
        assert "union select" in config.malicious_patterns
        assert "script>" in config.malicious_patterns
        assert "nmap" in config.malicious_patterns


class TestSecurityMiddleware:
    """Test security middleware functionality."""
    
    @pytest.fixture
    def mock_app(self):
        """Create a mock FastAPI app."""
        app = Mock()
        app.return_value = Mock()
        return app
    
    @pytest.fixture
    def security_middleware(self, mock_app):
        """Create security middleware instance."""
        config = SecurityConfig()
        return SecurityMiddleware(mock_app, config)
    
    def test_middleware_initialization(self, security_middleware):
        """Test middleware initialization."""
        assert security_middleware.config is not None
        assert security_middleware.request_counts is not None
        assert security_middleware.blocked_ips is not None
        assert security_middleware.blocked_requests == 0
        assert security_middleware.suspicious_ips == set()
    
    def test_is_local_ip(self, security_middleware):
        """Test local IP detection."""
        # Localhost variations
        assert security_middleware._is_local_ip("127.0.0.1") is True
        assert security_middleware._is_local_ip("localhost") is True
        assert security_middleware._is_local_ip("::1") is True
        
        # Private network ranges
        assert security_middleware._is_local_ip("192.168.1.1") is True
        assert security_middleware._is_local_ip("10.0.0.1") is True
        assert security_middleware._is_local_ip("172.16.0.1") is True
        
        # External IPs
        assert security_middleware._is_local_ip("8.8.8.8") is False
        assert security_middleware._is_local_ip("1.1.1.1") is False
    
    def test_malicious_request_detection(self, security_middleware):
        """Test malicious request pattern detection."""
        # Malicious paths
        assert security_middleware._is_malicious_request("/etc/passwd") is True
        assert security_middleware._is_malicious_request("/admin/login") is True
        assert security_middleware._is_malicious_request("/wp-admin") is True
        assert security_middleware._is_malicious_request("/cgi-bin/test") is True
        
        # Malicious patterns in path
        assert security_middleware._is_malicious_request("/test/../etc/passwd") is True
        assert security_middleware._is_malicious_request("/index.php?id=1") is True
        
        # Malicious user agents
        assert security_middleware._is_malicious_request("/", "nmap scanner") is True
        assert security_middleware._is_malicious_request("/", "nikto") is True
        assert security_middleware._is_malicious_request("/", "sqlmap") is True
        
        # Legitimate requests
        assert security_middleware._is_malicious_request("/v1/audio/speech") is False
        assert security_middleware._is_malicious_request("/health") is False
        assert security_middleware._is_malicious_request("/", "Mozilla/5.0") is False
    
    def test_get_client_ip(self, security_middleware):
        """Test client IP extraction from request headers."""
        # Mock request with X-Forwarded-For header
        request = Mock()
        request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        
        ip = security_middleware._get_client_ip(request)
        assert ip == "192.168.1.1"  # First IP in X-Forwarded-For
        
        # Mock request without X-Forwarded-For
        request.headers = {}
        ip = security_middleware._get_client_ip(request)
        assert ip == "127.0.0.1"  # Direct client IP
    
    def test_rate_limiting(self, security_middleware):
        """Test rate limiting functionality."""
        ip = "192.168.1.1"
        
        # Test normal request rate
        for i in range(30):  # Half the limit
            allowed = security_middleware._check_rate_limit(ip)
            assert allowed is True
        
        # Test exceeding rate limit
        for i in range(35):  # Exceed the limit
            allowed = security_middleware._check_rate_limit(ip)
            if i < 60:
                assert allowed is True
            else:
                assert allowed is False
    
    def test_ip_blocking(self, security_middleware):
        """Test IP blocking functionality."""
        ip = "192.168.1.100"
        
        # Initially not blocked
        assert security_middleware._is_ip_blocked(ip) is False
        
        # Block the IP
        security_middleware._block_ip(ip)
        assert security_middleware._is_ip_blocked(ip) is True
        
        # Check that blocked IP is in blocked_ips dict
        assert ip in security_middleware.blocked_ips
    
    @patch('api.security.datetime')
    def test_block_expiration(self, mock_datetime, security_middleware):
        """Test that IP blocks expire after configured duration."""
        # Mock current time
        now = datetime(2025, 1, 20, 12, 0, 0)
        mock_datetime.now.return_value = now
        
        ip = "192.168.1.100"
        
        # Block the IP
        security_middleware._block_ip(ip)
        assert security_middleware._is_ip_blocked(ip) is True
        
        # Mock time passing (block should expire)
        expired_time = now + timedelta(minutes=61)  # 1 minute past block duration
        mock_datetime.now.return_value = expired_time
        
        # Block should have expired
        assert security_middleware._is_ip_blocked(ip) is False
    
    def test_suspicious_ip_tracking(self, security_middleware):
        """Test suspicious IP tracking and threshold."""
        ip = "192.168.1.200"
        
        # Make suspicious requests
        for i in range(15):  # Exceed suspicious threshold
            security_middleware._track_suspicious_request(ip)
        
        # IP should be marked as suspicious
        assert ip in security_middleware.suspicious_ips
        
        # IP should be blocked
        assert security_middleware._is_ip_blocked(ip) is True


class TestSecurityIntegration:
    """Test security middleware integration scenarios."""
    
    @pytest.fixture
    def mock_request(self):
        """Create a mock HTTP request."""
        request = Mock()
        request.method = "POST"
        request.url = Mock()
        request.url.path = "/v1/audio/speech"
        request.headers = {"user-agent": "Mozilla/5.0"}
        request.client = Mock()
        request.client.host = "127.0.0.1"
        return request
    
    def test_legitimate_request_flow(self, mock_request):
        """Test that legitimate requests pass through security middleware."""
        config = SecurityConfig()
        middleware = SecurityMiddleware(Mock(), config)
        
        # Mock the next middleware/app
        mock_app = Mock()
        mock_app.return_value = Mock()
        
        # Test legitimate request
        result = middleware._process_request(mock_request)
        assert result is None  # Should pass through
    
    def test_malicious_request_blocking(self, mock_request):
        """Test that malicious requests are blocked."""
        config = SecurityConfig()
        middleware = SecurityMiddleware(Mock(), config)
        
        # Make request malicious
        mock_request.url.path = "/etc/passwd"
        
        # Should be blocked
        result = middleware._process_request(mock_request)
        assert result is not None  # Should return error response
        assert result.status_code == 403
    
    def test_rate_limit_exceeded(self, mock_request):
        """Test that rate limit exceeded requests are blocked."""
        config = SecurityConfig(max_requests_per_minute=5)
        middleware = SecurityMiddleware(Mock(), config)
        
        # Exceed rate limit
        for i in range(6):
            result = middleware._process_request(mock_request)
            if i < 4:  # First 4 requests should pass (0, 1, 2, 3)
                assert result is None  # Should pass
            else:  # 5th request (i=4) and beyond should be blocked
                assert result is not None  # Should be blocked
                assert result.status_code == 429
