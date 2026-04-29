# tools/build-catalog/test_build_catalog.py
"""
Unit tests for build_catalog helpers. Run with:

    python -m unittest tools/build-catalog/test_build_catalog.py
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Make the script importable as a module without needing a package marker.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_catalog  # noqa: E402


class NormalizePermissionsTests(unittest.TestCase):
    """
    The host model ships a tolerant JSON converter that accepts string-form
    permissions (legacy "None", empty string, single token), but the catalog
    should only ever publish the canonical array shape so downstream tools
    (jq, the index.html renderer, third-party clients without our converter)
    don't trip over the same legacy degenerate shapes.
    """

    def test_list_passthrough(self):
        self.assertEqual(
            build_catalog._normalize_permissions(["FileSystemSandbox", "NetworkOutbound"]),
            ["FileSystemSandbox", "NetworkOutbound"],
        )

    def test_none_string_becomes_empty_list(self):
        self.assertEqual(build_catalog._normalize_permissions("None"), [])

    def test_none_string_case_insensitive(self):
        self.assertEqual(build_catalog._normalize_permissions("none"), [])
        self.assertEqual(build_catalog._normalize_permissions("NONE"), [])

    def test_empty_string_becomes_empty_list(self):
        self.assertEqual(build_catalog._normalize_permissions(""), [])

    def test_single_token_string_becomes_single_element_list(self):
        self.assertEqual(
            build_catalog._normalize_permissions("FileSystemSandbox"),
            ["FileSystemSandbox"],
        )

    def test_python_none_becomes_empty_list(self):
        self.assertEqual(build_catalog._normalize_permissions(None), [])

    def test_list_drops_empty_strings(self):
        self.assertEqual(
            build_catalog._normalize_permissions(["A", "", "B"]),
            ["A", "B"],
        )

    def test_list_drops_non_strings(self):
        self.assertEqual(
            build_catalog._normalize_permissions(["A", 42, None, "B"]),
            ["A", "B"],
        )


class RiskLevelTests(unittest.TestCase):
    def test_low_for_no_perms(self):
        self.assertEqual(build_catalog.risk_level([]), "low")
        self.assertEqual(build_catalog.risk_level(None), "low")

    def test_medium_for_process_or_filesystem_user(self):
        self.assertEqual(build_catalog.risk_level(["ProcessExec"]), "medium")
        self.assertEqual(build_catalog.risk_level(["FileSystemUser"]), "medium")

    def test_high_for_dangerous_combo(self):
        self.assertEqual(
            build_catalog.risk_level(["ProcessExec", "FileSystemUser", "Network"]),
            "high",
        )


if __name__ == "__main__":
    unittest.main()
