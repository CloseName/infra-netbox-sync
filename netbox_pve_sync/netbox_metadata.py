MANAGED_DEVICE_CUSTOM_FIELDS = (
    'sync_identities',
    'sync_original_names',
    'hypervisor_version',
    'cpu_model',
    'cpu_vendor',
    'cpu_sockets',
    'cpu_cores',
    'cpu_threads',
    'memory_mb',
    'physical_disks',
)


def matches_sync_identity(
        custom_fields,
        host,
):
    custom_fields = dict(
        custom_fields or {}
    )

    identities = custom_fields.get(
        'sync_identities'
    )

    if not isinstance(identities, list):
        return False

    original_names = custom_fields.get(
        'sync_original_names'
    )

    if not isinstance(
        original_names,
        dict,
    ):
        original_names = {}

    for identity in identities:
        if isinstance(identity, dict):
            identity_source = identity.get(
                'source'
            )

            identity_id = identity.get(
                'source_id',
                identity.get('id'),
            )

            if (
                identity_source == host.source
                and identity_id == host.source_id
            ):
                return True

            continue

        # Transitional compatibility for the first
        # version where pynetbox collapsed:
        #
        # {"source": "...", "id": "..."}
        #
        # into just the value of "id".
        if isinstance(identity, str):
            if (
                identity == host.source_id
                and original_names.get(
                    host.source
                ) == host.original_name
            ):
                return True

    return False


def build_device_custom_fields(
        host,
        existing_custom_fields=None,
):
    existing = dict(
        existing_custom_fields or {}
    )

    original_names = existing.get(
        'sync_original_names'
    )

    if original_names is None:
        original_names = {}

    if not isinstance(
        original_names,
        dict,
    ):
        raise ValueError(
            'sync_original_names '
            'must be a JSON object'
        )

    merged_original_names = dict(
        original_names
    )

    merged_original_names[
        host.source
    ] = host.original_name

    identities = existing.get(
        'sync_identities'
    )

    if identities is None:
        identities = []

    if not isinstance(identities, list):
        raise ValueError(
            'sync_identities '
            'must be a JSON list'
        )

    merged_identities = []

    for identity in identities:
        if isinstance(identity, dict):
            normalized = dict(identity)

            # Migrate the old JSON schema:
            # id -> source_id
            if (
                'source_id' not in normalized
                and 'id' in normalized
            ):
                normalized[
                    'source_id'
                ] = normalized.pop('id')

            source = normalized.get(
                'source'
            )

            source_id = normalized.get(
                'source_id'
            )

            if (
                source is None
                or source_id is None
            ):
                raise ValueError(
                    'sync_identities contains '
                    'an invalid identity object'
                )

            # The current source is replaced by
            # freshly discovered identity below.
            if source == host.source:
                continue

            merged_identities.append(
                normalized
            )
            continue

        if isinstance(identity, str):
            # Migrate the malformed value produced
            # by the first implementation.
            if (
                identity == host.source_id
                and original_names.get(
                    host.source
                ) == host.original_name
            ):
                continue

            raise ValueError(
                'sync_identities contains '
                'an unattributed legacy string: '
                f'{identity!r}'
            )

        raise ValueError(
            'sync_identities contains '
            'an unsupported value'
        )

    merged_identities.append({
        'source': host.source,
        'source_id': host.source_id,
    })

    merged_identities.sort(
        key=lambda item: (
            str(item.get('source', '')),
            str(
                item.get(
                    'source_id',
                    '',
                )
            ),
        )
    )

    physical_disks = []

    for disk in sorted(
        host.disks,
        key=lambda item: item.path,
    ):
        physical_disks.append({
            'path': disk.path,
            'model': disk.model,
            'serial': disk.serial,
            'type': disk.disk_type,
            'size_bytes': disk.size_bytes,
            'health': disk.health,
        })

    result = dict(existing)

    result.update({
        'sync_identities':
            merged_identities,

        'sync_original_names':
            merged_original_names,

        'hypervisor_version':
            host.hypervisor_version,

        'cpu_model':
            host.cpu.model,

        'cpu_vendor':
            host.cpu.vendor,

        'cpu_sockets':
            host.cpu.sockets,

        'cpu_cores':
            host.cpu.cores,

        'cpu_threads':
            host.cpu.logical_cpus,

        'memory_mb':
            host.memory_bytes // 1024**2,

        'physical_disks':
            physical_disks,
    })

    return result
