"""Characterize retain-only disappearance reporting."""

from dataclasses import replace

from netbox_pve_sync.netbox_disappearance import (
    report_missing_managed_objects,
)
from netbox_pve_sync.netbox_planner import NetBoxTargetConfig
from netbox_pve_sync.proxmox_discovery import discover_hosts

from tests.fakes import FakeProxmox, FakeRecord
from tests.sample_data import (
    proxmox_responses,
    sample_source_config,
)


def test_disappearance_reports_missing_guest_without_delete(
        capsys,
        fake_netbox,
):
    site = fake_netbox.dcim.sites.add(
        FakeRecord(id=1, slug='test-site', name='Test Site')
    )
    cluster = fake_netbox.virtualization.clusters.add(
        FakeRecord(
            id=2,
            name='Test Cluster',
            scope_type='dcim.site',
            scope_id=site.id,
        )
    )
    fake_netbox.virtualization.virtual_machines.add(
        FakeRecord(
            id=3,
            name='missing-vm',
            cluster=cluster,
            custom_fields={
                'sync_identities': [
                    {
                        'source': 'proxmox',
                        'source_id': 'node-a:999',
                    },
                ],
            },
        )
    )

    hosts = discover_hosts(
        FakeProxmox(proxmox_responses()),
        sample_source_config(),
    )
    config = NetBoxTargetConfig(
        site_slug='test-site',
        device_role_slug='server',
        platform_slug='proxmox',
        device_type_slug='generic',
        cluster_type_slug='proxmox',
        cluster_name='Test Cluster',
    )

    report_missing_managed_objects(
        fake_netbox,
        hosts,
        config,
    )

    output = capsys.readouterr().out
    assert 'WARNING MISSING GUEST' in output
    assert 'identity=proxmox:node-a:999' in output
    assert 'action=retained' in output
    assert 'No objects were deleted.' in output
    assert fake_netbox.mutation_count('delete') == 0
    assert fake_netbox.mutations == []


def test_disappearance_does_not_cross_source_instance_boundary(
        capsys,
        fake_netbox,
):
    site = fake_netbox.dcim.sites.add(
        FakeRecord(id=1, slug='test-site', name='Test Site')
    )
    cluster = fake_netbox.virtualization.clusters.add(
        FakeRecord(
            id=2,
            name='Test Cluster',
            scope_type='dcim.site',
            scope_id=site.id,
        )
    )
    for record_id, instance in ((3, 'pve-a'), (4, 'pve-b')):
        fake_netbox.virtualization.virtual_machines.add(
            FakeRecord(
                id=record_id,
                name=f'missing-{instance}',
                cluster=cluster,
                custom_fields={
                    'sync_identities': [{
                        'schema': 'v2',
                        'type': 'proxmox',
                        'instance': instance,
                        'kind': 'qemu',
                        'external_id': '999',
                    }],
                },
            )
        )

    source_config = replace(
        sample_source_config(),
        id='pve-a',
        source_instance='pve-a',
        legacy_identity_owner=False,
    )
    hosts = discover_hosts(
        FakeProxmox(proxmox_responses()),
        source_config,
    )

    report_missing_managed_objects(
        fake_netbox,
        hosts,
        source_config.target,
    )

    output = capsys.readouterr().out
    assert 'identity=proxmox/pve-a/qemu/999' in output
    assert 'pve-b' not in output
    assert fake_netbox.mutation_count('delete') == 0
