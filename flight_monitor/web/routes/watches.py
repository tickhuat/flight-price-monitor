from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..database import SearchRun, Watch, db
from ..forms import WatchForm
from .. import services

bp = Blueprint("watches", __name__)


@bp.route("/")
def index():
    watches = Watch.query.order_by(Watch.created_at.desc()).all()
    # Attach latest search run to each watch for display
    latest_runs = {}
    for w in watches:
        run = w.search_runs.order_by(SearchRun.started_at.desc()).first()
        latest_runs[w.id] = run
    return render_template("watches/index.html", watches=watches, latest_runs=latest_runs)


@bp.route("/new", methods=["GET", "POST"])
def create():
    form = WatchForm()
    if form.validate_on_submit():
        watch = Watch(
            name=form.name.data,
            enabled=form.enabled.data,
            trip_type=form.trip_type.data,
            departure_date_from=form.departure_date_from.data,
            departure_date_to=form.departure_date_to.data,
            return_date_from=form.return_date_from.data,
            return_date_to=form.return_date_to.data,
            max_stopovers=form.max_stopovers.data,
            adults=form.adults.data,
            max_price=form.max_price.data,
            currency=form.currency.data.upper(),
            max_results=form.max_results.data,
        )
        watch.set_origins(form.get_origins_list())
        watch.set_destinations(form.get_destinations_list())
        watch.set_cabin_classes(form.cabin_classes.data)
        db.session.add(watch)
        db.session.commit()
        flash(f"Watch '{watch.name}' created.", "success")
        return redirect(url_for("watches.index"))
    return render_template("watches/form.html", form=form, watch=None)


@bp.route("/<int:watch_id>/edit", methods=["GET", "POST"])
def edit(watch_id: int):
    watch = Watch.query.get_or_404(watch_id)
    form = WatchForm(obj=watch)

    if request.method == "GET":
        # Pre-populate fields that need special handling
        form.origins.data = ", ".join(watch.get_origins())
        form.destinations.data = ", ".join(watch.get_destinations())
        form.cabin_classes.data = watch.get_cabin_classes()

    if form.validate_on_submit():
        watch.name = form.name.data
        watch.enabled = form.enabled.data
        watch.trip_type = form.trip_type.data
        watch.departure_date_from = form.departure_date_from.data
        watch.departure_date_to = form.departure_date_to.data
        watch.return_date_from = form.return_date_from.data
        watch.return_date_to = form.return_date_to.data
        watch.max_stopovers = form.max_stopovers.data
        watch.adults = form.adults.data
        watch.max_price = form.max_price.data
        watch.currency = form.currency.data.upper()
        watch.max_results = form.max_results.data
        watch.set_origins(form.get_origins_list())
        watch.set_destinations(form.get_destinations_list())
        watch.set_cabin_classes(form.cabin_classes.data)
        db.session.commit()
        flash(f"Watch '{watch.name}' updated.", "success")
        return redirect(url_for("watches.index"))

    return render_template("watches/form.html", form=form, watch=watch)


@bp.route("/<int:watch_id>/delete", methods=["POST"])
def delete(watch_id: int):
    watch = Watch.query.get_or_404(watch_id)
    name = watch.name
    # Delete cascaded records manually (no cascade set on model)
    for run in watch.search_runs.all():
        run.offers.delete()
    watch.search_runs.delete()
    db.session.delete(watch)
    db.session.commit()
    flash(f"Watch '{name}' deleted.", "success")
    return redirect(url_for("watches.index"))


@bp.route("/<int:watch_id>/toggle", methods=["POST"])
def toggle(watch_id: int):
    watch = Watch.query.get_or_404(watch_id)
    watch.enabled = not watch.enabled
    db.session.commit()
    state = "enabled" if watch.enabled else "disabled"
    flash(f"Watch '{watch.name}' {state}.", "success")
    return redirect(url_for("watches.index"))


@bp.route("/<int:watch_id>/search", methods=["POST"])
def run_search(watch_id: int):
    watch = Watch.query.get_or_404(watch_id)
    try:
        run_id = services.run_search_for_watch(watch_id, triggered_by="manual")
        flash(f"Search for '{watch.name}' completed.", "success")
        return redirect(url_for("searches.detail", run_id=run_id))
    except Exception as e:
        flash(f"Search failed: {e}", "error")
        return redirect(url_for("watches.index"))
