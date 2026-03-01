#!/usr/bin/env python3
"""Generate a boilerplate adapter package and unit tests."""

import argparse
from pathlib import Path
from string import Template

ROOT = Path(__file__).resolve().parents[1]


def to_camel_case(name: str) -> str:
    parts = [part for part in name.replace("-", "_").split("_") if part]
    return "".join(part.capitalize() for part in parts)


def write_file(path: Path, content: str, force: bool) -> bool:
    if path.exists() and not force:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def build_templates(package: str, class_prefix: str, dependency: str) -> dict[Path, str]:
    adapter_class = f"{class_prefix}Adapter"
    config_class = f"{class_prefix}AdapterConfig"
    factory_class = f"{class_prefix}AdapterFactory"
    backend_name = package
    dep_list = f'["{dependency}"]' if dependency else "[]"

    src_base = ROOT / "src" / "omni_cache" / "adapters" / package
    test_base = ROOT / "tests" / "unit" / "adapters" / package

    templates: dict[Path, str] = {}

    templates[src_base / "__init__.py"] = Template(
        '"""$class_prefix adapter package."""\n\n'
        "from .config import $config_class\n"
        "from .$package import $adapter_class\n\n"
        '__all__ = ["$adapter_class", "$config_class"]\n'
    ).substitute(
        class_prefix=class_prefix,
        config_class=config_class,
        package=package,
        adapter_class=adapter_class,
    )

    templates[src_base / "config.py"] = Template(
        '"""$class_prefix adapter configuration."""\n\n'
        "from dataclasses import dataclass\n\n"
        "from omni_cache.adapters.base import AdapterConfig\n\n\n"
        "@dataclass\n"
        "class $config_class(AdapterConfig):\n"
        '    """Configuration for $adapter_class."""\n\n'
        '    backend: str = "$backend_name"\n'
    ).substitute(
        class_prefix=class_prefix,
        config_class=config_class,
        adapter_class=adapter_class,
        backend_name=backend_name,
    )

    templates[src_base / f"{package}.py"] = Template(
        '"""$class_prefix adapter implementation."""\n\n'
        "from collections.abc import Iterator\n"
        "from typing import Any, TypeVar\n\n"
        "from omni_cache.adapters.base import BaseCacheAdapter\n"
        "from omni_cache.adapters.$package.config import $config_class\n"
        "from omni_cache.core.interfaces import KeyValueInterface\n\n"
        'K = TypeVar("K")\n'
        'V = TypeVar("V")\n\n\n'
        "class $adapter_class(BaseCacheAdapter, KeyValueInterface[K, V]):\n"
        '    """In-memory placeholder adapter for $class_prefix backend."""\n\n'
        "    def __init__(self, config: dict[str, Any] | $config_class | None = None):\n"
        "        if isinstance(config, dict):\n"
        "            parsed_config = $config_class(**config)\n"
        "        elif isinstance(config, $config_class):\n"
        "            parsed_config = config\n"
        "        else:\n"
        "            parsed_config = $config_class()\n\n"
        "        super().__init__(parsed_config)\n"
        "        self._store: dict[Any, Any] = {}\n\n"
        "    def _do_connect(self) -> bool:\n"
        "        return True\n\n"
        "    def _do_disconnect(self) -> bool:\n"
        "        self._store.clear()\n"
        "        return True\n\n"
        "    def _do_health_check(self) -> bool:\n"
        "        return True\n\n"
        "    def get(self, key: K, default: V | None = None) -> V | None:\n"
        "        value = self._store.get(key, default)\n"
        '        self._update_cache_stats("get", success=value is not None)\n'
        "        return value\n\n"
        "    def set(self, key: K, value: V, ttl: int | float | None = None) -> bool:\n"
        "        _ = ttl\n"
        "        self._store[key] = value\n"
        '        self._update_cache_stats("set", success=True, size=len(self._store))\n'
        "        return True\n\n"
        "    def delete(self, key: K) -> bool:\n"
        "        existed = key in self._store\n"
        "        self._store.pop(key, None)\n"
        "        if existed:\n"
        '            self._update_cache_stats("delete", success=True, size=len(self._store))\n'
        "        return existed\n\n"
        "    def exists(self, key: K) -> bool:\n"
        "        return key in self._store\n\n"
        "    def clear(self) -> bool:\n"
        "        self._store.clear()\n"
        '        self._update_cache_stats("delete", success=True, size=0)\n'
        "        return True\n\n"
        "    def keys(self) -> Iterator[K]:\n"
        "        return iter(self._store.keys())\n\n"
        "    def size(self) -> int:\n"
        "        return len(self._store)\n\n"
        "    def get_many(self, keys: list[K]) -> dict[K, V | None]:\n"
        "        return {key: self.get(key, None) for key in keys}\n\n"
        "    def set_many(\n"
        "        self,\n"
        "        mapping: dict[K, V],\n"
        "        ttl: int | float | None = None,\n"
        "    ) -> dict[K, bool]:\n"
        "        return {key: self.set(key, value, ttl) for key, value in mapping.items()}\n\n"
        "    def delete_many(self, keys: list[K]) -> dict[K, bool]:\n"
        "        return {key: self.delete(key) for key in keys}\n"
    ).substitute(
        class_prefix=class_prefix,
        package=package,
        config_class=config_class,
        adapter_class=adapter_class,
    )

    templates[src_base / "factory.py"] = Template(
        '"""Factory for $class_prefix adapters."""\n\n'
        "from typing import Any\n\n"
        "from omni_cache.core.factories.abstract_factory import AbstractFactory\n"
        "from omni_cache.core.factories.factory_metadata import FactoryMetadata\n"
        "from omni_cache.core.interfaces import AdapterInterface\n\n"
        "from .$package import $adapter_class\n"
        "from .config import $config_class\n\n\n"
        "class $factory_class(AbstractFactory):\n"
        '    """Factory for creating $class_prefix adapters."""\n\n'
        "    def _get_default_metadata(self) -> FactoryMetadata:\n"
        "        return FactoryMetadata(\n"
        '            backend="$backend_name",\n'
        '            factory_class="$factory_class",\n'
        '            description="Factory for $class_prefix cache adapters",\n'
        '            version="1.0.0",\n'
        "            dependencies=$dep_list,\n"
        '            adapter_types=["cache"],\n'
        '            config_schema={"type": "object", "properties": {}, "required": []},\n'
        "        )\n\n"
        "    def _setup_config_validators(self) -> None:\n"
        "        return None\n\n"
        "    def _create_adapter(self, config: dict[str, Any]) -> AdapterInterface:\n"
        "        adapter_config = $config_class(**config)\n"
        "        return $adapter_class(adapter_config)\n"
    ).substitute(
        class_prefix=class_prefix,
        package=package,
        adapter_class=adapter_class,
        config_class=config_class,
        factory_class=factory_class,
        backend_name=backend_name,
        dep_list=dep_list,
    )

    templates[test_base / f"test_{package}_config.py"] = Template(
        '"""Tests for $class_prefix adapter config."""\n\n'
        "from omni_cache.adapters.$package.config import $config_class\n\n\n"
        "def test_default_backend_name() -> None:\n"
        "    config = $config_class()\n"
        '    assert config.backend == "$backend_name"\n'
    ).substitute(
        class_prefix=class_prefix,
        package=package,
        config_class=config_class,
        backend_name=backend_name,
    )

    templates[test_base / f"test_{package}_factory.py"] = Template(
        '"""Tests for $class_prefix adapter factory."""\n\n'
        "from omni_cache.adapters.$package.factory import $factory_class\n\n\n"
        "def test_factory_create() -> None:\n"
        "    factory = $factory_class()\n"
        "    adapter = factory.create({})\n"
        "    assert adapter is not None\n"
    ).substitute(
        class_prefix=class_prefix,
        package=package,
        factory_class=factory_class,
    )

    templates[test_base / f"test_{package}_adapter.py"] = Template(
        '"""Tests for $class_prefix adapter."""\n\n'
        "from omni_cache.adapters.$package.$package import $adapter_class\n"
        "from omni_cache.adapters.$package.config import $config_class\n\n\n"
        "def test_basic_get_set_delete() -> None:\n"
        "    adapter = $adapter_class($config_class())\n"
        "    assert adapter.connect() is True\n"
        '    assert adapter.set("k", "v") is True\n'
        '    assert adapter.get("k") == "v"\n'
        '    assert adapter.delete("k") is True\n'
        '    assert adapter.get("k") is None\n'
    ).substitute(
        class_prefix=class_prefix,
        package=package,
        adapter_class=adapter_class,
        config_class=config_class,
    )

    return templates


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", help="Adapter package name in snake_case (example: my_cache)")
    parser.add_argument(
        "--class-prefix",
        help="Class prefix in CamelCase (default: derived from name)",
    )
    parser.add_argument(
        "--dependency",
        default="",
        help="Optional dependency name used in factory metadata",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )
    return parser.parse_args()


def validate_name(name: str) -> None:
    if not name:
        raise ValueError("Adapter name must not be empty")
    if name != name.lower() or "-" in name:
        raise ValueError("Adapter name must be snake_case (lowercase with underscores)")


def main() -> int:
    args = parse_args()
    validate_name(args.name)

    class_prefix = args.class_prefix or to_camel_case(args.name)
    templates = build_templates(args.name, class_prefix, args.dependency)

    created = []
    skipped = []

    for path, content in templates.items():
        if write_file(path, content, force=args.force):
            created.append(path)
        else:
            skipped.append(path)

    print(f"Generated adapter scaffold for '{args.name}' ({class_prefix}).")
    if created:
        print("Created files:")
        for path in created:
            print(f"  - {path.relative_to(ROOT)}")

    if skipped:
        print("Skipped existing files (use --force to overwrite):")
        for path in skipped:
            print(f"  - {path.relative_to(ROOT)}")

    print("\nNext manual steps:")
    print("  1) Export adapter in src/omni_cache/adapters/__init__.py")
    print("  2) Register factory in src/omni_cache/core/factories/factory_registry.py")
    print("  3) Export factory in src/omni_cache/core/factories/__init__.py")
    print("  4) Add optional dependency and entry point in pyproject.toml")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
