from __future__ import annotations

from flask import Blueprint, render_template

from ..database import FlightOfferRow, SearchRun, Watch

bp = Blueprint("dashboard", __name__)


@bp.route("/")
def index():
    from datetime import date, datetime

    total_watches = Watch.query.count()
    enabled_watches = Watch.query.filter_by(enabled=True).count()

    today_start = datetime.combine(date.today(), datetime.min.time())
    searches_today = SearchRun.query.filter(SearchRun.started_at >= today_start).count()
    deals_today = (
        FlightOfferRow.query
        .join(SearchRun)
        .filter(SearchRun.started_at >= today_start, FlightOfferRow.is_under_threshold == True)
        .count()
    )

    recent_searches = (
        SearchRun.query
        .order_by(SearchRun.started_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "dashboard.html",
        total_watches=total_watches,
        enabled_watches=enabled_watches,
        searches_today=searches_today,
        deals_today=deals_today,
        recent_searches=recent_searches,
    )
