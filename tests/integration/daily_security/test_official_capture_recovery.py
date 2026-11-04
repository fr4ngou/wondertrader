"""官方原件持久化和容量回归；全部HTTP来自独立替身。"""
from datetime import date,timedelta
import io,json,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from integrations.guanheng import official_index_prices as prices


class Response(io.BytesIO):
    def __init__(self,url,data,code='200'):
        super().__init__(json.dumps(dict(code=code,data=data)).encode());self.url=url;self.status=200
    def geturl(self):return self.url


class OfficialCaptureRecovery(unittest.TestCase):
    def test_basic_business_failure_and_price_identity_share_same_recovery(self):
        identity=dict(symbol='SSE.000925',name='基本面50',security_type='index')
        def reply(request,**kwargs):
            url=request.full_url
            if 'index-basic-info'in url:return Response(url,None,code='404')
            return Response(url,[dict(indexCode='000925',indexNameCn='基本面50',indexNameCnAll='中证锐联基本面50指数',tradeDate='20261103',open=10.,high=11.,low=9.,close=10.,tradingVol=1.,tradingValue=1.)])
        with tempfile.TemporaryDirectory()as directory,patch.object(prices,'urlopen',reply),patch.object(prices,'_REQUEST_INTERVAL',0):
            result=prices.prepare_official_index_prices({identity['symbol']:identity},'20261103','20261103',Path(directory)/'capture',deadline=time.monotonic()+30)
            self.assertEqual(prices.load_official_index_prices(result)['securities'][identity['symbol']]['reason'],'available')

    def test_cni_fills_target_even_when_csi_has_only_previous_day(self):
        identity=dict(symbol='SZSE.399379',name='国证基金',security_type='index');calls=[]
        def reply(request,**kwargs):
            url=request.full_url;calls.append(url)
            if 'index-basic-info'in url:return Response(url,dict(indexCode='399379',indexShortNameCn='国证基金'))
            if 'hq.cnindex.com.cn'in url:return Response(url,dict(indexCode='399379',indexName='国证基金',item=['timestamp','open','high','low','close','volume','amount'],data=[[1793635200000,10.,11.,9.,10.,1.,1.]]),code=200)
            return Response(url,[dict(indexCode='399379',tradeDate='20261102',open=10.,high=11.,low=9.,close=10.,tradingVol=1.,tradingValue=1.)])
        with tempfile.TemporaryDirectory()as directory,patch.object(prices,'urlopen',reply),patch.object(prices,'_REQUEST_INTERVAL',0):
            result=prices.prepare_official_index_prices({identity['symbol']:identity},'20261102','20261103',Path(directory)/'capture',deadline=time.monotonic()+30)
            entry=prices.load_official_index_prices(result)['securities'][identity['symbol']]
            self.assertIn('20261103',entry['data']);self.assertEqual(entry['metadata']['source']['provider'],'CNI')
            self.assertIn('20261102',entry['data'])
            self.assertEqual(entry['provider_by_date'],{'20261102':'CSI','20261103':'CNI'})
            self.assertEqual(entry['metadata_by_provider']['CSI']['source']['provider'],'CSI')
            self.assertEqual(entry['metadata_by_provider']['CNI']['source']['provider'],'CNI')
            self.assertEqual(sum('hq.cnindex.com.cn'in url for url in calls),1)
            # 旧v1的单源投影仍沿原合同可恢复；原件不被v2的并集要求否定或覆盖。
            from integrations.guanheng.daily_data_update import _save,_descriptor
            path=Path(result['path']);old=json.loads(path.read_bytes());old['schema']='guanheng.official-index-prices.v1'
            row=old['securities'][identity['symbol']];row['data'].pop('20261102')
            for key in ('provider_by_date','metadata_by_provider','source_basics'):row.pop(key)
            _save(path,old);saved=path.read_bytes()
            resumed=prices.load_official_index_prices(_descriptor(path))
            self.assertEqual(resumed['securities'][identity['symbol']]['provider_by_date'],{'20261103':'CNI'})
            self.assertEqual(path.read_bytes(),saved)

    def test_partial_capture_resumes_original_bytes_and_corrupt_raw_rejected(self):
        identity=dict(symbol='SSE.000925',name='基本面50',security_type='index')
        calls=[]
        def reply(request,**kwargs):
            url=request.full_url;calls.append(url)
            if 'index-basic-info'in url:return Response(url,dict(indexCode='000925',indexShortNameCn='基本面50'))
            if len(calls)==2:raise RuntimeError('synthetic process failure before response')
            return Response(url,[dict(indexCode='000925',tradeDate='20261103',open=10.,high=11.,low=9.,close=10.,tradingVol=1.,tradingValue=1.)])
        with tempfile.TemporaryDirectory()as directory,patch.object(prices,'urlopen',reply),patch.object(prices,'_REQUEST_INTERVAL',0):
            root=Path(directory)/'capture'
            with self.assertRaises(RuntimeError):prices.prepare_official_index_prices({identity['symbol']:identity},'20261103','20261103',root,deadline=time.monotonic()+30)
            original=(root/'REQUEST.json').read_bytes();raw=(root/'SSE.000925-basic.json').read_bytes()
            result=prices.prepare_official_index_prices({identity['symbol']:identity},'20261103','20261103',root,deadline=time.monotonic()+30)
            self.assertEqual((root/'REQUEST.json').read_bytes(),original)
            self.assertEqual((root/'SSE.000925-basic.json').read_bytes(),raw)
            self.assertEqual(len(calls),3)
            self.assertEqual(prices.prepare_official_index_prices({identity['symbol']:identity},'20261103','20261103',root,deadline=time.monotonic()+30),result)
            self.assertEqual(len(calls),3)
            (root/'SSE.000925-basic.json').write_bytes(b'corrupt raw')
            with self.assertRaises(ValueError):prices.load_official_index_prices(result)

    def test_large_valid_result_recovers_above_general_metadata_budget(self):
        end=date(2026,11,3);dates=[];day=end
        while len(dates)<2000:
            if day.weekday()<5:dates.append(day.strftime('%Y%m%d'))
            day-=timedelta(days=1)
        securities={'SSE.%06d'%i:dict(symbol='SSE.%06d'%i,name='synthetic',security_type='index')for i in range(100)}
        def reply(request,**kwargs):
            url=request.full_url
            if 'index-basic-info'in url:return Response(url,dict(indexCode=url.rsplit('/',1)[1],indexShortNameCn='synthetic'))
            code=parse_qs(urlsplit(url).query)['indexCode'][0]
            return Response(url,[dict(indexCode=code,tradeDate=d,open=10.,high=11.,low=9.,close=10.,tradingVol=1.,tradingValue=1.)for d in dates])
        with tempfile.TemporaryDirectory()as directory,patch.object(prices,'urlopen',reply),patch.object(prices,'_REQUEST_INTERVAL',0):
            root=Path(directory)/'capture'
            result=prices.prepare_official_index_prices(securities,'20170101','20261103',root,deadline=time.monotonic()+120)
            self.assertGreater(Path(result['path']).stat().st_size,16777216)
            loaded=prices.load_official_index_prices(result)
            self.assertEqual(sum(len(v['data'])for v in loaded['securities'].values()),200000)
