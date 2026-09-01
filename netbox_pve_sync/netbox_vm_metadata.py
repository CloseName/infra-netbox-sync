MANAGED_VM_CUSTOM_FIELDS = (
    'sync_identities',
    'sync_original_names',
)


def vm_identity_source_id(vm):
    """
    Return a source-local VM identifier.

    Discovery currently exposes:
        proxmox:new-infra-test:100

    The custom field stores:
        source=proxmox
        source_id=new-infra-test:100
    """

    source_id = str(vm.source_id)
    prefix = f'{vm.source}:'

    if source_id.startswith(prefix):
        return source_id[len(prefix):]

    return source_id


def matches_vm_sync_identity(
        custom_fields,
        vm,
):
    custom_fields = dict(
        custom_fields or {}
    )

    identities = custom_fields.get(
        'sync_identities'
    )

    if not isinstance(identities, list):
        return False

    wanted_id = vm_identity_source_id(vm)

    for identity in identities:
        if not isinstance(identity, dict):
            continue

        source = identity.get('source')

        source_id = identity.get(
            'source_id',
            identity.get('id'),
        )

        if (
            source == vm.source
            and source_id == wanted_id
        ):
            return True

        # Compatibility in case a prefixed source_id
        # ever appeared in NetBox.
        if (
            source == vm.source
            and source_id == vm.source_id
        ):
            return True

    return False


def build_vm_custom_fields(
        vm,
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
        vm.source
    ] = vm.original_name

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
        if not isinstance(identity, dict):
            raise ValueError(
                'sync_identities contains '
                'an unsupported value'
            )

        normalized = dict(identity)

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

        # Fresh discovery owns the identity for
        # its own source.
        if source == vm.source:
            continue

        merged_identities.append(
            normalized
        )

    merged_identities.append({
        'source': vm.source,
        'source_id':
            vm_identity_source_id(vm),
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

    result = dict(existing)

    result.update({
        'sync_identities':
            merged_identities,

        'sync_original_names':
            merged_original_names,
    })

    return result
