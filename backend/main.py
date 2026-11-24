from datetime import datetime, timezone, timedelta
from contextlib import contextmanager
from pathlib import Path
import sqlite3, os, json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, AwareDatetime, model_validator
from typing import Literal
from decimal import Decimal

DB = os.getenv('BIDFLOW_DB', str(Path(__file__).with_name('bidflow.db')))
app = FastAPI(title='BidFlow RFQ API')
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173','http://127.0.0.1:5173'], allow_methods=['*'], allow_headers=['*'])
SCHEMA = '''CREATE TABLE IF NOT EXISTS rfqs(id INTEGER PRIMARY KEY, name TEXT NOT NULL, reference TEXT UNIQUE NOT NULL, start TEXT NOT NULL, original_close TEXT NOT NULL, current_close TEXT NOT NULL, forced_close TEXT NOT NULL, service_date TEXT NOT NULL, x INTEGER NOT NULL CHECK(x>0), y INTEGER NOT NULL CHECK(y>0), trigger TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS bids(id INTEGER PRIMARY KEY, rfq_id INTEGER NOT NULL REFERENCES rfqs(id), carrier TEXT NOT NULL, freight INTEGER NOT NULL, origin INTEGER NOT NULL, destination INTEGER NOT NULL, total INTEGER NOT NULL, transit INTEGER NOT NULL, validity TEXT NOT NULL, created TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS activity(id INTEGER PRIMARY KEY, rfq_id INTEGER NOT NULL REFERENCES rfqs(id), created TEXT NOT NULL, kind TEXT NOT NULL, message TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS bids_rfq ON bids(rfq_id,carrier,id); CREATE INDEX IF NOT EXISTS activity_rfq ON activity(rfq_id,id);'''
def now(): return datetime.now(timezone.utc)
def iso(t): return t.astimezone(timezone.utc).isoformat()
def dt(t): return datetime.fromisoformat(t)
@contextmanager
def db(write=False):
    c=sqlite3.connect(DB, timeout=15); c.row_factory=sqlite3.Row
    try:
        c.execute('PRAGMA foreign_keys=ON'); c.executescript(SCHEMA)
        c.execute('BEGIN IMMEDIATE' if write else 'BEGIN')
        yield c; c.commit()
    except Exception:
        c.rollback(); raise
    finally: c.close()
class RFQ(BaseModel):
    name: str=Field(min_length=1,max_length=120)
    reference: str=Field(min_length=1,max_length=60)
    start: AwareDatetime
    close: AwareDatetime
    forced_close: AwareDatetime
    service_date: AwareDatetime
    x: int=Field(gt=0,le=1440)
    y: int=Field(gt=0,le=1440)
    trigger: Literal['any_bid','rank_change','l1_change']
    @model_validator(mode='after')
    def dates(self):
        if not self.name.strip() or not self.reference.strip(): raise ValueError('Name and reference required')
        if not self.start < self.close < self.forced_close: raise ValueError('Start < close < forced close required')
        if self.service_date < self.forced_close: raise ValueError('Service date must follow forced close')
        return self
class Bid(BaseModel):
    carrier: str=Field(min_length=1,max_length=100)
    freight: Decimal=Field(ge=0,le=100000000,decimal_places=2)
    origin: Decimal=Field(ge=0,le=100000000,decimal_places=2)
    destination: Decimal=Field(ge=0,le=100000000,decimal_places=2)
    transit: int=Field(gt=0,le=3650)
    validity: AwareDatetime

def status(r,t):
    if t>=dt(r['current_close']): return 'Force Closed' if r['current_close']==r['forced_close'] else 'Closed'
    return 'Scheduled' if t<dt(r['start']) else 'Active'
def get(c,i):
    r=c.execute('SELECT * FROM rfqs WHERE id=?',(i,)).fetchone()
    if not r: raise HTTPException(404,'RFQ not found')
    return dict(r)
