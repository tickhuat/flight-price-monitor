#!/usr/bin/env python3
"""Web application entry point for Flight Price Monitor."""

from dotenv import load_dotenv

load_dotenv()

from flight_monitor.web import create_app

app = create_app()

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    app.run(debug=True, port=port)
