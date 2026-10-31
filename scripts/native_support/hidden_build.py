"""Run a build driver in one hidden console inside an already managed Job.

An outer creation-bound Job owns this bootstrap before it runs. Descendants then
inherit that Job, including the interval before native.run attaches its nested Job.
The driver must keep using background_process_options for direct tool launches.
"""
from pathlib import Path
import argparse
import ctypes as C
import os
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import native


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, required=True)
    parser.add_argument('--log', type=Path, required=True)
    parser.add_argument('--cwd', type=Path, required=True)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if (os.name != 'nt' or not 0 < args.seconds <= 3600 or not command
            or not Path(command[0]).is_absolute() or not args.cwd.is_absolute()
            or not args.log.is_absolute()):
        parser.error('requires Windows, a bounded deadline and explicit absolute paths')
    kernel = C.WinDLL('kernel32', use_last_error=True)
    kernel.GetCurrentProcess.restype = C.c_void_p
    kernel.IsProcessInJob.argtypes = (C.c_void_p, C.c_void_p, C.POINTER(C.c_int))
    kernel.IsProcessInJob.restype = C.c_int
    member = C.c_int()
    if not kernel.IsProcessInJob(kernel.GetCurrentProcess(), None, C.byref(member)):
        raise C.WinError(C.get_last_error())
    if not member.value:
        parser.error('outer Job membership is required before starting the build driver')
    native.run(command, cwd=args.cwd, log=args.log, timeout=args.seconds, private_console=True)


if __name__ == '__main__':
    main()
