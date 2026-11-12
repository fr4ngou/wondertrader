"""从冻结策略行和证券资料准备 WT 正常重启材料。"""

import argparse
from hashlib import sha256
from pathlib import Path, PurePosixPath

from .execution_dependency_handoff import GENERIC_SCHEMA, retired_target_symbols, without_retired_filters
from .execution_process import write_installation_manifest
from .execution_recovery import _extension_row, compatible_business_configuration
from .execution_security import required_etf_dependencies
from .managed_local_process import _inspect, _json, _path, _read, _sha
from .service_control import _write_exclusive


def read_reference(path, expected_sha256, maximum):
    raw = _read(_path(str(path)), maximum)
    if sha256(raw).hexdigest() != _sha(expected_sha256):
        raise ValueError(f'启动材料摘要不一致：{path.name}')
    return _json(raw)


def prepare_startup_configuration(template, template_sha256, catalog_path, catalog_sha256, output, *, source_extension=None):
    """在新目录准备可交给原 prepare_transition 的配置，原安装和账本只读。"""
    native = read_reference(template, template_sha256, 256 * 1024)
    marker = native['strategy_extension_origin']
    added = _extension_row(native)
    predecessor_path = Path(marker['file'])
    predecessor = read_reference(predecessor_path, marker['sha256'], 256 * 1024)
    catalog = read_reference(catalog_path, catalog_sha256, 16 * 1024 * 1024)
    securities = added['parameters']['python_strategy']['execution_securities']
    old_app = _path(predecessor['installation_root'])
    source_app = _path(native['installation_root'])
    manifest_path = source_app.parent / 'execution-install.json'
    manifest = _json(_read(manifest_path, 256 * 1024))
    files = manifest['files']
    if manifest.get('schema') != 'guanheng.execution-install.v1' or type(files) is not dict or not 1 <= len(files) <= 512:
        raise ValueError('原安装清单无效')
    contract_file = predecessor['base_data']['contracts']
    old_contracts = _json(_read(old_app / contract_file, 16 * 1024 * 1024))
    old_rows = predecessor['data']['store']['symbols']
    additions, contracts = required_etf_dependencies(catalog, securities, old_rows, old_contracts)
    retirements = retired_target_symbols(marker, predecessor)
    if retirements and 'role_replacement' in predecessor:
        native.pop('role_replacement', None)
    filter_file = predecessor['environment'].get('filters')
    if len({row['symbol'] for row in old_rows + additions}) != len(old_rows) + len(additions):
        raise ValueError('新增行情映射与原来源代码冲突')

    destination = _path(str(output))
    _inspect(destination.parent, directory=True)
    destination.mkdir()
    installation = destination / 'installation'
    app = installation / 'app'
    app.mkdir(parents=True)
    for name, expected in files.items():
        relative = PurePosixPath(name)
        if (relative.parts[:1] != ('app',) or len(relative.parts) < 2 or '..' in relative.parts
                or ':' in name or '\\' in name or relative.as_posix() != name):
            raise ValueError('原安装文件路径无效')
        source = source_app.parent / relative
        raw = _read(source, 256 * 1024 * 1024)
        if sha256(raw).hexdigest() != _sha(expected):
            raise ValueError(f'原安装文件摘要不一致：{name}')
        target = installation / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if name == 'app/' + contract_file:
            updated = _json(raw)
            if updated != old_contracts:
                raise ValueError('候选安装的原合约与前代不一致')
            for market, rows in contracts.items():
                updated.setdefault(market, {}).update(rows)
            _write_exclusive(target, updated)
        elif retirements and name == 'app/' + filter_file:
            original_filter = _read(old_app / filter_file, 16 * 1024 * 1024)
            if raw != original_filter:
                raise ValueError('候选安装的原过滤与前代不一致')
            _write_exclusive(target, without_retired_filters(original_filter, retirements))
        else:
            with target.open('xb') as stream:
                stream.write(raw)

    write_installation_manifest(installation)
    previous_manifest = old_app.parent / 'execution-install.json'
    current_manifest = installation / 'execution-install.json'
    dependencies = {
        'schema': GENERIC_SCHEMA,  # 本代通用依赖接续协议。
        'origin_configuration_sha256': marker['sha256'],  # 前代已绑定原配置摘要。
        'previous_installation': {'file': str(previous_manifest), 'sha256': sha256(_read(previous_manifest, 256 * 1024)).hexdigest()},
        'current_installation': {'file': str(current_manifest), 'sha256': sha256(_read(current_manifest, 256 * 1024)).hexdigest()},
        'reader_additions': additions,  # 本代自动生成的新增行情映射。
        'contract_additions': contracts,  # 本代自动生成的新增合约，按交易所与代码分组。
        'contract_reference': {'file': str(catalog_path), 'sha256': catalog_sha256},  # 原证券资料出处与摘要。
        'source_extension': source_extension,  # 已采用的 Source 证明，None 表示原绑定继续使用。
    }
    handoff = destination / 'dependency-handoff.json'
    marker['dependency_handoff'] = {'file': str(handoff), 'sha256': _write_exclusive(handoff, dependencies)}
    native['installation_root'] = str(app)
    native['data']['store']['symbols'] = old_rows + additions
    if not compatible_business_configuration(native, predecessor):
        raise ValueError('准备的新代业务配置与前代不兼容')
    prepared = destination / 'native-template.json'
    _write_exclusive(prepared, native)
    return prepared


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'security-reference', 'output', 'source-extension'):
        parser.add_argument('--' + name, type=Path, required=name != 'source-extension')
    parser.add_argument('--template-sha256', required=True)
    parser.add_argument('--security-reference-sha256', required=True)
    parser.add_argument('--source-extension-sha256')
    args = parser.parse_args()
    if (args.source_extension is None) != (args.source_extension_sha256 is None):
        parser.error('Source 证明及摘要应成对提供')
    try:
        source_extension = None if args.source_extension is None else read_reference(
            args.source_extension, args.source_extension_sha256, 1024 * 1024)
        prepared = prepare_startup_configuration(args.template, args.template_sha256, args.security_reference,
                                                 args.security_reference_sha256, args.output,
                                                 source_extension=source_extension)
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'准备 WT 启动材料失败：{exc}\n')
    print(prepared)


if __name__ == '__main__':
    main()
