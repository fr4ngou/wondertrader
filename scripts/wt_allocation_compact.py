"""在独占新目录生成分账归并候选及原始证据映射。"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/wt_runtime'))
from guanheng_wt_runtime.account_allocation import _wire
from guanheng_wt_runtime.allocation_compaction import compact


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(_wire(compact(args.source, args.output)))
