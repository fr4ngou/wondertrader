"""Choice 按公告日整理的已回购金额；原件与日汇总归观衡采集所有。"""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import re
from uuid import uuid4

from .source_fetch import SourceFailure
from .storage import encode

TABLE = 'source.buyback_announced'
URL = 'https://np-tjxg-g.eastmoney.com/api/smart-tag/stock/v3/pw/search-code'
BASIS = 'choice_announced_date_checked'


def _money(value):
    try:
        text = str(value).replace(',','').strip()
        match = re.fullmatch(r'(\d+(?:\.\d+)?)(亿|万|元)?',text)
        if not match:
            raise ValueError()
        amount = Decimal(match[1])*{'亿':100_000_000,'万':10_000,'元':1,None:1}[match[2]]
        if not amount.is_finite() or amount < 0:
            raise ValueError()
        return amount
    except (ValueError,InvalidOperation):
        raise SourceFailure('choice_buyback_amount_invalid') from None


def history(fetch, days, *, existing=()):
    """先复用已落盘日汇总；官网只读查询不需要账号、Key或积分。"""
    prior={row['date']:row for row in existing if row.get('amount_cny') is not None
           and (row['amount_cny']>0 or row.get('date_verified') is True)}
    captured=[]
    for selected in windows(days):
        if all(day in prior for day in selected):continue
        try:
            if captured:fetch.wait(1)
            rows=public_window(fetch,[day for day in selected if day not in prior])
        except SourceFailure as error:
            if error.code=='collection_stopped':raise
            _diagnostic(fetch,error.code)
            break
        captured.extend(row for row in rows if row['date'] in selected and row['date'] not in prior)
        if fetch.records and fetch.records[-1].get('diagnostic_code'):break
    merged={**prior,**{row['date']:row for row in captured}}
    return [merged[day] for day in days if day in merged]


def public_query(first, last, page, client_id):
    """官网公开选股查询；随机匿名客户端编号仅用于本次请求分页。"""
    fmt=lambda day:date.fromisoformat(day).strftime('%Y年%m月%d日')
    return dict(gids=[],matchWord='',timestamp='',shareToGuba=False,needAmbiguousSuggest=True,
        requestId='',product='',needCorrect=True,removedConditionIdList=[],client='WEB',ownSelectAll=False,
        dxInfo=[],biz='web_ai_select_stocks',customData='',
        keyWord=fmt(first)+'至'+fmt(last)+'已回购金额合计',pageSize=500,pageNo=page,fingerprint=client_id)


def public_window(fetch, days):
    """完整分页后生成带原件引用的自然日日汇总；截断和分页漂移保留缺口。"""
    client_id=uuid4().hex;rows=[];parents=[];columns=None;total=None;page=1
    while total is None or len(rows)<total:
        body=fetch.post_private_query(URL,public_query(days[0],days[-1],page,client_id))
        try:
            value=json.loads(body);data=value['data'];result=data['result']
            if str(value['code']) not in ('100','201'):raise ValueError()
            count=result['total'];part=result['dataList']
            if type(count)is not int or count<0 or type(part)is not list:raise ValueError()
            if total is None:total=count;columns=result['columns']
            if count!=total or result['columns']!=columns or len(rows)+len(part)>total:raise ValueError()
            if count and not part:raise ValueError()
            rows.extend(part);parents.append(fetch.records[-1]['sha256']);page+=1
        except (ValueError,KeyError,TypeError):
            raise SourceFailure('choice_public_query_incomplete') from None
    output=parse_public(columns,rows,total,days)
    proof=fetch.objects.put(encode(dict(
        schema='guanheng.choice-announced-window.v1',  # 完整官网窗口的输入证明版本。
        first=days[0],  # 已核查询首个自然日。
        last=days[-1],  # 已核查询末个自然日。
        stocks=total,  # 官网本窗口股票总数，逐页核同。
        parents=parents,  # 实际完整分页响应的摘要。
    )),kind='standard')
    received=fetch.records[-1]['retrieved_at']
    fetch.records.append(dict(kind='choice_window',sha256=proof,source_host='np-tjxg-g.eastmoney.com',
        status=200,retrieved_at=received,media_type='application/json'))
    output=[dict(row,
        source_sha256=proof,  # 定日金额实际依赖的完整查询证明。
        received_at=received,  # 对应原件实收UTC时间。
        date_verified=True,  # 空日经完整空查询或单日SUM独立核验。
    )for row in output]
    for day in sorted(set(days)-{row['date']for row in output}):
        # 多日预览未展示的日期以单日查询独立核零，避免小金额被舍入遮住。
        try:output.extend(public_window(fetch,[day]))
        except SourceFailure as error:
            if error.code=='collection_stopped':raise
            _diagnostic(fetch,error.code)
            break
    return sorted(output,key=lambda row:row['date'])


