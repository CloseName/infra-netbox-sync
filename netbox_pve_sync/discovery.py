from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DiscoveredDisk:
    path: str
    model: Optional[str]
    serial: Optional[str]
    size_bytes: int
    disk_type: Optional[str]
    health: Optional[str]


@dataclass
class DiscoveredStorage:
    name: str
    storage_type: Optional[str]
    content: Optional[str]
    total_bytes: int
    used_bytes: int
    available_bytes: int
    active: bool


@dataclass
class DiscoveredCPU:
    model: Optional[str]
    vendor: Optional[str]
    sockets: int
    cores: int
    logical_cpus: int


@dataclass
class DiscoveredHost:
    source: str
    source_id: str

    original_name: str
    normalized_name: str

    management_ip: Optional[str]

    hypervisor: str
    hypervisor_version: Optional[str]

    cpu: DiscoveredCPU
    memory_bytes: int

    disks: list[DiscoveredDisk] = field(default_factory=list)
    storages: list[DiscoveredStorage] = field(default_factory=list)
    virtual_machines: list['DiscoveredVirtualMachine'] = field(default_factory=list)


@dataclass
class DiscoveredVirtualDisk:
    name: str
    storage: Optional[str]
    size_bytes: int


@dataclass
class DiscoveredInterface:
    name: str
    mac_address: Optional[str]
    bridge: Optional[str]
    vlan_id: Optional[int]
    ip_addresses: list[str] = field(default_factory=list)


@dataclass
class DiscoveredVirtualMachine:
    source: str
    source_id: str
    node_source_id: str

    vmid: int
    original_name: str
    normalized_name: str

    status: str
    vcpus: int
    memory_bytes: int
    autostart: bool

    disks: list[DiscoveredVirtualDisk] = field(default_factory=list)
    interfaces: list[DiscoveredInterface] = field(default_factory=list)
