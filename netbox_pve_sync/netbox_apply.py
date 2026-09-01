import ipaddress


class HostApplyError(RuntimeError):
    pass


def _object_id(value):
    if value is None:
        return None

    if isinstance(value, int):
        return value

    if isinstance(value, dict):
        return value.get('id')

    return getattr(value, 'id', None)


def _choice_value(value):
    if value is None:
        return None

    if isinstance(value, str):
        return value

    if isinstance(value, dict):
        return value.get('value')

    return getattr(value, 'value', value)


def _canonical_address(value):
    return str(
        ipaddress.ip_interface(
            str(value)
        )
    )


def _address_ip(value):
    return str(
        ipaddress.ip_interface(
            str(value)
        ).ip
    )


def _required(endpoint, description, **filters):
    result = endpoint.get(**filters)

    if result is None:
        raise HostApplyError(
            f'NetBox prerequisite not found: '
            f'{description} filters={filters}'
        )

    return result


def _resolve_cluster(
        nb_api,
        site,
        cluster_type,
        cluster_name,
):
    matches = []

    for cluster in nb_api.virtualization.clusters.filter(
        name=cluster_name
    ):
        data = cluster.serialize()

        if (
            _object_id(data.get('type'))
            == cluster_type.id
            and data.get('scope_type')
            == 'dcim.site'
            and data.get('scope_id')
            == site.id
        ):
            matches.append(cluster)

    if len(matches) != 1:
        raise HostApplyError(
            f'Expected exactly one target cluster '
            f'{cluster_name!r}; found {len(matches)}'
        )

    return matches[0]


def _resolve_device(
        nb_api,
        host,
        site,
):
    matches = list(
        nb_api.dcim.devices.filter(
            name=host.normalized_name
        )
    )

    if not matches:
        return None

    if len(matches) != 1:
        raise HostApplyError(
            f'Device name conflict: '
            f'{host.normalized_name!r} '
            f'matches={len(matches)}'
        )

    device = matches[0]
    data = device.serialize()

    existing_site = _object_id(
        data.get('site')
    )

    if existing_site != site.id:
        raise HostApplyError(
            f'Device {host.normalized_name!r} '
            f'already exists outside target site: '
            f'site_id={existing_site}'
        )

    return device


def _load_existing_interfaces(
        nb_api,
        device,
):
    if device is None:
        return {}

    result = {}

    for interface in nb_api.dcim.interfaces.filter(
        device_id=device.id
    ):
        if interface.name in result:
            raise HostApplyError(
                f'Duplicate interface '
                f'{interface.name!r} '
                f'on device id={device.id}'
            )

        result[interface.name] = interface

    return result


def _find_ip_matches(
        nb_api,
        address,
):
    canonical = _canonical_address(address)

    result = []

    for candidate in nb_api.ipam.ip_addresses.filter(
        address=canonical
    ):
        if (
            _canonical_address(candidate.address)
            == canonical
        ):
            result.append(candidate)

    return result


def _management_binding(host):
    matches = []

    for interface in host.interfaces:
        for address in interface.addresses:
            if (
                _address_ip(address)
                == host.management_ip
            ):
                matches.append(
                    (
                        interface.name,
                        _canonical_address(address),
                    )
                )

    if len(matches) != 1:
        raise HostApplyError(
            f'Expected exactly one management '
            f'address for {host.normalized_name}; '
            f'found {len(matches)}'
        )

    return matches[0]


def _desired_interface_type(
        interface,
):
    if interface.interface_type in {
        'bridge',
        'vlan',
    }:
        return 'virtual'

    return 'other'


def _preflight_host(
        nb_api,
        host,
        site,
):
    device = _resolve_device(
        nb_api,
        host,
        site,
    )

    existing_interfaces = (
        _load_existing_interfaces(
            nb_api,
            device,
        )
    )

    discovered_names = [
        interface.name
        for interface in host.interfaces
    ]

    if (
        len(discovered_names)
        != len(set(discovered_names))
    ):
        raise HostApplyError(
            f'Duplicate discovered interface '
            f'name on {host.normalized_name}'
        )

    management_interface, management_address = (
        _management_binding(host)
    )

    addresses = []

    for interface in host.interfaces:
        expected_interface = (
            existing_interfaces.get(
                interface.name
            )
        )

        for raw_address in interface.addresses:
            address = _canonical_address(
                raw_address
            )

            matches = _find_ip_matches(
                nb_api,
                address,
            )

            if len(matches) > 1:
                raise HostApplyError(
                    f'IP conflict: {address} '
                    f'matches={len(matches)}'
                )

            if len(matches) == 1:
                ip = matches[0]
                data = ip.serialize()

                assigned_type = data.get(
                    'assigned_object_type'
                )

                assigned_id = data.get(
                    'assigned_object_id'
                )

                if (
                    assigned_type is None
                    and assigned_id is None
                ):
                    pass

                elif (
                    expected_interface is not None
                    and assigned_type
                    == 'dcim.interface'
                    and assigned_id
                    == expected_interface.id
                ):
                    pass

                else:
                    raise HostApplyError(
                        f'IP {address} is already '
                        f'assigned to '
                        f'{assigned_type}:'
                        f'{assigned_id}'
                    )

            addresses.append(
                (
                    interface.name,
                    address,
                )
            )

    return {
        'host': host,
        'device': device,
        'interfaces': existing_interfaces,
        'management_interface':
            management_interface,
        'management_address':
            management_address,
        'addresses': addresses,
    }


