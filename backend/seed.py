from backend.main import create, bid, RFQ, Bid, now
from datetime import timedelta
from uuid import uuid4
if __name__=='__main__':
    t=now(); r=create(RFQ(name='Delhi to Mumbai freight',reference='DEMO-'+uuid4().hex[:6],start=t-timedelta(minutes=1),close=t+timedelta(minutes=8),forced_close=t+timedelta(minutes=20),service_date=t+timedelta(days=2),x=3,y=5,trigger='any_bid'))
    for name,price in [('BlueLine Logistics',12000),('Swift Cargo',11500)]: bid(r['id'],Bid(carrier=name,freight=price,origin=500,destination=300,transit=3,validity=t+timedelta(days=3)))
    print('Created demo RFQ',r['id'])
