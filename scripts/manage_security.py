#!/usr/bin/env python3
"""
Security Management Script for Kokoro-ONNX TTS API

This script provides utilities to monitor and manage the security middleware,
including viewing blocked IPs, security statistics, and managing blacklists.

@author @darianrosebrook
@version 1.0.0
@since 2025-07-17
"""

import requests
import json
import sys
import argparse
from typing import Dict, Any, Optional


def get_security_status(
    api_url: str = "http://127.0.0.1:8000",
) -> Optional[Dict[str, Any]]:
    """Get security status from the API."""
    try:
        response = requests.get(f"{api_url}/security-status", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error: API returned status code {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Error connecting to API: {e}")
        return None


def display_security_status(status: Dict[str, Any]):
    """Display security status in a readable format."""
    print("🔒 Security Status")
    print("=" * 50)

    if not status.get("security_enabled", False):
        print("❌ Security middleware is not enabled")
        return

    print(f"✅ Security middleware: ENABLED")
    print(f"🌐 Localhost only: {status.get('localhost_only', 'Unknown')}")
    print(f"📅 Last updated: {status.get('timestamp', 'Unknown')}")

    stats = status.get("statistics", {})
    print("\n📊 Security Statistics:")
    print(f"   • Blocked requests: {stats.get('blocked_requests', 0)}")
    print(f"   • Suspicious IPs: {stats.get('suspicious_ips', 0)}")
    print(f"   • Currently blocked IPs: {stats.get('currently_blocked_ips', 0)}")
    print(f"   • Rate limited IPs: {stats.get('rate_limited_ips', 0)}")

    # Display blacklisted IPs
    blacklisted = stats.get("blacklisted_ips", [])
    if blacklisted:
        print(f"\n🚫 Blacklisted IPs ({len(blacklisted)}):")
        for ip in blacklisted:
            print(f"   • {ip}")

    # Display suspicious IPs
    suspicious = stats.get("suspicious_ips_list", [])
    if suspicious:
        print(f"\n⚠️  Suspicious IPs ({len(suspicious)}):")
        for ip in suspicious:
            print(f"   • {ip}")

    # Display currently blocked IPs
    blocked = stats.get("blocked_ips_list", [])
    if blocked:
        print(f"\n🔒 Currently Blocked IPs ({len(blocked)}):")
        for ip in blocked:
            print(f"   • {ip}")


def test_local_connection(api_url: str = "http://127.0.0.1:8000"):
    """Test if local connection to API works."""
    print("🔍 Testing local connection...")

    try:
        # Test health endpoint
        response = requests.get(f"{api_url}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Local connection successful")
            health = response.json()
            print(f"   • Status: {health.get('status', 'Unknown')}")
            print(f"   • Model ready: {health.get('model_ready', 'Unknown')}")
        else:
            print(f"❌ Health check failed: {response.status_code}")

    except requests.exceptions.RequestException as e:
        print(f"❌ Local connection failed: {e}")
        print("💡 Make sure the API server is running on localhost:8000")


def main():
    parser = argparse.ArgumentParser(description="Manage Kokoro-ONNX TTS API Security")
    parser.add_argument(
        "--api-url",
        default="http://127.0.0.1:8000",
        help="API base URL (default: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--test-connection", action="store_true", help="Test local connection to API"
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    if args.test_connection:
        test_local_connection(args.api_url)
        return

    # Get security status
    status = get_security_status(args.api_url)

    if status is None:
        print("❌ Failed to get security status")
        sys.exit(1)

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        display_security_status(status)


if __name__ == "__main__":
    main()
