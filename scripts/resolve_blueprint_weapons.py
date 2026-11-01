#!/usr/bin/env python3
"""Resolve firing endpoints from exported Foxhole Blueprints, read-only.

No display-name inference, numerical-proxy lookups, or production writes.
All exports and the game PAK remain private; only derived output is emitted.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path

DATA_ROOT = Path('Data')


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(root, name):
    path = root / DATA_ROOT / (name + '.json')
    objects = load(path)
    if not isinstance(objects, list) or len(objects) != 1 or not isinstance(objects[0].get('Rows'), dict):
        raise ValueError('Invalid DataTable: ' + name)
    return objects[0]['Rows'], path


def explicit_property(root, asset, names, trail=None):
    """Find nearest class-default property along explicit exported parent links."""
    trail = [] if trail is None else trail
    asset = asset.resolve()
    if not asset.is_relative_to(root.resolve()) or asset in trail:
        raise ValueError('Unsafe or cyclic Blueprint reference: ' + str(asset))
    if not asset.is_file():
        raise ValueError('Referenced Blueprint not exported: ' + str(asset))
    objects = load(asset)
    cls = [x for x in objects if x.get('Type') == 'BlueprintGeneratedClass']
    defaults = [x for x in objects if str(x.get('Name', '')).startswith('Default__')]
    if len(cls) != 1 or len(defaults) != 1:
        raise ValueError('Invalid Blueprint class/default layout: ' + str(asset))
    props = defaults[0].get('Properties') or {}
    for name in names:
        if name in props:
            return props[name], {'asset': asset.relative_to(root).as_posix(),
                                 'property': 'Default__/' + name,
                                 'sha256': sha256(asset)}
    parent = cls[0].get('SuperStruct') or cls[0].get('Super') or {}
    ref = parent.get('ObjectPath', '')
    if ref.startswith('War/Content/Blueprints/'):
        relative = ref.removeprefix('War/Content/Blueprints/').split('.', 1)[0] + '.json'
        return explicit_property(root, root / relative, names, trail + [asset])
    return None, None


def numeric(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value > 0


def resolve(root: Path, vehicle: Path, build_id: str, kinetic_factor=1.25):
    root = root.resolve()
    vehicle = (root / vehicle).resolve()
    if not vehicle.is_relative_to(root) or not vehicle.is_file():
        raise ValueError('Vehicle path must be an exported JSON inside source root')
    if not build_id.isdecimal():
        raise ValueError('A numeric pinned game build ID is required')
    ammo, ammo_path = table(root, 'BPAmmoDynamicData')
    mount, mount_path = table(root, 'BPMountDynamicData')
    objs = load(vehicle)
    defaults = [x for x in objs if str(x.get('Name', '')).startswith('Default__')]
    if len(defaults) != 1:
        raise ValueError('Missing or duplicate vehicle class default')
    props = defaults[0].get('Properties') or {}
    candidates = []
    cfgs = props.get('WeaponConfigs')
    if cfgs is not None:
        if not isinstance(cfgs, list):
            raise ValueError('Malformed WeaponConfigs')
        for i, cfg in enumerate(cfgs):
            if not isinstance(cfg, dict):
                raise ValueError('Malformed WeaponConfigs entry')
            candidates.append({'endpoint': 'WeaponConfigs/' + str(i),
                               'ammo': cfg.get('AmmoCodeName'), 'mount': cfg.get('WeaponCodeName'),
                               'edges': [{'asset': vehicle.relative_to(root).as_posix(),
                                          'property': f'Default__/WeaponConfigs/{i}/AmmoCodeName',
                                          'value': cfg.get('AmmoCodeName')},
                                         {'asset': vehicle.relative_to(root).as_posix(),
                                          'property': f'Default__/WeaponConfigs/{i}/WeaponCodeName',
                                          'value': cfg.get('WeaponCodeName')}],
                               'source_sha256': sha256(vehicle)})
    else:
        for obj in objs:
            if obj.get('Type') != 'VehicleSeatComponent':
                continue
            p = obj.get('Properties') or {}
            mount_id = p.get('MountCodeName')
            component = p.get('MountComponent') or {}
            ref = component.get('ObjectPath') if isinstance(component, dict) else None
            if not mount_id or not ref:
                continue
            entry = {'endpoint': obj.get('Name'), 'mount': mount_id,
                     'edges': [{'asset': vehicle.relative_to(root).as_posix(),
                                'property': obj.get('Name') + '/Properties/MountCodeName',
                                'value': mount_id},
                               {'asset': vehicle.relative_to(root).as_posix(),
                                'property': obj.get('Name') + '/Properties/MountComponent/ObjectPath',
                                'value': ref}], 'source_sha256': sha256(vehicle)}
            if not ref.startswith('War/Content/Blueprints/'):
                entry['problem'] = 'non_exportable_component_reference'
            else:
                comp_path = root / (ref.removeprefix('War/Content/Blueprints/').split('.', 1)[0] + '.json')
                try:
                    found, evidence = explicit_property(root, comp_path, ('AmmoName', 'MultiAmmo'))
                    if evidence:
                        entry['edges'].append(evidence)
                    if isinstance(found, str):
                        entry['ammo'] = found
                    elif isinstance(found, dict) and isinstance(found.get('CompatibleAmmoNames'), list):
                        opts = found['CompatibleAmmoNames']
                        if len(opts) == 1:
                            entry['ammo'] = opts[0]
                        else:
                            entry['problem'] = 'multiple_ammunition_options'
                    else:
                        entry['problem'] = 'ammo_reference_missing'
                except ValueError as err:
                    entry['problem'] = str(err)
            candidates.append(entry)
    result = []
    for c in candidates:
        id_ammo, id_mount = c.get('ammo'), c.get('mount')
        base = {'endpoint': c['endpoint'], 'ammo': id_ammo, 'mount': id_mount,
                'edges': c['edges'], 'source_sha256': c['source_sha256'],
                'status': 'unresolved', 'safe_for_unattended_publication': False}
        if c.get('problem'):
            base['reason'] = c['problem']
        elif not isinstance(id_mount, str) or id_mount not in mount:
            base['reason'] = 'named_mount_row_missing'
        elif not isinstance(id_ammo, str) or id_ammo not in ammo:
            base['reason'] = 'named_ammo_row_missing'
        else:
            m, a = mount[id_mount].get('DamageMultiplier'), ammo[id_ammo].get('Damage')
            dtype = (ammo[id_ammo].get('DamageType') or {}).get('ObjectName', '')
            if not numeric(m) or not numeric(a) or not isinstance(dtype, str):
                base['reason'] = 'invalid_numeric_or_damage_type'
            else:
                factor = kinetic_factor if 'Kinetic' in dtype or id_ammo == 'AircraftAmmo' else 1.0
                if not numeric(factor):
                    raise ValueError('Invalid gameplay factor')
                base.update({'status': 'resolved_with_manual_gameplay_rule' if factor != 1 else 'resolved_from_exported_tables',
                             'damage': a * m * factor, 'ammo_damage': a, 'mount_multiplier': m,
                             'gameplay_factor': factor, 'gameplay_factor_provenance': 'manual_rule_kinetic_1_25' if factor != 1 else 'none',
                             'source_rows': [{'asset': ammo_path.relative_to(root).as_posix(), 'row': id_ammo,
                                              'property': 'Damage', 'sha256': sha256(ammo_path)},
                                             {'asset': mount_path.relative_to(root).as_posix(), 'row': id_mount,
                                              'property': 'DamageMultiplier', 'sha256': sha256(mount_path)}]})
        result.append(base)
    return {'schema_version': 1, 'build_id': build_id,
            'vehicle_asset': vehicle.relative_to(root).as_posix(),
            'status': 'review_only_no_automatic_publication', 'endpoints': result}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source-root', type=Path, required=True,
                   help='Private export/War/Content/Blueprints directory')
    p.add_argument('--vehicle', type=Path, required=True,
                   help='Vehicle Blueprint JSON path relative to source root')
    p.add_argument('--build-id', required=True)
    p.add_argument('--output', type=Path)
    args = p.parse_args()
    result = resolve(args.source_root, args.vehicle, args.build_id)
    data = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.output:
        args.output.write_text(data, encoding='utf-8')
    else:
        print(data, end='')


if __name__ == '__main__':
    main()
