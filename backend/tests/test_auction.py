from datetime import datetime,timezone,timedelta
from fastapi.testclient import TestClient
import pytest
from backend import main as m
@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setattr(m,'DB',str(tmp_path/'test.db')); t=datetime(2026,1,1,12,tzinfo=timezone.utc); clock=[t]; monkeypatch.setattr(m,'now',lambda:clock[0]); return TestClient(m.app),clock,t

def create(c,t,trigger='any_bid',**kw):
    d=dict(name='Freight',reference='RFQ-1',start=(t-timedelta(minutes=1)).isoformat(),close=(t+timedelta(minutes=20)).isoformat(),forced_close=(t+timedelta(minutes=27)).isoformat(),service_date=(t+timedelta(days=1)).isoformat(),x=10,y=5,trigger=trigger);d.update(kw);return c.post('/api/rfqs',json=d)
def bid(c,t,carrier,price):
    return c.post('/api/rfqs/1/bids',json=dict(carrier=carrier,freight=price,origin=0,destination=0,transit=2,validity=(t+timedelta(days=1)).isoformat()))
@pytest.mark.parametrize('trigger',['any_bid','rank_change','l1_change'])
def test_triggers(setup,trigger):
    c,clock,t=setup;assert create(c,t,trigger).status_code==201
    assert bid(c,t,'A',100).status_code==201;assert bid(c,t,'B',120).status_code==201
    clock[0]=t+timedelta(minutes=10)
    r=bid(c,t,'B',110).json();assert r['current_close']==(t+timedelta(minutes=25 if trigger=='any_bid' else 20)).isoformat()
    clock[0]=t+timedelta(minutes=16);r=bid(c,t,'B',90).json();assert r['rankings'][0]['carrier']=='B';assert r['current_close']==(t+timedelta(minutes=27 if trigger=='any_bid' else 25)).isoformat()
    assert any(a['kind']=='extension' for a in r['activity'])
def test_cap_and_close(setup):
    c,clock,t=setup;create(c,t);clock[0]=t+timedelta(minutes=19);bid(c,t,'A',100);r=bid(c,t,'B',90).json();assert r['current_close']==r['forced_close'];clock[0]=t+timedelta(minutes=27);assert bid(c,t,'C',80).status_code==409;assert c.get('/api/rfqs/1').json()['status']=='Force Closed'
def test_validation(setup):
    c,clock,t=setup;assert create(c,t,forced_close=(t+timedelta(minutes=20)).isoformat()).status_code==422;assert create(c,t).status_code==201;assert create(c,t).status_code==409;assert bid(c,t,'A',100).status_code==201;assert bid(c,t,'A',101).status_code==422;assert bid(c,t,'A',99).status_code==201;assert len(c.get('/api/rfqs/1').json()['bids'])==2
    clock[0]=t+timedelta(minutes=20);assert bid(c,t,'B',50).status_code==409;assert c.get('/api/rfqs/1').json()['status']=='Closed'
def test_scheduled(setup):
    c,clock,t=setup;create(c,t,start=(t+timedelta(minutes=1)).isoformat());assert bid(c,t,'A',100).status_code==409;assert c.get('/api/rfqs').json()[0]['status']=='Scheduled'
def test_rank_not_l1(setup):
    c,clock,t=setup;create(c,t,'rank_change');bid(c,t,'A',100);bid(c,t,'B',200);bid(c,t,'C',300);clock[0]=t+timedelta(minutes=11);r=bid(c,t,'C',150).json();assert r['current_close']==(t+timedelta(minutes=25)).isoformat();assert [b['carrier'] for b in r['rankings']]==['A','C','B']
