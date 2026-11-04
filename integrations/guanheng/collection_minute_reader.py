"""管理线程通过薄C ABI调用既有WT标准分钟Reader；活动DMB仅由原Reader读取。"""
import ctypes as C
from datetime import date, datetime
import math
import os
from pathlib import Path
import re
import threading

from .market_generation import read_fixed
from .native_history import WTSBar


class CollectionMinuteReader:
    """一批最多64证券；创建、查询、关闭沿同一管理线程，原DLL保留至进程退出。"""
    def __init__(self, configuration, symbols, *, maximum=2000):
        if (type(configuration) is not dict or set(configuration) != {'library', 'reader', 'storage_root', 'basefiles'}
                or type(symbols) is not dict or not 1 <= len(symbols) <= 64
                or any(re.fullmatch(r'(SSE|SZSE)\.(STK|ETF|IDX)\.[0-9]{6}', key) is None for key in symbols)):
            raise ValueError('collection minute reader configuration invalid')
        if type(maximum) is not int or not 1 <= maximum <= 2000:
            raise ValueError('collection minute reader copy bound invalid')
        self._owner = threading.get_ident()  # 单管理线程的原生读取句柄，禁止接收回调或跨线程调用。
        self._handle = None  # 原C ABI上下文；close成功后清空，未确认时继续持有。
        self._library = None  # 自有薄绑定及其固定原NMR依赖，寿命覆盖全部调用。
        self._directories = []  # 本批DLL搜索目录句柄，原生close后再释放目录配置。
        self._symbols = dict(symbols)  # 已装配标准代码到证券描述，只允许本批固定映射。
        self._maximum = maximum  # 本批复制额度，沿原公开分钟请求1..2000行。
        try:
            paths = []
            for key in ('library', 'reader'):
                descriptor = configuration[key]
                if (type(descriptor) is not dict or set(descriptor) != {'path', 'sha256'}
                        or re.fullmatch('[0-9a-f]{64}', descriptor['sha256']) is None):
                    raise ValueError('collection minute reader artifact invalid')
                path = self._path(descriptor['path'])
                read_fixed(path, maximum=67108864, identity=descriptor['sha256'])
                paths.append(path)
            base = configuration['basefiles']
            if type(base) is not dict or set(base) != {'session', 'commodity', 'contract'}:
                raise ValueError('collection minute reader base files invalid')
            arguments = [paths[1], self._path(configuration['storage_root'])]
            for name in ('session', 'commodity', 'contract'):
                descriptor = base[name]
                if type(descriptor) is not dict or set(descriptor) != {'path', 'sha256'}:
                    raise ValueError('collection minute reader base identity missing')
                path = self._path(descriptor['path'])
                read_fixed(path, maximum=16777216, identity=descriptor['sha256'])
                arguments.append(path)
            if not arguments[1].is_dir():
                raise ValueError('collection storage root unavailable')
            for path in paths:
                self._directories.append(os.add_dll_directory(str(path.parent)))
            self._library = C.CDLL(str(paths[0]))
            lib = self._library
            lib.gh_collection_reader_version.restype = C.c_uint32
            lib.gh_collection_reader_bar_size.restype = C.c_uint32
            if lib.gh_collection_reader_version() != 1 or lib.gh_collection_reader_bar_size() != C.sizeof(WTSBar):
                raise ValueError('collection minute reader ABI differs')
            lib.gh_collection_reader_create.argtypes = [C.c_char_p] * 5 + [C.POINTER(C.c_char_p), C.c_uint32, C.c_uint32]
            lib.gh_collection_reader_create.restype = C.c_void_p
            lib.gh_collection_reader_read.argtypes = [C.c_void_p, C.c_char_p, C.c_uint32, C.c_uint32,
                C.POINTER(WTSBar), C.c_uint32, C.POINTER(C.c_uint32), C.POINTER(C.c_uint32), C.c_uint32, C.POINTER(C.c_uint32)]
            lib.gh_collection_reader_read.restype = C.c_int32
            lib.gh_collection_reader_close.argtypes = [C.c_void_p, C.c_uint32]
            lib.gh_collection_reader_close.restype = C.c_bool
            codes = (C.c_char_p * len(symbols))(*(key.encode('ascii') for key in symbols))
            self._handle = lib.gh_collection_reader_create(*(str(p).encode('ascii') for p in arguments), codes, len(codes), maximum)
            if not self._handle:
                raise RuntimeError('collection standard reader initialization failed')
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _path(value):
        if type(value) is not str or not value or len(value) > 1023 or not value.isascii() or '\x00' in value:
            raise ValueError('collection native path invalid')
        path = Path(value)
        if not path.is_absolute() or '..' in path.parts:
            raise ValueError('collection native path must be absolute')
        return path

    def _check(self):
        if self._owner != threading.get_ident() or not self._handle:
            raise RuntimeError('collection standard reader owner unavailable')

    def _read_rows(self, symbol, day, minute):
        self._check()
        if symbol not in self._symbols or type(day) is not str or date.fromisoformat(day).isoformat() != day:
            raise ValueError('collection minute query identity invalid')
        if type(minute) is not int or not 0 <= minute <= 2359 or minute % 100 > 59:
            raise ValueError('collection minute cutoff invalid')
        label = int(day.replace('-', ''))
        bars, expected = (WTSBar * self._maximum)(), (C.c_uint32 * 1440)()
        count, expected_count = C.c_uint32(), C.c_uint32()
        code = self._library.gh_collection_reader_read(self._handle, symbol.encode('ascii'), label, minute,
            bars, len(bars), C.byref(count), expected, len(expected), C.byref(expected_count))
        if code != 0 or count.value > len(bars) or expected_count.value > len(expected):
            raise RuntimeError('collection standard reader query failed')
        rows = []
        previous = 0
        for item in bars[:count.value]:
            stamp = 199000000000 + item.time
            values = (item.open, item.high, item.low, item.close, item.vol, item.money)
            if stamp <= previous or not all(math.isfinite(v) for v in values):
                raise ValueError('collection standard reader row invalid')
            previous = stamp
            if stamp > label * 10000 + minute:
                raise ValueError('collection standard reader future label')
            rows.append(dict(minute=stamp, open=item.open, high=item.high, low=item.low,
                close=item.close, volume=item.vol, amount=item.money))  # 全部数值沿原Reader，量/额单位仍为unknown。
        grid = [label * 10000 + value for value in expected[:expected_count.value]]
        return rows, grid

    def read_range(self, symbol, first, last, limit):
        """读取原请求最近N根，保留跨日原值；原Reader单次复制，不按自然日反复扫描。"""
        if type(first) is not int or type(last) is not int or first > last:
            raise ValueError('collection minute range invalid')
        datetime.strptime(str(first), '%Y%m%d%H%M')
        end = datetime.strptime(str(last), '%Y%m%d%H%M')
        if type(limit) is not int or not 1 <= limit <= self._maximum:
            raise ValueError('collection minute range count invalid')
        rows, unused = self._read_rows(symbol, end.date().isoformat(), last % 10000)
        return [row for row in rows if first <= row['minute'] <= last][-limit:]

    def read_day(self, symbol, day, minute):
        """保留原88字节字段和右端标签；预期网格来自原WT session，不推造缺失值。"""
        rows, grid = self._read_rows(symbol, day, minute)
        label = int(day.replace('-', ''))
        rows = [row for row in rows if row['minute'] // 10000 == label]
        actual = {row['minute'] for row in rows}
        return dict(
            symbol=symbol,  # 本批已配置标准代码。
            date=day, cutoff=minute,  # 显式北京时间日期及原右端HHMM。
            bars=rows,  # 原Reader返回的当日实际记录，缺口不填值。
            expected_minutes=grid,  # 原WT session给出的已结束时段标签，交易日资格由调用方日历核对。
            missing_minutes=sorted(set(grid) - actual),  # 预期标签中原Reader实际未给出的部分。
            unexpected_minutes=sorted(actual - set(grid)),  # 未改写的时段外源标签，供保留原因。
            volume_unit='unknown', amount_unit='unknown')  # WT文件格式不自动证明供应商量额单位。

    def close(self):
        """创建线程关闭；停止未确认时保留句柄，外层采集进程仍拥有最终截止。"""
        if self._owner != threading.get_ident():
            raise RuntimeError('collection standard reader close owner differs')
        if self._handle:
            if not self._library.gh_collection_reader_close(self._handle, 3000):
                raise RuntimeError('collection standard reader close unconfirmed')
            self._handle = None
        for directory in self._directories:
            directory.close()
        self._directories.clear()
