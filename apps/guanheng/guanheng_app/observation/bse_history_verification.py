"""官方终止上市公告完整复核；原退出登记仍由配置owner核验。"""
from datetime import date,datetime
import re
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .provider_tables import parse_json
from .source_fetch import SourceFailure
from .storage import encode,digest

URL='https://www.bse.cn/disclosureInfoController/companyAnnouncement.do?callback=guanhengBseHistory'
PAGE='https://www.bse.cn/disclosure/announcement.html'
MAX_PAGES=20


def _need(value,code='bse_history_verification_schema'):
    if not value:raise SourceFailure(code)


def verify_history(fetch,history,as_of,aliases):
    """复核既有登记的完整覆盖后返回副本及证明SHA；新事实要求显式核验。

    采用官网标题查询的完整分页，原退出PDF路径须齐备；新公司/新公告、
    分页漂移或身份异常均失败。查询字节、原seed及证明共用原capture/D。
    """
    check=fetch.budget.remaining;check()
    _need(as_of<=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat(),'bse_history_future_qualification')
    known={item['code']:item for item in history['exits']}
    seen=set();paths={};companies=set();pages=None;total=None;query=[]
    try:
        page=0
        while pages is None or page<pages:
            check()
            body=fetch.post_readonly(URL,dict(page=str(page),companyCd='',isNewThree='1',
                startTime=history['market_open'],endTime=as_of,keyword='终止上市',hyType='',
                **{'xxfcbj[]':'2','disclosureType[]':'5'}),referer=PAGE,session_handoff=True)
            match=re.fullmatch(rb'guanhengBseHistory\((.*)\);?\s*',body,re.S)
            _need(match is not None)
            payload=parse_json(match[1]);_need(type(payload) is list and len(payload)==1)
            root=payload[0];_need(type(root) is dict and type(root.get('status')) is int and root['status']==0)
            value=root['listInfo'];_need(type(value) is dict)
            _need(all(type(value[key]) is int for key in ('number','size','totalElements','totalPages','numberOfElements')))
            if total is None:
                total=value['totalElements'];pages=value['totalPages']
                _need(0<=total<=20*MAX_PAGES and pages==(total+19)//20,'bse_history_verification_capacity')
            rows=value['content']
            _need(type(rows) is list and value['totalElements']==total and value['totalPages']==pages
                and value['number']==page and value['size']==20 and value['numberOfElements']==len(rows)
                and len(rows)==min(20,max(0,total-page*20))
                and value['firstPage'] is (page==0) and value['lastPage'] is (page==max(0,pages-1)))
            for row in rows:
                check();_need(type(row) is dict)
                code=row['companyCd'];identity=row['disclosureCode'];title=row['disclosureTitle'];day=row['publishDate'];path=row['destFilePath']
                _need(type(code) is str and re.fullmatch('[0-9]{6}',code)
                    and type(identity) is str and re.fullmatch('[A-Za-z0-9_-]{1,128}',identity)
                    and type(title) is str and len(title)<=2048 and '终止上市' in title
                    and type(day) is str and re.fullmatch('[0-9]{4}-[0-9]{2}-[0-9]{2}',day)
                    and history['market_open']<=day<=as_of and row['xxfcbj']=='2'
                    and type(path) is str and len(path)<=1024 and path.startswith('/disclosure/')
                    and path.endswith('.pdf') and '?' not in path and '#' not in path and '..' not in path.split('/'))
                _need(date.fromisoformat(day).isoformat()==day)
                _need(identity not in seen and path not in paths)
                code=aliases.get(code,code)
                _need(code in known,'bse_history_registry_changed')
                _need(day<=history['verified_through'],'bse_history_new_announcement')
                seen.add(identity);paths[path]=code;companies.add(code)
            query.append(dict(page=page,sha256=digest(body),rows=len(rows),total=total))
            page+=1
        _need(len(seen)==total and companies==set(known),'bse_history_registry_changed')
        for code,item in known.items():
            check();_need(paths.get(urlsplit(item['source_url']).path)==code,'bse_history_original_missing')
    except SourceFailure:raise
    except (KeyError,ValueError,TypeError,IndexError,OverflowError,RecursionError):
        raise SourceFailure('bse_history_verification_schema') from None
    check();seed_body=encode(history);seed=fetch.objects.put(seed_body)
    proof=dict(schema='guanheng.bse-history-verification.v1',seed_sha256=seed,
        original_verified_through=history['verified_through'],verified_through=as_of,
        company_count=len(companies),announcements=total,query= query)
    identity=fetch.objects.put(encode(proof))
    fetch.records.extend([dict(kind='bse_history_seed',sha256=seed),dict(kind='bse_history_verification',sha256=identity)])
    check();return dict(history,verified_through=as_of),identity
