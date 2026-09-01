MANAGED_LXC_CUSTOM_FIELDS = (
    'sync_identities',
    'sync_original_names',
    'guest_kind',
    'guest_architecture',
    'guest_os_type',
    'swap_mb',
)


def lxc_identity_source_id(container):
    source_id = str(
        container.source_id
    )

    prefix = (
        f'{container.source}:'
    )

    if source_id.startswith(prefix):
        return source_id[
            len(prefix):
        ]

    return source_id


def matches_lxc_sync_identity(
        custom_fields,
        container,
):
    custom_fields = dict(
        custom_fields or {}
    )

    identities = custom_fields.get(
        'sync_identities'
    )

    if not isinstance(
        identities,
        list,
    ):
        return False

    wanted = (
        lxc_identity_source_id(
            container
        )
    )

    for identity in identities:
        if not isinstance(
            identity,
            dict,
        ):
            continue

        source_id = identity.get(
            'source_id',
            identity.get('id'),
        )

        if (
            identity.get('source')
            == container.source
            and source_id == wanted
        ):
            return True

    return False


def build_lxc_custom_fields(
        container,
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

    if not isinstance(
        identities,
        list,
    ):
        raise ValueError(
            'sync_identities '
            'must be a JSON list'
        )

    merged_identities = []

    for identity in identities:
        if not isinstance(
            identity,
            dict,
        ):
            raise ValueError(
                'sync_identities contains '
                'an unsupported value'
            )

        normalized = dict(identity)

        if (
            'source_id'
            not in normalized
            and 'id' in normalized
        ):
            normalized[
                'source_id'
            ] = normalized.pop('id')

        if normalized.get(
            'source'
        ) == container.source:
            continue

        merged_identities.append(
            normalized
        )

    merged_identities.append({
        'source':
            container.source,
        'source_id':
            lxc_identity_source_id(
                container
            ),
    })

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
        container.source
    ] = container.original_name

    result = dict(existing)

    result.update({
        'sync_identities':
            merged_identities,

        'sync_original_names':
            merged_original_names,

        'guest_kind':
            'lxc',

        'guest_architecture':
            container.architecture,

        'guest_os_type':
            container.os_type,

        'swap_mb':
            container.swap_bytes
            // 1024**2,
    })

    return result
