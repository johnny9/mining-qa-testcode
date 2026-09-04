from __future__ import annotations

import json
import unittest

from miner_testcode.errors import ConfigError
from miner_testcode.module_catalog import (
    load_module_catalog,
    parse_module_catalog,
    selected_module_options,
    validate_selected_module_pattern,
)


class ModuleCatalogTest(unittest.TestCase):
    def test_packaged_catalog_describes_production_modules_and_options(self) -> None:
        catalog = load_module_catalog()

        self.assertEqual(
            [module.id for module in catalog.modules],
            [
                "public_pool_smoke",
                "stratum_v1_regression",
                "stratum_v2_regression",
            ],
        )
        public_pool = catalog.module("public_pool_smoke")
        self.assertEqual(public_pool.test_pattern, "test_public_pool_smoke.py")
        self.assertEqual(public_pool.required_capabilities, ("http", "stratum-v1"))
        self.assertIn("require_accepted_share", [option.id for option in public_pool.options])
        stratum_v2 = catalog.module("stratum_v2_regression")
        self.assertEqual(
            stratum_v2.test_pattern, "test_stratum_v2_regression.py"
        )
        self.assertEqual(stratum_v2.required_capabilities, ("http", "stratum-v2"))
        channel_type = next(
            option for option in stratum_v2.options if option.id == "channel_type"
        )
        self.assertEqual(channel_type.default, "extended")
        self.assertEqual(channel_type.choices, ("standard", "extended"))

    def test_selection_accepts_only_declared_typed_bounded_values(self) -> None:
        catalog = load_module_catalog()
        selected = selected_module_options(
            {
                "MINER_TEST_MODULE_OPTIONS": json.dumps(
                    {
                        "schema_version": 1,
                        "module_id": "public_pool_smoke",
                        "values": {
                            "stable_samples": 4,
                            "require_accepted_share": True,
                        },
                    }
                )
            },
            catalog,
        )
        self.assertIsNotNone(selected)
        assert selected is not None
        self.assertEqual(selected[0], "public_pool_smoke")
        self.assertEqual(
            dict(selected[1]),
            {"stable_samples": 4, "require_accepted_share": True},
        )

        sv2_environment = {
            "MINER_TEST_MODULE_OPTIONS": json.dumps(
                {
                    "schema_version": 1,
                    "module_id": "stratum_v2_regression",
                    "values": {"channel_type": "standard"},
                }
            )
        }
        sv2_selected = selected_module_options(sv2_environment, catalog)
        self.assertIsNotNone(sv2_selected)
        assert sv2_selected is not None
        self.assertEqual(dict(sv2_selected[1]), {"channel_type": "standard"})
        sv2_environment["MINER_TEST_MODULE_OPTIONS"] = json.dumps(
            {
                "schema_version": 1,
                "module_id": "stratum_v2_regression",
                "values": {"channel_type": "group"},
            }
        )
        with self.assertRaises(ConfigError):
            selected_module_options(sv2_environment, catalog)

        for values in (
            {"stable_samples": 0},
            {"stable_samples": True},
            {"password": "private"},
        ):
            with self.subTest(values=values), self.assertRaises(ConfigError):
                selected_module_options(
                    {
                        "MINER_TEST_MODULE_OPTIONS": json.dumps(
                            {
                                "schema_version": 1,
                                "module_id": "public_pool_smoke",
                                "values": values,
                            }
                        )
                    },
                    catalog,
                )

    def test_catalog_rejects_private_option_keys_and_unsafe_patterns(self) -> None:
        base = {
            "schema_version": 1,
            "modules": [
                {
                    "id": "smoke",
                    "name": "Smoke",
                    "description": "Bounded smoke test.",
                    "test_pattern": "test_smoke.py",
                    "required_capabilities": ["http"],
                    "options": [
                        {
                            "id": "password_env",
                            "label": "Password variable",
                            "description": "Must stay private.",
                            "type": "string",
                            "required": False,
                        }
                    ],
                }
            ],
        }
        with self.assertRaisesRegex(ConfigError, "not eligible"):
            parse_module_catalog(json.dumps(base).encode())

        base["modules"][0]["options"] = []
        base["modules"][0]["test_pattern"] = "../test_smoke.py"
        with self.assertRaisesRegex(ConfigError, "unsafe"):
            parse_module_catalog(json.dumps(base).encode())

    def test_no_selection_preserves_legacy_behavior(self) -> None:
        self.assertIsNone(selected_module_options({}))
        validate_selected_module_pattern("custom_test.py", {})

    def test_selection_is_bound_to_its_catalog_pattern(self) -> None:
        environment = {
            "MINER_TEST_MODULE_OPTIONS": json.dumps(
                {
                    "schema_version": 1,
                    "module_id": "public_pool_smoke",
                    "values": {},
                }
            )
        }
        validate_selected_module_pattern("test_public_pool_smoke.py", environment)
        with self.assertRaisesRegex(ConfigError, "does not match"):
            validate_selected_module_pattern("test_stratum_v1_regression.py", environment)


if __name__ == "__main__":
    unittest.main()
