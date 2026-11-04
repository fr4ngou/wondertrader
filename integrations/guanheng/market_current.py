"""同一WT读取服务内原子换代；单次批量始终使用同一已准入Reader。"""
from contextlib import contextmanager
from pathlib import Path
import threading

from ..guanheng_market_client import API_VERSION, MarketUnavailable
from .market_generation import read_generation, load_generation


class CurrentSourceMarket:
    """原HTTP线程拥有实例；请求时查看指针，读取端没有计时器或下载副作用。"""
    def __init__(self, config, *, max_response_bytes):
        if (type(config) is not dict or set(config) != {'mode', 'current_file'}
                or config['mode'] != 'source-market-current'
                or type(config['current_file']) is not str or not Path(config['current_file']).is_absolute()):
            raise ValueError('market current configuration invalid')
        self._path = Path(config['current_file'])  # 数据侧独占写入的小型原子版本指针；读端只读。
        self._maximum = max_response_bytes  # 沿用原HTTP单次响应字节上限。
        self._owner = threading.get_ident()  # Reader与全部原生句柄的唯一线程所有者。
        self._current = None  # 当前已准入SnapshotSourceMarket，换代成功后关闭前一实例。
        self._identity = None  # 已加载指针的完整SHA，重复请求复用实例和其有界缓存。
        self._depth = 0  # 嵌套请求域；整个批次仅在最外层刷新一次。
        self._error = False  # 本请求域换代错误；返回IoError并保留旧实例供恢复。
        self._closed = False  # close后全部动作拒绝，原生缓存与文件句柄已释放。
        self._refresh()

    def _check(self):
        if self._closed or threading.get_ident() != self._owner:
            raise MarketUnavailable('market current owner unavailable')

    def _refresh(self):
        value, identity = read_generation(self._path)
        if identity == self._identity:
            return
        candidate = load_generation(value, max_response_bytes=self._maximum)
        old, self._current = self._current, candidate
        self._identity = identity
        if old is not None:
            old.close()

    @contextmanager
    def read_scope(self):
        """在整个HTTP批次持有同一版本；下一次请求才采用中途发布的新指针。"""
        self._check()
        if self._depth == 0:
            self._error = False
            try:
                self._refresh()
            except (OSError, ValueError, KeyError, TypeError, MarketUnavailable):
                self._error = True
        self._depth += 1
        try:
            yield
        finally:
            self._depth -= 1

    def call(self, request):
        """失败返回明确IoError；已固定旧snapshot_id在成功换版后由原合同报Conflict。"""
        with self.read_scope():
            if self._error:
                return dict(api_version=API_VERSION,
                            status=dict(code='IoError', reason='market generation read failed'), data={})
            return self._current.call(request)

    def close(self):
        if self._closed:
            return
        self._check()
        try:
            self._current.close()
        finally:
            self._current = None
            self._closed = True
