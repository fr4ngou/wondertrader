"""央行大型银行原表准入；年月/单位及金额比值由本来源唯一解释。"""
import calendar
import io
import math
import re
from .source_fetch import SourceFailure

MAX_PDF_BYTES=4*1024*1024
MAX_TEXT_BYTES=1024*1024
MAX_PAGES=4
MAX_OBJECTS=10000


def bank_pdf(body,year,start,end,budget):
    """HTTP已存原件后读取固定PDF；库内非协作工作沿原Job，检查点不续D。"""
    budget.remaining()
    if not body.startswith(b'%PDF-') or len(body)>min(MAX_PDF_BYTES,budget.response_bytes):
        raise SourceFailure('pbc_pdf_budget_or_format')
    from pypdf import PdfReader
    try:
        with io.BytesIO(body) as stream:
            document=PdfReader(stream,strict=True)
            try:
                budget.remaining()
                if document.is_encrypted:raise SourceFailure('pbc_pdf_encrypted')
                if sum(len(items) for items in document.xref.values())+len(document.xref_objStm)>MAX_OBJECTS:
                    raise SourceFailure('pbc_pdf_budget_or_format')
                declared=document.root_object['/Pages'].get('/Count')
                if not isinstance(declared,int) or not 1<=declared<=MAX_PAGES:
                    raise SourceFailure('pbc_pdf_budget_or_format')
                parts=[];size=0;pages=0
                for page in document.pages:
                    budget.remaining();pages+=1
                    if pages>MAX_PAGES:raise SourceFailure('pbc_pdf_budget_or_format')
                    text=page.extract_text(extraction_mode='layout') or '';budget.remaining()
                    size+=len(text.encode('utf8'))
                    if size>MAX_TEXT_BYTES:raise SourceFailure('pbc_pdf_text_budget')
                    parts.append(text)
                if pages!=declared:raise SourceFailure('pbc_pdf_budget_or_format')
                rows,months=bank_text('\n'.join(parts),year,start,end)
                budget.remaining()
                return rows,dict(year=year,unit='CNY_100m',months=months,pages=pages)
            finally:document.close()
    except SourceFailure:raise
    except Exception:raise SourceFailure('pbc_pdf_invalid') from None


def bank_text(text,year,start,end):
    """布局月列决定金额归属，空白尾月保留未披露，内部空列拒绝。"""
    if not any(title in text for title in ('中资大型银行人民币信贷收支表','中资全国性大型银行人民币信贷收支表')):
        raise SourceFailure('pbc_report_identity')
    if re.search(r'单位\s*[:：]\s*亿元',text) is None:raise SourceFailure('pbc_report_unit')
    lines=text.splitlines()
    headers=[list(re.finditer(r'(?<!\d)(\d{4})\.(0[1-9]|1[0-2])(?!\d)',line))
        for line in lines if '项目' in line and re.search(r'\bItem\b',line)]
    headers=[items for items in headers if items]
    if len(headers)!=1 or [(int(item[1]),int(item[2])) for item in headers[0]]!=[(year,month) for month in range(1,13)]:
        raise SourceFailure('pbc_report_year_or_months')
    centers=[(item.start()+item.end())/2 for item in headers[0]]
    left=math.floor(centers[0]-(centers[1]-centers[0])/2)
    def amounts(label):
        candidates=[line for line in lines if label in line]
        if len(candidates)!=1:raise SourceFailure('pbc_report_schema_changed')
        line=candidates[0];values={}
        for item in re.finditer(r'\S+',line):
            if item.end()<=left:continue
            if item.start()<left:raise SourceFailure('pbc_report_columns_changed')
            # 校验完整金额，拒绝括号/未知符号/尾注及不规则千分位，避免截出正数。
            if re.fullmatch(r'-?(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)(?:\.[0-9]+)?',item[0]) is None:
                raise SourceFailure('pbc_report_amount_format')
            center=(item.start()+item.end())/2
            distances=[abs(center-location) for location in centers];column=min(range(12),key=distances.__getitem__)
            width=(centers[min(column+1,11)]-centers[max(column-1,0)])/(2 if 0<column<11 else 1)
            if distances[column]>=width/2 or column in values:raise SourceFailure('pbc_report_columns_changed')
            value=float(item[0].replace(',',''))
            if not math.isfinite(value):raise SourceFailure('pbc_report_denominator_invalid')
            values[column]=value
        if not values or sorted(values)!=list(range(len(values))):raise SourceFailure('pbc_report_columns_changed')
        return values
    bonds,totals=amounts('二、债券投资'),amounts('资金运用总计')
    if bonds.keys()!=totals.keys():raise SourceFailure('pbc_report_columns_changed')
    rows=[]
    for column in sorted(bonds):
        bond,total=bonds[column],totals[column]
        if not 0<=bond<=total or total<=0:raise SourceFailure('pbc_report_denominator_invalid')
        month=column+1;day=f'{year:04}-{month:02}-{calendar.monthrange(year,month)[1]:02}'
        if start<=day<=end:rows.append(dict(date=day,bonds=bond,total=total,bond_pct=100*bond/total,available_at=None))
    return rows,[column+1 for column in sorted(bonds)]
