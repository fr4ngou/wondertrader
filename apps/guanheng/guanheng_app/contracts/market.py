"""图表1.4标准分钟、1.5来源分钟、1.6来源日线；资格由原生服务提供。"""

from datetime import datetime
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_serializer, model_validator

SHANGHAI_TIME_ZONE = ZoneInfo("Asia/Shanghai")


class MarketModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @field_validator("*", mode="before")
    @classmethod
    def finite_numeric_types(cls, value, info):
        if info.field_name in {"open", "high", "low", "close", "volume", "price"} and isinstance(value, bool):
            raise ValueError("数值字段不接受布尔值")
        return value


class MarketChartCandle(MarketModel):
    occurred_at: datetime
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_candle(self):
        if self.occurred_at.utcoffset() is None:
            raise ValueError("分钟时间须包含时区")
        if self.high < max(self.open, self.close, self.low) or self.low > min(self.open, self.close, self.high):
            raise ValueError("OHLC关系不一致")
        return self


class MarketChartOverlayEvent(MarketModel):
    kind: Literal["signal", "execution"]
    occurred_at: datetime
    label: str = Field(min_length=1, max_length=500)
    direction: Literal["increase", "hold", "decrease", "buy", "sell"] | None = None
    price: float | None = Field(default=None, gt=0)
    status: str | None = Field(default=None, max_length=128)
    source: str = Field(min_length=1, max_length=128)
    correlation_id: UUID | None = None
    evidence_refs: list[str] = Field(default_factory=list, max_length=50)
    occurrence_count: int = Field(default=1, ge=1, le=10_000)

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError("标记时间须包含时区")
        return value


class MarketChartBenchmarkPoint(MarketModel):
    occurred_at: datetime
    close: float = Field(gt=0)

    @field_validator("occurred_at")
    @classmethod
    def aware(cls, value):
        if value.utcoffset() is None:
            raise ValueError("基准时间须包含时区")
        return value


class MarketChartBenchmark(MarketModel):
    symbol: str = Field(pattern=r"^[0-9]{6}\.(SH|SZ|BJ)$")  # 基准沿主图同一沪深北证券边界。
    points: list[MarketChartBenchmarkPoint] = Field(default_factory=list, max_length=2000)
    data_available: bool
    missing_reason: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def consistent(self):
        if self.data_available != bool(self.points) or self.data_available == bool(self.missing_reason):
            raise ValueError("基准可用性与数据不一致")
        return self


class MarketChartNativeSource(MarketModel):
    # 通达信适配仍保留设计；当前真实来源验收仅使用QMT。
    provider: Literal["Qmt"]
    dataset_version: str = Field(min_length=1, max_length=256)
    content_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    qualification: Literal["DevelopmentVerified", "NativeVerified", "ProductionQualified"]
    coverage: Literal["Unknown"] = "Unknown"
    adjustment: Literal["none"] = "none"
    source_minute_boundary: Literal["right"] = "right"
    chart_minute_boundary: Literal["left"] = "left"
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"


class MarketChartSourceLabelSource(MarketModel):
    """1.5原值投影保留来源标签；未知单位不授标准化股数或闭合分钟语义。"""
    provider: Literal["Qmt", "BigQuant", "Mixed"]
    dataset_version: str = Field(min_length=1, max_length=256)
    content_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    qualification: Literal["DevelopmentVerified"]
    coverage: Literal["Unknown"] = "Unknown"
    adjustment: Literal["none"] = "none"
    source_minute_boundary: Literal["left", "right", "unknown"]
    chart_minute_boundary: Literal["source_label"] = "source_label"
    timezone: Literal["Asia/Shanghai"] = "Asia/Shanghai"
    value_semantics: Literal["source"] = "source"
    timestamp_semantics: Literal["source_label"] = "source_label"
    price_unit: Literal["CNY", "unknown"]
    volume_unit: Literal["share", "lot", "unknown"]
    amount_unit: Literal["CNY", "unknown"]


class MarketChartCurrentDay(MarketModel):
    """WT原Writer形成中的日线；日期标签与实际来源时刻分别显示/传递。"""
    date: int = Field(strict=True, ge=10000101, le=99991231)  # 原交易日YYYYMMDD。
    source_at: datetime  # 原tick发生时刻，包含时区。
    observed_at: datetime  # WT读取原Writer副本的时刻，包含时区。
    closed: Literal[False] = False  # 当前值不声明已收盘归档。


