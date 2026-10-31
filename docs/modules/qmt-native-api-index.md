# 国信内置 Python API 查阅索引

类型：版本化参考目录。来源快照：2026-10-28本机国信213页手册；共148个去重函数/属性名。实际调用、参数及权限以当前国信终端和官方正文为准。

## 怎样使用

先查职责表，再按名称和PDF页码定位本机手册。页码为PDF物理页，从1开始，属性不按函数调用；此表不复制完整签名，不代表接口已逐一实测，也不授账户或交易权限。不同版本会出现拼写差异，例如本机手册的 ContextInfo.get_instrumentdetail 与新版在线 get_instrument_detail，须在对应版本核验，不能自行互换。

原件路径、摘要和提取依据见[本机环境证据](../evidence/2026-10-28-qmt-installed-runtime.md)，新版在线 API 与更新依据见[官方资料](../evidence/2026-10-28-guosen-qmt-official-runtime.md)。运行及性能规则见[内置Python手册](../runbooks/guosen-qmt-python.md)。

## 常用职责

| 职责 | 主要入口 | 注意事项 |
| --- | --- | --- |
| 初始化和停止 | init / after_init / handlebar / stop | 原策略回调；持续状态放全局对象，ContextInfo有回滚语义 |
| 快照、全推及取消 | ContextInfo.get_full_tick / subscribe_whole_quote / unsubscribe_quote | 快照与分钟K线分开；全推结果按证券过滤，退订用订阅号 |
| 分钟历史 | ContextInfo.get_market_data_ex | 显式1m、起止、复权、fill_data及subscribe；已下载缓存与在线订阅分别解释 |
| 历史补齐 | 全局download_history_data | 与ContextInfo方法和外部xtquant同名函数分别核实；函数返回后再查询实际日期/条数，不能仅按None返回判为成功 |
| 清单和日历 | ContextInfo.get_stock_list_in_sector / get_trading_dates | 函数及初始化阶段按当前官方版本确认 |
| 账户、资金、持仓、委托和成交 | get_trade_detail_data | 按账户/类别参数读取；字段和时点由券商来源决定 |
| 委托和撤单 | passorder / cancel | 真正交易副作用；平台文档存在和已获调用授权分别核对 |
| 回报 | account_callback / order_callback / deal_callback / position_callback / orderError_callback | 回报属于异步通知，查询快照与回报同步沿原交易适配 |

## 与本仓接入能力的关系

内置 API、外部 xtquant API、共享内存 operation 是三层名称。现有[普通只读能力表](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/read_capabilities.py)登记 market.full_tick、market.history_1m、account.trade_detail；[长历史描述](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/bulk_capabilities.py)登记 market.history_1m.bulk；[交易描述](../../connectors/qmt_shm/agent/guanheng_qmt_shm_agent/trade_capabilities.py)登记 order.insert/order.cancel。部署profile决定实际开放子集。

[全推报价流](qmt-quote-stream.md)是独立报价运输合同，复用全推/退订，不把每条报价变成命令 operation。旧项目文档的50操作目录属于旧入口，不能作为当前适配器已开放50项的依据。真实验证及尚未打通项由对应证据登记。

## 本机手册条目名称与页码

下表仅提取编号标题中的可定位API名；同名不同重载合并页码，正文中分行或未编号的条目可能未被收录。在线新增 schedule_run/cancel_schedule_run 等另查当前官方系统函数，不把其存在推定为本机已支持。

