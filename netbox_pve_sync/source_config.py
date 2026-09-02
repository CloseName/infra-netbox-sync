"""Immutable configuration models for one infrastructure source."""

import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


SOURCE_INSTANCE_PATTERN = re.compile(
    r'^[a-z0-9][a-z0-9._-]{1,62}$'
)
SOURCE_TYPE_PATTERN = re.compile(
    r'^[a-z][a-z0-9_-]{1,31}$'
)


def _require_text(value: str, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f'{field_name} must be a non-empty string'
        )


@dataclass(frozen=True)
class NetBoxTargetConfig:
    """NetBox objects to which one source is reconciled."""

    site_slug: str
    device_role_slug: str
    platform_slug: str
    device_type_slug: str
    cluster_type_slug: str
    cluster_name: str

    def __post_init__(self):
        for field_name in (
            'site_slug',
            'device_role_slug',
            'platform_slug',
            'device_type_slug',
            'cluster_type_slug',
            'cluster_name',
        ):
            _require_text(
                getattr(self, field_name),
                field_name,
            )


@dataclass(frozen=True)
class SecretReference:
    """Opaque reference to a secret; never the secret value itself."""

    provider: str
    key: str

    def __post_init__(self):
        _require_text(self.provider, 'provider')
        _require_text(self.key, 'key')


@dataclass(frozen=True)
class SourceCredentials:
    """Non-secret username and references to source API credentials."""

    username: str
    token_id: SecretReference
    token_secret: SecretReference

    def __post_init__(self):
        _require_text(self.username, 'username')


@dataclass(frozen=True)
class SourceConfig:
    """Complete immutable configuration for one discovery source."""

    id: str
    source_instance: str
    name: str
    source_type: str
    address: str
    enabled: bool
    sync_enabled: bool
    sync_interval_seconds: int
    verify_ssl: bool
    target: NetBoxTargetConfig
    credentials: SourceCredentials
    settings: Mapping[str, object] = field(
        default_factory=dict
    )

    def __post_init__(self):
        for field_name in (
            'id',
            'name',
            'address',
        ):
            _require_text(
                getattr(self, field_name),
                field_name,
            )

        if not SOURCE_INSTANCE_PATTERN.fullmatch(
            self.source_instance
        ):
            raise ValueError(
                'source_instance must match '
                '^[a-z0-9][a-z0-9._-]{1,62}$'
            )

        if not SOURCE_TYPE_PATTERN.fullmatch(
            self.source_type
        ):
            raise ValueError(
                'source_type must match '
                '^[a-z][a-z0-9_-]{1,31}$'
            )

        if (
            not isinstance(self.sync_interval_seconds, int)
            or isinstance(self.sync_interval_seconds, bool)
            or self.sync_interval_seconds <= 0
        ):
            raise ValueError(
                'sync_interval_seconds must be '
                'a positive integer'
            )

        if not isinstance(self.settings, Mapping):
            raise ValueError('settings must be a mapping')

        object.__setattr__(
            self,
            'settings',
            MappingProxyType(dict(self.settings)),
        )
