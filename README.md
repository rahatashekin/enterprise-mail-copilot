# Enterprise Business Mail Copilot — Multi-Tier Procurement Intelligence

An autonomous AI-powered procurement intelligence and real-time communication copilot designed for high-value industrial trading, supply chain management, and engineering contracts.

---

## 🌟 Architecture & Key Capabilities

The platform autonomously ingests, classifies, extracts, and reports enterprise correspondence across three operational domains:

`	ext
                               ┌── Tier 1: Buyers (RFQ, Technical Clarifications, PO Awards, Challans)
                               │
[Incoming Mail] ──► [DomainRouter] ──► Tier 2: Global Suppliers (Quotations, Proforma Invoices, Specs)
                               │
                               └── Tier 3: Banking & Finance (LCs, SWIFT, Telegraphic Transfers)
                                        │
                                        ▼
                            [Gemini 3.5 Flash Engine]
                                        │
                        ┌───────────────┴───────────────┐
                        ▼                               ▼
            [Real-time WhatsApp Alert]      [Google Sheets Live Sync]
             (Executive Dispatcher)           (Multi-tab Cloud Tracker)
`

1. **Intelligent Domain & Protocol Routing (src/domain_router.py):**
   - Routes inbound mail into BUYER, SUPPLIER, BANK, or IGNORE.
   - Multi-stage evaluation covering exact domain matches, authorized sender identities, and semantic keyword heuristics.
   - Automatically filters marketing newsletters and non-actionable transactional noise.

2. **Multimodal Document Unpacking (src/document_unpacker.py):**
   - Automatically unpacks incoming tender attachments: PDF schedules, DOCX specifications, Excel BOQs, and scanned inspection certificates.
   - Extracts tabular line-items, quantities, warranties, and delivery deadlines into high-fidelity AI prompts.

3. **Stage-Aware AI Extraction (src/main_worker.py):**
   - Powered by Google Gemini structured JSON schemas.
   - Dynamically adapts extraction targets based on contract lifecycle:
     - **RFQ / Tender:** Tender Reference, Issuing Authority, Pre-bid meeting date, EMD value, Submission Deadlines.
     - **PO / Award:** PO Number, Contract Sum, PG / Retention %, Delivery Deadlines, Tax/AIT Terms.
     - **Supplier Quotes:** Country of origin, Incoterms, Currency, Unit Price Breakdown, Lead Times.
     - **Bank LC / TT:** LC Reference, LC Type (Sight/UPAS), Required Documents, Expiry Dates.

4. **Continuous Background Daemon (src/daemon_watcher.py):**
   - Resilient Linux systemd background service polling Gmail API.
   - Idempotent execution backed by a transactional SQLite state graph (src/state_manager.py).
   - Guarantees zero duplicate processing and exactly-once notification delivery.

5. **Multi-Tab Live Cloud Synchronization (src/google_sheet_sync.py):**
   - Synchronizes extracted structured entities into Google Sheets via Google Service Account authentication.
   - Real-time event auditing and chronological contract tracking across dedicated lifecycle worksheets.

---

## 🏗️ Project Layout

`	ext
├── .env.example             # Environment configuration template
├── .gitignore               # Strict credentials and data exclusions
├── README.md                # Project documentation
├── requirements.txt         # Python dependencies
├── main.py                  # CLI invocation & batch runner
├── src/
│   ├── daemon_watcher.py    # Background polling daemon
│   ├── document_unpacker.py # Attachment parsing (PDF, DOCX, XLSX, Images)
│   ├── domain_router.py     # 3-tier email classifier
│   ├── download_attachments.py
│   ├── google_sheet_sync.py # Google Sheets synchronization
│   ├── main_worker.py       # Core orchestration & Gemini extraction
│   ├── notifier.py          # WhatsApp Green-API dispatch
│   ├── project_graph.py     # Entity relation graph & cross-thread tracking
│   ├── state_manager.py     # Deduplication & idempotency management
│   └── tender_parser.py     # Notification formatting templates
└── tests/                   # Automated unit & integration test suites
`

---

## 🔒 Security & Privacy

- **Decoupled Configuration:** Secrets, OAuth tokens, and API credentials are kept in .env and local configuration directories.
- **Minimal OAuth Scopes:** Operates under read-only Gmail access scopes.
- **Anonymized Data:** Test fixtures and documentation use synthetic enterprise entities.
