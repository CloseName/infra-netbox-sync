import ipaddress
from dataclasses import dataclass

import pynetbox


@dataclass
class NetBoxTargetConfig:
    site_slug: str
    device_role_slug: str
    platform_slug: str
    device_type_slug: str
    cluster_type_slug: str
    cluster_name: str


def _ip_without_prefix(value):
    if not value:
        return None

    try:
        return str(ipaddress.ip_interface(str(value)).ip)
    except ValueError:
        return str(value).split('/', 1)[0]


def _find_device_match(nb_objects: dict, host):
    """
    Transitional matching policy.

    Later source_id/provider serial/MAC will have higher priority.
    For now:
      1. management IP
      2. normalized device name
    """

    if host.management_ip:
        for device in nb_objects['devices'].values():
            device_ip = _ip_without_prefix(
                getattr(device, 'primary_ip4', None)
            )

            if device_ip == host.management_ip:
                return device, 'management_ip'

    device = nb_objects['devices'].get(
        host.normalized_name.lower()
    )

    if device is not None:
        return device, 'normalized_name'

    return None, None


def _get_required(endpoint, *, description: str, **filters):
    result = endpoint.get(**filters)

    if result is None:
        raise RuntimeError(
            f'NetBox prerequisite not found: {description} '
            f'filters={filters}'
        )

    return result


def plan_hosts(
        nb_api: pynetbox.api,
        nb_objects: dict,
        hosts: list,
        config: NetBoxTargetConfig,
) -> None:

    site = _get_required(
        nb_api.dcim.sites,
        description='site',
        slug=config.site_slug,
    )

    role = _get_required(
        nb_api.dcim.device_roles,
        description='device role',
        slug=config.device_role_slug,
    )

    platform = _get_required(
        nb_api.dcim.platforms,
        description='platform',
        slug=config.platform_slug,
    )

    device_type = _get_required(
        nb_api.dcim.device_types,
        description='device type',
        slug=config.device_type_slug,
    )

    cluster_type = _get_required(
        nb_api.virtualization.cluster_types,
        description='cluster type',
        slug=config.cluster_type_slug,
    )

    cluster = None

    for candidate in nb_api.virtualization.clusters.filter(
        name=config.cluster_name
    ):
        serialized = candidate.serialize()

        if (
            serialized.get('type') == cluster_type.id
            and serialized.get('scope_type') == 'dcim.site'
            and serialized.get('scope_id') == site.id
        ):
            cluster = candidate
            break

    print('=== NETBOX INFRASTRUCTURE PLAN ===')
    print('No changes will be written to NetBox.')
    print()

    print('TARGET CONFIG')
    print(f'  site:         {site.name} (id={site.id})')
    print(f'  device_role:  {role.name} (id={role.id})')
    print(f'  platform:     {platform.name} (id={platform.id})')
    print(
        f'  device_type:  '
        f'{getattr(device_type, "model", None) or device_type.slug} '
        f'(id={device_type.id})'
    )
    print(
        f'  cluster_type: {cluster_type.name} '
        f'(id={cluster_type.id})'
    )
    print()

    if cluster is None:
        print(
            f'CREATE CLUSTER name={config.cluster_name} '
            f'type={cluster_type.name} '
            f'scope=dcim.site:{site.id}'
        )
    else:
        print(
            f'MATCH CLUSTER id={cluster.id} '
            f'name={cluster.name} '
            f'reason=name+type+scope'
        )

    print()

    for host in hosts:
        print(
            f'HOST source={host.source} '
            f'source_id={host.source_id}'
        )

        device, reason = _find_device_match(
            nb_objects,
            host,
        )

        if device is None:
            print(
                f'  CREATE DEVICE '
                f'name={host.normalized_name}'
            )
        else:
            print(
                f'  MATCH DEVICE '
                f'id={device.id} '
                f'name={device.name} '
                f'reason={reason}'
            )

        print(f'  SET site={site.name}')
        print(f'  SET role={role.name}')
        print(f'  SET platform={platform.name}')
        print(f'  SET device_type={device_type.slug}')
        print(f'  SET cluster={config.cluster_name}')
        print(
            f'  SET primary_ip4='
            f'{host.management_ip or "-"}'
        )

        print()
        print('  DISCOVERED HARDWARE')
        print(f'    cpu_model={host.cpu.model or "-"}')
        print(f'    cpu_vendor={host.cpu.vendor or "-"}')
        print(f'    cpu_sockets={host.cpu.sockets}')
        print(f'    cpu_cores={host.cpu.cores}')
        print(f'    cpu_threads={host.cpu.logical_cpus}')
        print(
            f'    memory_mib='
            f'{host.memory_bytes // 1024**2}'
        )
        print(
            f'    physical_disk_count='
            f'{len(host.disks)}'
        )
        print(
            f'    physical_disk_raw_gib='
            f'{sum(d.size_bytes for d in host.disks) / 1024**3:.2f}'
        )
        print(
            f'    hypervisor_version='
            f'{host.hypervisor_version or "-"}'
        )

        print()
        print(
            f'  GUESTS qemu={len(host.virtual_machines)} '
            f'lxc={len(host.containers)}'
        )

        print()
