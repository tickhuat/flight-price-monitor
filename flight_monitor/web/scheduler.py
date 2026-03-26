from __future__ import annotations

import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler()
JOB_ID = "scheduled_flight_search"


def init_scheduler(app) -> None:
    """Initialize and start the background scheduler."""
    # Avoid double-start when Flask reloader is active
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    if not scheduler.running:
        scheduler.start()
        logger.info("Scheduler started")

    # Load schedule settings from DB and configure job
    with app.app_context():
        reschedule(app)


def _run_all_watches(app) -> None:
    """Job function: run searches for all enabled watches."""
    with app.app_context():
        from .database import Watch
        from .services import run_search_for_watch

        watches = Watch.query.filter_by(enabled=True).all()
        logger.info(f"Scheduled run: processing {len(watches)} enabled watches")
        for watch in watches:
            try:
                run_search_for_watch(watch.id, triggered_by="schedule")
            except Exception as e:
                logger.error(f"Scheduled search failed for watch {watch.id}: {e}")


def reschedule(app) -> None:
    """Update or remove the scheduled job based on current DB settings."""
    from .database import Setting

    enabled = Setting.get("schedule_enabled", "false") == "true"
    hour = int(Setting.get("schedule_hour", "21"))

    if scheduler.get_job(JOB_ID):
        scheduler.remove_job(JOB_ID)

    if enabled:
        scheduler.add_job(
            _run_all_watches,
            CronTrigger(hour=hour, minute=0),
            id=JOB_ID,
            args=[app],
            replace_existing=True,
        )
        logger.info(f"Scheduled job set to run daily at {hour:02d}:00")
    else:
        logger.info("Scheduled job disabled")
