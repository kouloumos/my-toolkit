#!/usr/bin/env python3

"""
Test suite for My Toolkit.

This test suite can be run:
1. Directly: python3 -m unittest tests/test_toolkit.py
2. Via pytest: pytest tests/
3. Via nix: nix flake check

Tests are organized into categories:
- Configuration tests
- Service tests
- Network tests
- Integration tests
"""

import unittest
import sys
import os
from pathlib import Path
import subprocess
import json

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python_scripts"))

try:
    from toolkit_utils import ProxyConfig, SSLConfig
    TOOLKIT_UTILS_AVAILABLE = True
except ImportError:
    TOOLKIT_UTILS_AVAILABLE = False


class TestConfiguration(unittest.TestCase):
    """Test configuration and file management"""

    def test_toolkit_utils_available(self):
        """Test that toolkit_utils module is available"""
        self.assertTrue(TOOLKIT_UTILS_AVAILABLE, "toolkit_utils module should be importable")

    def test_proxy_config_initialization(self):
        """Test ProxyConfig can be initialized"""
        if not TOOLKIT_UTILS_AVAILABLE:
            self.skipTest("toolkit_utils not available")

        config = ProxyConfig()
        self.assertIsNotNone(config)
        self.assertIsInstance(config.enabled, bool)

    def test_ssl_config_initialization(self):
        """Test SSLConfig can be initialized"""
        if not TOOLKIT_UTILS_AVAILABLE:
            self.skipTest("toolkit_utils not available")

        config = SSLConfig()
        self.assertIsNotNone(config)
        self.assertIsInstance(config.verify, bool)

    def test_proxy_config_directory(self):
        """Test that config directory can be created"""
        config_dir = Path.home() / ".config" / "my-toolkit-test"
        config_dir.mkdir(parents=True, exist_ok=True)
        self.assertTrue(config_dir.exists())
        self.assertTrue(config_dir.is_dir())

        # Cleanup
        try:
            config_dir.rmdir()
        except OSError:
            pass  # Directory not empty or doesn't exist


class TestProxyConfiguration(unittest.TestCase):
    """Test proxy configuration functionality"""

    def test_proxy_detection_from_env(self):
        """Test proxy detection from environment variables"""
        if not TOOLKIT_UTILS_AVAILABLE:
            self.skipTest("toolkit_utils not available")

        # Save original env
        original_http = os.environ.get('HTTP_PROXY')

        # Set test proxy
        os.environ['HTTP_PROXY'] = 'http://test-proxy:8080'

        try:
            config = ProxyConfig()
            self.assertTrue(config.enabled)
            self.assertEqual(config.url, 'http://test-proxy:8080')
            self.assertIsNotNone(config.proxies)
            self.assertEqual(config.proxies['http'], 'http://test-proxy:8080')
        finally:
            # Restore original env
            if original_http:
                os.environ['HTTP_PROXY'] = original_http
            else:
                os.environ.pop('HTTP_PROXY', None)

    def test_proxy_disabled_by_default(self):
        """Test that proxy is disabled when not configured"""
        if not TOOLKIT_UTILS_AVAILABLE:
            self.skipTest("toolkit_utils not available")

        # Clear env vars
        original_http = os.environ.pop('HTTP_PROXY', None)
        original_https = os.environ.pop('HTTPS_PROXY', None)

        try:
            # Ensure no config file
            config_file = Path.home() / ".config" / "my-toolkit" / "proxy.json"
            has_config = config_file.exists()

            if not has_config:
                config = ProxyConfig()
                # Only check if no config exists
                self.assertFalse(config.enabled, "Proxy should be disabled without configuration")
        finally:
            # Restore env vars
            if original_http:
                os.environ['HTTP_PROXY'] = original_http
            if original_https:
                os.environ['HTTPS_PROXY'] = original_https


