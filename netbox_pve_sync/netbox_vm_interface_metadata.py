from .netbox_vm_metadata import (
    vm_identity_source_id,
)
from .source_identity import (
    lxc_nic_source_identity,
    qemu_nic_source_identity,
    source_identity_match_rank,
)


MANAGED_VM_INTERFACE_CUSTOM_FIELDS = (
    'sync_identities',
    'sync_original_names',
    'source_bridge',
    'source_vlan_id',
)


def nic_identity_source_id(vm, nic):
    return (
        f'{vm_identity_source_id(vm)}:'
        f'{nic.name}'
    )


def matches_nic_sync_identity(
        custom_fields,
        vm,
        nic,
):
    wanted = nic_identity_source_id(
        vm,
        nic,
    )
    builder = (
        lxc_nic_source_identity
        if hasattr(vm, 'architecture')
        else qemu_nic_source_identity
    )
    return bool(source_identity_match_rank(
        custom_fields,
        builder(vm, nic),
        (wanted,),
        vm.legacy_identity_owner,
    ))


def build_nic_custom_fields(
        vm,
        nic,
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

        if normalized.get(
            'source'
        ) == vm.source:
            continue

        merged_identities.append(
            normalized
        )

    merged_identities.append({
        'source': vm.source,
        'source_id': nic_identity_source_id(
            vm,
            nic,
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
        vm.source
    ] = nic.name

    result = dict(existing)

    result.update({
        'sync_identities':
            merged_identities,

        'sync_original_names':
            merged_original_names,

        'source_bridge':
            nic.bridge,

        'source_vlan_id':
            nic.vlan_id,
    })

    return result
