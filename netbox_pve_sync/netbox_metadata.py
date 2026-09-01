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


def build_device_custom_fields(
        host,
        existing_custom_fields=None,
):
    existing = dict(
        existing_custom_fields or {}
    )

    identities = existing.get(
        'sync_identities'
    )

    if identities is None:
        identities = []

    if not isinstance(identities, list):
        raise ValueError(
            'sync_identities must be a JSON list'
        )

    new_identity = {
        'source': host.source,
        'id': host.source_id,
    }

    merged_identities = []

    for identity in identities:
        if not isinstance(identity, dict):
            raise ValueError(
                'sync_identities contains '
                'a non-object value'
            )

        if (
            identity.get('source')
            == host.source
        ):
            continue

        merged_identities.append(
            dict(identity)
        )

    merged_identities.append(
        new_identity
    )

    merged_identities.sort(
        key=lambda item: (
            str(item.get('source', '')),
            str(item.get('id', '')),
        )
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
