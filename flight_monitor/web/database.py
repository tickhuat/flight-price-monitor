from __future__ import annotations

import json
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Watch(db.Model):
    __tablename__ = "watches"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=True)

    origins = db.Column(db.Text, nullable=False)  # JSON array
    destinations = db.Column(db.Text, nullable=False)  # JSON array
    trip_type = db.Column(db.String(20), nullable=False, default="round_trip")

    departure_date_from = db.Column(db.Date, nullable=False)
    departure_date_to = db.Column(db.Date, nullable=False)
    return_date_from = db.Column(db.Date, nullable=True)
    return_date_to = db.Column(db.Date, nullable=True)

    cabin_classes = db.Column(db.Text, nullable=False)  # JSON array
    max_stopovers = db.Column(db.Integer, nullable=False, default=0)
    adults = db.Column(db.Integer, nullable=False, default=1)

    max_price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False, default="USD")
    max_results = db.Column(db.Integer, nullable=False, default=20)

    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    search_runs = db.relationship("SearchRun", backref="watch", lazy="dynamic")

    def get_origins(self) -> list[str]:
        return json.loads(self.origins)

    def set_origins(self, values: list[str]):
        self.origins = json.dumps(values)

    def get_destinations(self) -> list[str]:
        return json.loads(self.destinations)

    def set_destinations(self, values: list[str]):
        self.destinations = json.dumps(values)

    def get_cabin_classes(self) -> list[str]:
        return json.loads(self.cabin_classes)

    def set_cabin_classes(self, values: list[str]):
        self.cabin_classes = json.dumps(values)


class SearchRun(db.Model):
    __tablename__ = "search_runs"

    id = db.Column(db.Integer, primary_key=True)
    watch_id = db.Column(db.Integer, db.ForeignKey("watches.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    offers_found = db.Column(db.Integer, default=0)
    offers_matched = db.Column(db.Integer, default=0)
    errors = db.Column(db.Text, nullable=True)  # JSON array
    triggered_by = db.Column(db.String(20), nullable=False, default="manual")

    offers = db.relationship("FlightOfferRow", backref="search_run", lazy="dynamic")

    def get_errors(self) -> list[str]:
        if not self.errors:
            return []
        return json.loads(self.errors)

    def set_errors(self, values: list[str]):
        self.errors = json.dumps(values)


class FlightOfferRow(db.Model):
    __tablename__ = "flight_offers"

    id = db.Column(db.Integer, primary_key=True)
    search_run_id = db.Column(
        db.Integer, db.ForeignKey("search_runs.id"), nullable=False
    )

    provider = db.Column(db.String(50), nullable=False)
    airline = db.Column(db.String(100))
    airline_code = db.Column(db.String(10))
    origin = db.Column(db.String(10), nullable=False)
    destination = db.Column(db.String(10), nullable=False)

    departure_date = db.Column(db.Date)
    return_date = db.Column(db.Date, nullable=True)
    departure_time = db.Column(db.String(10))
    arrival_time = db.Column(db.String(10))
    return_departure_time = db.Column(db.String(10), nullable=True)
    return_arrival_time = db.Column(db.String(10), nullable=True)

    duration_outbound_minutes = db.Column(db.Integer)
    duration_return_minutes = db.Column(db.Integer, nullable=True)

    stopovers = db.Column(db.Integer, default=0)
    cabin_class = db.Column(db.String(30))

    price_original = db.Column(db.Float, nullable=False)
    currency_original = db.Column(db.String(10), nullable=False)
    price_display = db.Column(db.Float, nullable=True)
    currency_display = db.Column(db.String(10), nullable=True)

    booking_link = db.Column(db.Text)
    is_under_threshold = db.Column(db.Boolean, nullable=False, default=False)


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    @staticmethod
    def get(key: str, default: str = "") -> str:
        row = Setting.query.filter_by(key=key).first()
        return row.value if row and row.value else default

    @staticmethod
    def set(key: str, value: str):
        row = Setting.query.filter_by(key=key).first()
        if row:
            row.value = value
        else:
            row = Setting(key=key, value=value)
            db.session.add(row)
        db.session.commit()

    @staticmethod
    def get_all() -> dict[str, str]:
        rows = Setting.query.all()
        return {r.key: (r.value or "") for r in rows}