def _device_changes(
        device,
        *,
        site,
        role,
        platform,
        device_type,
        cluster,
):
    data = device.serialize()
    changes = {}

    expected = {
        'site': site.id,
        'role': role.id,
        'platform': platform.id,
        'device_type': device_type.id,
        'cluster': cluster.id,
    }

    for field, desired_id in expected.items():
        if (
            _object_id(data.get(field))
            != desired_id
        ):
            changes[field] = desired_id

    return changes


def _interface_changes(
        interface,
        discovered,
):
    data = interface.serialize()

    desired_type = (
        _desired_interface_type(
            discovered
        )
    )

    changes = {}

    current_type = _choice_value(
        data.get('type')
    )

    if current_type != desired_type:
        changes['type'] = desired_type

    desired_enabled = bool(
        discovered.autostart
    )

    if (
        bool(data.get('enabled'))
        != desired_enabled
    ):
        changes['enabled'] = (
            desired_enabled
        )

    if discovered.comments is not None:
        current_description = (
            data.get('description') or ''
        )

        if (
            current_description
            != discovered.comments
        ):
            changes['description'] = (
                discovered.comments
            )

    return changes


def apply_hosts(
        nb_api,
        hosts,
        config,
        *,
        confirmed=False,
):
    site = _required(
        nb_api.dcim.sites,
        'site',
        slug=config.site_slug,
    )

    role = _required(
        nb_api.dcim.device_roles,
        'device role',
        slug=config.device_role_slug,
    )

    platform = _required(
        nb_api.dcim.platforms,
        'platform',
        slug=config.platform_slug,
    )

    device_type = _required(
        nb_api.dcim.device_types,
        'device type',
        slug=config.device_type_slug,
    )

    cluster_type = _required(
        nb_api.virtualization.cluster_types,
        'cluster type',
        slug=config.cluster_type_slug,
    )

    cluster = _resolve_cluster(
        nb_api,
        site,
        cluster_type,
        config.cluster_name,
    )

    contexts = []

    for host in hosts:
        contexts.append(
            _preflight_host(
                nb_api,
                host,
                site,
            )
        )

    print('=== HOST APPLY PRECHECK ===')
    print(
        f'target_site={site.name} '
        f'cluster={cluster.name}'
    )
    print()

    for context in contexts:
        host = context['host']
        device = context['device']

        action = (
            'MATCH'
            if device is not None
            else 'CREATE'
        )

        print(
            f'{action} DEVICE '
            f'{host.normalized_name}'
        )

        print(
            f'  interfaces='
            f'{len(host.interfaces)}'
        )

        print(
            f'  addresses='
            f'{len(context["addresses"])}'
        )

        print(
            f'  management='
            f'{context["management_interface"]}:'
            f'{context["management_address"]}'
        )

    print()
    print('PRECHECK PASSED')

    if not confirmed:
        print(
            'APPLY_CONFIRM=HOST_WRITE '
            'is not set.'
        )
        print(
            'No changes were written '
            'to NetBox.'
        )
        return

    print()
    print('=== HOST APPLY ===')

    created = 0
    updated = 0
    skipped = 0

    for context in contexts:
        host = context['host']
        device = context['device']

        if device is None:
            device = (
                nb_api.dcim.devices.create(
                    name=host.normalized_name,
                    device_type=device_type.id,
                    role=role.id,
                    site=site.id,
                    platform=platform.id,
                    cluster=cluster.id,
                    status='active',
                )
            )

            created += 1

            print(
                f'CREATE DEVICE '
                f'id={device.id} '
                f'name={device.name}'
            )

        else:
            changes = _device_changes(
                device,
                site=site,
                role=role,
                platform=platform,
                device_type=device_type,
                cluster=cluster,
            )

            if changes:
                device.update(changes)
                updated += 1

                print(
                    f'UPDATE DEVICE '
                    f'id={device.id} '
                    f'fields={",".join(changes)}'
                )
            else:
                skipped += 1

                print(
                    f'SKIP DEVICE '
                    f'id={device.id}'
                )

        interfaces = {}

        existing_interfaces = (
            _load_existing_interfaces(
                nb_api,
                device,
            )
        )

        for discovered in sorted(
            host.interfaces,
            key=lambda item: item.name,
        ):
            interface = (
                existing_interfaces.get(
                    discovered.name
                )
            )

            desired_type = (
                _desired_interface_type(
                    discovered
                )
            )

            if interface is None:
                payload = {
                    'device': device.id,
                    'name': discovered.name,
                    'type': desired_type,
                    'enabled': bool(
                        discovered.autostart
                    ),
                }

                if (
                    discovered.comments
                    is not None
                ):
                    payload['description'] = (
                        discovered.comments
                    )

                interface = (
                    nb_api.dcim.interfaces.create(
                        **payload
                    )
                )

                created += 1

                print(
                    f'CREATE INTERFACE '
                    f'id={interface.id} '
                    f'name={interface.name}'
                )

            else:
                changes = (
                    _interface_changes(
                        interface,
                        discovered,
                    )
                )

                if changes:
                    interface.update(
                        changes
                    )

                    updated += 1

                    print(
                        f'UPDATE INTERFACE '
                        f'id={interface.id} '
                        f'name={interface.name} '
                        f'fields='
                        f'{",".join(changes)}'
                    )
                else:
                    skipped += 1

                    print(
                        f'SKIP INTERFACE '
                        f'id={interface.id} '
                        f'name={interface.name}'
                    )

            interfaces[
                discovered.name
            ] = interface

        ip_objects = {}

        for interface_name, address in (
            context['addresses']
        ):
            interface = interfaces[
                interface_name
            ]

            matches = _find_ip_matches(
                nb_api,
                address,
            )

            if len(matches) > 1:
                raise HostApplyError(
                    f'IP conflict appeared '
                    f'during apply: '
                    f'{address}'
                )

            if not matches:
                ip = (
                    nb_api.ipam.ip_addresses.create(
                        address=address,
                        status='active',
                        assigned_object_type=(
                            'dcim.interface'
                        ),
                        assigned_object_id=(
                            interface.id
                        ),
                    )
                )

                created += 1

                print(
                    f'CREATE IP '
                    f'id={ip.id} '
                    f'address={address} '
                    f'interface='
                    f'{interface_name}'
                )

            else:
                ip = matches[0]
                data = ip.serialize()

                assigned_type = data.get(
                    'assigned_object_type'
                )
                assigned_id = data.get(
                    'assigned_object_id'
                )

                if (
                    assigned_type is None
                    and assigned_id is None
                ):
                    ip.update({
                        'assigned_object_type':
                            'dcim.interface',
                        'assigned_object_id':
                            interface.id,
                    })

                    updated += 1

                    print(
                        f'ASSIGN IP '
                        f'id={ip.id} '
                        f'address={address} '
                        f'interface='
                        f'{interface_name}'
                    )

                elif (
                    assigned_type
                    == 'dcim.interface'
                    and assigned_id
                    == interface.id
                ):
                    skipped += 1

                    print(
                        f'SKIP IP '
                        f'id={ip.id} '
                        f'address={address}'
                    )

                else:
                    raise HostApplyError(
                        f'IP assignment changed '
                        f'after preflight: '
                        f'{address} -> '
                        f'{assigned_type}:'
                        f'{assigned_id}'
                    )

            ip_objects[address] = ip

        management_address = (
            context[
                'management_address'
            ]
        )

        primary_ip = ip_objects[
            management_address
        ]

        current_device = (
            nb_api.dcim.devices.get(
                device.id
            )
        )

        current_primary = _object_id(
            current_device.serialize().get(
                'primary_ip4'
            )
        )

        if current_primary != primary_ip.id:
            current_device.update({
                'primary_ip4':
                    primary_ip.id,
            })

            updated += 1

            print(
                f'SET PRIMARY IPv4 '
                f'device={device.name} '
                f'address='
                f'{management_address}'
            )

        else:
            skipped += 1

            print(
                f'SKIP PRIMARY IPv4 '
                f'device={device.name}'
            )

    print()
    print(
        f'APPLY SUMMARY '
        f'created={created} '
        f'updated={updated} '
        f'skipped={skipped}'
    )