class TestScriptAvailability(unittest.TestCase):
    """Test that scripts are available and executable"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.script_dir = Path(__file__).parent.parent / "python_scripts"

    def test_torrent_search_exists(self):
        """Test torrent-search.py exists"""
        script = self.script_dir / "torrent-search.py"
        self.assertTrue(script.exists(), f"Script should exist: {script}")

    def test_proxy_setup_exists(self):
        """Test proxy-setup.py exists"""
        script = self.script_dir / "proxy-setup.py"
        self.assertTrue(script.exists(), f"Script should exist: {script}")

    def test_health_check_exists(self):
        """Test health-check.py exists"""
        script = self.script_dir / "health-check.py"
        self.assertTrue(script.exists(), f"Script should exist: {script}")

    def test_toolkit_utils_exists(self):
        """Test toolkit_utils.py exists"""
        script = self.script_dir / "toolkit_utils.py"
        self.assertTrue(script.exists(), f"Module should exist: {script}")


class TestScriptHelp(unittest.TestCase):
    """Test that scripts provide help messages"""

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures"""
        cls.script_dir = Path(__file__).parent.parent / "python_scripts"

    def _test_help(self, script_name):
        """Helper to test script help output"""
        script = self.script_dir / script_name
        if not script.exists():
            self.skipTest(f"Script {script_name} not found")

        try:
            # Try to run with --help
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                capture_output=True,
                text=True,
                timeout=5
            )
            # Help should exit with 0 and produce output
            self.assertEqual(result.returncode, 0, f"{script_name} --help should exit with 0")
            self.assertGreater(len(result.stdout), 0, f"{script_name} --help should produce output")
            self.assertIn("usage:", result.stdout.lower(), f"{script_name} should show usage")
        except subprocess.TimeoutExpired:
            self.fail(f"{script_name} --help timed out")

    def test_proxy_setup_help(self):
        """Test proxy-setup.py provides help"""
        self._test_help("proxy-setup.py")

    def test_health_check_help(self):
        """Test health-check.py provides help"""
        self._test_help("health-check.py")

    def test_torrent_search_help(self):
        """Test torrent-search.py provides help"""
        self._test_help("torrent-search.py")


class TestDependencies(unittest.TestCase):
    """Test that required dependencies are available"""

    def test_requests_available(self):
        """Test that requests module is available"""
        try:
            import requests
            self.assertTrue(True)
        except ImportError:
            self.fail("requests module should be available")

    def test_json_available(self):
        """Test that json module is available"""
        import json
        self.assertTrue(True)

    def test_pathlib_available(self):
        """Test that pathlib is available"""
        from pathlib import Path
        self.assertTrue(True)


class TestIntegration(unittest.TestCase):
    """Integration tests (may require services to be running)"""

    def test_proxy_config_file_format(self):
        """Test proxy configuration file format if it exists"""
        config_file = Path.home() / ".config" / "my-toolkit" / "proxy.json"

        if not config_file.exists():
            self.skipTest("Proxy configuration file not present")

        try:
            with open(config_file, 'r') as f:
                config = json.load(f)

            # Verify expected keys
            self.assertIsInstance(config, dict)
            if "enabled" in config:
                self.assertIsInstance(config["enabled"], bool)
            if "local_port" in config:
                self.assertIsInstance(config["local_port"], int)
                self.assertGreater(config["local_port"], 0)
                self.assertLess(config["local_port"], 65536)

        except json.JSONDecodeError:
            self.fail("Proxy configuration file should be valid JSON")
        except Exception as e:
            self.fail(f"Error reading proxy configuration: {e}")


def run_tests(verbosity=2):
    """
    Run all tests

    Args:
        verbosity: Test output verbosity (0, 1, or 2)

    Returns:
        True if all tests passed, False otherwise
    """
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestProxyConfiguration))
    suite.addTests(loader.loadTestsFromTestCase(TestScriptAvailability))
    suite.addTests(loader.loadTestsFromTestCase(TestScriptHelp))
    suite.addTests(loader.loadTestsFromTestCase(TestDependencies))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    # Support both unittest and direct execution
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # Direct execution: python3 test_toolkit.py run
        success = run_tests(verbosity=2)
        sys.exit(0 if success else 1)
    else:
        # Standard unittest execution
        unittest.main()
