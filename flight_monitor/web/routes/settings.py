from __future__ import annotations

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from ..database import Setting
from ..forms import EmailSettingsForm, ProviderSettingsForm, ScheduleSettingsForm

bp = Blueprint("settings", __name__)


@bp.route("/", methods=["GET", "POST"])
def index():
    email_form = EmailSettingsForm(prefix="email")
    provider_form = ProviderSettingsForm(prefix="provider")
    schedule_form = ScheduleSettingsForm(prefix="schedule")

    if request.method == "GET":
        s = Setting.get_all()
        email_form.smtp_host.data = s.get("smtp_host", "smtp.gmail.com")
        email_form.smtp_port.data = int(s.get("smtp_port", "587") or 587)
        email_form.smtp_user.data = s.get("smtp_user", "")
        email_form.email_from.data = s.get("email_from", "")
        email_form.email_recipient.data = s.get("email_recipient", "")
        # smtp_password intentionally left blank for security

        provider_form.google_flights_enabled.data = s.get("google_flights_enabled", "true") == "true"
        provider_form.travelpayouts_enabled.data = s.get("travelpayouts_enabled", "false") == "true"
        provider_form.travelpayouts_token.data = s.get("travelpayouts_token", "")

        schedule_form.schedule_enabled.data = s.get("schedule_enabled", "false") == "true"
        schedule_form.schedule_hour.data = int(s.get("schedule_hour", "21") or 21)

    elif request.method == "POST":
        form_name = request.form.get("form_name")

        if form_name == "email" and email_form.validate():
            Setting.set("smtp_host", email_form.smtp_host.data or "")
            Setting.set("smtp_port", str(email_form.smtp_port.data or 587))
            Setting.set("smtp_user", email_form.smtp_user.data or "")
            if email_form.smtp_password.data:
                Setting.set("smtp_password", email_form.smtp_password.data)
            Setting.set("email_from", email_form.email_from.data or "")
            Setting.set("email_recipient", email_form.email_recipient.data or "")
            flash("Email settings saved.", "success")
            return redirect(url_for("settings.index"))

        elif form_name == "provider" and provider_form.validate():
            Setting.set("google_flights_enabled", "true" if provider_form.google_flights_enabled.data else "false")
            Setting.set("travelpayouts_enabled", "true" if provider_form.travelpayouts_enabled.data else "false")
            Setting.set("travelpayouts_token", provider_form.travelpayouts_token.data or "")
            flash("Provider settings saved.", "success")
            return redirect(url_for("settings.index"))

        elif form_name == "schedule" and schedule_form.validate():
            Setting.set("schedule_enabled", "true" if schedule_form.schedule_enabled.data else "false")
            Setting.set("schedule_hour", str(schedule_form.schedule_hour.data))
            from ..scheduler import reschedule
            reschedule(current_app._get_current_object())
            flash("Schedule settings saved.", "success")
            return redirect(url_for("settings.index"))

        else:
            flash("Invalid form submission.", "error")

    return render_template(
        "settings.html",
        email_form=email_form,
        provider_form=provider_form,
        schedule_form=schedule_form,
    )