def parse_public(columns, rows, total, days):
    """日期来自已核查询列及每项最新公告日，金额沿供应商显示精度。"""
    try:
        selected=[c for c in columns if c.get('title')=='回购' and c.get('key','').startswith('DIM{')]
        column,=selected;key=column['key']
        bounds=re.findall(r'\d{4}-\d{2}-\d{2}',key)
        if len(days)==1 and len(bounds)==1:bounds*=2
        if bounds!=[min(days),max(days)] or '已回购金额'not in key or len(rows)!=total:raise ValueError()
        amounts={day:Decimal(0)for day in days};issuers={day:set()for day in days};seen=set()
        for row in rows:
            code=row['SECURITY_CODE']
            if not re.fullmatch(r'\d{6}',code) or code in seen:raise ValueError()
            seen.add(code)
            groups=json.loads(row['MTM_EXTRA|'+key])
            if not groups:raise ValueError()
            for group in groups:
                heads={h['colProp']:h for h in group['colHeads']}
                if heads['DIM_REPURAMOUNT']['unit']!='元' or 'DIM_UPDATEDATE'not in heads:raise ValueError()
                items=group['data']
                if not items:raise ValueError()
                # 官网嵌套表可能只预览部分方案；供应商区间总额独立核覆盖。
                controls={Decimal(str(item['SUM']))for item in items}
                if len(controls)!=1:raise ValueError()
                control=controls.pop()
                if not control.is_finite() or control<0:raise ValueError()
                observed=sum(_money(item['DIM_REPURAMOUNT'])for item in items)
                rounding=Decimal(0)
                for item in items:
                    match=re.fullmatch(r'(\d+(?:\.\d+)?)(亿|万|元)?',str(item['DIM_REPURAMOUNT']).replace(',',''))
                    digits=len(match[1].partition('.')[2])
                    rounding+=Decimal(10)**(-digits)*{'亿':100_000_000,'万':10_000,'元':1,None:1}[match[2]]/2
                if abs(observed-control)>rounding+Decimal('.01'):raise ValueError()
                for item in items:
                    day=item['DIM_UPDATEDATE'];date.fromisoformat(day)
                    if not min(days)<=day<=max(days):raise ValueError()
                    amount=_money(item['DIM_REPURAMOUNT'])
                    if code.startswith(('00','30','60','68')) and day in amounts:
                        amounts[day]+=amount;issuers[day].add(code)
                if len(days)==1 and code.startswith(('00','30','60','68')):
                    # 单日SUM包含同股票的全部方案，无需从预览逐项相加推断总额。
                    amounts[days[0]]+=control-observed
        return [dict(date=day,  # 供应商当前记录的最新公告日。
                     amount_cny=float(amounts[day]),  # 已回购公告金额，人民币元。
                     announcement_count=len(issuers[day]))  # 有相关公告的沪深发行人数。
                for day in sorted(days) if amounts[day]>0 or total==0 or len(days)==1]
    except (ValueError,KeyError,TypeError,AttributeError,InvalidOperation):
        raise SourceFailure('choice_public_query_incomplete') from None


def _diagnostic(fetch, code):
    """采集阶段结束后由原收束预算保存固定原因，无凭据及供应商错误原文。"""
    sha=fetch.objects.put(encode(dict(source='Choice',code=code)),kind='standard')
    fetch.records.append(dict(kind='choice_diagnostic',sha256=sha,source_host='np-tjxg-g.eastmoney.com',
        status=0,retrieved_at=datetime.now(timezone.utc).isoformat(),media_type='application/json',diagnostic_code=code))


def windows(days):
    """五个自然日分批核对与恢复，周末公告也归档。"""
    remaining=list(days)
    while remaining:
        first=date.fromisoformat(remaining[0]);selected=[day for day in remaining
            if date.fromisoformat(day)<first+timedelta(days=5)]
        yield selected
        remaining=remaining[len(selected):]


