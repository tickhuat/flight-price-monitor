from __future__ import annotations

import os

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .database import db

csrf = CSRFProtect()


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "dev-secret-change-me")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL", "sqlite:///flight_monitor.db"
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)
    csrf.init_app(app)

    # Register blueprints
    from .routes.dashboard import bp as dashboard_bp
    from .routes.searches import bp as searches_bp
    from .routes.settings import bp as settings_bp
    from .routes.watches import bp as watches_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(watches_bp, url_prefix="/watches")
    app.register_blueprint(searches_bp, url_prefix="/searches")
    app.register_blueprint(settings_bp, url_prefix="/settings")

    # Create tables
    with app.app_context():
        db.create_all()

    # Initialize scheduler
    from .scheduler import init_scheduler

    init_scheduler(app)

    return app
