"""独立数据入口；WT受管HTTP组合沿原source_market_service入口选择。"""
from integrations.guanheng.daily_data_service import main

if __name__ == '__main__':
    raise SystemExit(main())
