from __future__ import annotations

from flask import Blueprint, render_template

from ..database import FlightOfferRow, SearchRun

bp = Blueprint("searches", __name__)


@bp.route("/")
def index():
    runs = SearchRun.query.order_by(SearchRun.started_at.desc()).all()
    return render_template("searches/index.html", runs=runs)


@bp.route("/<int:run_id>")
def detail(run_id: int):
    run = SearchRun.query.get_or_404(run_id)
    offers = (
        FlightOfferRow.query
        .filter_by(search_run_id=run_id)
        .order_by(FlightOfferRow.price_display.asc())
        .all()
    )
    deals = [o for o in offers if o.is_under_threshold]
    others = [o for o in offers if not o.is_under_threshold]
    return render_template("searches/detail.html", run=run, deals=deals, others=others)
