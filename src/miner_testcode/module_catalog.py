from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Mapping

from .errors import ConfigError


MAX_CATALOG_BYTES = 256 * 1024
MAX_SELECTION_BYTES = 16 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._*-]{0,199}$")
_PRIVATE_KEY_PARTS = (
    "address",
    "command",
    "credential",
    "device",
    "endpoint",
    "environment",
    "host",
    "password",
    "path",
    "pool",
    "secret",
    "serial",
    "token",
    "url",
    "user",
    "worker",
)


def _strict(value: Mapping[str, Any], allowed: frozenset[str], context: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigError(f"{context} has unknown fields: {', '.join(unknown)}")


def _text(value: Any, context: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ConfigError(f"{context} must be a non-empty string up to {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ConfigError(f"{context} must not contain control characters")
    return value.strip()


def _identifier(value: Any, context: str) -> str:
    parsed = _text(value, context, 128)
    if not _ID.fullmatch(parsed):
        raise ConfigError(f"{context} must be an opaque identifier")
    return parsed


def _integer(value: Any, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(f"{context} must be an integer")
    if not -1_000_000_000 <= value <= 1_000_000_000:
        raise ConfigError(f"{context} exceeds the portable integer bound")
    return value


@dataclass(frozen=True, slots=True)
class ModuleOption:
    id: str
    label: str
    description: str
    type: str
    required: bool
    default: bool | int | str | None
    minimum: int | None
    maximum: int | None
    choices: tuple[str, ...]

    def validate(self, value: Any, context: str) -> bool | int | str:
        if self.type == "boolean":
            if not isinstance(value, bool):
                raise ConfigError(f"{context} must be boolean")
            return value
        if self.type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise ConfigError(f"{context} must be an integer")
            parsed = value
        elif self.type in {"string", "enum"}:
            parsed_text = _text(value, context, 256)
            if parsed_text != value:
                raise ConfigError(f"{context} must be trimmed text")
            if self.type == "enum" and parsed_text not in self.choices:
                raise ConfigError(f"{context} must be one of the declared choices")
            return parsed_text
        else:
            raise ConfigError(f"{context} has an unsupported option type")
        if self.minimum is not None and parsed < self.minimum:
            raise ConfigError(f"{context} is below its declared minimum")
        if self.maximum is not None and parsed > self.maximum:
            raise ConfigError(f"{context} exceeds its declared maximum")
        return parsed


@dataclass(frozen=True, slots=True)
class TestModule:
    id: str
    name: str
    description: str
    test_pattern: str
    required_capabilities: tuple[str, ...]
    options: tuple[ModuleOption, ...]


@dataclass(frozen=True, slots=True)
class ModuleCatalog:
    schema_version: int
    modules: tuple[TestModule, ...]

    def module(self, module_id: str) -> TestModule:
        for module in self.modules:
            if module.id == module_id:
                return module
        raise ConfigError(f"unknown Testcode module: {module_id}")


def _parse_option(value: Any, context: str) -> ModuleOption:
    if not isinstance(value, dict):
        raise ConfigError(f"{context} must be an object")
    allowed = frozenset(
        {"id", "label", "description", "type", "required", "default", "minimum", "maximum", "choices"}
    )
    _strict(value, allowed, context)
    option_id = _identifier(value.get("id"), f"{context}.id")
    lowered = option_id.lower()
    if any(part in lowered for part in _PRIVATE_KEY_PARTS):
        raise ConfigError(f"{context}.id is not eligible for portable configuration")
    option_type = _text(value.get("type"), f"{context}.type", 16)
    if option_type not in {"boolean", "integer", "string", "enum"}:
        raise ConfigError(f"{context}.type is unsupported")
    required = value.get("required", False)
    if not isinstance(required, bool):
        raise ConfigError(f"{context}.required must be boolean")
    minimum = (
        _integer(value["minimum"], f"{context}.minimum")
        if "minimum" in value
        else None
    )
    maximum = (
        _integer(value["maximum"], f"{context}.maximum")
        if "maximum" in value
        else None
    )
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ConfigError(f"{context} has an inverted numeric range")
    choices_raw = value.get("choices", [])
    if not isinstance(choices_raw, list) or len(choices_raw) > 64:
        raise ConfigError(f"{context}.choices must be a bounded array")
    choices = tuple(
        _text(choice, f"{context}.choices", 128) for choice in choices_raw
    )
    if len(set(choices)) != len(choices):
        raise ConfigError(f"{context}.choices must be unique")
    if option_type == "enum" and not choices:
        raise ConfigError(f"{context}.choices is required for enum options")
    if option_type != "enum" and choices:
        raise ConfigError(f"{context}.choices is allowed only for enum options")
    option = ModuleOption(
        id=option_id,
        label=_text(value.get("label"), f"{context}.label", 120),
        description=_text(value.get("description"), f"{context}.description", 500),
        type=option_type,
        required=required,
        default=None,
        minimum=minimum,
        maximum=maximum,
        choices=choices,
    )
    default = value.get("default")
    if "default" in value:
        default = option.validate(default, f"{context}.default")
    elif required:
        raise ConfigError(f"{context}.default is required for required options")
    return ModuleOption(
        id=option.id,
        label=option.label,
        description=option.description,
        type=option.type,
        required=option.required,
        default=default,
        minimum=option.minimum,
        maximum=option.maximum,
        choices=option.choices,
    )


def parse_module_catalog(payload: bytes) -> ModuleCatalog:
    if len(payload) > MAX_CATALOG_BYTES:
        raise ConfigError("Testcode module catalog exceeds 256 KiB")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ConfigError("Testcode module catalog must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ConfigError("Testcode module catalog must be an object")
    _strict(value, frozenset({"schema_version", "modules"}), "module catalog")
    if value.get("schema_version") != 1:
        raise ConfigError("unsupported Testcode module catalog version")
    modules_raw = value.get("modules")
    if not isinstance(modules_raw, list) or not 1 <= len(modules_raw) <= 128:
        raise ConfigError("module catalog must contain 1 through 128 modules")
    modules: list[TestModule] = []
    module_ids: set[str] = set()
    for index, raw in enumerate(modules_raw):
        context = f"modules[{index}]"
        if not isinstance(raw, dict):
            raise ConfigError(f"{context} must be an object")
        _strict(
            raw,
            frozenset({"id", "name", "description", "test_pattern", "required_capabilities", "options"}),
            context,
        )
        module_id = _identifier(raw.get("id"), f"{context}.id")
        if module_id in module_ids:
            raise ConfigError(f"duplicate Testcode module ID: {module_id}")
        module_ids.add(module_id)
        pattern = _text(raw.get("test_pattern"), f"{context}.test_pattern", 200)
        if not _PATTERN.fullmatch(pattern) or ".." in pattern:
            raise ConfigError(f"{context}.test_pattern is unsafe")
        capabilities_raw = raw.get("required_capabilities")
        if not isinstance(capabilities_raw, list) or not 1 <= len(capabilities_raw) <= 64:
            raise ConfigError(f"{context}.required_capabilities must be a bounded array")
        capabilities = tuple(
            _identifier(item, f"{context}.required_capabilities")
            for item in capabilities_raw
        )
        if len(set(capabilities)) != len(capabilities):
            raise ConfigError(f"{context}.required_capabilities must be unique")
        options_raw = raw.get("options")
        if not isinstance(options_raw, list) or len(options_raw) > 64:
            raise ConfigError(f"{context}.options must be a bounded array")
        options = tuple(
            _parse_option(option, f"{context}.options[{option_index}]")
            for option_index, option in enumerate(options_raw)
        )
        option_ids = [option.id for option in options]
        if len(set(option_ids)) != len(option_ids):
            raise ConfigError(f"{context}.options must have unique IDs")
        modules.append(
            TestModule(
                id=module_id,
                name=_text(raw.get("name"), f"{context}.name", 120),
                description=_text(raw.get("description"), f"{context}.description", 500),
                test_pattern=pattern,
                required_capabilities=capabilities,
                options=options,
            )
        )
    return ModuleCatalog(schema_version=1, modules=tuple(modules))


def load_module_catalog() -> ModuleCatalog:
    resource = files("miner_testcode").joinpath("module-catalog.v1.json")
    return parse_module_catalog(resource.read_bytes())


def selected_module_options(
    environ: Mapping[str, str] | None = None,
    catalog: ModuleCatalog | None = None,
) -> tuple[str, Mapping[str, Any]] | None:
    actual_environment = os.environ if environ is None else environ
    raw = actual_environment.get("MINER_TEST_MODULE_OPTIONS", "").strip()
    if not raw:
        return None
    if len(raw.encode("utf-8")) > MAX_SELECTION_BYTES:
        raise ConfigError("MINER_TEST_MODULE_OPTIONS exceeds 16 KiB")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError("MINER_TEST_MODULE_OPTIONS must be JSON") from exc
    if not isinstance(value, dict):
        raise ConfigError("MINER_TEST_MODULE_OPTIONS must be an object")
    _strict(
        value,
        frozenset({"schema_version", "module_id", "values"}),
        "module option selection",
    )
    if value.get("schema_version") != 1:
        raise ConfigError("unsupported module option selection version")
    module_id = _identifier(value.get("module_id"), "module option selection.module_id")
    values = value.get("values")
    if not isinstance(values, dict) or len(values) > 64:
        raise ConfigError("module option selection.values must be a bounded object")
    module = (catalog or load_module_catalog()).module(module_id)
    declarations = {option.id: option for option in module.options}
    unknown = sorted(set(values) - set(declarations))
    if unknown:
        raise ConfigError(f"module option selection has unknown options: {', '.join(unknown)}")
    selected = {
        key: declarations[key].validate(option_value, f"module option {key}")
        for key, option_value in values.items()
    }
    for option in module.options:
        if option.required and option.id not in selected:
            raise ConfigError(f"required module option is missing: {option.id}")
    return module.id, MappingProxyType(selected)


def validate_selected_module_pattern(
    pattern: str,
    environ: Mapping[str, str] | None = None,
) -> None:
    catalog = load_module_catalog()
    selection = selected_module_options(environ, catalog)
    if selection is None:
        return
    module = catalog.module(selection[0])
    if pattern != module.test_pattern:
        raise ConfigError(
            "selected Testcode module does not match the requested discovery pattern"
        )
