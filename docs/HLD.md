# High-level design
## Architecture
```mermaid
flowchart TD
 B[Buyer] --> UI[React dashboard]
 S[Supplier] --> UI
 UI -->|REST and polling| API[FastAPI]
 API --> R[RFQ validation]
 API --> E[Auction engine and ranking]
 R --> DB[(SQLite)]
 E -->|Atomic bid, extension and log| DB
```
## Bid sequence
```mermaid
sequenceDiagram
 participant U as Supplier UI
 participant A as FastAPI
 participant D as SQLite
 U->>A: POST quote
 A->>D: BEGIN IMMEDIATE
 A->>D: Read RFQ and previous rankings
 A->>A: Validate server time and quote
 A->>D: Insert bid and compute new rankings
 A->>A: Evaluate trigger in current window
 A->>D: Update close if triggered and append logs
 A->>D: COMMIT
 A-->>U: Updated auction snapshot
```
Reject invalid bids before insertion; rollback on failure. SQLite serializes writers, preventing concurrent extensions from overwriting one another. Reads use transactions for consistent snapshots. Money uses integer minor units. Time is normalized to UTC. Polling refreshes rankings and status without sockets. For larger scale migrate to PostgreSQL row locks and push updates via SSE/WebSocket. Success metrics: bids per RFQ and final price improvement against comparable non-extended auctions; no improvement is claimed without observed data.
