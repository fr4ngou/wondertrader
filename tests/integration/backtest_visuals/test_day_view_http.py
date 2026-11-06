"""悬停摘要沿原只读worker/绝对截止和固定收据准入，不新增执行入口。"""
from contextlib import asynccontextmanager
from threading import current_thread
from time import monotonic

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from guanheng_app import backtest_readonly
from guanheng_app.reading import BoundedReader


def application(tmp_path,monkeypatch):
    calls=[]
    class Archive:
        def visual(self,run,receipt,deadline,**selection):
            calls.append((current_thread().name,deadline-monotonic(),run,receipt,selection))
            return dict(schema='nbw-day-summaries-v1',run_id=run,receipt_sha256=receipt,report_sha256='c'*64,points=[])
    monkeypatch.setattr(backtest_readonly,'BacktestArchive',lambda root:Archive())
    @asynccontextmanager
    async def lifespan(app):
        app.state.backtest_reader=BoundedReader(workers=1,capacity=4);app.state.backtest_reader.start()
        try:yield
        finally:assert app.state.backtest_reader.close(5)
    app=FastAPI(lifespan=lifespan);app.include_router(backtest_readonly.router(str(tmp_path)))
    return app,calls


def test_summary_runs_in_original_bounded_reader_and_no_store(tmp_path,monkeypatch):
    app,calls=application(tmp_path,monkeypatch)
    with TestClient(app) as client:
        response=client.get('/v1/ui/backtest/archive/'+'a'*32+'/day-summaries?receipt_sha256='+'b'*64)
        assert response.status_code==200 and response.headers['cache-control']=='no-store'
        assert calls[0][0].startswith('guanheng-read-') and 0<calls[0][1]<=backtest_readonly.REQUEST_SECONDS
        assert calls[0][2:]==('a'*32,'b'*64,{'summaries':True})
    assert app.state.backtest_reader.live_threads==0


@pytest.mark.parametrize('query,body',[( '&extra=x',None),('&receipt_sha256='+'b'*64,None),('',b'{}')])
def test_summary_rejects_hidden_or_repeated_input(tmp_path,monkeypatch,query,body):
    app,calls=application(tmp_path,monkeypatch)
    with TestClient(app) as client:
        response=client.request('GET','/v1/ui/backtest/archive/'+'a'*32+'/day-summaries?receipt_sha256='+'b'*64+query,content=body)
        assert response.status_code==422 and calls==[]


def test_summary_has_no_post_mutation(tmp_path,monkeypatch):
    app,calls=application(tmp_path,monkeypatch)
    with TestClient(app) as client:
        assert client.post('/v1/ui/backtest/archive/'+'a'*32+'/day-summaries').status_code==405
        assert calls==[]
