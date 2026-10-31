"""Explicit frozen data component variants for the existing Reader build."""
from pathlib import Path
import json
import shutil


def prepare(root, work, entries, source, write_snapshot, expected):
    declaration = "config/native-data-sources.json"
    raw = source(root, declaration)
    lock = json.loads(raw["data"])
    if lock != expected:
        raise ValueError("data source declaration changed during preparation")
    if lock["schema"] != "guanheng.native-data-sources.v1":
        raise ValueError("unsupported data source declaration")
    material = {declaration: raw}
    directories = []
    for name, variant in lock["variants"].items():
        if name not in ("account006", "parser_v6", "collection004", "analysis001", "quotes_hpr3"):
            raise ValueError("unknown native data variant")
        files = dict(entries)
        for target, row in variant["files"].items():
            value = source(root, row["source"], row["sha256"])
            material[row["source"]] = value
            files[target] = value
        directory = "data/" + name
        write_snapshot(work / "inputs" / directory, files, commit=lock["commit"])
        directories.append(directory)
    return material, directories


def package(installed, save, sha256):
    """Publish portable native slices with entry paths and exact file identity."""
    components = {
        "native_account": {"scan": "app/GuanhengAccountScan.exe", "trader": "app/traders/TraderQMTReadOnly.dll"},
        "native_qmt_history": {"history": "app/GuanhengQmtHistory.exe", "bulk_history": "app/GuanhengQmtBulkHistory.exe"},
        "native_analysis": {"probe": "app/WtAdjustmentProbe.exe", "helper": "app/WtDtHelper.dll", "reader": "app/WtDataStorage.dll"},
        "native_bar_file": {"bars": "app/GuanhengNativeBarFile.dll", "helper": "app/WtDtHelper.dll", "quotes": "app/GuanhengShmQuotes.dll"},
        "collection": {"session": "app/GuanhengDataKitSession.dll", "writer": "app/WtDataStorage.dll", "lifecycle_writer": "app/WtDataStorageLifecycle.dll", "helper": "app/WtDtHelper.dll"},
        "parser_v6": {"parser": "app/ParserQMTHostV6.dll"},
    }
    # MSVC/UCRT support is copied from CMake's ordinary installation, never
    # sourced from a historical component or a tool cache.
    support = [p for p in (installed / "app").glob("*.dll")
               if p.name.lower().startswith(("api-ms-", "vcruntime", "msvcp", "concrt", "ucrtbase"))]
    for name, entries in components.items():
        directory = installed / "components" / name
        for p in support:
            shutil.copyfile(p, directory / "app" / p.name)
        shutil.copytree(installed / "licenses", directory / "licenses")
        shutil.copytree(installed / "provenance", directory / "provenance")
        files = {p.relative_to(directory).as_posix(): sha256(p) for p in directory.rglob("*") if p.is_file()}
        if not all(path in files for path in entries.values()):
            raise ValueError("incomplete component: " + name)
        save(directory / "INSTALLATION.json", dict(schema="guanheng.native-data-component.v1", component=name,
             entries=entries, files=files, rebuilt=True, production_switch=False))
    return components
