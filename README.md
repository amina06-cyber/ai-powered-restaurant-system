# Mirch & Co — AI-Powered Restaurant Ordering & Reservation System

*Food Worth Coming Back For.*

So here's the idea: customers can browse the menu, place orders, and book a table either through a website or by just chatting with an AI. And no, the AI isn't just answering questions and leaving you hanging, it actually goes and does the thing. Places the order. Books the table for real.

---

## Tech Stack

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL, hosted on Supabase
- **AI Agent:** GPT-4o-mini via OpenAI function calling
- **Frontend:** React (built with Lovable)
- **Automation:** n8n (planned)

---

## Architecture

```
                    CUSTOMER
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
       WEBSITE       AI CHAT      (PHONE — stretch goal)
          │            │
          └────────────┼────────────┘
                       ▼
                  FASTAPI BACKEND
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
       ORDERS     RESERVATIONS    MENU
                       │
                       ▼
              Availability Engine
              (DB-level exclusion
                  constraint)
                       │
                       ▼
                   DATABASE
                  (Supabase)
```

Basically, everything routes through one backend, the website, the AI, and eventually an admin dashboard all hit the same FastAPI endpoints. So no matter how someone orders, the data stays consistent. No weird "the website says X but the AI thinks Y" situations.

---

## Features Built So Far

### Core Backend
- Full database schema: customers, menu items, orders, order items, tables, reservations
- Menu browsing (`GET /menu`) and menu item creation (`POST /menu`)
- Order placement (`POST /orders`) — the server calculates the real total from menu prices itself, it does not trust whatever price a client sends. (Because letting a client set its own price is how you end up with a Rs. 1 biryani.)
- Order status tracking (`GET /orders/{id}`, `GET /orders`, `PATCH /orders/{id}/status`)

### Reservation System (the part that actually kept me up)
- Reservation creation with overlap detection (`POST /reservations`)
- **Database-level exclusion constraint** (Postgres `EXCLUDE USING gist`) so double-booking is blocked at the database itself, not just hoped-away in application code
- Actually stress-tested this — fired two simultaneous booking requests at the exact same table and time to see what would happen. Only one went through, the other got cleanly rejected. No double bookings, no chaos.
- Reservation cancellation (`PATCH /reservations/{id}/cancel`) — cancel it and the slot genuinely frees back up for someone else
- Availability check (`GET /tables/{id}/availability`) — lets you check before you commit to booking
- Errors are handled gracefully now — a conflict returns a clean JSON message instead of the server just faceplanting

### AI Agent (in progress)
- Tool schema is done for GPT-4o-mini: `get_menu`, `create_order`, `check_order_status`, `check_availability`, `create_reservation`, `cancel_reservation`
- Agent script is fully written and wired to call the FastAPI backend directly
- Still pending: actually running it live — waiting on OpenAI billing to get sorted

### Code Structure
Started as one giant `main.py`, which got unmanageable fast, so it's now properly split up:
```
restaurant-backend/
├── main.py            # App entry point, wires routers together
├── database.py         # Supabase/Postgres connection
├── models.py            # SQLAlchemy models
├── schemas.py            # Pydantic request/response schemas
├── routers/
│   ├── menu.py
│   ├── orders.py
│   └── reservations.py
├── ai_tools.py          # GPT function-calling tool definitions
├── agent.py              # AI agent logic
└── test_concurrent.py    # The race-condition test script
```

---

## Known Limitations / Design Notes

- **No authentication** yet on any endpoint — fine for a demo project on a tight deadline, but would absolutely need to be added before this touched real customers
- Reservation conflict checking works in two layers: a quick application-level check first, and a database-level exclusion constraint underneath as the actual guarantee. Both exist, both are tested.
- The 2-hour reservation window is hardcoded right now. In a real version, this would probably be configurable per table/restaurant.

---

## What's Next

- Get the GPT-4o-mini agent actually running live (waiting on OpenAI billing)
- Hook up the React (Lovable) frontend to the backend
- Build a minimal admin/staff dashboard for managing orders and reservations
- n8n automation — order confirmations, reservation reminders
- Deploy the backend to Render
- Voice, via Vapi or an open-source alternative like Pipecat/Vocode — stretch goal, only if there's time left

---

## Setup (Local Development)

```bash
# Clone the repo
git clone https://github.com/amina06-cyber/ai-powered-restaurant-system.git
cd ai-powered-restaurant-system

# Create and activate a virtual environment
python -m venv venv
venv\Scripts\Activate.ps1   # Windows PowerShell
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
# Create a .env file with:
# DATABASE_URL=your_supabase_pooler_connection_string
# OPENAI_API_KEY=your_openai_key

# Run the server
uvicorn main:app --reload
```

Then head to `http://127.0.0.1:8000/docs` for the interactive API docs.