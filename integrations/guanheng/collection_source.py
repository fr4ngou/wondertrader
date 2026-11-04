"""离线生成正式分钟Source；HPR、分析owner及其原身份由原正文完整保留。"""
import ast
from copy import deepcopy
from pathlib import Path

from guanheng_qmt_shm.private_files import create_private_directory, write_private_new
from guanheng_qmt_shm_agent.protocol import canonical
from .collection_deployment import load
from .collection_installation import descriptor
from .market_generation import read_fixed
from .source_history_transport import require


def _settings(raw):
    """只解析生成正文的字面量；不执行导入、回调、SDK或环境访问。"""
    tree = ast.parse(raw.decode('ascii'))
    values = [node.value for node in tree.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == '_settings' for target in node.targets)]
    require(len(values) == 1)
    return ast.literal_eval(values[0])


def prepare_source(request):
    """新建E盘私有完整正文和CAS；更换QST集合，原HPR/v7/v8保持逐值相等。

    request各文件输入使用path/sha256固定身份；agent_root指向当前正式源码闭包。
    目标Source、配对、Journal和任何进程均不修改。Root后续按CAS显式采用。
    """
    # 离线冻结器依赖原Host产品环境；普通核验/读取命令保持原有轻依赖。
    from guanheng_qmt_shm.market_source import render_market_source
    require(type(request) is dict and set(request) == {'schema', 'output', 'source_before', 'roster',
        'hpr_pair_manifest', 'agent_root', 'sdk_metadata', 'stdlib_license'}
        and request['schema'] == 'qmt.minute-source-request.v1')
    root = Path(request['output'])
    require(root.is_absolute() and root.resolve().drive.upper() == 'E:' and not root.exists())
    original = read_fixed(request['source_before']['path'], maximum=2097152,
        identity=request['source_before']['sha256'])
    before = _settings(original)
    names = ('quotes', 'preparation', 'preparation_reconnect_seconds', 'analysis_read', 'analysis_batch_read')
    require(set(names) <= set(before))
    selected = {key: deepcopy(before[key]) for key in names}
    roster = load(request['roster'])
    connection = load(roster['files']['connection'])
    selected['quotes'].update(symbols=connection['symbols'], profile=connection['profile'])
    manifest = load(request['hpr_pair_manifest'])
    require(manifest['schema_version'] == 'qmt.history-preparation-product-pair.v1')
    pair = Path(request['hpr_pair_manifest']['path']).parent
    fragment = _settings(read_fixed(pair / 'strategy.py', maximum=2097152,
        identity=manifest['files']['strategy.py']))
    # 旧产品QST片段仅供原Host内部制品验证；实际新QST两端按roster固定，HPR不换profile或Journal。
    for key in ('preparation', 'preparation_reconnect_seconds'):
        require(selected[key] == fragment[key])
    license_bytes = read_fixed(request['stdlib_license']['path'], maximum=1048576,
        identity=request['stdlib_license']['sha256'])
    strategy, memory = render_market_source(selected, agent_root=request['agent_root'],
        sdk_metadata=load(request['sdk_metadata']), stdlib_license=license_bytes)
    body = strategy.encode('ascii') if isinstance(strategy, str) else strategy
    after = _settings(body)
    for key in names[1:]:
        require(after[key] == before[key])
    require(after['quotes'] == selected['quotes'])
    create_private_directory(root)
    write_private_new(root / 'strategy.py', body)
    write_private_new(root / 'source.before.py', original)
    write_private_new(root / 'MEMORY.json', canonical(memory))
    result = dict(
        schema='qmt.minute-source-adoption.v1',  # 完整正文采用材料，实际Source尚未修改。
        source_before=request['source_before'],  # 原目标完整字节CAS，Root采用前再核。
        source_after=descriptor(root / 'strategy.py'),  # 新完整私有正文，回退同目录source.before.py。
        quote_count=len(connection['symbols']),  # 同一原QST配对集合；不授真实收到行情数量。
        hpr_pair_manifest=request['hpr_pair_manifest'],  # 既有原HPR产品固定引用，其Journal/未知ID保持。
        hpr_unchanged=True, analysis_owners_unchanged=True, trading_owner_removed=True)  # SDK行为仍由原owner实现。
    write_private_new(root / 'SOURCE-CAS.json', canonical(result))
    return descriptor(root / 'SOURCE-CAS.json')
