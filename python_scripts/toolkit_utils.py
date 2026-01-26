"""
Shared utilities for My Toolkit Python scripts.

This module provides common functionality like proxy detection, SSL configuration,
and other utilities that scripts can reuse.
"""

import os
import json
from pathlib import Path
from typing import Optional, Dict


class ProxyConfig:
    """
    Auto-detect and manage proxy configuration for toolkit scripts.

    Checks multiple sources in priority order:
    1. Environment variables (HTTP_PROXY, HTTPS_PROXY)
    2. My Toolkit proxy configuration (~/.config/my-toolkit/proxy.json)

    Usage:
        proxy_config = ProxyConfig()
        if proxy_config.enabled:
            response = requests.get(url, proxies=proxy_config.proxies)
    """

    def __init__(self):
        self._proxy_url = self._detect_proxy()

    def _detect_proxy(self) -> Optional[str]:
        """Detect proxy from environment or configuration"""
        # Priority 1: Check environment variables
        http_proxy = os.environ.get('HTTP_PROXY') or os.environ.get('http_proxy')
        https_proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy')

        if http_proxy or https_proxy:
            return http_proxy or https_proxy

        # Priority 2: Check my-toolkit proxy configuration
        proxy_config_file = Path.home() / ".config" / "my-toolkit" / "proxy.json"
        if proxy_config_file.exists():
            try:
                with open(proxy_config_file, 'r') as f:
                    config = json.load(f)
                    if config.get("enabled"):
                        local_port = config.get("local_port", 3128)
                        return f"http://127.0.0.1:{local_port}"
            except Exception:
                pass

        return None

    @property
    def enabled(self) -> bool:
        """Check if proxy is configured"""
        return self._proxy_url is not None

    @property
    def url(self) -> Optional[str]:
        """Get proxy URL"""
        return self._proxy_url

    @property
    def proxies(self) -> Optional[Dict[str, str]]:
        """
        Get proxies dict for requests library.

        Returns:
            Dict with 'http' and 'https' keys, or None if no proxy configured
        """
        if not self.enabled:
            return None

        return {
            "http": self._proxy_url,
            "https": self._proxy_url,
        }

    def __str__(self) -> str:
        """String representation"""
        if self.enabled:
            return f"Proxy: {self._proxy_url}"
        return "Proxy: Not configured"


class SSLConfig:
    """
    SSL configuration utilities for toolkit scripts.

    Handles SSL certificate verification issues on NixOS systems.

    Usage:
        ssl_config = SSLConfig()
        response = requests.get(url, verify=ssl_config.verify)
    """

    def __init__(self):
        self._verify = self._detect_ssl_config()

    def _detect_ssl_config(self) -> bool:
        """Detect SSL verification setting"""
        # Allow forcing SSL verification on
        if os.environ.get('FORCE_SSL_VERIFY') == '1':
            return True

        # Default: disable verification due to NixOS OpenSSL 3.x issues
        # This is safe for known-good APIs like YTS
        return False

    @property
    def verify(self) -> bool:
        """Get SSL verification setting"""
        return self._verify

    @staticmethod
    def disable_warnings():
        """Disable SSL warnings when verification is disabled"""
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except ImportError:
            pass


def setup_requests_environment(proxy: bool = True, ssl: bool = True) -> tuple:
    """
    Setup requests environment with proxy and SSL configuration.

    Args:
        proxy: Enable proxy detection
        ssl: Enable SSL configuration

    Returns:
        Tuple of (ProxyConfig, SSLConfig)

    Usage:
        proxy_config, ssl_config = setup_requests_environment()

        # Disable SSL warnings if needed
        if not ssl_config.verify:
            ssl_config.disable_warnings()

        # Make request
        response = requests.get(
            url,
            proxies=proxy_config.proxies,
            verify=ssl_config.verify
        )
    """
    proxy_config = ProxyConfig() if proxy else None
    ssl_config = SSLConfig() if ssl else None

    return proxy_config, ssl_config


# Convenience function for quick setup
def get_requests_kwargs() -> Dict:
    """
    Get a dict of keyword arguments for requests library calls.

    Returns:
        Dict with 'proxies' and 'verify' keys ready for requests

    Usage:
        import requests
        from toolkit_utils import get_requests_kwargs

        response = requests.get(url, **get_requests_kwargs())
    """
    proxy_config, ssl_config = setup_requests_environment()

    kwargs = {
        "verify": ssl_config.verify,
    }

    if proxy_config.enabled:
        kwargs["proxies"] = proxy_config.proxies

    # Disable warnings if SSL verification is off
    if not ssl_config.verify:
        ssl_config.disable_warnings()

    return kwargs
