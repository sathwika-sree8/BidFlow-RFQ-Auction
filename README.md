# BidFlow — British Auction RFQ System
A simplified reverse-auction procurement workspace. Buyers create RFQs; suppliers submit progressively lower quotes. React + FastAPI + SQLite. No external services or API keys required.

## Run locally
Requires Python 3.10+ and Node 20+ (22 recommended). Open two terminals at repository root.

Backend (Windows PowerShell):
```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend/requirements.txt
.venv\Scripts\python -m backend.seed
.venv\Scripts\python -m uvicorn backend.main:app --reload
```
On macOS/Linux substitute `.venv/bin/python` for `.venv\Scripts\python`.
Frontend (second terminal):
```sh
cd frontend
npm install
npm run dev
```
Open http://localhost:5173. Swagger: http://localhost:8000/docs. Seed is optional and creates a fresh demo each run. Database is created automatically in backend/bidflow.db; set BIDFLOW_DB to override.

## Demo
Create an RFQ starting before now, closing in 2 minutes, forced close in 5 minutes, service tomorrow, X=2 and Y=2. Submit a quote with future validity. Under Any new bid, close moves forward by 2 minutes, capped at forced close. Submit another carrier's quote to see rankings and logs. Repeat with the rank and L1 triggers. At the exact closing instant bids are rejected. Refreshing retains data.

## Tests
From root: `python -m pytest -q` (use virtual environment interpreter). Frontend compilation: `cd frontend && npm run build`.

## Deliverables
- [High-level design](docs/HLD.md)
- [Database schema](docs/Database_Schema.md)
- [API and rules](docs/API.md)
- Backend and frontend source in respective directories.

## Scope and assumptions
All RFQs use British auction mode. Demo carrier names stand in for authenticated supplier identities; no login or access control is provided. Currency INR, charges stored as integer paise. Latest quote per carrier determines rank, ties favor earlier accepted quote. A new entrant changes the rank list; first entrant establishes L1. A supplier must improve its own total, not necessarily beat L1. Quote validity is informational after submission. Service date must follow forced close. Scheduled is an additional status. Server UTC is authoritative; frontend polls every two seconds and countdown is indicative. No background job is needed: status is derived at read and write time. For production add authentication, authorization, PostgreSQL, rate limits and deployment configuration. Do not publish confidential assignment material or credentials.
