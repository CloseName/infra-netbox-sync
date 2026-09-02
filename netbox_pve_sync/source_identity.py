"""Pure, versioned identities for objects discovered from a source."""

from dataclasses import dataclass


IDENTITY_SCHEMA_V2 = 'v2'
NO_IDENTITY_MATCH = 0
LEGACY_IDENTITY_MATCH = 1
V2_IDENTITY_MATCH = 2


def _required_text(value, field_name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f'{field_name} must be a non-empty string')


@dataclass(frozen=True, order=True)
class SourceIdentity:
    """Stable identity of one source-owned object."""

    schema: str
    type: str
    instance: str
    kind: str
    external_id: str

    def __post_init__(self):
        if self.schema != IDENTITY_SCHEMA_V2:
            raise ValueError('unsupported source identity schema')

        for field_name in ('type', 'instance', 'kind', 'external_id'):
            _required_text(getattr(self, field_name), field_name)

    def to_record(self):
        """Return the JSON-compatible representation stored in NetBox."""

        return {
            'schema': self.schema,
            'type': self.type,
            'instance': self.instance,
            'kind': self.kind,
            'external_id': self.external_id,
        }

    @classmethod
    def from_record(cls, value):
        """Parse a v2 record, returning ``None`` for another schema."""

        if not isinstance(value, dict) or value.get('schema') != IDENTITY_SCHEMA_V2:
            return None

        try:
            return cls(
                schema=value['schema'],
                type=value['type'],
                instance=value['instance'],
                kind=value['kind'],
                external_id=str(value['external_id']),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError('invalid source identity v2 record') from exc


def _identity(obj, kind, external_id):
    return SourceIdentity(
        schema=IDENTITY_SCHEMA_V2,
        type=str(obj.source),
        instance=str(obj.source_instance),
        kind=kind,
        external_id=str(external_id),
    )


def host_source_identity(host):
    """Build the stable identity of a Proxmox host."""

    return _identity(host, 'host', host.source_id)


def qemu_source_identity(vm):
    """Build a node-independent QEMU identity."""

    return _identity(vm, 'qemu', vm.vmid)


def lxc_source_identity(container):
    """Build a node-independent LXC identity."""

    return _identity(container, 'lxc', container.vmid)


def qemu_nic_source_identity(vm, nic):
    """Build a node-independent QEMU NIC identity."""

    return _identity(vm, 'qemu-nic', f'{vm.vmid}:{nic.name}')


def lxc_nic_source_identity(container, nic):
    """Build a node-independent LXC NIC identity."""

    return _identity(container, 'lxc-nic', f'{container.vmid}:{nic.name}')


def original_name_key(identity):
    """Return the source-aware key used by ``sync_original_names``."""

    return f'{identity.type}/{identity.instance}/{identity.kind}'


def source_identity_match_rank(
        custom_fields,
        desired,
        legacy_source_ids=(),
        legacy_identity_owner=False,
):
    """Match v2 first and permit v1 only for the explicit legacy owner."""

    identities = dict(custom_fields or {}).get('sync_identities')
    if not isinstance(identities, list):
        return NO_IDENTITY_MATCH

    for value in identities:
        parsed = SourceIdentity.from_record(value)
        if parsed == desired:
            return V2_IDENTITY_MATCH

    if not legacy_identity_owner:
        return NO_IDENTITY_MATCH

    wanted = {str(value) for value in legacy_source_ids}
    for value in identities:
        if not isinstance(value, dict) or value.get('schema') == IDENTITY_SCHEMA_V2:
            continue

        if (
            value.get('source') == desired.type
            and str(value.get('source_id', value.get('id'))) in wanted
        ):
            return LEGACY_IDENTITY_MATCH

    return NO_IDENTITY_MATCH
