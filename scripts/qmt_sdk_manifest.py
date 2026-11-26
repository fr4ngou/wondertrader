"""在终端外使用 QMT 配套 Python 采集 SDK 身份；只读 SDK，独占创建清单。"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import sys


def collect():
    """返回生成器要求的 3.6.8/64 位身份；不导入券商 API 或启动服务。"""
    if os.name != 'nt' or sys.version_info[:3] != (3, 6, 8) or struct.calcsize('P') != 8:
        raise ValueError('requires the QMT CPython 3.6.8 64-bit interpreter')
    sdk = Path(sys.executable).resolve().parent
    executable, dll, stdlib = sdk / 'pythonw.exe', sdk / 'python36.dll', sdk / 'Lib'
    if not stdlib.is_dir():
        raise ValueError('requires the matching SDK Lib directory')
    return {
        'schema_version': 'qmt.memory-sdk.v1',  # 当前内存生成器接受的清单协议。
        'python_version': list(sys.version_info[:3]),  # 实际运行的解释器版本。
        'python_executable': str(executable),  # 配对核验的窗口隐藏解释器绝对路径。
        'python_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(),  # 解释器文件身份。
        'python_dll_sha256': hashlib.sha256(dll.read_bytes()).hexdigest(),  # 同目录运行库身份。
        'builtin_names': sorted(sys.builtin_module_names),  # 此解释器实际支持的内建模块。
        'stdlib_root': str(stdlib),  # 冻结纯 Python 依赖时读取的标准库根。
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='新建清单的绝对路径；父目录须存在')
    args = parser.parse_args(argv)
    if not args.output.is_absolute():
        parser.error('output must be an absolute path')
    value = collect()
    # 采集失败或目标已存在时保留原件；清单仅含 SDK 身份，不读取账户或凭据。
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=True, indent=2)
        stream.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
