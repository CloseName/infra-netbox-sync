"""Characterize legacy identity and managed metadata behavior."""

from netbox_pve_sync.netbox_lxc_metadata import (
    build_lxc_custom_fields,
    matches_lxc_sync_identity,
)
from netbox_pve_sync.netbox_metadata import (
    build_device_custom_fields,
    matches_sync_identity,
)
from netbox_pve_sync.netbox_vm_interface_metadata import (
    build_nic_custom_fields,
    matches_nic_sync_identity,
)
from netbox_pve_sync.netbox_vm_metadata import (
    build_vm_custom_fields,
    matches_vm_sync_identity,
)
from netbox_pve_sync.proxmox_discovery import discover_hosts

from tests.fakes import FakeProxmox
from tests.sample_data import (
    proxmox_responses,
    sample_source_config,
)


def _objects():
    host = discover_hosts(
        FakeProxmox(proxmox_responses()),
        sample_source_config(),
    )[0]
    return (
        host,
        host.virtual_machines[0],
        host.containers[0],
    )


def test_current_v1_identities_are_read_for_all_managed_objects():
    host, vm, container = _objects()
    vm_nic = vm.interfaces[0]

    assert matches_sync_identity(
        {
            'sync_identities': [
                {'source': 'proxmox', 'source_id': 'node-a'},
            ],
        },
        host,
    )
    assert matches_vm_sync_identity(
        {
            'sync_identities': [
                {'source': 'proxmox', 'source_id': 'node-a:100'},
            ],
        },
        vm,
    )
    assert matches_lxc_sync_identity(
        {
            'sync_identities': [
                {
                    'source': 'proxmox',
                    'source_id': 'node-a:lxc:100',
                },
            ],
        },
        container,
    )
    assert matches_nic_sync_identity(
        {
            'sync_identities': [
                {
                    'source': 'proxmox',
                    'source_id': 'node-a:100:net0',
                },
            ],
        },
        vm,
        vm_nic,
    )


def test_qemu_and_lxc_with_same_vmid_have_distinct_v1_identities():
    _, vm, container = _objects()
    vm_fields = build_vm_custom_fields(vm)
    lxc_fields = build_lxc_custom_fields(container)

    assert matches_vm_sync_identity(vm_fields, vm)
    assert not matches_lxc_sync_identity(vm_fields, container)
    assert matches_lxc_sync_identity(lxc_fields, container)
    assert not matches_vm_sync_identity(lxc_fields, vm)


def test_metadata_builders_preserve_unmanaged_custom_fields():
    host, vm, container = _objects()
    existing = {
        'operator_note': 'must survive sync',
    }

    results = (
        build_device_custom_fields(host, existing),
        build_vm_custom_fields(vm, existing),
        build_lxc_custom_fields(container, existing),
        build_nic_custom_fields(vm, vm.interfaces[0], existing),
    )

    assert all(
        result['operator_note'] == 'must survive sync'
        for result in results
    )
