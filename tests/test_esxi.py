"""Standalone ESXi adapter, discovery, identity, and executor tests."""

from dataclasses import replace

import pytest

from netbox_pve_sync.esxi_client import (
    EsxiClient,
    EsxiConnectionError,
    test_source_connection as check_source_connection,
)
from netbox_pve_sync.esxi_discovery import discover_hosts
from netbox_pve_sync.esxi_executor import execute_esxi_source
from netbox_pve_sync.orchestrator import run_sources
from netbox_pve_sync.source_config import SecretReference, SourceCredentials
from netbox_pve_sync.source_executor import SourceExecutorDispatch
from netbox_pve_sync.source_identity import (
    virtual_machine_nic_source_identity,
    virtual_machine_source_identity,
)

from tests.fakes.esxi import fake_esxi_service
from tests.sample_data import sample_source_config


class FakeResolver:
    """Secret resolver returning an injected ephemeral value."""

    def __init__(self, value='fake-password'):
        self.value = value
        self.references = []

    def resolve(self, reference):
        self.references.append(reference)
        return self.value


def esxi_config(source_id='esxi-a', password_key='ESXI_A_PASSWORD'):
    """Return one valid password-reference-only ESXi SourceConfig."""

    password = SecretReference(provider='env', key=password_key)
    return replace(
        sample_source_config(address=f'{source_id}.example.test'),
        id=source_id,
        source_instance=source_id,
        source_type='esxi',
        legacy_identity_owner=False,
        credentials=SourceCredentials.for_password('root', password),
    )


def test_esxi_host_vm_datastore_disk_nic_and_tools_ip_mapping():
    host = discover_hosts(fake_esxi_service(), esxi_config())[0]
    vm = host.virtual_machines[0]

    assert host.source == 'esxi'
    assert host.source_instance == 'esxi-a'
    assert host.source_id == 'host-uuid-a'
    assert host.management_ip == '192.0.2.10'
    assert host.hypervisor == 'VMware ESXi'
    assert host.hypervisor_version == '8.0.3 build-24022510'
    assert (host.cpu.sockets, host.cpu.cores, host.cpu.logical_cpus) == (2, 16, 32)
    assert host.memory_bytes == 128 * 1024**3
    assert host.interfaces[0].name == 'vmnic0'
    assert host.disks[0].serial == 'FAKE-SERIAL'
    assert host.storages[0].name == 'datastore1'
    assert host.storages[0].used_bytes == 300 * 1024**3
    assert vm.status == 'running'
    assert vm.vcpus == 4
    assert vm.memory_bytes == 8192 * 1024**2
    assert vm.autostart is True
    assert vm.disks[0].storage == 'datastore1'
    assert vm.interfaces[0].external_id == '4000'
    assert vm.interfaces[0].vlan_id == 120
    assert vm.interfaces[0].ip_addresses == ['192.0.2.50/24']


@pytest.mark.parametrize(
    ('power_state', 'expected'),
    (('poweredOn', 'running'), ('poweredOff', 'stopped'), ('suspended', 'stopped')),
)
def test_esxi_power_state_mapping(power_state, expected):
    host = discover_hosts(
        fake_esxi_service(power_state=power_state),
        esxi_config(),
    )[0]

    assert host.virtual_machines[0].status == expected


def test_missing_vmware_tools_and_optional_hardware_are_safe():
    host = discover_hosts(
        fake_esxi_service(
            tools_available=False,
            optional_hardware=False,
        ),
        esxi_config(),
    )[0]

    assert host.cpu.model is None
    assert host.cpu.sockets == 0
    assert host.virtual_machines[0].interfaces[0].ip_addresses == []


def test_vm_rename_preserves_uuid_and_nic_identity():
    before = discover_hosts(fake_esxi_service(vm_name='OLD'), esxi_config())[0]
    after = discover_hosts(fake_esxi_service(vm_name='NEW'), esxi_config())[0]
    before_vm = before.virtual_machines[0]
    after_vm = after.virtual_machines[0]

    assert before_vm.original_name != after_vm.original_name
    assert before_vm.external_id == '503c5ad7-0000-1111-2222-0123456789ab'
    assert virtual_machine_source_identity(before_vm) == (
        virtual_machine_source_identity(after_vm)
    )
    assert virtual_machine_source_identity(before_vm).kind == 'vm'
    assert virtual_machine_nic_source_identity(
        before_vm, before_vm.interfaces[0],
    ) == virtual_machine_nic_source_identity(
        after_vm, after_vm.interfaces[0],
    )
    assert virtual_machine_nic_source_identity(
        before_vm, before_vm.interfaces[0],
    ).kind == 'vm-nic'


@pytest.mark.parametrize('verify_ssl', (True, False))
def test_esxi_client_honors_tls_flag_and_disconnects(verify_ssl):
    connected = []
    disconnected = []
    service = fake_esxi_service()
    config = replace(esxi_config(), verify_ssl=verify_ssl)
    client = EsxiClient(
        resolver=FakeResolver(),
        connector=lambda host, user, password, verify: connected.append(
            (host, user, password, verify)
        ) or service,
        disconnecter=disconnected.append,
    )

    with client.session(config) as session:
        assert session is service

    assert connected == [(
        config.address, 'root', 'fake-password', verify_ssl,
    )]
    assert disconnected == [service]


def test_authentication_failure_is_safe_and_contains_no_password():
    secret = 'FAKE_ESXI_PASSWORD_MUST_NOT_APPEAR'
    client = EsxiClient(
        resolver=FakeResolver(secret),
        connector=lambda *_args: (_ for _ in ()).throw(
            RuntimeError(f'authentication failed for {secret}')
        ),
    )

    with pytest.raises(EsxiConnectionError) as error:
        with client.session(esxi_config()):
            pass

    assert secret not in repr(error.value)
    result = check_source_connection(esxi_config(), client=client)
    assert result.success is False
    assert secret not in repr(result)


def test_esxi_executor_dispatches_discovery_to_shared_reconciliation():
    service = fake_esxi_service()
    client = EsxiClient(
        resolver=FakeResolver(),
        connector=lambda *_args: service,
        disconnecter=lambda _service: None,
    )
    seen = []

    execute_esxi_source(
        esxi_config(),
        'plan',
        lambda config, hosts, mode: seen.append((config, hosts, mode)),
        client=client,
    )

    assert seen[0][0].source_type == 'esxi'
    assert seen[0][1][0].source == 'esxi'
    assert seen[0][2] == 'plan'


@pytest.mark.parametrize('failing_type', ('esxi', 'proxmox'))
def test_mixed_source_failure_isolation(failing_type):
    calls = []
    configs = (
        esxi_config(),
        replace(
            sample_source_config(),
            id='pve-a',
            source_instance='pve-a',
            legacy_identity_owner=False,
        ),
    )

    def executor(config):
        calls.append(config.id)
        if config.source_type == failing_type:
            raise RuntimeError('safe fake failure')

    dispatch = SourceExecutorDispatch({
        'esxi': executor,
        'proxmox': executor,
    })
    result = run_sources(configs, dispatch.execute)

    assert calls == ['esxi-a', 'pve-a']
    assert result.succeeded == 1
    assert result.failed == 1