class MarketChartSourceDateSource(MarketChartSourceLabelSource):
    """1.6日期标签保留来源日线；00:00标签不授闭合或知晓时间资格。"""
    # 日线原提供者或已核分段组合；分钟与快照仍沿各自原合同。
    provider: Literal["Qmt", "Tdx", "BaoStock", "Tencent", "CSI", "CNI", "Mixed"]  # 原提供者或实际分段组合。
    source_minute_boundary: Literal["unknown"]  # 日线不推导分钟边界。
    chart_minute_boundary: Literal["source_date"] = "source_date"  # 横轴使用上海交易日期。
    timestamp_semantics: Literal["source_date"] = "source_date"  # 日期标签与实际源时刻分别保留。
    current_day: MarketChartCurrentDay | None = None  # 末根来自原Writer时提供，已归档日线为None。


class MarketChartSourceWindow(MarketModel):
    from_at: datetime
    to_at: datetime

    @model_validator(mode="after")
    def ordered(self):
        if self.from_at.utcoffset() is None or self.to_at.utcoffset() is None or self.from_at > self.to_at:
            raise ValueError("来源窗口须为明确时区的顺序范围")
        return self


class MarketChartSourceObservation(MarketModel):
    source_schema: Literal["qmt.source-selection-observation.v1"]
    state: Literal["Archive", "Observed", "Partial"]
    source_window: MarketChartSourceWindow | None
    source_rows: int = Field(strict=True, ge=0, le=1000000)
    requested_limit: int = Field(strict=True, ge=1, le=2000)
    selected_rows: int = Field(strict=True, ge=0, le=2000)
    preparation_state: Literal["NotNeeded", "CallReturned", "Unknown", "Pending", "Unavailable", "NotSupported", "Budget"]
    preparation_request_id: UUID | None


class MarketChartSourceIdentity(MarketModel):
    provider: Literal["Qmt", "BigQuant"]
    instance_id: str = Field(min_length=1, max_length=128)
    session_id: str = Field(min_length=1, max_length=128)
    generation: int = Field(strict=True, ge=1)


class MarketChartProvenanceMetadata(MarketModel):
    """仅原分段捕获身份；集合内容身份不冒充捕获会话。"""
    source: MarketChartSourceIdentity
    qualification: Literal["DevelopmentVerified"]
    dataset_version: str = Field(min_length=1, max_length=256)
    source_license: str = Field(min_length=1, max_length=1024)
    adjustment: Literal["none"]
    factor_version: Literal[""]
    minute_boundary: Literal["left", "right", "unknown"]
    timezone: Literal["Asia/Shanghai"]
    content_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    value_semantics: Literal["source"]
    timestamp_semantics: Literal["source_label"]
    price_unit: Literal["CNY", "unknown"]
    volume_unit: Literal["share", "lot", "unknown"]
    amount_unit: Literal["CNY", "unknown"]


class MarketChartSourceProvenance(MarketModel):
    offset: int = Field(strict=True, ge=0, le=1999)
    count: int = Field(strict=True, ge=1, le=2000)
    first_at: datetime
    last_at: datetime
    metadata: MarketChartProvenanceMetadata


