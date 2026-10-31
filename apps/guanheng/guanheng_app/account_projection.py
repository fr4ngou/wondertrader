"""显式v2/v3事实到各自公开DTO；金融规则共用，ABI中性槽不补事实。"""

import math
import re
from datetime import datetime
from dataclasses import dataclass

from .contracts.account import (AccountClose, AccountField, AccountGroup, AccountOverview, AccountRow, AccountSource,
                                AccountGroupV2, AccountOverviewV2, ShmAccountSource, AccountTransport, AccountBrokerSession)

DATATYPES = ("position", "order", "deal", "account")
FIELD_MAP = {
    "position": dict(quantity="m_nVolume", sellable="m_nCanUseVolume", yesterday="m_nYesterdayVolume",
                     frozen="m_nFrozenVolume", onroad="m_nOnRoadVolume", average_price="m_dAvgPrice",
                     open_price="m_dOpenPrice", position_profit="m_dPositionProfit", float_profit="m_dFloatProfit",
                     market_value="m_dMarketValue"),
    "order": dict(side="m_nOffsetFlag", quantity="m_nVolumeTotalOriginal", filled="m_nVolumeTraded",
                  remaining="m_nVolumeTotal", price="m_dLimitPrice", state="m_nOrderStatus", cancel="m_dCancelAmount",
                  date="m_strInsertDate", time="m_strInsertTime"),
    "deal": dict(side="m_nOffsetFlag", quantity="m_nVolume", price="m_dPrice", amount="m_dTradeAmount",
                 date="m_strTradeDate", time="m_strTradeTime"),
    "account": dict(total_asset="m_dBalance", available="m_dAvailable", previous_balance="m_dPreBalance",
                    commission="m_dCommission", frozen_cash="m_dFrozenCash", frozen_margin="m_dFrozenMargin",
                    frozen_commission="m_dFrozenCommission", position_profit="m_dPositionProfit", float_profit="m_dFloatProfit"),
}
IDENTITY_KEYS = {"m_strInstrumentID", "m_strExchangeID", "m_strOrderSysID", "m_strTradeID",
                 "m_strInsertDate", "m_strInsertTime", "m_strTradeDate", "m_strTradeTime",
                 "derived_trade_id", "mapping_version"}
REQUIRED = {"position": ("quantity", "sellable"), "order": ("side", "quantity", "filled", "remaining", "price", "state", "date", "time"),
            "deal": ("side", "quantity", "price", "amount", "date", "time"), "account": ("total_asset", "available")}


class AccountProtocolError(ValueError):
    """协议错误只携带固定内部原因标识，公开端统一中文。"""


def require(condition):
    if not condition:
        raise AccountProtocolError("invalid_protocol")


def integer(value, minimum=0, maximum=2**53 - 1):
    return type(value) is int and minimum <= value <= maximum


def text(value, maximum=512):
    return isinstance(value, str) and 0 < len(value) <= maximum and all(ord(c) >= 32 and ord(c) != 127 for c in value)


def field(raw):
    require(isinstance(raw, dict) and set(raw) == {"availability", "value", "reason"})
    availability, value = raw["availability"], raw["value"]
    require(availability in {"present", "unknown", "invalid", "not_applicable"} and isinstance(raw["reason"], str))
    if availability == "present":
        require(isinstance(value, (str, int, float)) and not isinstance(value, bool))
        require(not isinstance(value, (int, float)) or math.isfinite(value))
        require(not isinstance(value, str) or text(value))
        return AccountField(availability="present", value=value)
    require(value is None)
    state = "invalid" if availability == "invalid" else "unknown"
    return AccountField(availability=state, reason="来源字段类型或数值无效" if state == "invalid" else "来源未提供该字段")


def unknown(reason="来源未提供该字段"):
    return AccountField(availability="unknown", reason=reason)


def unavailable_account(reason="尚未配置原生账户只读来源，请配置后刷新", scan_id=None, close=None, *, schema_version="1.0"):
    overview_type, group_type = _public_types(schema_version)
    return overview_type(scan_id=scan_id, status="unavailable", reason=reason, trade_date=unknown("来源交易日不可用"),
                           close=close or AccountClose(), groups={name: group_type(datatype=name, status="unavailable", reason=reason) for name in DATATYPES})


def _timestamp(value):
    require(text(value, 64))
    try:
        stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise AccountProtocolError("invalid_protocol") from None
    require(stamp.utcoffset() is not None)
    return stamp