| 名称 | PDF页码 |
| --- | --- |
| `init` | 27 |
| `after_init` | 27 |
| `handlebar` | 28 |
| `ContextInfo.set_universe` | 28 |
| `ContextInfo.set_account` | 29 |
| `ContextInfo.start` | 29 |
| `ContextInfo.end` | 29 |
| `ContextInfo.capital` | 30 |
| `ContextInfo.set_slippage` | 30 |
| `ContextInfo.set_commission` | 31 |
| `ContextInfo.get_universe` | 32 |
| `ContextInfo.period` | 32 |
| `ContextInfo.barpos` | 33 |
| `ContextInfo.time_tick_size` | 33 |
| `ContextInfo.is_last_bar` | 33 |
| `ContextInfo.is_new_bar` | 34 |
| `ContextInfo.is_suspended_stock` | 34 |
| `is_sector_stock` | 35 |
| `is_typed_stock` | 35 |
| `ContextInfo.stockcode` | 36 |
| `ContextInfo.dividend_type` | 36 |
| `ContextInfo.market` | 37 |
| `ContextInfo.get_stock_name` | 37 |
| `get_open_date` | 37 |
| `ContextInfo.do_back_test` | 38 |
| `ContextInfo.benchmark` | 38 |
| `ContextInfo.data_info_level` | 38 |
| `get_result_records` | 38 |
| `ContextInfo.run_time` | 40 |
| `stop` | 40 |
| `create_sector` | 41 |
| `create_sector_folder` | 41 |
| `get_sector_list` | 41 |
| `reset_sector_stock_list` | 42 |
| `remove_stock_from_sector` | 42 |
| `add_stock_to_sector` | 42 |
| `ContextInfo.get_last_volume` | 43 |
| `ContextInfo.get_bar_timetag` | 43 |
| `ContextInfo.get_sector` | 44 |
| `ContextInfo.get_industry` | 44 |
| `ContextInfo.get_stock_list_in_sector` | 44 |
| `ContextInfo.get_weight_in_index` | 45 |
| `ContextInfo.get_contract_multiplier` | 45 |
| `ContextInfo.get_risk_free_rate` | 45 |
| `ContextInfo.get_date_location` | 46 |
| `ContextInfo.get_slippage` | 46 |
| `ContextInfo.get_commission` | 46 |
| `ContextInfo.get_net_value` | 47 |
| `ContextInfo.get_financial_data` | 47、48 |
| `ContextInfo.get_history_data` | 49 |
| `ContextInfo.get_market_data` | 50 |
| `ContextInfo.get_full_tick` | 56 |
| `ContextInfo.get_divid_factors` | 57 |
| `ContextInfo.get_main_contract` | 58 |
| `timetag_to_datetime` | 58 |
| `ContextInfo.get_total_share` | 58 |
| `ContextInfo.get_svol` | 60 |
| `ContextInfo.get_bvol` | 60 |
| `ContextInfo.get_longhubang` | 60 |
| `ContextInfo.get_top10_share_holder` | 61 |
| `ContextInfo.load_stk_list` | 63 |
| `ContextInfo.load_stk_vol_list` | 63 |
| `ContextInfo.get_local_data` | 64 |
| `ContextInfo.get_turnover_rate` | 66 |
| `get_etf_info` | 66 |
| `get_etf_iopv` | 67 |
| `ContextInfo.get_instrumentdetail` | 68 |
| `ContextInfo.get_contract_expire_date` | 69 |
| `get_st_status` | 69 |
| `ContextInfo.get_his_st_data` | 69 |
| `ContextInfo.subscribe_quote` | 70 |
| `ContextInfo.unsubscribe_quote` | 71 |
| `ContextInfo.get_all_subscription` | 71 |
| `ContextInfo.get_market_data_ex` | 72 |
| `ContextInfo.get_option_list` | 73 |
| `ContextInfo.get_option_iv` | 73 |
| `ContextInfo.bsm_price` | 74 |
| `ContextInfo.bsm_iv` | 74 |
| `ContextInfo.get_raw_financial_data` | 75 |
| `ContextInfo.get_his_contract_list` | 76 |
| `ContextInfo.get_north_finance_change` | 77 |
| `ContextInfo.get_hkt_statistics` | 77 |
| `ContextInfo.get_hkt_details` | 78 |
| `get_market_time` | 79 |
| `ContextInfo.subscribe_whole_quote` | 79 |
| `ContextInfo.get_holder_num` | 79 |
| `get_chip_distribution` | 80 |
| `get_winner_chips` | 80 |
| `ContextInfo.get_factor_data` | 81 |
| `passorder` | 85 |
| `smart_algo_passorder` | 91 |
| `get_trade_detail_data` | 95 |
| `get_value_by_order_id` | 96 |
| `get_last_order_id` | 97 |
| `can_cancel_order` | 98 |
| `cancel` | 99 |
| `cancel_task` | 100 |
| `pause_task` | 100 |
| `resume_task` | 101 |
| `do_order` | 102 |
| `order_lots` | 103 |
| `order_value` | 103 |
| `order_percent` | 104 |
| `order_target_value` | 105 |
| `order_target_percent` | 106 |
| `order_shares` | 107 |
| `buy_open` | 108 |
| `buy_close_tdayfirst` | 108 |
| `buy_close_ydayfirst` | 109 |
| `sell_open` | 110 |
| `sell_close_tdayfirst` | 111 |
| `sell_close_ydayfirst` | 112 |
| `get_debt_contract` | 112 |
| `get_assure_contract` | 113 |
| `get_enable_short_contract` | 113、123 |
| `get_ipo_data` | 114 |
| `get_new_purchase_limit` | 114 |
| `algo_passorder` | 114 |
| `get_basket` | 120 |
| `set_basket` | 120 |
| `get_unclosed_compacts` | 120 |
| `get_closed_compacts` | 121 |
| `get_hkt_exchange_rate` | 122 |
| `get_option_subject_position` | 123 |
| `get_comb_option` | 124 |
| `make_option_combination` | 124 |
| `release_option_combination` | 125 |
| `account_callback` | 125 |
| `task_callback` | 126 |
| `order_callback` | 126 |
| `deal_callback` | 127 |
| `position_callback` | 128 |
| `orderError_callback` | 128 |
| `query_credit_account` | 129 |
| `credit_account_callback` | 129 |
| `query_credit_opvolume` | 129 |
| `credit_opvolume_callback` | 130 |
| `ext_data` | 130 |
| `ext_data_rank` | 131 |
| `ext_data_range` | 132 |
| `get_factor_value` | 132 |
| `get_factor_rank` | 133 |
| `call_vba` | 133 |
| `ContextInfo.paint` | 135 |
| `ContextInfo.draw_text` | 136 |
| `ContextInfo.draw_number` | 136 |
| `ContextInfo.draw_vertline` | 136 |
| `ContextInfo.draw_icon` | 137 |
