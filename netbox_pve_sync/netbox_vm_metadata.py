MANAGED_VM_CUSTOM_FIELDS = (
    'sync_identities',
    'sync_original_names',
)

from .source_identity import (
    merge_original_name,
    merge_source_identities,
    qemu_source_identity,
    source_identity_match_rank,
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
    wanted_id = vm_identity_source_id(vm)
    return bool(source_identity_match_rank(
        custom_fields,
        qemu_source_identity(vm),
        (wanted_id, vm.source_id),
        vm.legacy_identity_owner,
    ))


def build_vm_custom_fields(
        vm,
        existing_custom_fields=None,
):
    existing = dict(
        existing_custom_fields or {}
    )

    desired_identity = qemu_source_identity(vm)
    merged_identities = merge_source_identities(existing, desired_identity)
    merged_original_names = merge_original_name(
        existing, desired_identity, vm.original_name,
    )

    result = dict(existing)

    result.update({
        'sync_identities':
            merged_identities,

        'sync_original_names':
            merged_original_names,
    })

    return result
