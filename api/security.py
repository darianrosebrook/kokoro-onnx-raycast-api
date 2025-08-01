"""
Security middleware for protecting the TTS API against malicious requests.

This module provides comprehensive security features including:
- IP-based rate limiting and blacklisting
- Request pattern filtering for common attacks
- Localhost-only access control
- Automatic blocking of suspicious IPs
- Raycast-friendly local access

@author @darianrosebrook
@version 1.0.0
@since 2025-07-17
"""

import asyncio
import logging
import time
from collections import defaultdict, deque
from typing import Dict, Set, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import re

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

@dataclass
class SecurityConfig:
    """Configuration for security middleware."""
    
    # Rate limiting settings
    max_requests_per_minute: int = 60
    max_requests_per_hour: int = 1000
    
    # IP blocking settings
    block_suspicious_ips: bool = True
    suspicious_request_threshold: int = 10  # Requests before considering IP suspicious
    block_duration_minutes: int = 60  # How long to block suspicious IPs
    
    # Local access settings
    allow_localhost_only: bool = True
    allowed_local_ips: Set[str] = field(default_factory=lambda: {
        "127.0.0.1", "localhost", "::1",  # IPv4 and IPv6 localhost
        "192.168.0.0/16",  # Common local network range
        "10.0.0.0/8",      # Private network range (but we'll block 10.4.22.177 specifically)
        "172.16.0.0/12"    # Private network range
    })
    
    # Attack pattern detection
    malicious_patterns: Set[str] = field(default_factory=lambda: {
        # Common pentesting paths
        "/etc/", "/proc/", "/sys/", "/var/", "/tmp/",
        "/admin", "/administrator", "/wp-admin", "/phpmyadmin",
        "/cgi-bin/", "/webcgi/", "/EemAdminService/", "/AsyncResponseService",
        "/rest/v1/", "/mgmt/", "/portal/", "/lexicom", "/harmony", "/vltrader",
        "/index.php", "/index.html", "/index.jsp",
        # Common attack patterns
        "union select", "drop table", "exec(", "eval(", "system(",
        "script>", "javascript:", "vbscript:", "onload=", "onerror=",
        # File inclusion attempts
        "..", "~", "~root", "~admin",
        # Common pentesting tools
        "nmap", "nikto", "sqlmap", "burp", "zap"
    })
    
    # Specific IP blacklist (add known malicious IPs here)
    blacklisted_ips: Set[str] = field(default_factory=lambda: {
        "10.4.22.177"  # The IP from your logs
    })

