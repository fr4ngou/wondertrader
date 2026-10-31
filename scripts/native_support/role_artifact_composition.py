"""按角色组合独立发行的预建制品，保留各自wheel、锁及来源。"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from . import account_runtime_install as roles


def compose(inputs: Path, inputs_sha256: str, output: Path) -> dict:
    """构建期组合固定制品；不构建wheel、不安装环境、不启动业务进程。

    inputs为qar.role-artifact-selection.v1，roles按app/host/wt稳定顺序选择。
    每项及runtime_tools均显式绑定一个原角色制品根和manifest摘要。
    运行工具独立选择，其来源随包保留；每个角色继续使用自己的精确依赖锁。
    输出沿原qar.role-artifacts.v1，后续安装复用原离线安装器。
    """
    roles._require(roles._sha(inputs) == inputs_sha256, 'role selection identity')
    selected = json.loads(roles._read(inputs).decode('utf8'))
    roles._require(set(selected) == {'schema', 'roles', 'runtime_tools'}
                   and selected['schema'] == 'qar.role-artifact-selection.v1'
                   and type(selected['roles']) is dict, 'role selection schema')
    names = tuple(selected['roles'])
    roles._roles(names)
    sources = {}
    for name, record in [*selected['roles'].items(), ('tools', selected['runtime_tools'])]:
        roles._require(type(record) is dict and set(record) == {'root', 'sha256'},
                       'role artifact reference')
        root = Path(record['root'])
        roles._require(root.is_absolute(), 'absolute role artifact root required')
        document = roles.verify_artifacts(root, record['sha256'])
        roles._require(name == 'tools' or name in document['roles'], 'selected role missing')
        sources[name] = (root.resolve(strict=True), document, record['sha256'])
    roles._separate_paths((output,), tuple(root for root, _, _ in sources.values()))
    roles._require(output.is_absolute() and not output.exists(), 'fresh artifact output required')
    roles._unlinked(output.parent)
    output.mkdir()
    output = output.resolve(strict=True)

    def copy(root, relative, digest):
        source = roles._within(root, root / relative)
        roles._require(roles._sha(source) == digest, 'composition source changed')
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.open('rb') as src, target.open('xb') as dst:
            shutil.copyfileobj(src, dst, 1024 ** 2)
        roles._require(roles._sha(target) == digest and roles._sha(source) == digest,
                       'composition copy identity')

    provenance = {}
    for name, (root, document, identity) in sources.items():
        # 原来源清单作为证据保存，明确表示制品组合，避免伪称一次共同构建安装。
        origin = output / 'origins' / name
        origin.mkdir(parents=True)
        for relative in (roles.ARTIFACT_MANIFEST, 'source-installation.json'):
            raw = roles._read(root / relative)
            expected = identity if relative == roles.ARTIFACT_MANIFEST else document['source_installation_sha256']
            roles._require(hashlib.sha256(raw).hexdigest() == expected, 'origin identity changed')
            (origin / relative).write_bytes(raw)
        provenance[name] = dict(artifact_sha256=identity,
                                source_installation_sha256=document['source_installation_sha256'])
        if name == 'tools':
            for relative in ('qa/runtime_identity.py', 'qa/fixture_control.py', 'runtime-generator.py'):
                copy(root, relative, document['files'][relative])
        else:
            for relative, digest in document['files'].items():
                if relative.startswith(name + '/'):
                    copy(root, relative, digest)

    origin = dict(schema='qar.role-artifact-composition.v1', inputs_sha256=inputs_sha256,
                  sources=provenance)
    roles._json_write(output / 'source-installation.json', origin)
    document = dict(schema='qar.role-artifacts.v1',
                    source_installation_sha256=roles._sha(output / 'source-installation.json'),
                    roles={name: sources[name][1]['roles'][name] for name in names},
                    extras={name: sources[name][1]['extras'][name] for name in names},
                    files=roles._artifact_files(output))
    roles._json_write(output / roles.ARTIFACT_MANIFEST, document)
    identity = roles._sha(output / roles.ARTIFACT_MANIFEST)
    roles.verify_artifacts(output, identity)
    # 组合结束再核来源，保持原发行制品只读及角色选择的一致性。
    roles._require(roles._sha(inputs) == inputs_sha256, 'role selection changed')
    for root, _, expected in sources.values():
        roles.verify_artifacts(root, expected)
    return dict(manifest_sha256=identity, roles=list(names), root=str(output),
                installed=False, business_processes_started=0)
