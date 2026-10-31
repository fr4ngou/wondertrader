# -*- coding: utf-8 -*-
"""长窗历史的原线程 SDK 边界；Python 3.6 标准库。

每个实例绑定一个原窗口和一个 BulkSnapshot。SDK、Frame 及 NumPy 标量
始终由构造线程访问；分页调用者只取得独立快照，不取得 Context/Frame。
此适配器不注册能力、不启动线程，也不改变普通 history_1m 的默认路径。
"""
import threading
import time

from .bulk_snapshot import BulkSnapshot, BulkSnapshotError
from .history_1m import FIELDS, HistoryError, arguments


class BulkHistory1mAdapter(object):
    """一次 SDK 读取及有界脱离复制，重传由 snapshot.page/ack 承担。

    limits 来自已准入的部署 owner；请求只可缩小 max_rows。原绝对单调
    deadline 传给快照，不因 SDK 返回、分页或再次 capture 而重新计时。
    SDK 内部内存及单次调用不可抢占；close/status 的 pending 独立报告。
    """

    def __init__(self, context, value, identity, limits, deadline,
                 clock=time.monotonic, as_of_date_provider=None):
        from .read_capabilities import shanghai_date
        keys = frozenset(('max_calendar_days', 'max_rows', 'max_row_bytes',
            'max_snapshot_bytes', 'max_page_rows', 'max_page_bytes', 'max_total_bytes'))
        if (type(limits) is not dict or set(limits) != keys
                or any(type(n) is not int or n <= 0 for n in limits.values())
                or not 1 <= limits['max_calendar_days'] <= 36600):
            raise BulkSnapshotError('invalid_contract')
        if not callable(clock):
            raise BulkSnapshotError('invalid_contract')
        date_provider = shanghai_date if as_of_date_provider is None else as_of_date_provider
        if not callable(date_provider):
            raise BulkSnapshotError('invalid_contract')
        # 构造先核固定 envelope/额度/D；日期 provider 与任何 SDK 钩子均在后。
        snapshot_limits = {key: item for key, item in limits.items() if key != 'max_calendar_days'}
        self.snapshot = BulkSnapshot(identity, snapshot_limits, deadline, clock)
        self._require_active()
        try:
            as_of = date_provider()
            self._require_active()
            args = arguments(value, as_of, limits['max_calendar_days'], limits['max_rows'])
        except HistoryError:
            raise BulkSnapshotError('invalid_contract')
        if (identity['symbol'], identity['start_time'], identity['end_time']) != args[:3]:
            raise BulkSnapshotError('invalid_contract')
        if not callable(getattr(context, 'get_market_data_ex', None)):
            raise BulkSnapshotError('invalid_contract')
        self._require_active()
        # 请求可缩小行数；页行数同时收窄，不放宽部署快照/字节上限。
        if args[3] != limits['max_rows']:
            snapshot_limits['max_rows'] = args[3]
            snapshot_limits['max_page_rows'] = min(snapshot_limits['max_page_rows'], args[3])
            self.snapshot = BulkSnapshot(identity, snapshot_limits, deadline, clock)
        self._context, self._args = context, args
        self._owner = threading.get_ident()

    def _require_active(self):
        state = self.snapshot.status()['state']
        if state in ('failed', 'expired', 'closed'):
            raise BulkSnapshotError(state)

    def _rows(self):
        # generator 只由 snapshot.capture 在原线程驱动。上下文及 Frame 局部
        # 引用随该 generator 的关闭释放，不向分页线程传递供应商对象。
        symbol, start, end, maximum, unused_start, unused_end = self._args
        self._require_active()
        try:
            values = self._context.get_market_data_ex(fields=list(FIELDS), stock_code=[symbol],
                period='1m', start_time=start, end_time=end, count=maximum + 1,
                dividend_type='none', fill_data=False, subscribe=False)
        except Exception:
            self._require_active()
            raise BulkSnapshotError('source_failed')
        self._require_active()
        if type(values) is not dict or len(values) != 1 or symbol not in values:
            raise BulkSnapshotError('source_shape_invalid')
        frame = values[symbol]
        try:
            shape = frame.shape
            self._require_active()
            if (type(shape) not in (tuple, list) or len(shape) != 2
                    or any(type(n) is not int or n < 0 for n in shape)):
                raise BulkSnapshotError('source_shape_invalid')
            rows, cols = shape
            # count+1 为饱和哨兵；等于它也失败，绝不把截断响应当完整窗口。
            if rows >= maximum + 1:
                raise BulkSnapshotError('row_limit')
            if cols not in ((0, 7) if rows == 0 else (7,)):
                raise BulkSnapshotError('source_shape_invalid')
            columns = frame.columns
            self._require_active()
            if len(columns) != cols:
                raise BulkSnapshotError('source_shape_invalid')
            names, column_iter = [], iter(columns)
            for index in range(cols + 1):
                self._require_active()
                try:
                    name = next(column_iter)
                except StopIteration:
                    break
                self._require_active()
                if (index == cols or type(name) is not str or name not in FIELDS or name in names):
                    raise BulkSnapshotError('source_shape_invalid')
                names.append(name)
            if len(names) != cols or (cols and set(names) != set(FIELDS)):
                raise BulkSnapshotError('source_shape_invalid')
            positions = [names.index(field) for field in FIELDS] if cols else []
            iterator = iter(frame.itertuples(index=False, name=None))
            self._require_active()
            for index in range(rows + 1):
                self._require_active()
                try:
                    row = next(iterator)
                except StopIteration:
                    if index != rows:
                        raise BulkSnapshotError('source_shape_invalid')
                    break
                self._require_active()
                if index == rows or type(row) not in (tuple, list) or len(row) != cols:
                    raise BulkSnapshotError('source_shape_invalid')
                yield tuple(row[position] for position in positions)
        except BulkSnapshotError:
            raise
        except Exception:
            self._require_active()
            raise BulkSnapshotError('source_shape_invalid')

    def capture(self):
        """仅原线程一次调用；返回安全状态，工作线程另持有 snapshot。

        重复调用由快照的 once 状态拒绝，尚未进入 SDK 就终止；原调用未知
        时保留该实例，不能创建同身份的新实例冒充恢复。
        """
        if threading.get_ident() != self._owner:
            raise BulkSnapshotError('owner_required')
        return self.snapshot.capture(self._rows)
