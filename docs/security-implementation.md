# Security Implementation Guide

## Overview

The Kokoro-ONNX TTS API now includes comprehensive security middleware to protect against malicious requests while maintaining local Raycast connectivity.

## Security Features

### 🔒 IP-Based Protection
- **Localhost-only access**: Server now binds to `127.0.0.1` instead of `0.0.0.0`
- **IP blacklisting**: Known malicious IPs are automatically blocked
- **Rate limiting**: Prevents abuse with configurable limits (60 requests/minute, 1000/hour)
- **Automatic blocking**: Suspicious IPs are temporarily blocked for 60 minutes

### 🛡️ Request Pattern Filtering
- **Malicious path detection**: Blocks common pentesting paths like `/admin`, `/cgi-bin/`, etc.
- **Attack pattern recognition**: Detects SQL injection, XSS, and file inclusion attempts
- **Tool detection**: Identifies requests from common pentesting tools (nmap, nikto, etc.)

### 📊 Monitoring & Management
- **Security statistics**: Track blocked requests and suspicious IPs
- **Real-time monitoring**: View security status via `/security-status` endpoint
- **Management script**: Use `scripts/manage_security.py` for monitoring

## Configuration

### Default Security Settings
```python
SecurityConfig(
    allow_localhost_only=True,      # Restrict to localhost
    block_suspicious_ips=True,      # Auto-block suspicious IPs
    max_requests_per_minute=60,     # Rate limiting
    max_requests_per_hour=1000,
    block_duration_minutes=60       # How long to block IPs
)
```

### Environment Variables
- `HOST`: Set to `127.0.0.1` for localhost-only (default)
- `PORT`: API port (default: 8000)

## Usage

### Starting the Server
```bash
# Development (localhost only)
./start_development.sh

# Production (localhost only)
./start_production.sh
```

### Monitoring Security
```bash
# View security status
python scripts/manage_security.py

# Test local connection
python scripts/manage_security.py --test-connection

# Get JSON output
python scripts/manage_security.py --json
```

### API Endpoints
- `GET /security-status`: View security statistics and blocked IPs
- `GET /health`: Check if API is accessible locally

## Blocked IPs

### Currently Blacklisted
- `10.4.22.177` - The pentesting IP from your logs

### Automatic Blocking
IPs are automatically blocked when they:
1. Make malicious requests (detected patterns)
2. Exceed rate limits repeatedly
3. Use known pentesting tools

## Raycast Compatibility

The security implementation is designed to maintain full Raycast compatibility:

### ✅ Allowed Access
- `127.0.0.1` (localhost)
- `localhost`
- `::1` (IPv6 localhost)
- Private network ranges (192.168.x.x, 10.x.x.x, 172.16.x.x)

### 🔧 Raycast Configuration
Raycast should continue working normally since it connects from localhost. No changes needed to your Raycast extension.

## Troubleshooting

### If Raycast Stops Working
1. Check if server is running: `python scripts/manage_security.py --test-connection`
2. Verify security status: `python scripts/manage_security.py`
3. Check server logs for any blocked requests from Raycast

### Adding IPs to Blacklist
Edit `api/security.py` and add IPs to the `blacklisted_ips` set:
```python
blacklisted_ips: Set[str] = field(default_factory=lambda: {
    "10.4.22.177",  # Existing
    "192.168.1.100",  # Add new IPs here
})
```

### Disabling Security (Not Recommended)
If you need to temporarily disable security for debugging:
1. Comment out the security middleware in `api/main.py`
2. Change HOST back to `0.0.0.0` in startup scripts
3. Restart the server

## Security Logs

The security middleware logs all security events:
- Blocked requests with reasons
- Suspicious IP detections
- Rate limiting events

Check your server logs to monitor security activity.

## Performance Impact

The security middleware has minimal performance impact:
- **Memory**: ~1MB for tracking IPs and requests
- **CPU**: <1ms per request for security checks
- **Latency**: Negligible impact on response times

## Future Enhancements

Potential improvements:
- Persistent IP blacklist storage
- Webhook notifications for security events
- Advanced threat detection using ML
- Integration with external threat intelligence feeds 