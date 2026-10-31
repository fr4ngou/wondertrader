"""Synthetic ordinary native component exercise; no account or terminal access."""
from pathlib import Path
import ctypes as C
import datetime
import hashlib
import json
import os
import sys


class Bar(C.Structure):
    _fields_ = [("date", C.c_uint32), ("reserve", C.c_uint32), ("time", C.c_uint64)] + [
        (name, C.c_double) for name in ("open", "high", "low", "close", "settle", "money", "vol", "hold", "diff")]


BARS = C.CFUNCTYPE(None, C.POINTER(Bar), C.c_uint32, C.c_bool)
COUNT = C.CFUNCTYPE(None, C.c_uint32)
LOG = C.CFUNCTYPE(None, C.c_char_p)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2), encoding="utf8")


def main():
    installed, work = map(Path, sys.argv[1:3])
    work.mkdir(exist_ok=False)
    components = installed / "components"
    loaded = []
    directories = []

    def library(component, name):
        folder = components / component / "app"
        directories.append(os.add_dll_directory(str(folder)))
        dll = C.CDLL(str(folder / name))
        loaded.append(dll)
        return dll

    helper = library("native_bar_file", "WtDtHelper.dll")
    helper.store_bars.argtypes = [C.c_char_p, C.POINTER(Bar), C.c_int, C.c_char_p, LOG]
    helper.store_bars.restype = C.c_bool
    logger = LOG(lambda message: None)
    bars = (Bar * 3)()
    for index, row in enumerate(bars):
        row.date = 20261026 + index
        row.open = row.close = row.settle = 10 + index
        row.high = row.close + 1
        row.low = row.close - 1
        row.vol = 100 + index
        row.money = row.vol * row.close
    store = work / "storage"
    (store / "his/day/SSE").mkdir(parents=True)
    symbols = ["%06d.SH" % i for i in range(1, 9)]
    for symbol in symbols:
        path = store / "his/day/SSE" / (symbol[:6] + ".dsb")
        assert helper.store_bars(str(path).encode(), bars, len(bars), b"d", logger)
    path = store / "his/day/SSE/000001.dsb"
    reader = library("native_bar_file", "GuanhengNativeBarFile.dll")
    assert reader.gh_native_bar_file_version() == 1
    assert [reader.gh_native_bar_file_layout(i) for i in range(5)] == [C.sizeof(Bar), Bar.date.offset, Bar.time.offset, Bar.open.offset, Bar.diff.offset]
    reader.gh_native_bar_file_read.argtypes = [C.c_wchar_p, C.c_char_p, C.c_uint, C.c_uint, C.c_uint, BARS, COUNT, LOG]
    reader.gh_native_bar_file_read.restype = C.c_uint
    rows, counts = [], []
    callback = BARS(lambda values, size, last: rows.extend([[values[i].date, values[i].close, values[i].vol] for i in range(size)]))
    count = COUNT(counts.append)
    digest = hashlib.sha256(path.read_bytes()).hexdigest().encode()
    assert reader.gh_native_bar_file_read(str(path), digest, 10, 1024 * 1024, 23, callback, count, logger) == 3
    assert rows == [[20261026+i, 10+i, 100+i] for i in range(3)] and counts == [3]
    assert reader.gh_native_bar_file_read(str(path), b"0" * 64, 10, 1024 * 1024, 23, callback, count, logger) == 0
    assert len(rows) == 3 and counts == [3]
    for component, filename, create, stop, destroy in [
        ("native_account", "traders/TraderQMTReadOnly.dll", "createTrader", "stopReadOnlyTrader", "deleteTrader"),
        ("parser_v6", "ParserQMTHostV6.dll", "createParser", "stopParser", "deleteParser"),
    ]:
        dll = library(component, filename)
        make = getattr(dll, create); make.argtypes = []; make.restype = C.c_void_p
        free = getattr(dll, destroy); free.argtypes = [C.POINTER(C.c_void_p)]; free.restype = None
        pointer = C.c_void_p(make()); assert pointer.value
        halt = getattr(dll, stop)
        if component == "parser_v6":
            halt.argtypes = [C.c_void_p, C.c_uint32]; halt.restype = C.c_bool
            assert halt(pointer, 1000)
        else:
            halt.argtypes = [C.c_void_p]; halt.restype = C.c_int
            assert halt(pointer) == 0
        free(C.byref(pointer)); assert pointer.value is None
    sessions = {"DAY": {"name": "synthetic", "offset": 0, "sections": [{"from": 930, "to": 1130}, {"from": 1300, "to": 1500}]}}
    commodities = {"SSE": {"ETF": dict(name="synthetic", session="DAY", holiday="CHINA", category=0, pricetick=.001, volscale=1, covermode=0, pricemode=0, trademode=1)}}
    contracts = {"SSE": {s[:6]: dict(name=s, exchg="SSE", product="ETF", opendate=19900101, expiredate=20991231) for s in symbols}}
    for name, data in [("sessions", sessions), ("commodities", commodities), ("contracts", contracts), ("adjfactors", {})]:
        save(work / (name + ".json"), data)
    save(work / "request.json", dict(path=str(store), adjfactor=str(work / "adjfactors.json"), adjust_flag=0,
         basis_date=20261028, symbols=symbols, **{n:str(work / (n + ".json")) for n in ("sessions", "commodities", "contracts")}))
    datakit = library("collection", "GuanhengDataKitSession.dll")
    datakit.gh_datakit_create.argtypes = [C.c_char_p, C.c_char_p, C.POINTER(C.c_void_p)]
    datakit.gh_datakit_create.restype = C.c_int
    datakit.gh_datakit_count.argtypes = [C.c_void_p, C.c_uint32]; datakit.gh_datakit_count.restype = C.c_uint64
    datakit.gh_datakit_close.argtypes = [C.c_void_p]; datakit.gh_datakit_close.restype = C.c_int
    configuration = dict(allday=True, basefiles={"session": str(work / "sessions.json"), "commodity": str(work / "commodities.json"), "contract": str(work / "contracts.json")},
        writer=dict(module="WtDataStorageLifecycle", path=str(work / "collection-storage"), **{"async": False}, groupsize=1000, disabletick=True, disablemin5=True, disableday=True, disabletrans=True, disableordque=True, disableorddtl=True),
        qmt_source=dict(version="synthetic-only", source_license="synthetic-only", volume_multiplier=1.0, amount_multiplier=1.0))
    save(work / "datakit.json", configuration)
    module = ((components / "collection/app").as_posix() + "/").encode()
    session = C.c_void_p()
    assert datakit.gh_datakit_create(str(work / "datakit.json").encode(), module, C.byref(session)) == 0 and session.value
    assert datakit.gh_datakit_count(session, 0) == 8 and datakit.gh_datakit_count(session, 3) == 1
    assert datakit.gh_datakit_close(session) == 0
    session = C.c_void_p()
    assert datakit.gh_datakit_create(str(work / "missing.json").encode(), module, C.byref(session)) == -1 and session.value is None
    # Reverse library unloading follows all factory/session releases.
    kernel = C.WinDLL("kernel32", use_last_error=True)
    kernel.FreeLibrary.argtypes = [C.c_void_p]; kernel.FreeLibrary.restype = C.c_int
    for dll in reversed(loaded):
        assert kernel.FreeLibrary(dll._handle)
    for directory in reversed(directories): directory.close()
    save(work / "PROBE.json", dict(passed=True, native_bar_rows=rows, digest_rejected=True,
         parser_stopped_deleted=True, readonly_trader_stopped_deleted=True, datakit_closed=True,
         datakit_failed_create_released=True, all_libraries_unloaded=True, real_qmt_calls=0))


if __name__ == "__main__":
    main()
