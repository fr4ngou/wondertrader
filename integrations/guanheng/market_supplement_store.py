"""固定JSON补充事实Reader；由创建线程拥有，无下载、调度或独立数据库。"""
from copy import deepcopy
from pathlib import Path
import threading

from ..guanheng_market_client import MarketUnavailable, strict_json, _object
from ..guanheng_market_client.market_snapshot import _day, _hash
from ..guanheng_market_client.supplement_facts import (
    MAX_CATALOG_BYTES, cell_key, validate_supplement_catalog,
    validate_supplement_request, validate_supplement_data, validate_source_proof,
)
from .market_generation import read_fixed


class MarketSupplementStore:
    """单一快照的只读事实目录；每次查询核原字节SHA，关闭释放已准入对象。"""
    def __init__(self, descriptor, *, observation_date=None):
        _object(descriptor, ('path', 'sha256'))  # 固定原件绝对路径和完整字节摘要。
        path = descriptor['path']
        if type(path) is not str or not Path(path).is_absolute():
            raise ValueError('supplement catalog path invalid')
        self._path = Path(path)  # 数据owner发布的不可变JSON原件，不跟随动态指针。
        self._sha256 = _hash(descriptor['sha256'])  # snapshot provenance必须绑定同一目录SHA。
        self._owner = threading.get_ident()  # 创建/查询/关闭均归原HTTP/Reader线程。
        self._closed = False  # close后所有查询失败，避免使用已释放事实。
        self._catalog = validate_supplement_catalog(strict_json(read_fixed(
            self._path, maximum=MAX_CATALOG_BYTES, identity=self._sha256)))  # 最多32MiB准入对象。
        if observation_date is not None:
            _day(observation_date)
            if any(day > observation_date for day in self._catalog['dates']):
                raise ValueError('supplement dates exceed snapshot observation')
        from guanheng_app.observation.storage import ContentStore
        self._objects = ContentStore(self._catalog['raw_store'])  # 复用原对象库，仅get，不创建数据库或写对象。
        self._entries = sorted(
            [(False, row) for row in self._catalog['rows']]
            + [(True, row) for row in self._catalog['gaps']], key=lambda item: cell_key(item[1]))  # 同一有界排序索引。

    def _check_owner(self):
        if self._closed or threading.get_ident() != self._owner:
            raise MarketUnavailable('supplement store owner unavailable')

    @property
    def catalog(self):
        """供准备器核查的独立副本；调用方修改副本不改变已准入读取对象。"""
        self._check_owner()
        return deepcopy(self._catalog)

    def query(self, request):
        """按date/metric/symbol统一分页；原件损坏沿外层映射IoError，空匹配返回空。"""
        self._check_owner()
        validate_supplement_request(request)
        read_fixed(self._path, maximum=MAX_CATALOG_BYTES, identity=self._sha256)
        selected = [(gap, row) for gap, row in self._entries
                    if row['metric'] == request['metric'] and row['symbol'] in request['symbols']
                    and request['from'] <= row['date'] <= request['to']]
        start, limit, total = request['offset'], request['limit'], len(selected)
        page = selected[start:start + limit]
        self._verify_sources(page)
        evidence = deepcopy(self._catalog['qmt_evidence'])
        # 兼容旧SDK对既有指标能力枚举的严格验证。
        from ..guanheng_market_client.supplement_facts import LEGACY_METRICS
        known = (*LEGACY_METRICS, request['metric'])
        evidence['decisions'] = [row for row in evidence['decisions'] if row['metric'] in known]
        result = dict(
            schema='guanheng.market-supplement-query.v1',  # 固定补充事实分页协议。
            source_snapshot_id=request['snapshot_id'],  # 外层已核对的同一WT快照身份。
            source_sha256=self._sha256,  # 本次真实核对的目录原字节SHA。
            rows=[deepcopy(row) for gap, row in page if not gap],  # 事实原值和来源时刻保持。
            gaps=[deepcopy(row) for gap, row in page if gap],  # 当前页缺口原因保持。
            selection=dict(
                offset=start,  # rows/gaps合并排序后的请求偏移。
                limit=limit,  # 当前页最大单元数。
                total=total,  # 全部匹配单元数，含事实及缺口。
                next_offset=start + len(page) if start + len(page) < total else None),  # 末页为空。
            qmt_evidence=evidence)  # 本轮无凭据QMT能力原件身份。
        return validate_supplement_data(result, request)

    def verify_sources(self, check=lambda: None):
        """发布/复用前核整目录浅闭包；check由原owner注入总D/取消，读取不写任何状态。"""
        self._check_owner()
        check()
        read_fixed(self._path, maximum=MAX_CATALOG_BYTES, identity=self._sha256)
        self._verify_sources(self._entries, check=check)
        check()

    def _verify_sources(self, page, *, check=lambda: None):
        """复核QMT证据、行proof和一层父原件；同批去重，每行/原件前核原owner截止。"""
        from guanheng_app.observation.contracts import ObservationError
        from ..guanheng_market_client.supplement_facts import BUYBACK_EXECUTION,SHAREHOLDER_REDUCTION
        import re
        seen = set()
        proofs = {}

        def read(identity):
            check()
            try:
                return self._objects.get(identity)
            except ObservationError:
                raise ValueError('supplement source object unavailable or corrupt') from None

        evidence = self._catalog['qmt_evidence']['source_sha256']
        evidence_body = read(evidence)
        seen.add(evidence)
        if any(not gap and row['source_sha256'] == evidence for gap, row in page):
            proofs[evidence] = validate_source_proof(strict_json(evidence_body))
        del evidence_body
        parents = set()
        disclosure_indexes = {}
        reduction_indexes = {}
        for gap, row in page:
            check()
            if gap:
                continue
            identity = row['source_sha256']
            if identity not in proofs:
                proofs[identity] = validate_source_proof(strict_json(read(identity)))
                seen.add(identity)
            proof = validate_source_proof(proofs[identity], row)
            parents.update(proof['parents'])
            if row['metric'] == BUYBACK_EXECUTION:
                if len(proof['parents']) != 1:
                    raise ValueError('buyback disclosure proof parent invalid')
                disclosure_indexes[proof['parents'][0]] = row['date']
            if row['metric']==SHAREHOLDER_REDUCTION:
                for parent in proof['parents']:reduction_indexes.setdefault(parent,set()).add(row['date'])
        for parent,days in reduction_indexes.items():
            body=read(parent);seen.add(parent)
            try:index=strict_json(body)
            except (ValueError,UnicodeError):continue  # 旧版本可直接引用原始非JSON报表。
            if type(index)is not dict or index.get('schema')!='guanheng.shareholder-reduction-estimate.v1':continue
            counts={'priced_count','estimated_count','unpriced_count','timing_conflict_count'}
            if (set(index)!={'schema','date','method','parents',*counts}or {index['date']}!=days
                    or index['method']!='known_priced_disclosures; average_then_reference_close; timing_conflicts_excluded'
                    or any(type(index[k])is not int or index[k]<0 for k in counts)or index['unpriced_count']):
                raise ValueError('reduction estimate proof invalid')
            inputs=index['parents']
            if (type(inputs)is not list or not inputs or len(inputs)!=len(set(inputs))
                    or any(type(sha)is not str or re.fullmatch('[a-f0-9]{64}',sha)is None for sha in inputs)):
                raise ValueError('reduction estimate input identity invalid')
            parents.update(inputs)
            for identity in inputs:
                if identity in seen:continue
                raw=read(identity);seen.add(identity)
                # 历史补数的原参考价清单直接列出其全部价格原件；普通本地查询响应为叶子。
                try:book=strict_json(raw)
                except (ValueError,UnicodeError):continue
                if type(book)is not dict or book.get('schema')!='guanheng.reduction-reference-prices.v1':continue
                if (set(book)!={'schema','quotes','parents'}or type(book['quotes'])is not list
                        or type(book['parents'])is not list or not book['parents']
                        or any(type(sha)is not str or re.fullmatch('[a-f0-9]{64}',sha)is None for sha in book['parents'])
                        or len(book['parents'])!=len(set(book['parents']))):
                    raise ValueError('reduction reference price proof invalid')
                parents.update(book['parents'])
        for parent, day in disclosure_indexes.items():
            index = strict_json(read(parent))
            if (type(index) is not dict or set(index) != {'schema','date','parents'}
                    or index['schema'] != 'guanheng.buyback-disclosure-proof.v1'
                    or index['date'] != day or type(index['parents']) is not list
                    or not index['parents'] or any(type(sha) is not str or re.fullmatch('[a-f0-9]{64}',sha) is None
                                                   for sha in index['parents'])
                    or index['parents'] != sorted(set(index['parents']))):
                raise ValueError('buyback disclosure proof index invalid')
            parents.update(index['parents'])
            seen.add(parent)
        for parent in sorted(parents - seen):
            read(parent)

    def close(self):
        if self._closed:
            return
        self._check_owner()
        self._entries.clear()
        self._catalog.clear()
        self._objects = None
        self._closed = True