def _public_types(schema_version):
    require(schema_version in {"1.0", "2.0"})
    return (AccountOverviewV2, AccountGroupV2) if schema_version == "2.0" else (AccountOverview, AccountGroup)


@dataclass(frozen=True)
class AccountObservationV3:
    """只由显式v3准入返回；公开版次随本轮独立观察传到投影。"""
    groups: dict[str, AccountGroupV2]
    trade_date: AccountField
    qualified: bool


def _profile(binding):
    # 来源取部署配置，不从收到的frame推断，也不回退旧HTTP。
    declared = (getattr(binding, "ipc_schema", None), getattr(binding, "inspection_version", None), getattr(binding, "source", None))
    require(type(declared[1]) is int)
    if declared == ("guanheng.account-scan.v1", 2, "qmt_http"):
        return False, AccountGroup
    require(declared == ("guanheng.account-scan.v2", 3, "qmt_shm_bound"))
    require(getattr(binding, "read_profile_version", None) == "qmt.read-profile.v3")
    return True, AccountGroupV2


def _hex(value, length):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is not None


def _uuid(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", value) is not None


def _utc6(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z", value))
    return _timestamp(value)


def _route_text(value):
    # 路由沿Core的Unicode码点域；不得误缩为128个UTF8字节。
    if type(value) is not str or not 1 <= len(value) <= 128:
        return False
    try:
        return len(value.encode("utf-8", "strict")) <= 512
    except UnicodeError:
        return False


def _shm_source(source, binding):
    require(type(source) is dict and set(source) == {"kind", "account_id", "account_environment", "transport_binding", "binding_sha256", "broker_session"})
    require(source["kind"] == "qmt_shm_bound" and source["account_id"] == binding.account
            and source["account_environment"] == binding.environment and binding.environment in {"simulation", "live"})
    account = source["account_id"]
    require(type(account) is str and all(ord(c) >= 32 and not 127 <= ord(c) <= 159 for c in account))
    try:
        require(1 <= len(account.encode("utf-8", "strict")) <= 63)
    except UnicodeError:
        raise AccountProtocolError("invalid_protocol") from None
    transport = source["transport_binding"]
    require(type(transport) is dict and set(transport) == {"schema_version", "route", "transport_generation", "host_instance_id", "journal_generation", "observation_identity", "capability_sha256"})
    require(transport["schema_version"] == "1.0" and _hex(transport["host_instance_id"], 32)
            and _hex(transport["transport_generation"], 32) and _hex(transport["capability_sha256"], 64)
            and transport["journal_generation"] is None and transport["observation_identity"] is None)
    route = transport["route"]
    require(type(route) is dict and set(route) == {"route_id", "executor_id", "route_epoch"}
            and _route_text(route["route_id"]) and _route_text(route["executor_id"])
            and integer(route["route_epoch"], 0, 2**53 - 1))
    # 原B字节摘要已由Core认证；IPC中的DOM无原词法bytes，不能重编码冒充同一摘要。
    require(_hex(source["binding_sha256"], 64))
    require(source["broker_session"] == {"availability": "unknown", "value": None, "reason": "未取得券商登录会话证据"})
    masked = "****" + binding.account[-4:] if len(binding.account) > 4 else "****"
    return ShmAccountSource(account_label=masked, environment=binding.environment,
                            transport=AccountTransport(host_instance_id=transport["host_instance_id"],
                                                       transport_generation=transport["transport_generation"],
                                                       route=dict(route), capability_sha256=transport["capability_sha256"]),
                            broker_session=AccountBrokerSession())


def validate_observation(frame, scan_id, binding):
    """整帧准入后才交付批次，跨批来源代际必须与首个交付批一致。"""
    shm, group_type = _profile(binding)
    require(isinstance(frame, dict) and set(frame) == {"schema", "scan_id", "kind", "summary", "rows"})
    require(frame["schema"] == binding.ipc_schema and frame["scan_id"] == scan_id and frame["kind"] == "observation")
    summary, rows = frame["summary"], frame["rows"]
    require(isinstance(summary, dict) and isinstance(rows, dict) and set(rows) == set(DATATYPES))
    require(type(summary.get("version")) is int and summary["version"] == binding.inspection_version and type(summary.get("view")) is int and summary["view"] == 0)
    require(summary.get("source_kind") == binding.source and summary.get("profile") == "cny_cash_shsz_v1" and summary.get("aggregate_only") is True)
    require(summary.get("currency_binding") == {"value": "CNY", "source": "configuration"})
    require(type(summary.get("observation_qualified")) is bool)
    trade_date = field(summary.get("trade_date"))
    require(trade_date.availability == "unknown")
    trade_date = unknown("来源交易日不可用")
    failure = summary.get("failure")
    # 原v2 Diagnostics沿用负值Error枚举；采集失败仍可保留先前交付批。
    require(isinstance(failure, dict) and integer(failure.get("code"), -8, 0))
    batches = summary.get("batches")
    require(isinstance(batches, list) and len(batches) == 4)
    if shm:
        require(_uuid(scan_id))
        require(set(summary) == {"version", "view", "phase", "source_kind", "profile", "currency_binding", "observation_qualified", "aggregate_only", "trade_date", "batches", "close", "failure"})
        require(integer(summary["phase"], 0, 8))
        close_state = summary["close"]
        require(type(close_state) is dict and set(close_state) == {"status", "drained", "joined"}
                and close_state["status"] in {"not_started", "waiting", "timeout", "complete"}
                and type(close_state["drained"]) is bool and type(close_state["joined"]) is bool)
        require(set(failure) == {"code", "reason", "transport_error", "source_error_code"})
        require(type(failure["reason"]) is str and (failure["transport_error"] is None or text(failure["transport_error"]))
                and (failure["source_error_code"] is None or text(failure["source_error_code"])))
    groups, identity = {}, None
    request_ids = set()
    for index, name in enumerate(DATATYPES):
        batch, batch_rows = batches[index], rows[name]
        require(isinstance(batch, dict) and batch.get("datatype") == name and type(batch.get("delivered")) is bool)
        require(isinstance(batch_rows, list) and len(batch_rows) <= binding.max_rows)
        request_id = batch.get("request_id")
        require(request_id is None or (_uuid(request_id) if shm else text(request_id)))
        public_source = None
        if shm:
            require(set(batch) == {"datatype", "delivered", "source_row_count", "delivered_row_count", "request_id", "execution_started_at", "execution_finished_at", "result_sha256", "source"})
            if request_id is not None:
                require(request_id not in request_ids)
                request_ids.add(request_id)
            for key in ("execution_started_at", "execution_finished_at"):
                if batch[key] is not None:
                    _utc6(batch[key])
            require(batch["result_sha256"] is None or _hex(batch["result_sha256"], 64))
            if batch["source"] is not None:
                public_source = _shm_source(batch["source"], binding)
                require(identity is None or identity == batch["source"])
                identity = batch["source"]
        if not batch["delivered"]:
            require(not batch_rows and batch.get("delivered_row_count") is None and batch.get("source_row_count") is None)
            groups[name] = group_type(datatype=name, status="unavailable", request_id=request_id, reason="本轮来源未完整交付该类数据，请稍后刷新核查")
            continue
        require(integer(batch.get("delivered_row_count"), maximum=binding.max_rows) and batch["delivered_row_count"] == len(batch_rows))
        require(integer(batch.get("source_row_count"), maximum=binding.max_rows) and batch["source_row_count"] >= len(batch_rows))
        require(name != "account" or len(batch_rows) == 1)
        require(request_id is not None and isinstance(batch.get("result_sha256"), str) and re.fullmatch(r"[0-9a-f]{64}", batch["result_sha256"]))
        require(_timestamp(batch.get("execution_started_at")) <= _timestamp(batch.get("execution_finished_at")))
        source = batch.get("source")
        require(isinstance(source, dict) and source.get("account_id") == binding.account and source.get("account_environment") == binding.environment)
        if shm:
            require(public_source is not None)
            require(_utc6(batch["execution_started_at"]) <= _utc6(batch["execution_finished_at"]))
        else:
            require(all(text(source.get(key)) for key in ("agent_id", "qmt_session_id")) and integer(source.get("generation"), 1, 2**64 - 1))
            current = (source["agent_id"], source["qmt_session_id"], source["generation"])
            require(identity is None or identity == current)
            identity = current
        public_rows = []
        for row_index, row in enumerate(batch_rows):
            require(isinstance(row, dict) and type(row.get("version")) is int and row["version"] == binding.inspection_version and type(row.get("view")) is int and row["view"] == index + 1)
            require(type(row.get("index")) is int and row["index"] == row_index and isinstance(row.get("identity"), dict) and isinstance(row.get("facts"), dict) and isinstance(row.get("abi"), dict))
            if shm:
                expected_keys = {"version", "view", "index", "identity", "facts", "abi"}
                if name == "order":
                    expected_keys.add("price_type")
                require(set(row) == expected_keys)
                if name == "order":
                    # 原生mapper单列价格类型未知；ABI中性值不能转为业务已知值。
                    price_type = row["price_type"]
                    require(type(price_type) is dict and set(price_type) == {"availability", "value", "reason"})
                    require(price_type["availability"] == "unknown" and price_type["value"] is None
                            and text(price_type["reason"]))
            facts = row["facts"]
            for key, expected in (("m_strAccountID", binding.account), ("m_strMoneyType", "CNY")):
                if key in facts:
                    fact = field(facts[key])
                    require(fact.availability != "present" or fact.value == expected)
            public_identity = {key: value for key, value in row["identity"].items() if key in IDENTITY_KEYS}
            require(all(text(value) for value in public_identity.values()))
            if name != "account":
                require(bool(re.fullmatch(r"[0-9]{6}", public_identity.get("m_strInstrumentID", ""))) and public_identity.get("m_strExchangeID") in {"SH", "SZ"})
            if name in {"order", "deal"}:
                require(text(public_identity.get("m_strOrderSysID")))
            if name == "deal":
                require(text(public_identity.get("m_strTradeID")))
            fields = {public: field(facts[raw]) if raw in facts else unknown() for public, raw in FIELD_MAP[name].items()}
            require(all(fields[key].availability == "present" for key in REQUIRED[name]))
            for key, value in fields.items():
                if value.availability == "present":
                    require(isinstance(value.value, str) if key in {"date", "time"} else type(value.value) in {int, float})
                    if key in {"quantity", "sellable", "yesterday", "frozen", "onroad", "filled", "remaining", "state", "side", "cancel"}:
                        require(0 <= value.value <= 2**53 - 1 and value.value == int(value.value))
            if name == "position":
                require(fields["sellable"].value <= fields["quantity"].value)
            if name in {"order", "deal"}:
                require(fields["side"].value in {48, 49} and fields["quantity"].value > 0)
            if name == "order":
                require(49 <= fields["state"].value <= 57 and fields["price"].value >= 0)
                require(fields["filled"].value <= fields["quantity"].value
                        and fields["remaining"].value == fields["quantity"].value - fields["filled"].value)
            if name == "deal":
                require(fields["price"].value > 0 and fields["amount"].value >= 0)
            if name == "order":
                fields["management"] = unknown("来源未授予策略或本地管理归属")
                fields["price_type"] = unknown("来源未公开价格类型")
            public_rows.append(AccountRow(identity=public_identity, fields=fields))
        masked = "****" + binding.account[-4:] if len(binding.account) > 4 else "****"
        if not shm:
            public_source = AccountSource(account_label=masked, agent_id=source["agent_id"], environment=binding.environment,
                                          session_id=source["qmt_session_id"], generation=source["generation"])
        groups[name] = group_type(datatype=name, status="complete", rows=public_rows, source=public_source,
                                   execution_started_at=batch["execution_started_at"], execution_finished_at=batch["execution_finished_at"],
                                   request_id=request_id, result_sha256=batch["result_sha256"])
    qualified = summary["observation_qualified"] and failure["code"] == 0
    if shm:
        qualified = qualified and failure["transport_error"] is None and failure["source_error_code"] is None
        return AccountObservationV3(groups, trade_date, qualified)
    return groups, trade_date, qualified


def project_account(scan_id, observation, close, *, schema_version="1.0"):
    _public_types(schema_version)
    if observation is None:
        return unavailable_account("本轮账户读取失败，未取得完整数据，请核查来源后刷新", scan_id, close, schema_version=schema_version)
    if isinstance(observation, AccountObservationV3):
        schema_version = "2.0"
        groups, trade_date, qualified = observation.groups, observation.trade_date, observation.qualified
    else:
        require(schema_version == "1.0")
        groups, trade_date, qualified = observation
    overview_type, _ = _public_types(schema_version)
    complete = qualified and all(group.status == "complete" for group in groups.values()) and close.status == "complete"
    status = "complete" if complete else "partial" if any(group.status == "complete" for group in groups.values()) else "unavailable"
    reason = "本轮四类账户数据已完整读取，各批时间独立，仅供只读查看" if complete else "本轮账户数据部分可见，缺失批次或关闭异常已标明，请核查后刷新" if status == "partial" else "本轮来源未完整交付账户数据，请核查后刷新"
    return overview_type(scan_id=scan_id, status=status, trade_date=trade_date, groups=groups, close=close, reason=reason)