class MarketChartBundle(MarketModel):
    schema_version: Literal["1.4", "1.5", "1.6", "1.7", "1.8"] = "1.4"
    symbol: str = Field(pattern=r"^[0-9]{6}\.(SH|SZ|BJ)$")  # 沪深北证券；北交所日线沿SDK BSE路由读取。
    period: Literal["1m", "5m", "1d", "1w", "1mo"]
    candles: list[MarketChartCandle] = Field(default_factory=list, max_length=2000)
    data_available: bool
    as_of: datetime | None = None
    missing_reason: str | None = Field(default=None, max_length=500)
    source_period: Literal["1m", "1d"] = "1m"
    source_bar_count: int | None = Field(default=None, ge=0)
    first_source_at: datetime | None = None  # 周月图首个参与聚合的上海交易日零点，保留首周期的实际起点。
    archive_window: MarketChartSourceWindow | None = None  # 来源日线归档实际首末日期，不声明区间连续。
    source_kind: Literal["wondertrader"] = "wondertrader"
    native_source: MarketChartNativeSource | MarketChartSourceLabelSource | MarketChartSourceDateSource | None = None
    source_observation: MarketChartSourceObservation | None = None
    source_provenance: list[MarketChartSourceProvenance] = Field(default_factory=list, max_length=2000)
    observation_count: None = None
    volume_available: Literal[True] = True
    volume_partial: Literal[False] = False
    derived: bool = False
    benchmark: MarketChartBenchmark | None = None
    overlays: list[MarketChartOverlayEvent] = Field(default_factory=list, max_length=500)
    overlay_unavailable_sources: list[Literal["benchmark", "strategy", "bridge"]] = Field(default_factory=list)
    overlays_read_only: Literal[True] = True
    overlays_executable: Literal[False] = False

    @model_validator(mode="after")
    def consistent(self):
        source_dates = isinstance(self.native_source, MarketChartSourceDateSource)
        source_labels = isinstance(self.native_source, MarketChartSourceLabelSource) and not source_dates
        calendar_derived = self.period in ("1w", "1mo")
        if (self.schema_version in ("1.6", "1.8") or self.period in ("1d", "1w", "1mo")
                or self.source_period == "1d" or source_dates):
            expected_schema = "1.8" if calendar_derived else "1.6"
            if (self.schema_version != expected_schema or self.period not in ("1d", "1w", "1mo")
                    or self.source_period != "1d" or self.source_bar_count is None
                    or (not calendar_derived and self.source_bar_count != len(self.candles))
                    or self.native_source is not None and not source_dates):
                raise ValueError("来源日线及周月投影须绑定对应schema、日期语义及1d原周期")
            if any(c.occurred_at.astimezone(SHANGHAI_TIME_ZONE).time().isoformat() != "00:00:00" for c in self.candles):
                raise ValueError("日线时间仅接受上海交易日期零点标签")
        if source_labels and (self.schema_version not in ("1.5", "1.7") or self.period != "1m"):
            raise ValueError("来源标签图表须显式使用1.5/1.7与1分钟周期")
        if self.schema_version in ("1.5", "1.7") and self.data_available and not source_labels:
            raise ValueError("来源图表缺少原值语义")
        if self.schema_version == "1.7":
            if not source_labels or self.period != "1m" or not (self.source_observation or self.source_provenance):
                raise ValueError("来源范围图表须绑定1m原值及观测或分段")
            if self.source_observation and (self.source_observation.selected_rows != len(self.candles)
                    or self.source_observation.selected_rows > self.source_observation.requested_limit):
                raise ValueError("观测数量须与当前返回图表一致")
            offset = 0
            for part in self.source_provenance:
                if part.offset != offset or offset + part.count > len(self.candles):
                    raise ValueError("来源分段须连续覆盖返回行")
                if (part.first_at != self.candles[offset].occurred_at
                        or part.last_at != self.candles[offset+part.count-1].occurred_at):
                    raise ValueError("来源分段时间须与实际返回行一致")
                offset += part.count
            if self.source_provenance and offset != len(self.candles):
                raise ValueError("来源分段缺少返回行")
        elif self.source_observation is not None or self.source_provenance:
            raise ValueError("来源观测及分段须显式使用1.7")
        if self.data_available != bool(self.candles) or self.data_available == bool(self.missing_reason):
            raise ValueError("图表可用性与数据不一致")
        if self.derived != (self.period in ("5m", "1w", "1mo")):
            raise ValueError("周期推导身份不一致")
        if self.period == "5m" and self.source_bar_count is not None:
            raise ValueError("5分钟推导不声明原分钟数量")
        if self.data_available and (self.native_source is None or self.as_of != self.candles[-1].occurred_at):
            raise ValueError("图表缺少有效来源或观察时间")
        if self.as_of is not None and self.as_of.utcoffset() is None:
            raise ValueError("观察时间须包含时区")
        if any(c.volume is None for c in self.candles):
            raise ValueError("原生图表须具备来源成交量")
        if self.source_bar_count is not None:
            if calendar_derived and self.source_bar_count < len(self.candles):
                raise ValueError("周月聚合的来源日线数量不足")
            if not calendar_derived and self.source_bar_count != len(self.candles):
                raise ValueError("原生周期数量不一致")
        times = [c.occurred_at for c in self.candles]
        if times != sorted(set(times)):
            raise ValueError("分钟顺序或唯一性无效")
        if self.first_source_at is not None and (
            not calendar_derived or not times or self.first_source_at.utcoffset() is None
            or self.first_source_at.astimezone(SHANGHAI_TIME_ZONE).time().isoformat() != "00:00:00"
            or self.first_source_at > times[0]
        ):
            raise ValueError("周月图首个来源日期须落在首周期结束之前")
        if self.overlay_unavailable_sources != sorted(set(self.overlay_unavailable_sources)):
            raise ValueError("缺失来源须排序去重")
        return self

    @model_serializer(mode="wrap")
    def preserve_legacy_fields(self, handler):
        value = handler(self)
        if self.schema_version != "1.7":
            value.pop("source_observation", None)
            value.pop("source_provenance", None)
        if self.first_source_at is None:
            value.pop("first_source_at", None)
        if self.archive_window is None:
            value.pop("archive_window", None)
        return value
