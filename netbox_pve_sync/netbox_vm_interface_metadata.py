from .netbox_vm_metadata import (
    vm_identity_source_id,
)
from .source_identity import (
    lxc_nic_source_identity,
    merge_original_name,
    merge_source_identities,
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

    builder = (
        lxc_nic_source_identity
        if hasattr(vm, 'architecture')
        else qemu_nic_source_identity
    )
    desired_identity = builder(vm, nic)
    merged_identities = merge_source_identities(existing, desired_identity)
    merged_original_names = merge_original_name(
        existing, desired_identity, nic.name,
    )

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
