"""PostgreSQL storage foundation for source configuration references."""

import re

from psycopg import sql
from psycopg.rows import dict_row


SCHEMA_VERSION = 1
SCHEMA_NAME_PATTERN = re.compile(r'^[a-z][a-z0-9_]{2,62}$')


class SourceRegistryError(RuntimeError):
    """Base error for fail-closed registry operations."""


class SourceRegistry:
    """PostgreSQL registry with externally supplied connection bootstrap."""

    def __init__(self, connection_factory, schema):
        if not callable(connection_factory):
            raise TypeError('connection_factory must be callable')
        if not isinstance(schema, str) or not SCHEMA_NAME_PATTERN.fullmatch(schema):
            raise ValueError('schema must be a safe PostgreSQL identifier')
        self._connection_factory = connection_factory
        self.schema = schema

    def _connect(self):
        connection = self._connection_factory()
        connection.row_factory = dict_row
        return connection

    def _table(self, table_name):
        return sql.Identifier(self.schema, table_name)

    def initialize(self):
        """Transactionally create the versioned schema without data loss."""

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL('CREATE SCHEMA IF NOT EXISTS {}').format(
                        sql.Identifier(self.schema)
                    )
                )
                cursor.execute(
                    sql.SQL(
                        '''
                        CREATE TABLE IF NOT EXISTS {} (
                            key TEXT PRIMARY KEY,
                            value TEXT NOT NULL
                        )
                        '''
                    ).format(self._table('schema_meta'))
                )
                cursor.execute(
                    sql.SQL(
                        '''
                        INSERT INTO {} (key, value)
                        VALUES ('schema_version', %s)
                        ON CONFLICT (key) DO NOTHING
                        '''
                    ).format(self._table('schema_meta')),
                    (str(SCHEMA_VERSION),),
                )
                cursor.execute(
                    sql.SQL(
                        '''
                        CREATE TABLE IF NOT EXISTS {} (
                            id TEXT PRIMARY KEY,
                            source_instance TEXT NOT NULL UNIQUE,
                            name TEXT NOT NULL,
                            source_type TEXT NOT NULL,
                            address TEXT NOT NULL,
                            enabled BOOLEAN NOT NULL,
                            sync_enabled BOOLEAN NOT NULL,
                            sync_interval_seconds INTEGER NOT NULL,
                            verify_ssl BOOLEAN NOT NULL,
                            site_slug TEXT NOT NULL,
                            device_role_slug TEXT NOT NULL,
                            platform_slug TEXT NOT NULL,
                            device_type_slug TEXT NOT NULL,
                            cluster_type_slug TEXT NOT NULL,
                            cluster_name TEXT NOT NULL,
                            username TEXT NOT NULL,
                            token_id_provider TEXT NOT NULL,
                            token_id_key TEXT NOT NULL,
                            token_secret_provider TEXT NOT NULL,
                            token_secret_key TEXT NOT NULL,
                            legacy_identity_owner BOOLEAN NOT NULL DEFAULT FALSE,
                            settings JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                            created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            CONSTRAINT settings_is_object
                                CHECK (jsonb_typeof(settings) = 'object'),
                            CONSTRAINT positive_sync_interval
                                CHECK (sync_interval_seconds > 0)
                        )
                        '''
                    ).format(self._table('sources'))
                )
                cursor.execute(
                    sql.SQL(
                        "SELECT value FROM {} WHERE key = 'schema_version'"
                    ).format(self._table('schema_meta'))
                )
                row = cursor.fetchone()
                if row is None or int(row['value']) != SCHEMA_VERSION:
                    raise SourceRegistryError(
                        'unsupported source registry schema version'
                    )

    def schema_version(self):
        """Read the initialized schema version."""

        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    sql.SQL(
                        "SELECT value FROM {} WHERE key = 'schema_version'"
                    ).format(self._table('schema_meta'))
                )
                row = cursor.fetchone()
        if row is None:
            raise SourceRegistryError('source registry is not initialized')
        return int(row['value'])