class SecurityMiddleware(BaseHTTPMiddleware):
    """
    Comprehensive security middleware for protecting the TTS API.
    
    Features:
    - Rate limiting per IP
    - Automatic blocking of suspicious IPs
    - Request pattern filtering
    - Localhost-only access control
    - Raycast-friendly local access
    """
    
    def __init__(self, app, config: Optional[SecurityConfig] = None):
        super().__init__(app)
        self.config = config or SecurityConfig()
        
        # Rate limiting storage
        self.request_counts: Dict[str, deque] = defaultdict(lambda: deque())
        self.blocked_ips: Dict[str, datetime] = {}
        
        # Statistics
        self.blocked_requests = 0
        self.suspicious_ips = set()
        
        logger.info("Security middleware initialized with localhost-only access")
    
    def _is_local_ip(self, ip: str) -> bool:
        """Check if IP is in allowed local ranges."""
        if ip in self.config.allowed_local_ips:
            return True
            
        # Check for localhost variations
        if ip in ("127.0.0.1", "localhost", "::1"):
            return True
            
        # Check for private network ranges
        if ip.startswith(("192.168.", "10.", "172.")):
            return True
            
        return False
    
    def _is_malicious_request(self, path: str, user_agent: str = "") -> bool:
        """Check if request matches malicious patterns."""
        path_lower = path.lower()
        user_agent_lower = user_agent.lower()
        
        # Check path patterns
        for pattern in self.config.malicious_patterns:
            if pattern.lower() in path_lower:
                return True
        
        # Check for common pentesting tools in User-Agent
        pentesting_tools = ["nmap", "nikto", "sqlmap", "burp", "zap", "dirb", "gobuster"]
        for tool in pentesting_tools:
            if tool in user_agent_lower:
                return True
        
        return False
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers."""
        # Check for forwarded headers (common with proxies)
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        # Fallback to direct connection
        return request.client.host if request.client else "unknown"
    
    def _is_rate_limited(self, ip: str) -> bool:
        """Check if IP has exceeded rate limits."""
        now = time.time()
        requests = self.request_counts[ip]
        
        # Remove old requests outside the time windows
        while requests and now - requests[0] > 3600:  # 1 hour
            requests.popleft()
        
        # Check hourly limit
        if len(requests) >= self.config.max_requests_per_hour:
            return True
        
        # Check minute limit (last 60 seconds)
        recent_requests = [req for req in requests if now - req <= 60]
        if len(recent_requests) >= self.config.max_requests_per_minute:
            return True
        
        return False
    
    def _should_block_ip(self, ip: str) -> bool:
        """Determine if IP should be blocked."""
        # Check explicit blacklist
        if ip in self.config.blacklisted_ips:
            return True
        
        # Check if IP is currently blocked
        if ip in self.blocked_ips:
            block_until = self.blocked_ips[ip]
            if datetime.now() < block_until:
                return True
            else:
                # Unblock expired IPs
                del self.blocked_ips[ip]
        
        return False
    
    def _mark_suspicious_ip(self, ip: str):
        """Mark IP as suspicious and potentially block it."""
        self.suspicious_ips.add(ip)
        
        if self.config.block_suspicious_ips:
            block_until = datetime.now() + timedelta(minutes=self.config.block_duration_minutes)
            self.blocked_ips[ip] = block_until
            logger.warning(f"Blocked suspicious IP {ip} until {block_until}")
    
    async def dispatch(self, request: Request, call_next):
        """Process request through security checks."""
        client_ip = self._get_client_ip(request)
        path = request.url.path
        user_agent = request.headers.get("User-Agent", "")
        
        # Log the request for monitoring
        logger.debug(f"Request from {client_ip}: {request.method} {path}")
        
        # Check if IP is blocked
        if self._should_block_ip(client_ip):
            self.blocked_requests += 1
            logger.warning(f"Blocked request from blacklisted IP: {client_ip}")
            return Response(
                content="Access denied",
                status_code=403,
                headers={"X-Blocked-Reason": "IP blacklisted"}
            )
        
        # Check for localhost-only access
        if self.config.allow_localhost_only and not self._is_local_ip(client_ip):
            self.blocked_requests += 1
            logger.warning(f"Blocked non-local request from: {client_ip}")
            return Response(
                content="Access denied - localhost only",
                status_code=403,
                headers={"X-Blocked-Reason": "Non-local access"}
            )
        
        # Check for malicious request patterns
        if self._is_malicious_request(path, user_agent):
            self.blocked_requests += 1
            logger.warning(f"Blocked malicious request from {client_ip}: {path}")
            
            # Mark IP as suspicious
            self._mark_suspicious_ip(client_ip)
            
            return Response(
                content="Access denied",
                status_code=403,
                headers={"X-Blocked-Reason": "Malicious pattern detected"}
            )
        
        # Check rate limiting
        if self._is_rate_limited(client_ip):
            self.blocked_requests += 1
            logger.warning(f"Rate limited request from {client_ip}")
            
            # Mark IP as suspicious if it's hitting rate limits
            if client_ip in self.suspicious_ips:
                self._mark_suspicious_ip(client_ip)
            
            return Response(
                content="Rate limit exceeded",
                status_code=429,
                headers={"X-Blocked-Reason": "Rate limit exceeded"}
            )
        
        # Record request for rate limiting
        self.request_counts[client_ip].append(time.time())
        
        # Continue with normal request processing
        try:
            response = await call_next(request)
            return response
        except Exception as e:
            logger.error(f"Error processing request from {client_ip}: {e}")
            raise
    
    def get_security_stats(self) -> Dict:
        """Get security statistics."""
        return {
            "blocked_requests": self.blocked_requests,
            "suspicious_ips": len(self.suspicious_ips),
            "currently_blocked_ips": len(self.blocked_ips),
            "rate_limited_ips": len([ip for ip, requests in self.request_counts.items() 
                                   if len(requests) > self.config.max_requests_per_minute]),
            "blacklisted_ips": list(self.config.blacklisted_ips),
            "suspicious_ips_list": list(self.suspicious_ips),
            "blocked_ips_list": list(self.blocked_ips.keys())
        }

# Global security instance
security_middleware: Optional[SecurityMiddleware] = None

def get_security_middleware() -> SecurityMiddleware:
    """Get the global security middleware instance."""
    global security_middleware
    if security_middleware is None:
        security_middleware = SecurityMiddleware(None)
    return security_middleware 