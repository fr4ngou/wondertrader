# -*- coding: utf-8 -*-
"""Internal private migration authorized by the owner on 2026-10-22.

Original source notices are retained. No public redistribution license is
inferred. Paths below are static provenance only, never runtime dependencies.
Adaptation boundary and new bound-read rules belong to the repository QSW spec.
"""
SOURCE_FILES = {'app.py': {'source': 'src/qmt_platform/services/broker_host/app.py', 'source_sha256': '405c93fec78d6a07ecf50203de292efc76b8c1d20f27b882d230905e389eeebc'}, 'auth.py': {'source': 'qmt_agent/gateway/auth.py', 'source_sha256': '1f5c71268a297124316b1a3306bbed9f0982a874830e0e43403d0dc2160a89f5'}, 'bootstrap.py': {'source': 'src/qmt_platform/services/broker_host/__main__.py', 'source_sha256': '6c706a9a2413b5d12b0e9caffc8894421bdd30ef70c5ea7d74ac55a7dcbf4211'}, 'contracts.py': {'source': 'src/qmt_platform/common/contracts.py', 'source_sha256': '69429357442dd734d8f9b43885e3ace52a3e342d9b2aa1ec3cb86d8aab2478cc'}, 'control.py': {'source': 'src/qmt_platform/services/broker_host/control.py', 'source_sha256': '8224c9c918280833f673c787dd5bf7df5167d186303b16a2ceb2452866caa484'}, 'domain.py': {'source': 'src/qmt_platform/services/broker_host/domain.py', 'source_sha256': 'fb6a057c99daf75f4f5f515cd86e6a30d77c78981bfc80291c68816af2953be9'}, 'journal.py': {'source': 'src/qmt_platform/services/broker_host/journal.py', 'source_sha256': '354efd200292a54ac8e9701dce0cd43ea1e242e888a6e560910944f144a9d14d'}, 'material_integrity.py': {'source': 'src/qmt_platform/services/broker_host/material_integrity.py', 'source_sha256': 'f86c3edc4cee288cd7df30141c7be0d1dae2e1fef448e40c7c86cd20281ab10b'}, 'pair.py': {'source': 'src/qmt_platform/services/broker_host/bundle.py', 'source_sha256': '21f633d6cc6e55fe73c4130f3d7d7bfc44215bebacb79c024b94b23d4eb33149'}, 'policy.py': {'source': 'src/qmt_platform/common/operation_policy.py', 'source_sha256': 'f877998249c0864afef46f16ff6018ac4210e5377c4205ceb5508bd19250522f'}, 'private_files.py': {'source': 'src/qmt_platform/services/broker_host/private_files.py', 'source_sha256': 'c36de8a151df304a061ed28accb2a2e82188c925f7d3cbc8f40fe2df1407433f'}, 'runtime.py': {'source': 'src/qmt_platform/services/broker_host/runtime.py', 'source_sha256': '6dd92396e4a9b9dac5e70724583061a8582668cd19711152e0da2c38f3fa9bb6'}}

# 内存依赖生成器迁入；生成正文和标准库许可身份由私有配对manifest拥有。
MEMORY_SOURCE_FILES = {
  "memory_runtime.py": {
    "source": "src/qmt_platform/services/broker_host/memory_runtime.py",
    "source_sha256": "59afce9e828aa45d59a3f5f0230c842528d096c76908eb8e8dc250ba1515c73c",
    "adaptation": "independent Agent namespace; builtin transport; private parent-package ordering; exact datetime; CPython inspect static helpers; bounded source/binary/license identity"
  }
}
