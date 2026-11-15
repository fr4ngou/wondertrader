"""显式离线QMT分钟缓存导出；布局来自已验证样本，存储仍归原QMI/WT入口。"""
from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import sys
from uuid import uuid4

from .price_quality import PriceRangeQuality
from .qmt_dat_layout import MAGIC, RECORD_BYTES, DATASET_VERSION, COUNTERS

SHANGHAI=timezone(timedelta(hours=8))
MAX_FILE_BYTES=268435456
DEFAULT_TOTAL_ROWS=10000000


class CacheExportError(ValueError):
    """固定分类不包含源记录；失败保留本次partial供调用方核查。"""
    def __init__(self,category):
        self.category=category
        super().__init__(category)


def _need(value,category='input'):
    if not value:raise CacheExportError(category)


def _ordinary(path,directory=False):
    info=path.lstat()
    _need(not stat.S_ISLNK(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400,'source_identity')
    _need(stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode),'source_identity')
    return info


def _root(path):
    path=Path(path).absolute()
    _need('..' not in path.parts)
    for parent in reversed(path.parents):_ordinary(parent,True)
    _ordinary(path,True)
    return path


def _stamp(info):
    return info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns


def _same_file(path_info,handle_info):
    # Windows的lstat与fstat可能分别把创建时间、修改时间放在ctime；
    # 跨接口只比较共同身份字段，birthtime双方具备时再明确比较创建时间。
    fields=('st_dev','st_ino','st_size','st_mtime_ns')
    if any(getattr(path_info,key)!=getattr(handle_info,key) for key in fields):return False
    if hasattr(path_info,'st_birthtime_ns') and hasattr(handle_info,'st_birthtime_ns'):
        return path_info.st_birthtime_ns==handle_info.st_birthtime_ns
    return True


def _new_root(path):
    path=Path(path).absolute()
    _need('..' not in path.parts)
    _root(path.parent)
    path.mkdir(parents=False,exist_ok=False)
    return path


def _symbol(value):
    _need(type(value) is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ)',value) is not None)
    return value


def _period(value):
    _need(value in ('1m','1d'))
    return ('60','sh-sz-minute-cache',2,'qmt-minute-cache-64.v2') if value=='1m' else (
        '86400','sh-sz-daily-cache',3,'qmt-daily-cache-64.v1')


def scan_cache(cache_root,period='1m'):
    """只发现所选沪深周期目录下六位DAT；发现不等同每文件均可成功导入。"""
    root=_root(cache_root);symbols=[];directory_name,unused,unused2,unused3=_period(period)
    for market in ('SH','SZ'):
        directory=root/market/directory_name
        if not directory.exists():continue
        _ordinary(root/market,True);_ordinary(directory,True)
        with os.scandir(directory) as entries:
            for entry in entries:
                if re.fullmatch(r'[0-9]{6}\.DAT',entry.name,re.IGNORECASE):
                    _ordinary(Path(entry.path))
                    symbols.append(entry.name[:6]+'.'+market)
                    _need(len(symbols)<=10000,'budget')
    return sorted(symbols)


