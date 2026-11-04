"""分钟采用的日线读方接线；原日线任务、动态发布及来源事实由既有owner保持。"""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from guanheng_qmt_shm_agent.protocol import decode
from guanheng_qmt_shm.private_files import create_private_directory
from .collection_deployment import load
from .collection_installation import descriptor
from .market_generation import read_fixed, read_generation
from .source_history_transport import require


def prepare_daily_connection(selected, supplied_base, program, root, producer, minute_source, save):
    """纯准备正式日线SMP及新角色配置；返回固定文件、原件身份与保留范围。

    selected指向实际WT服务控制配置，supplied_base为当前Snapshot.base的固定捕获。
    同线程无进程/网络操作。新角色使用全新控制根及角色CURRENT，市场发布CURRENT、
    daily_update、任务目录、保护槽与环境文件保持原件；正式启停由Root统一执行。
    """
    old_role = load(selected)
    require(old_role['schema'] == 'guanheng.wt-service.v1')
    current_path = Path(old_role['current_file'])
    current = decode(read_fixed(current_path, maximum=16384))
    runtime = dict(path=old_role['bootstrap_configuration'], sha256=old_role['bootstrap_configuration_sha256'])
    if current['wt_configuration_sha256'] != runtime['sha256']:
        # 普通重启可能产生新一代配置，沿原generation记录定位实际代，避免采用过期bootstrap。
        generation = Path(old_role['generation_root']) / current['wt_control_id'] / 'generation.json'
        record = decode(read_fixed(generation, maximum=16384))
        require(record['control_id'] == current['wt_control_id'])
        runtime = dict(path=record['runtime_configuration'], sha256=record['runtime_configuration_sha256'])
    require(runtime['sha256'] == current['wt_configuration_sha256'])
    before_runtime = load(runtime)
    require(set(before_runtime['components']) == {'history'})
    component = before_runtime['components']['history']
    process_ref = dict(path=component['descriptor'], sha256=component['sha256'])
    before_process = load(process_ref)
    smp_ref = dict(path=before_process['configuration'], sha256=before_process['configuration_sha256'])
    before_smp = load(smp_ref)
    require(before_smp['schema'] == 'guanheng.source-market-service.v1' and 'daily_update' in before_smp)
    original_read = load(before_smp['source_configuration'])
    require(original_read['mode'] == 'source-market-current')
    pointer, pointer_sha = read_generation(original_read['current_file'])
    snapshot = load(pointer['configuration'])
    require(snapshot['mode'] == 'source-market-snapshot' and load(supplied_base) == snapshot['base'])
    leaf = snapshot['base']
    while leaf.get('mode') == 'source-daily-overlay':
        leaf = leaf['base']
    require(leaf.get('mode') == 'source-collected')
    minute_base = deepcopy(leaf)
    for key in ('collection', 'minute_native'):
        minute_base[key] = deepcopy(minute_source[key])
    recovered = dict(mode='source-recovered', base=minute_base, producer=producer,
        delegate=original_read)  # 日线/资料/事实/快照均沿原动态读方，只有分钟查询进入恢复读取。
    files = {'daily_source': save('daily-source.json', recovered)}
    smp = dict(before_smp, source_configuration=files['daily_source'])
    files['daily_smp'] = save('daily-market-service.json', smp)
    control = root / 'daily-history-controls'
    create_private_directory(control)
    entry = descriptor(program / 'integrations/guanheng/source_market_service.py')
    process = dict(before_process, entry=entry['path'], entry_sha256=entry['sha256'],
        configuration=files['daily_smp']['path'], configuration_sha256=files['daily_smp']['sha256'],
        control_root=str(control))
    files['daily_process'] = save('daily-history-process.json', process)
    updated_runtime = deepcopy(before_runtime)
    updated_runtime['instance_id'] = str(uuid4())
    updated_runtime['components']['history'].update(descriptor=files['daily_process']['path'],
        sha256=files['daily_process']['sha256'])
    files['daily_runtime'] = save('daily-runtime.json', updated_runtime)
    role = deepcopy(old_role)
    role.update(bootstrap_configuration=files['daily_runtime']['path'],
        bootstrap_configuration_sha256=files['daily_runtime']['sha256'])
    # 原服务控制器重启会沿原代恢复；独立新角色首次启动才能采用新bootstrap。
    for key, name in [('generation_root', 'daily-generations'), ('control_root', 'daily-controls')]:
        directory = root / name
        create_private_directory(directory)
        role[key] = str(directory)
    role['current_file'] = str(root / 'DAILY-ROLE-CURRENT.json')
    files['daily_role_service'] = save('daily-role-service.json', role)
    originals = dict(daily_role=selected, daily_runtime=runtime, daily_process=process_ref, daily_smp=smp_ref,
        daily_read=before_smp['source_configuration'], daily_update=before_smp['daily_update'])
    facts = dict(
        market_current_file=original_read['current_file'],  # 稳定市场CURRENT；本次不写入，后继自然新日继续由原owner发布。
        captured_current_sha256=pointer_sha,  # 本次准备时的实际市场指针身份；最终维护前须复核是否推进。
        captured_snapshot=pointer['configuration'],  # 原Snapshot完整不可变正文，五层历史/CNI等均保持。
        old_runtime_current=str(current_path),  # 原日线角色控制指针，回退继续沿原控制器恢复。
        new_runtime_current=role['current_file'],  # 新角色专属CURRENT；与市场发布指针及金融CURRENT分别管理。
        daily_update_unchanged=True, snapshot_unchanged=True, task_root_unchanged=True)  # 原事实/请求不复制、不迁移。
    return files, originals, facts
