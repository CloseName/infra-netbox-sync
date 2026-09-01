from .discovery import (
    DiscoveredCPU,
    DiscoveredDisk,
    DiscoveredHost,
    DiscoveredStorage,
)


def discover_hosts(pve_api) -> list[DiscoveredHost]:
    cluster_status = pve_api.cluster.status.get()

    node_ips = {}

    for item in cluster_status:
        if item.get('type') != 'node':
            continue

        node_name = item.get('name')

        if node_name:
            node_ips[node_name] = item.get('ip')

    hosts = []

    for node in pve_api.nodes.get():
        node_name = node['node']

        status = pve_api.nodes(node_name).status.get()
        cpu_info = status.get('cpuinfo', {})
        memory = status.get('memory', {})

        cpu = DiscoveredCPU(
            model=cpu_info.get('model'),
            vendor=cpu_info.get('vendor'),
            sockets=int(cpu_info.get('sockets', 0)),
            cores=int(cpu_info.get('cores', 0)),
            logical_cpus=int(cpu_info.get('cpus', 0)),
        )

        disks = []

        for disk in pve_api.nodes(node_name).disks.list.get():
            disks.append(
                DiscoveredDisk(
                    path=disk.get('devpath', disk.get('path', '')),
                    model=disk.get('model'),
                    serial=disk.get('serial'),
                    size_bytes=int(disk.get('size', 0)),
                    disk_type=disk.get('type'),
                    health=disk.get('health'),
                )
            )

        storages = []

        for storage in pve_api.nodes(node_name).storage.get():
            storages.append(
                DiscoveredStorage(
                    name=storage['storage'],
                    storage_type=storage.get('type'),
                    content=storage.get('content'),
                    total_bytes=int(storage.get('total', 0)),
                    used_bytes=int(storage.get('used', 0)),
                    available_bytes=int(storage.get('avail', 0)),
                    active=bool(storage.get('active')),
                )
            )

        pve_version = status.get('pveversion')

        if pve_version and pve_version.startswith('pve-manager/'):
            pve_version = pve_version.split('/', 2)[1]

        hosts.append(
            DiscoveredHost(
                source='proxmox',
                source_id=node_name,
                original_name=node_name,
                normalized_name=node_name.upper(),
                management_ip=node_ips.get(node_name),
                hypervisor='Proxmox VE',
                hypervisor_version=pve_version,
                cpu=cpu,
                memory_bytes=int(memory.get('total', 0)),
                disks=disks,
                storages=storages,
            )
        )

    return hosts
