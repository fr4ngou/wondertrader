"""Run a fixed public encoder on synthetic native-shaped objects, without QMT startup."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys, types
QMT=Path('D:/workspace/qmt')

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    head=subprocess.check_output(['git','-C',str(QMT),'rev-parse','HEAD']).decode().strip()
    paths=['qmt_agent/broker/errors.py','qmt_agent/broker/encoding.py']
    # Import only these two audited, standard-library-only source blobs. No package init/service.
    package=types.ModuleType('nqb_public_encoder');package.__path__=[];sys.modules[package.__name__]=package
    hashes={}
    for path in paths:
        raw=subprocess.check_output(['git','-C',str(QMT),'show',head+':'+path])
        assert (QMT/path).read_bytes().replace(b'\r\n',b'\n')==raw.replace(b'\r\n',b'\n'), 'public encoder differs from fixed HEAD'
        hashes[path]=hashlib.sha256(raw).hexdigest()
        name='nqb_public_encoder.'+Path(path).stem;module=types.ModuleType(name);module.__package__=package.__name__;sys.modules[name]=module
        exec(compile(raw,str(QMT/path),'exec'),module.__dict__)
    convert=sys.modules['nqb_public_encoder.encoding'].to_json_value
    samples={
      'position':dict(m_strInstrumentID='600000',m_strExchangeID='SH',m_nVolume=700,m_nCanUseVolume=420,m_nYesterdayVolume=500,m_dAvgPrice=10.25,m_nTodayVolume=200,m_nAvailableYesterdayVolume=420,m_nAvailableTodayVolume=0),
      'order':dict(m_strInstrumentID='600000',m_strExchangeID='SH',m_strOrderSysID='SYNTHETIC-ORDER',m_nVolumeTotalOriginal=200,m_nVolumeTraded=70,m_nVolumeTotal=130,m_dLimitPrice=10.35,m_nDirection=48,m_nOrderStatus=50,m_strInsertDate='20261022',m_strInsertTime='093507'),
      'trade':dict(m_strInstrumentID='600000',m_strExchangeID='SH',m_strOrderSysID='SYNTHETIC-ORDER',m_strTradeID='SYNTHETIC-TRADE',m_nVolume=70,m_dPrice=10.31,m_dTradeAmount=721.7,m_strTradeDate='20261022',m_strTradeTime='093508'),
      'account':dict(m_dBalance=100000,m_dAvailable=82000,m_dCommission=12.34,m_dTotalAsset=100000,m_dFrozenCash=200)
    }
    expected={
      'position':{'m_nTodayVolume','m_nAvailableYesterdayVolume','m_nAvailableTodayVolume'},
      'order':{'m_nVolumeTotalOriginal','m_dLimitPrice','m_strInsertDate','m_strInsertTime'},
      'trade':{'m_strTradeID','m_dPrice','m_dTradeAmount','m_strTradeDate','m_strTradeTime'},
      'account':{'m_dTotalAsset','m_dFrozenCash'}
    }
    results=[]
    for name,fields in samples.items():
        native=type('SyntheticNative'+name,(),fields)()
        projected=convert(native);dictionary=convert(fields)
        missing=set(fields)-set(projected)
        assert missing==expected[name], (name,missing)
        assert dictionary==fields
        results.append(dict(kind=name,passed=True,retained=sorted(projected),missing=sorted(missing),dictionary_preserves_all=True,
            real_source_qualified=False))
    result=dict(qmt_head=head,source_hashes=hashes,passed=4,failed=0,skipped=0,results=results,
        limits=['Synthetic native-shaped objects; names illustrate public projection coverage, not proof of a vendor runtime shape.',
        'Yesterday/current-remaining semantics, source session/account binding, completeness and observation scope still require source-owner contract.',
        'Only fixed source encoder executed. No service, network, QMT SDK or account loaded.'])
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