def ranks(c,i):
    return [dict(r) for r in c.execute('SELECT * FROM bids WHERE rfq_id=? AND id IN (SELECT MAX(id) FROM bids WHERE rfq_id=? GROUP BY carrier COLLATE NOCASE) ORDER BY total,id',(i,i))]
def log(c,i,t,k,m): c.execute('INSERT INTO activity(rfq_id,created,kind,message) VALUES(?,?,?,?)',(i,iso(t),k,m))
def view(c,r,t,detail=False):
    a=ranks(c,r['id']); r.update(status=status(r,t),lowest=a[0]['total'] if a else None,server_time=iso(t),supplier_count=len(a))
    if detail:
        r['rankings']=[dict(b,rank=j+1) for j,b in enumerate(a)]
        r['bids']=[dict(b) for b in c.execute('SELECT * FROM bids WHERE rfq_id=? ORDER BY total,id',(r['id'],))]
        r['activity']=[dict(b) for b in c.execute('SELECT * FROM activity WHERE rfq_id=? ORDER BY id DESC',(r['id'],))]
    return r
@app.get('/api/rfqs')
def listing():
    with db() as c: return [view(c,dict(r),now()) for r in c.execute('SELECT * FROM rfqs ORDER BY id DESC')]
@app.post('/api/rfqs',status_code=201)
def create(p:RFQ):
    with db(True) as c:
        try: i=c.execute('INSERT INTO rfqs(name,reference,start,original_close,current_close,forced_close,service_date,x,y,trigger) VALUES(?,?,?,?,?,?,?,?,?,?)',(p.name.strip(),p.reference.strip(),iso(p.start),iso(p.close),iso(p.close),iso(p.forced_close),iso(p.service_date),p.x,p.y,p.trigger)).lastrowid
        except sqlite3.IntegrityError: raise HTTPException(409,'Reference already exists')
        log(c,i,now(),'created','British auction created'); return view(c,get(c,i),now(),True)
@app.get('/api/rfqs/{i}')
def detail(i:int):
    with db() as c: return view(c,get(c,i),now(),True)
@app.post('/api/rfqs/{i}/bids',status_code=201)
def bid(i:int,p:Bid):
    with db(True) as c:
        t=now(); r=get(c,i)
        if status(r,t)!='Active': raise HTTPException(409,'Auction is not active')
        if p.validity<=t: raise HTTPException(422,'Quote validity must be in the future')
        carrier=p.carrier.strip()
        if not carrier: raise HTTPException(422,'Carrier required')
        before=ranks(c,i); amounts=[int(v*100) for v in (p.freight,p.origin,p.destination)]; total=sum(amounts)
        old=next((b for b in before if b['carrier'].lower()==carrier.lower()),None)
        if old and total>=old['total']: raise HTTPException(422,'New quote must be lower than your previous quote')
        c.execute('INSERT INTO bids(rfq_id,carrier,freight,origin,destination,total,transit,validity,created) VALUES(?,?,?,?,?,?,?,?,?)',(i,carrier,*amounts,total,p.transit,iso(p.validity),iso(t)))
        after=ranks(c,i); a=[b['carrier'].lower() for b in before]; b=[q['carrier'].lower() for q in after]
        log(c,i,t,'bid',f'{carrier} submitted {total/100:.2f}')
        reason={'any_bid':'New bid received','rank_change':'Supplier ranking changed','l1_change':'Lowest bidder changed'}[r['trigger']]
        changed={'any_bid':True,'rank_change':a!=b,'l1_change':a[:1]!=b[:1]}[r['trigger']]
        close=dt(r['current_close']); forced=dt(r['forced_close'])
        if changed and t>=close-timedelta(minutes=r['x']):
            new=min(close+timedelta(minutes=r['y']),forced)
            if new>close:
                c.execute('UPDATE rfqs SET current_close=? WHERE id=?',(iso(new),i)); log(c,i,t,'extension',f'{reason}: {iso(close)} → {iso(new)}'+(' (forced cap)' if new==forced else ''))
        return view(c,get(c,i),t,True)