def _json_new(path,value,maximum=4*1024*1024):
    raw=(json.dumps(value,ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')
    _need(type(maximum) is int and 1<=maximum<=16*1024*1024 and len(raw)<=maximum,'budget')
    with path.open('xb') as stream:
        stream.write(raw);stream.flush();os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def _date_window(from_date,to_date):
    """来源标签日期的显式闭区间；省略端点表示该方向不设日期边界。"""
    values=[]
    for value in (from_date,to_date):
        _need(value is None or type(value) is str and re.fullmatch(r'\d{4}-\d{2}-\d{2}',value) is not None)
        values.append(date.fromisoformat(value) if value is not None else None)
    start,end=values
    _need(start is None or end is None or start<=end)
    return start,end,dict(from_date=from_date,to_date=to_date,basis='source_label_date')


def _export_one(root,symbol,csv_path,max_rows,max_input_bytes,block_records,period='1m',*,from_date=None,to_date=None,max_scan_rows=None,
                dates=None,consume=None,check=lambda:None):
    start,end,selection=_date_window(from_date,to_date)
    code,market=symbol.split('.')
    directory_name,unused,unused2,unused3=_period(period)
    directory=root/market/directory_name;_ordinary(root/market,True);_ordinary(directory,True)
    source=directory/(code+'.DAT');before=_ordinary(source)
    _need(before.st_size>=8 and (before.st_size-8)%RECORD_BYTES==0,'layout')
    count=(before.st_size-8)//RECORD_BYTES
    # 窗口仍完整扫描并计算原件SHA；输出行预算与有界原文件扫描分别约束。
    _need(before.st_size<=MAX_FILE_BYTES and (start is not None or end is not None or count<=max_rows),'budget')
    _need(max_scan_rows is None or count<=max_scan_rows,'budget')
    if count==0:
        with source.open('rb') as stream:
            opened=os.fstat(stream.fileno())
            _need(_same_file(before,opened),'source_changed')
            raw=stream.read(9);_need(raw==MAGIC,'layout')
            after=os.fstat(stream.fileno());path_after=_ordinary(source)
            _need(_stamp(after)==_stamp(opened) and _stamp(path_after)==_stamp(before) and
                  _same_file(path_after,after),'source_changed')
        return dict(symbol=symbol,status='empty',source_path=str(source),
            source_sha256=hashlib.sha256(raw).hexdigest(),source_size=opened.st_size,
            source_mtime_ns=opened.st_mtime_ns,source_device=opened.st_dev,
            source_file_id=opened.st_ino,rows=0,scanned_rows=0,selected_rows=0,excluded_rows=0,selection=selection)
    original=hashlib.sha256();csv_hash=hashlib.sha256();csv_bytes=0
    first=last=None;previous=None;observed=selected=0;quality=PriceRangeQuality()
    with source.open('rb') as stream, (csv_path.open('xb') if csv_path is not None else nullcontext()) as output:
        opened=os.fstat(stream.fileno());_need(_same_file(before,opened),'source_changed')
        header=stream.read(8);_need(header==MAGIC,'layout');original.update(header)
        def emit(raw):
            nonlocal csv_bytes
            _need(csv_bytes+len(raw)<=max_input_bytes,'budget')
            output.write(raw);csv_hash.update(raw);csv_bytes+=len(raw)
        if output is not None:
            emit(b'timestamp,open,high,low,close,volume,amount\n')
        remaining=opened.st_size-8
        while remaining:
            check()
            size=min(remaining,block_records*RECORD_BYTES)
            block=stream.read(size);_need(len(block)==size,'source_changed')
            original.update(block);remaining-=size
            for offset in range(0,size,RECORD_BYTES):
                seconds=struct.unpack_from('<I',block,offset)[0]
                _need(seconds%60==0 and (previous is None or seconds>previous),'minute_order')
                label=datetime.fromtimestamp(seconds,SHANGHAI)
                # 日线日期范围由uint32纪元秒及零点+08标签推出；分钟沿原范围。
                _need(period=='1d' or 1992<=label.year<=2099,'timestamp')
                if period=='1d':_need(not (label.hour or label.minute or label.second),'timestamp')
                previous=seconds;observed+=1
                if (start is not None and label.date()<start) or (end is not None and label.date()>end):continue
                if dates is not None and label.date() not in dates:continue
                _need(selected<max_rows,'budget')
                prices=struct.unpack_from('<4I',block,offset+4)
                volume,amount=COUNTERS.unpack_from(block,offset+24)
                _need(volume>=0 and amount>=0,'quantity')
                op,high,low,close=prices
                _need(min(prices)>0,'price')
                text=label.isoformat();first=text if first is None else first;last=text
                # 原始四价独立保存；来源范围异常只记录质量，不改值或丢整只证券。
                quality.observe(text,op,high,low,close)
                # 只按固定布局还原千分之一价格；量额不猜倍率，原整数文本保留。
                prices=tuple(value/1000.0 for value in prices)
                if output is not None:
                    row=[text]+[repr(value) for value in prices]+[str(volume),str(amount)]
                    emit((','.join(row)+'\n').encode('ascii'))
                else:
                    consume(label,prices,volume,amount)
                selected+=1
        _need(not stream.read(1) and observed==count,'source_changed')
        after=os.fstat(stream.fileno())
        path_after=_ordinary(source)
        # 同一句柄及同一路径各自前后保留ctime稳定性检查。
        _need(_stamp(after)==_stamp(opened) and _stamp(path_after)==_stamp(before) and
              _same_file(path_after,after),'source_changed')
        if output is not None:
            output.flush();os.fsync(output.fileno())
        _need(_stamp(os.fstat(stream.fileno()))==_stamp(opened),'source_changed')
    return dict(symbol=symbol,status='exported' if selected else 'empty',source_path=str(source),source_sha256=original.hexdigest(),
        source_size=opened.st_size,source_mtime_ns=opened.st_mtime_ns,source_device=opened.st_dev,
        source_file_id=opened.st_ino,rows=selected,scanned_rows=observed,selected_rows=selected,
        excluded_rows=observed-selected,selection=selection,first_label=first,last_label=last,
        csv_path='csv/'+csv_path.name if csv_path is not None else None,csv_sha256=csv_hash.hexdigest(),csv_bytes=csv_bytes,
        price_range_quality=quality.result())


def read_cache_dates(cache_root,symbol,days,*,period,check):
    """复用本地DAT原解析器，仅向日更返回指定日期及已核原件，不写CSV。"""
    root=_root(cache_root)
    _need(type(symbol) is str and re.fullmatch(r'[0-9]{6}\.(SH|SZ|BJ)',symbol) is not None)
    dates={date.fromisoformat(day) for day in days}
    if not dates:
        return [],None
    bounds=_inspect_one(root,symbol,period)
    if (bounds['status']=='empty' or bounds['first_label'][:10]>max(dates).isoformat()
            or bounds['last_label'][:10]<min(dates).isoformat()):
        return [],None
    rows=[]
    def receive(label,prices,volume,amount):
        rows.append((label,*prices,volume,amount))
    evidence=_export_one(root,symbol,None,len(dates)*(241 if period=='1m' else 1),
        MAX_FILE_BYTES,4096,period,from_date=min(dates).isoformat(),to_date=max(dates).isoformat(),
        dates=dates,consume=receive,check=check)
    return rows,evidence['source_sha256']


def _select_cache(root,symbols,all_cache):
    _need(type(all_cache) is bool)
    if all_cache:
        _need(symbols is None);selected=scan_cache(root)
    else:
        _need(type(symbols) in (list,tuple));selected=[_symbol(value) for value in symbols]
    _need(0<len(selected)<=10000 and len(selected)==len(set(selected)))
    return selected


def _inspect_one(root,symbol,period='1m'):
    code,market=symbol.split('.')
    directory_name,unused,unused2,unused3=_period(period)
    _ordinary(root/market,True);_ordinary(root/market/directory_name,True)
    path=root/market/directory_name/(code+'.DAT');before=_ordinary(path)
    _need(before.st_size>=8 and (before.st_size-8)%RECORD_BYTES==0,'layout')
    count=(before.st_size-8)//RECORD_BYTES
    with path.open('rb') as stream:
        opened=os.fstat(stream.fileno());_need(_same_file(before,opened),'source_changed')
        _need(stream.read(8)==MAGIC,'layout')
        labels=[]
        if count:
            # 首末抽样只定位磁盘边界；中间记录质量仍由export/Importer逐行验证。
            for offset in (8,8+(count-1)*RECORD_BYTES):
                stream.seek(offset);raw=stream.read(RECORD_BYTES)
                _need(len(raw)==RECORD_BYTES,'source_changed')
                seconds=struct.unpack_from('<I',raw)[0]
                label=datetime.fromtimestamp(seconds,SHANGHAI)
                _need(seconds%60==0 and (period=='1d' or 1992<=label.year<=2099),'timestamp')
                if period=='1d':_need(not (label.hour or label.minute or label.second),'timestamp')
                labels.append(label.isoformat())
            _need(labels[0]<=labels[1],'minute_order')
        after=os.fstat(stream.fileno());path_after=_ordinary(path)
        _need(_stamp(after)==_stamp(opened) and _stamp(path_after)==_stamp(before)
              and _same_file(path_after,after),'source_changed')
    return dict(symbol=symbol,status='sampled' if count else 'empty',source_path=str(path),
        source_size=opened.st_size,source_mtime_ns=opened.st_mtime_ns,
        source_device=opened.st_dev,source_file_id=opened.st_ino,estimated_rows=count,
        sampled_records=min(count,2),first_label=labels[0] if labels else None,
        last_label=labels[-1] if labels else None)


def inspect_cache(cache_root,symbols,output_root,*,all_cache=False,period='1m'):
    """返回首末抽样库存并保存新清单；只读、有界、无SDK，完整覆盖仍为unknown。"""
    root=_root(cache_root);directory_name,scope,unused,unused2=_period(period)
    selected=_select_cache(root,symbols,all_cache) if not all_cache else scan_cache(root,period)
    root_before=_ordinary(root,True);output=_new_root(output_root)
    sources=[];last_dates={};first_dates={};rows=0
    # 逐文件保留只读观察，长清点超时后可核已读进度；最终inventory.json才表示整次完成。
    journal_bytes=0
    with (output/'inventory-items.jsonl').open('xb') as journal:
        for symbol in selected:
            try:
                item=_inspect_one(root,symbol,period)
            except (CacheExportError,OSError,OverflowError,ValueError) as error:
                item=dict(symbol=symbol,status='unavailable',
                    category=error.category if isinstance(error,CacheExportError) else 'dependency')
            raw=(json.dumps(item,ensure_ascii=True,sort_keys=True,separators=(',',':'))+'\n').encode('utf-8')
            journal_bytes+=len(raw);_need(journal_bytes<=4*1024*1024,'budget')
            journal.write(raw);journal.flush()
            sources.append(item);rows+=item.get('estimated_rows',0)
            if item.get('first_label'):
                for field,counts in (('first_label',first_dates),('last_label',last_dates)):
                    key=item[field][:10];counts[key]=counts.get(key,0)+1
    root_after=_ordinary(root,True)
    _need((root_before.st_dev,root_before.st_ino)==(root_after.st_dev,root_after.st_ino),'source_changed')
    result=dict(schema='qmt.local-dat-inventory.v1',status='passed',cache_root=str(root),period=period,
        inventory_scope=scope,validation='header-length-first-last-only',
        coverage='unknown',new_sdk_calls=0,files=len(sources),
        sampled_files=sum(item['status']=='sampled' for item in sources),
        empty_files=sum(item['status']=='empty' for item in sources),
        unavailable_files=sum(item['status']=='unavailable' for item in sources),
        estimated_rows=rows,source_bytes=sum(item.get('source_size',0) for item in sources),
        first_dates=dict(sorted(first_dates.items())),last_dates=dict(sorted(last_dates.items())),
        securities=sources)
    _json_new(output/'inventory.json',result,16*1024*1024)
    return result


def export_cache(cache_root,symbols,output_root,*,all_cache=False,period='1m',max_rows=1000000,
                 max_total_rows=DEFAULT_TOTAL_ROWS,max_input_bytes=MAX_FILE_BYTES,block_records=4096,from_date=None,to_date=None,
                 max_scan_rows=None):
    """每次新根；每证券流式写一CSV，全部稳定后发布原QMI v2和来源收据。"""
    root=_root(cache_root);directory_name,scope,schema_version,layout=_period(period)
    unused_start,unused_end,date_selection=_date_window(from_date,to_date)
    # 完整导出沿原总行预算；日期窗口将输出与全原件扫描分开限额。
    # 默认窗口扫描至多原默认总量或调用者已显式提高的总量。
    for value,maximum in ((max_rows,1000000),(max_total_rows,10000000000),
                          (max_input_bytes,MAX_FILE_BYTES),(block_records,16384)):
        _need(type(value) is int and 1<=value<=maximum,'budget')
    scan_budget=(max_total_rows if from_date is None and to_date is None else max(DEFAULT_TOTAL_ROWS,max_total_rows)) if max_scan_rows is None else max_scan_rows
    _need(type(scan_budget) is int and 1<=scan_budget<=10000000000,'budget')
    selected=_select_cache(root,symbols,all_cache) if not all_cache else scan_cache(root,period)
    # 离线实例由根路径和目录身份派生，与在线broker transport Session明确区分。
    info=_ordinary(root,True)
    root_identity=hashlib.sha256(json.dumps([str(root).casefold(),info.st_dev,info.st_ino],
        ensure_ascii=True,separators=(',',':')).encode('utf-8')).hexdigest()
    export_id=str(uuid4())
    profile=dict(provider='Qmt',instance_id='local-dat:'+root_identity,
        session_id='local-dat:'+export_id,generation=1,dataset_version=DATASET_VERSION,
        source_license='unknown',input_kind='qmt_export',timezone='Asia/Shanghai',minute_boundary='unknown',
        adjustment='none',factor_version='',value_semantics='source',price_unit='unknown',
        volume_unit='unknown',amount_unit='unknown')
    output=_new_root(output_root);csv_root=output/'csv';csv_root.mkdir()
    sources=[];securities=[];total=0;scanned=0
    for symbol in selected:
        item=_export_one(root,symbol,csv_root/(symbol+'.csv'),min(max_rows,max_total_rows-total),max_input_bytes,block_records,period,
                         from_date=from_date,to_date=to_date,max_scan_rows=scan_budget-scanned)
        sources.append(item);total+=item['rows'];scanned+=item['scanned_rows']
        if item['status']=='empty':continue
        securities.append(dict(symbol=symbol,chunks=[dict(path=item['csv_path'],sha256=item['csv_sha256'])]))
    after_root=_ordinary(root,True)
    _need((after_root.st_dev,after_root.st_ino)==(info.st_dev,info.st_ino),'source_changed')
    manifest=dict(schema_version=schema_version,profile=profile,securities=securities)
    if period=='1d':manifest['period']='1d'
    manifest_sha=_json_new(output/'qmi-manifest.json',manifest) if securities else None
    receipt=dict(schema='qmt.local-dat-export.v1',status='passed',export_id=export_id,
        layout=layout,period=period,magic=MAGIC.hex(),record_bytes=RECORD_BYTES,
        cache_root=str(root),cache_root_identity=root_identity,manifest_path=str(output/'qmi-manifest.json') if securities else None,
        manifest_sha256=manifest_sha,profile=profile,securities=sources,total_rows=total,
        exported_securities=len(securities),empty_securities=len(sources)-len(securities),
        inventory_scope=scope,coverage='unknown',new_sdk_calls=0,selection=date_selection,
        scanned_rows=scanned,selected_rows=total,scan_row_budget=scan_budget,
        excluded_rows=sum(item['excluded_rows'] for item in sources))
    _json_new(output/'export.json',receipt,16*1024*1024)
    return receipt


def convert_cache(cache_root,symbols,output_root,*,helper,helper_sha256,all_cache=False,period='1m',
                  max_rows=1000000,max_total_rows=DEFAULT_TOTAL_ROWS,max_input_bytes=MAX_FILE_BYTES,block_records=4096,
                  from_date=None,to_date=None,max_scan_rows=None):
    """多证券同QMI进入原Importer单一WT store；Importer自身按证券占用内存。"""
    from .qmt_minute_import import import_dataset
    output=_new_root(output_root)
    exported=export_cache(cache_root,symbols,output/'qmi',all_cache=all_cache,period=period,max_rows=max_rows,
        max_total_rows=max_total_rows,max_input_bytes=max_input_bytes,block_records=block_records,
        from_date=from_date,to_date=to_date,max_scan_rows=max_scan_rows)
    if exported['manifest_path'] is None:
        result=dict(schema='qmt.local-dat-convert.v1',status='empty',period=period,securities=0,
            empty_securities=exported['empty_securities'],total_rows=0,manifest_path=None,
            manifest_sha256=None,store_path=None,value_semantics='source',coverage='unknown',new_sdk_calls=0,
            selection=exported['selection'],scanned_rows=exported['scanned_rows'],selected_rows=0,
            excluded_rows=exported['excluded_rows'],scan_row_budget=exported['scan_row_budget'])
        _json_new(output/'convert.json',result)
        return result
    imported=import_dataset(exported['manifest_path'],output/'store',helper,helper_sha256,
        max_bars=max_rows,max_total_bars=max_total_rows,max_input_bytes=max_input_bytes)
    result=dict(schema='qmt.local-dat-convert.v1',status='passed',period=period,securities=len(imported['securities']),
        total_rows=exported['total_rows'],manifest_path=exported['manifest_path'],
        manifest_sha256=exported['manifest_sha256'],store_path=str(output/'store'),
        import_receipt_sha256=hashlib.sha256((output/'store/qmt-import.json').read_bytes()).hexdigest(),
        value_semantics='source',coverage='unknown',new_sdk_calls=0,selection=exported['selection'],
        scanned_rows=exported['scanned_rows'],selected_rows=exported['selected_rows'],excluded_rows=exported['excluded_rows'],
        scan_row_budget=exported['scan_row_budget'])
    _json_new(output/'convert.json',result)
    return result


def main(argv=None):
    parser=argparse.ArgumentParser(description='离线QMT DAT导出QMI或转换WT历史，不启动SDK')
    parser.add_argument('mode',choices=('inspect','export','convert'))
    for key in ('cache-root','output-root'):parser.add_argument('--'+key,required=True)
    selection=parser.add_mutually_exclusive_group(required=True)
    selection.add_argument('--symbols');selection.add_argument('--all-cache',action='store_true')
    parser.add_argument('--period',choices=('1m','1d'),default='1m')
    parser.add_argument('--helper');parser.add_argument('--helper-sha256')
    parser.add_argument('--from-date');parser.add_argument('--to-date')
    parser.add_argument('--max-scan-rows',type=int)
    for key,default in (('max-rows',1000000),('max-total-rows',DEFAULT_TOTAL_ROWS),('max-input-bytes',MAX_FILE_BYTES),('block-records',4096)):
        parser.add_argument('--'+key,type=int,default=default)
    args=parser.parse_args(argv)
    try:
        options=dict(all_cache=args.all_cache,period=args.period,max_rows=args.max_rows,max_total_rows=args.max_total_rows,
            max_input_bytes=args.max_input_bytes,block_records=args.block_records,
            from_date=args.from_date,to_date=args.to_date,max_scan_rows=args.max_scan_rows)
        symbols=None if args.all_cache else args.symbols.split(',')
        if args.mode=='inspect':
            _need(args.helper is None and args.helper_sha256 is None)
            _need(args.from_date is None and args.to_date is None and args.max_scan_rows is None)
            value=inspect_cache(args.cache_root,symbols,args.output_root,
                                all_cache=args.all_cache,period=args.period)
            result={key:value[key] for key in ('schema','status','files','sampled_files','empty_files',
                'unavailable_files','estimated_rows','source_bytes','validation','coverage','new_sdk_calls')}
            result['period']=value['period']
            result['inventory_path']=str(Path(args.output_root).absolute()/'inventory.json')
        elif args.mode=='convert':
            _need(args.helper is not None and args.helper_sha256 is not None)
            result=convert_cache(args.cache_root,symbols,args.output_root,helper=args.helper,
                helper_sha256=args.helper_sha256,**options)
        else:
            _need(args.helper is None and args.helper_sha256 is None)
            value=export_cache(args.cache_root,symbols,args.output_root,**options)
            result=dict(schema=value['schema'],status=value['status'],securities=len(value['securities']),
                total_rows=value['total_rows'],manifest_path=value['manifest_path'],manifest_sha256=value['manifest_sha256'],
                period=value['period'],value_semantics='source',coverage='unknown',new_sdk_calls=0,
                selection=value['selection'],scanned_rows=value['scanned_rows'],selected_rows=value['selected_rows'],excluded_rows=value['excluded_rows'],scan_row_budget=value['scan_row_budget'])
        print(json.dumps(result,ensure_ascii=True,allow_nan=False),flush=True)
        return 0
    except Exception as error:
        from .qmt_minute_import import ImportFailure
        category=error.category if isinstance(error,(CacheExportError,ImportFailure)) else 'dependency' if isinstance(error,OSError) else 'input'
        print(json.dumps(dict(status='failed',category=category,message='离线缓存转换未完成，保留本次目录核查'),ensure_ascii=True),file=sys.stderr,flush=True)
        return 1


if __name__=='__main__':raise SystemExit(main())
