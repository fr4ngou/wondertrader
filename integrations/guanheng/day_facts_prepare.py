"""数据侧固化已准入的定日补充事实；输入来自现有来源适配器，不连接供应商。"""
import hashlib,json
import os,time,math
from pathlib import Path
from ..guanheng_market_client.daily_facts import validate_day_facts


def prepare_facts_catalog(days,output,*,maximum_total_bytes=268435456,maximum_rows=2000000):
    """逐日有界固化至独占新根；成功后才写目录，失败保留未发布原件供owner核查。

    days可为迭代器；每次只编码一个8MiB以内的日期，不物化全部原JSON副本。
    总原JSON字节及记录分别受显式预算约束，最多366日；不声明RSS硬上限。
    """
    if type(maximum_total_bytes)is not int or not 8388608<=maximum_total_bytes<=1073741824:
        raise ValueError('daily facts preparation byte budget invalid')
    if type(maximum_rows)is not int or not 1<=maximum_rows<=10000000:raise ValueError('daily facts preparation row budget invalid')
    encode=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    output=Path(output);output.mkdir(parents=False,exist_ok=False);entries=[];seen=set();total=rows=0
    for value in days:
        validate_day_facts(value)
        if value['date']in seen or len(seen)>=366:raise ValueError('daily facts preparation day repeated or exceeds capacity')
        seen.add(value['date']);body=encode(value);total+=len(body);rows+=len(value['rows'])
        if len(body)>8388608 or total>maximum_total_bytes or rows>maximum_rows:raise ValueError('daily facts preparation capacity')
        name=value['date']+'.json';(output/name).write_bytes(body)
        entries.append(dict(date=value['date'],  # 原观察交易日YYYY-MM-DD。
            path=name,  # 本次独占目录内的相对原件路径。
            sha256=hashlib.sha256(body).hexdigest()))  # 完整定日规范化事实身份。
    if not entries:raise ValueError('daily facts preparation days empty')
    entries.sort(key=lambda e:e['date'])
    catalog=output/'catalog.json';body=encode(dict(schema='guanheng.daily-facts-catalog.v1',days=entries));catalog.write_bytes(body)
    return dict(path=str(catalog.absolute()),sha256=hashlib.sha256(body).hexdigest())


def extend_facts_catalog(previous, days, output, *, deadline, maximum_total_bytes=268435456, maximum_rows=2000000,
                         enrich_existing=None):
    """新根逐日扩充/修订；旧原件逐件核SHA并保留，峰值只编码/解析一个日期。

    days可为迭代器，同日最多一个新版本；旧目录和文件保持原样，最多366日。
    更新同日文件以内容SHA命名，避免修改旧根的硬链接。可在核验旧原件时补充来源事实。
    成功后才写最终目录。
    """
    from .day_facts import DayFactsStore,_read
    if (type(maximum_total_bytes)is not int or not 8388608<=maximum_total_bytes<=1073741824
            or type(maximum_rows)is not int or not 1<=maximum_rows<=10000000
            or type(deadline)not in (int,float)or not math.isfinite(deadline)):
        raise ValueError('daily facts extension budget invalid')
    def check():
        if time.monotonic()>=deadline:raise TimeoutError('daily facts extension deadline expired')
    encode=lambda v:json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
    old=DayFactsStore(previous);output=Path(output).absolute();output.mkdir(parents=False,exist_ok=False)
    entries={};total=rows=0
    def admit(day,body,count):
        nonlocal total,rows
        check();total+=len(body);rows+=count
        if len(body)>8388608 or total>maximum_total_bytes or rows>maximum_rows or len(entries)>=366:
            raise ValueError('daily facts extension capacity')
        identity=hashlib.sha256(body).hexdigest();name=day+'-'+identity+'.json'
        entry=dict(date=day,  # 原定日事实的市场日期。
            path=name,  # 新独占根内的内容寻址文件名，不覆盖旧版本。
            sha256=identity)  # 完整原事实JSON字节身份。
        entries[day]=entry;return output/name
    try:
        for value in days:
            check();validate_day_facts(value);day=value['date']
            if day in entries:raise ValueError('daily facts extension day repeated')
            body=encode(value);admit(day,body,len(value['rows'])).write_bytes(body)
        for day,entry in sorted(old._entries.items()):
            check()
            if day in entries:continue
            path=(old._root/entry['path']).resolve(strict=True)
            if not path.is_relative_to(old._root):raise ValueError('daily facts extension source escaped')
            body=_read(path,8388608,entry['sha256'])
            from ..guanheng_market_client import strict_json
            value=validate_day_facts(strict_json(body))
            if value['date']!=day:raise ValueError('daily facts extension date differs')
            enriched = value if enrich_existing is None else enrich_existing(value)
            if enriched is not value:
                validate_day_facts(enriched)
                body = encode(enriched)
            target=admit(day,body,len(value['rows']))
            if enriched is value and path.drive.upper()==target.drive.upper():os.link(path,target)
            else:target.write_bytes(body)
        if not entries:raise ValueError('daily facts extension empty')
        catalog=output/'catalog.json';body=encode(dict(schema='guanheng.daily-facts-catalog.v1',days=[entries[d]for d in sorted(entries)]))
        check();catalog.write_bytes(body)
        return dict(path=str(catalog),sha256=hashlib.sha256(body).hexdigest())
    finally:old.close()
