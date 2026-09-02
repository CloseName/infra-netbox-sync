"""Single-source configuration selection and guarded registry bootstrap."""

import os

import psycopg

from .source_config import SourceConfig
from .source_registry import SourceRegistry


LEGACY_MODE = 'legacy'
REGISTRY_MODE = 'registry'
RUNTIME_MODES = frozenset({LEGACY_MODE, REGISTRY_MODE})


class SourceBootstrapError(RuntimeError):
    """Runtime source selection or bootstrap failed closed."""


def _required(environ, variable_name):
    value = environ.get(variable_name, '').strip()
    if not value:
        raise SourceBootstrapError(f'{variable_name} must be configured')
    return value


def runtime_source_mode(environ):
    """Return explicit mode, preserving legacy as the absent-variable default."""

    if 'SOURCE_CONFIG_MODE' not in environ:
        return LEGACY_MODE
    mode = environ.get('SOURCE_CONFIG_MODE', '').strip().lower()
    if mode not in RUNTIME_MODES:
        raise SourceBootstrapError(
            'SOURCE_CONFIG_MODE must be legacy or registry'
        )
    return mode


def _postgres_registry(dsn, schema):
    def connect():
        return psycopg.connect(dsn)

    return SourceRegistry(connect, schema)


def load_runtime_source_config(environ=None, registry_factory=None):
    """Load exactly one SourceConfig without registry-to-legacy fallback."""

    if environ is None:
        environ = os.environ
    mode = runtime_source_mode(environ)
    if mode == LEGACY_MODE:
        return SourceConfig.from_legacy_environment(environ)

    dsn = _required(environ, 'INFRA_SYNC_REGISTRY_DSN')
    schema = _required(environ, 'INFRA_SYNC_REGISTRY_SCHEMA')
    source_id = _required(environ, 'SOURCE_ID')
    factory = registry_factory or _postgres_registry
    registry = factory(dsn, schema)
    config = registry.get_source_config(source_id)
    if config is None:
        raise SourceBootstrapError(
            f'Registry source id {source_id!r} was not found'
        )
    if not config.enabled:
        raise SourceBootstrapError(
            f'Registry source id {source_id!r} is disabled'
        )
    if not config.sync_enabled:
        raise SourceBootstrapError(
            f'Registry source id {source_id!r} has sync disabled'
        )
    return config
