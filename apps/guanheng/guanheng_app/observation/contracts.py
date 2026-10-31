"""Public read-only observation contract; no execution qualifications."""
from datetime import date
from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

API_PREFIX = '/v1/market-observation'
UI_PREFIX = '/v1/ui/market-observation'
SCHEMA_VERSION = 'market-observation/1'
USAGE = dict(permitted_use='internal_research', authoritative_market_data=False,
             causal_eligible=False, executable=False, redistribution_allowed=False)

class ObservationField(BaseModel):
    model_config=ConfigDict(extra='allow')
    label:str=Field(min_length=1)
    data_type:Literal['number','integer','string','date','datetime']
    nullable:bool=True
    required:bool=False
    unit:str|None=None

class ObservationAsset(BaseModel):
    model_config=ConfigDict(extra='allow')
    asset_id:str
    sha256:str=Field(pattern=r'^[a-f0-9]{64}$')
    byte_size:int=Field(ge=0)
    source_id:str|None
    capture_id:str|None
    object_ref:str
    media_type:str|None
    encoding:str|None
    compression:str|None
    published_at:str|None
    available_at:str|None
    retrieved_at:str|None
    ingested_at:str|None
    source_timezone:str|None
    calendar_id:str|None
    calendar_version:str|None
    license_ref:str|None
    provider_symbol:str|None
    instrument_id:str|None
    market:str|None
    dataset_id:str|None
    dataset_version:str|None
    definition_id:str|None
    definition_version:str|None
    definition_hash:str|None
    schema_version:str
    revision_id:str|None
    observation_start:str|None
    observation_end:str|None
    internal_use:str
    redistribution_allowed:bool
    quality:dict[str,str]
    usage:dict[str,Any]

class SeriesQuery(BaseModel):
    model_config = ConfigDict(extra='forbid')
    metric_id: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9_.-]+$')
    snapshot_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    dataset_version: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    start: date | None = None
    end: date | None = None
    fields: str | None = Field(default=None, max_length=2000)
    cursor: str | None = Field(default=None, max_length=3000)
    limit: int = Field(default=500, ge=1, le=1000)
    window: int | None = Field(default=None, ge=2, le=2000)
    k: float | None = Field(default=None, ge=0, le=10)
    method: Literal['sma', 'ema', 'ema_moments'] | None = None
    pcr_type: Literal['oi', 'volume'] | None = None
    as_of: date | None = None

    @model_validator(mode='after')
    def check_dates(self):
        if self.start and self.end and self.start > self.end:
            raise ValueError('起始日期须早于或等于截止日期')
        return self

class ObservationError(Exception):
    def __init__(self, code: str, detail: str, status: int = 400):
        self.code, self.detail, self.status = code, detail, status
        super().__init__(detail)

class ExportQuery(SeriesQuery):
    format: Literal['csv','json','jsonl'] = 'jsonl'

class UIExportQuery(ExportQuery):
    format: Literal['csv','json','jsonl'] = 'csv'

class SeriesPage(BaseModel):
    metric_id: str
    snapshot_id: str
    dataset_version: str
    definition: dict[str, Any]
    rows: list[dict[str, Any]]
    next_cursor: str | None
    total: int
    coverage: dict[str, Any]
    usage: dict[str, Any] = Field(default_factory=lambda: dict(USAGE))


class SnapshotCoverage(BaseModel):
    model_config = ConfigDict(extra='allow')
    start: str
    end: str
    observations: int = Field(ge=0)

    @model_validator(mode='after')
    def dates(self):
        if date.fromisoformat(self.start) > date.fromisoformat(self.end):
            raise ValueError('invalid coverage')
        return self


class SnapshotLine(BaseModel):
    model_config = ConfigDict(extra='allow')
    key: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1)
    unit: str
    color: str
    formula: str
    reading: str


class SnapshotDefinition(BaseModel):
    """页面和公式读取必需的登记资料；额外原元数据原样保留。"""
    model_config = ConfigDict(extra='allow')
    id: str = Field(pattern=r'^[a-zA-Z0-9_.-]{1,100}$')
    board: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1)
    definition_version: str = Field(min_length=1)
    frequency: str = Field(min_length=1)
    source: str
    source_url: str
    unit: str
    parameters: bool
    primary_field: str
    field_schema: dict[str, ObservationField]
    lines: list[SnapshotLine] = Field(min_length=1, max_length=256)
    coverage: SnapshotCoverage
    limitations: list[str]
    reading: str
    formula: str
    calculation_defaults: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode='after')
    def calculation(self):
        SeriesQuery.model_validate(dict(metric_id=self.id, **self.calculation_defaults), strict=True)
        return self


class SnapshotDataset(BaseModel):
    model_config = ConfigDict(extra='allow')
    partition: str = Field(pattern=r'^[a-f0-9]{64}$')
    definition: SnapshotDefinition
    parents: list[str]
    parser_version: str = Field(min_length=1)
    rows: int = Field(ge=0, le=100000)


class SnapshotBoard(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1)


class SnapshotPreferences(BaseModel):
    model_config = ConfigDict(extra='allow')
    default_board: str
    default_datasets: dict[str, str]


class SnapshotReference(BaseModel):
    model_config = ConfigDict(extra='allow')
    object_sha256: str | None = Field(default=None, pattern=r'^[a-f0-9]{64}$')
    media_type: str | None = None
    data: str | None = None

    @model_validator(mode='after')
    def object_type(self):
        if self.object_sha256 and not self.media_type:
            raise ValueError('reference media type missing')
        return self


class SnapshotManifest(BaseModel):
    """采用前验证结构，验证结果不重编码原manifest，原版本身份保持。"""
    model_config = ConfigDict(extra='allow')
    schema_version: Literal['market-observation/1']
    published_at: str
    boards: list[SnapshotBoard] = Field(max_length=256)
    preferences: SnapshotPreferences
    datasets: dict[str, SnapshotDataset]
    assets: dict[str, ObservationAsset]
    source_tables: dict[str, str] = Field(default_factory=dict)
    source_table_parents: dict[str, list[Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]]] = Field(default_factory=dict)
    references: dict[str, SnapshotReference] = Field(default_factory=dict)
    stock_pb_partitions: dict[str, Any] | None = None
    migration_aliases: str | None = None
    source_payload: str | None = None

    @model_validator(mode='after')
    def identities(self):
        from datetime import datetime
        when = datetime.fromisoformat(self.published_at)
        if when.tzinfo is None:
            raise ValueError('publication timezone missing')
        boards = {board.id for board in self.boards}
        if len(boards) != len(self.boards) or len(self.datasets) > 256 or len(self.assets) > 100000:
            raise ValueError('duplicate boards or excessive datasets')
        if (len(self.source_table_parents)>256 or set(self.source_table_parents)-set(self.source_tables)
                or any(len(parents)>256 for parents in self.source_table_parents.values())):
            raise ValueError('source table parent identity or capacity invalid')
        if self.datasets and self.preferences.default_board not in boards:
            raise ValueError('default board missing')
        for key, item in self.datasets.items():
            if key != item.definition.id or item.definition.board not in boards:
                raise ValueError('dataset identity or board missing')
            if item.definition.primary_field not in item.definition.field_schema:
                raise ValueError('primary field missing')
        for key, item in self.assets.items():
            if key != item.asset_id:
                raise ValueError('asset identity mismatch')
        return self
