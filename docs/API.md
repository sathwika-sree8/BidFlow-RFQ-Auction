# API and auction rules
| Method | Route | Purpose |
|---|---|---|
| GET | /api/rfqs | Listing |
| POST | /api/rfqs | Create RFQ (201) |
| GET | /api/rfqs/{id} | Details, latest rankings, all bids, logs |
| POST | /api/rfqs/{id}/bids | Submit quote (201) |

Swagger documents request and response examples through interactive execution. Errors: 404 missing RFQ, 409 duplicate reference or inactive auction, 422 invalid fields or non-improving quote.

Trigger window is inclusive at current close minus X and exclusive at current close. If accepted bid matches configured trigger, new close = min(current close + Y, forced close). Any bid: every accepted bid. Rank change: ordered carrier list differs. L1 change: first carrier differs. At forced cap, no additional extension is logged. At or after current close no bid is accepted. Scheduled before start; Active during window; Closed at normal close; Force Closed when current close equals forced close and time reaches it. All ranking uses latest accepted quote per carrier, ascending total and bid ID. See README for assumptions.
