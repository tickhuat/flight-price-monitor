# Web UI Implementation Plan for Flight Price Monitor

## Context

The flight price monitor CLI tool is fully functional. Phase 2 is to add a web UI so the user can manage watches, trigger searches, view results, and configure settings through a browser instead of editing `config.yaml` manually.

A Flask web skeleton already exists with database models, forms, and a service layer — but **routes, templates, static assets, and the scheduler module are missing**. This plan fills in those gaps.

---

## What Already Exists (Reuse These)

| File | What It Provides |
|------|-----------------|
| [web/__init__.py](flight_monitor/web/__init__.py) | App factory, registers 4 blueprints, inits DB + scheduler |
| [web/database.py](flight_monitor/web/database.py) | `Watch`, `SearchRun`, `FlightOfferRow`, `Setting` models |
| [web/forms.py](flight_monitor/web/forms.py) | `WatchForm`, `EmailSettingsForm`, `ProviderSettingsForm`, `ScheduleSettingsForm` |
| [web/services.py](flight_monitor/web/services.py) | `run_search_for_watch()`, `build_providers()`, `db_watch_to_watch_config()` |
| [webapp.py](webapp.py) | Entry point: `python webapp.py` on port 5000 |

---

## Files to Create (14 new files)

### Phase 1: Foundation

**1. `flight_monitor/web/scheduler.py`** — Required at import time by `__init__.py`
- `init_scheduler(app)`: start APScheduler `BackgroundScheduler`
- `_run_all_watches(app)`: job function — queries enabled watches, calls `run_search_for_watch()` for each
- `reschedule(app)`: called by settings route when schedule config changes
- Guard against double-start with Flask reloader (`WERKZEUG_RUN_MAIN`)

**2. `flight_monitor/web/templates/base.html`** — Base layout
- Bootstrap 5.3 via CDN (CSS + JS bundle)
- Navbar: Dashboard / Watches / Searches / Settings
- Flash messages block (Bootstrap alerts)
- `{% block content %}` / `{% block extra_js %}`
- Link to custom `style.css`

**3. `flight_monitor/web/static/style.css`** — Minimal custom CSS
- Deal row highlight (green background)
- Stat card styling
- Table hover effects
- Minor spacing adjustments

### Phase 2: Dashboard

**4. `flight_monitor/web/routes/dashboard.py`** — Blueprint `bp`, name `dashboard`
- `GET /` → `index()`: query watch count, recent searches (last 10), recent deals. Render `dashboard.html`

**5. `flight_monitor/web/templates/dashboard.html`**
- Stat cards: Total Watches, Enabled Watches, Searches Today, Deals Found
- Recent searches table (watch name, status badge, time, offers found/matched)
- Quick action: "Create Watch" button

### Phase 3: Watches (core CRUD)

**6. `flight_monitor/web/routes/watches.py`** — Blueprint `bp`, name `watches`

| Method | URL | Function | Description |
|--------|-----|----------|-------------|
| GET | `/` | `index()` | List all watches |
| GET/POST | `/new` | `create()` | Create watch form |
| GET/POST | `/<id>/edit` | `edit(id)` | Edit watch form |
| POST | `/<id>/delete` | `delete(id)` | Delete watch + cascaded data |
| POST | `/<id>/toggle` | `toggle(id)` | Toggle enabled/disabled |
| POST | `/<id>/search` | `run_search(id)` | Trigger manual search via `services.run_search_for_watch()` |

**7. `flight_monitor/web/templates/watches/index.html`**
- Table: name, routes (origins -> destinations), dates, max price, enabled toggle, last search status, actions (edit/search/delete)

**8. `flight_monitor/web/templates/watches/form.html`** — Shared for create & edit
- All WatchForm fields grouped: Basic Info, Routes, Trip Details, Preferences, Price
- Return date fields conditionally shown via JS when trip_type is "round_trip"

### Phase 4: Search Results

**9. `flight_monitor/web/routes/searches.py`** — Blueprint `bp`, name `searches`

| Method | URL | Function |
|--------|-----|----------|
| GET | `/` | `index()` — list all search runs |
| GET | `/<run_id>` | `detail(run_id)` — view offers for a run |

**10. `flight_monitor/web/templates/searches/index.html`**
- Table: watch name, status badge, time, offers found/matched, triggered by

**11. `flight_monitor/web/templates/searches/detail.html`**
- Summary card (status, time, counts)
- Errors section (collapsible)
- Deals table (green highlight, sorted by price)
- All offers table

### Phase 5: Settings & JS

**12. `flight_monitor/web/routes/settings.py`** — Blueprint `bp`, name `settings`
- `GET/POST /` → `index()`: three forms on one page (email, providers, schedule)
- Each form has hidden `form_name` field to identify which was submitted
- On save, persist to `Setting.set(key, value)`
- When schedule settings change, call `reschedule(app)`

**13. `flight_monitor/web/templates/settings.html`**
- Three Bootstrap cards, each with its own form
- SMTP, Provider, and Schedule settings

**14. `flight_monitor/web/static/app.js`** — Minimal vanilla JS
- Show/hide return date fields based on trip_type
- Delete confirmation dialog
- Auto-dismiss flash messages
- Search button loading state (disable + spinner)

---

## Files to Modify (2 files)

**1. `requirements.txt`** — Add missing Flask dependencies:
```
Flask>=3.0
Flask-SQLAlchemy>=3.1
Flask-WTF>=1.2
APScheduler>=3.10
```

**2. `flight_monitor/web/database.py`** — Add cascade deletes to relationships:
- `Watch.search_runs`: add `cascade="all, delete-orphan"`
- `SearchRun.offers`: add `cascade="all, delete-orphan"`

---

## Key Design Decisions

- **Server-side rendering** with Jinja2 — matches existing Flask skeleton, no frontend build tools needed
- **Bootstrap 5 CDN** — quick, clean, responsive UI without build complexity
- **Synchronous search** — "Search Now" runs synchronously; acceptable for personal tool. Button shows loading state via JS
- **Shared form template** — `watches/form.html` handles both create and edit by checking if a `watch` variable exists in context
- **Settings on one page** — three separate forms with `form_name` hidden field to identify which was submitted

---

## Verification

1. `pip install -r requirements.txt` to ensure all dependencies are declared
2. `python webapp.py` — app should start on http://localhost:5000 without errors
3. Dashboard (`/`) shows empty state with "Create Watch" button
4. Create a watch at `/watches/new` — fill in all fields, submit, verify it appears in the list
5. Edit the watch — verify pre-populated values are correct
6. Toggle enable/disable — verify it toggles
7. "Search Now" — triggers a search, redirects to results detail page
8. `/searches` — lists the search run with correct status
9. `/searches/<id>` — shows flight offers with deal highlights
10. `/settings` — save email/provider/schedule settings, verify they persist across page reloads
11. Delete a watch — verify cascaded deletion of search runs and offers
