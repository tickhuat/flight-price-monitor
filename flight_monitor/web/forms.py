from __future__ import annotations

from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    FloatField,
    IntegerField,
    PasswordField,
    SelectField,
    SelectMultipleField,
    StringField,
    widgets,
)
from wtforms.validators import DataRequired, NumberRange, Optional, ValidationError


class MultiCheckboxField(SelectMultipleField):
    widget = widgets.ListWidget(prefix_label=False)
    option_widget = widgets.CheckboxInput()


class WatchForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    enabled = BooleanField("Enabled", default=True)

    origins = StringField(
        "Origins (IATA codes, comma-separated)",
        validators=[DataRequired()],
        description="e.g. KUL, PEN, SZB",
    )
    destinations = StringField(
        "Destinations (IATA codes, comma-separated)",
        validators=[DataRequired()],
        description="e.g. TPE, TSA, NRT",
    )

    trip_type = SelectField(
        "Trip Type",
        choices=[("one_way", "One Way"), ("round_trip", "Round Trip")],
        default="round_trip",
    )

    departure_date_from = DateField("Departure From", validators=[DataRequired()])
    departure_date_to = DateField("Departure To", validators=[DataRequired()])
    return_date_from = DateField("Return From", validators=[Optional()])
    return_date_to = DateField("Return To", validators=[Optional()])

    cabin_classes = MultiCheckboxField(
        "Cabin Class",
        choices=[
            ("economy", "Economy"),
            ("premium_economy", "Premium Economy"),
            ("business", "Business"),
            ("first", "First"),
        ],
        default=["economy"],
    )

    max_stopovers = IntegerField(
        "Max Stopovers", default=0, validators=[NumberRange(min=0, max=5)]
    )
    adults = IntegerField(
        "Adults", default=1, validators=[NumberRange(min=1, max=9)]
    )
    max_price = FloatField("Max Price", validators=[DataRequired(), NumberRange(min=0)])
    currency = StringField("Currency", default="TWD", validators=[DataRequired()])
    max_results = IntegerField(
        "Max Results", default=20, validators=[NumberRange(min=1, max=100)]
    )

    def validate_departure_date_to(self, field):
        if field.data and self.departure_date_from.data:
            if field.data < self.departure_date_from.data:
                raise ValidationError("Must be >= departure from date")

    def validate_return_date_from(self, field):
        if self.trip_type.data == "round_trip":
            if not field.data:
                raise ValidationError("Required for round trip")
            if self.departure_date_from.data and field.data < self.departure_date_from.data:
                raise ValidationError("Must be >= departure from date")

    def validate_return_date_to(self, field):
        if self.trip_type.data == "round_trip":
            if not field.data:
                raise ValidationError("Required for round trip")
            if self.return_date_from.data and field.data < self.return_date_from.data:
                raise ValidationError("Must be >= return from date")

    def validate_cabin_classes(self, field):
        if not field.data:
            raise ValidationError("Select at least one cabin class")

    def get_origins_list(self) -> list[str]:
        return [s.strip().upper() for s in self.origins.data.split(",") if s.strip()]

    def get_destinations_list(self) -> list[str]:
        return [
            s.strip().upper() for s in self.destinations.data.split(",") if s.strip()
        ]


class EmailSettingsForm(FlaskForm):
    smtp_host = StringField("SMTP Host", default="smtp.gmail.com")
    smtp_port = IntegerField("SMTP Port", default=587)
    smtp_user = StringField("SMTP User")
    smtp_password = PasswordField("SMTP Password")
    email_from = StringField("From Address")
    email_recipient = StringField("Recipient")


class ProviderSettingsForm(FlaskForm):
    google_flights_enabled = BooleanField("Google Flights", default=True)
    travelpayouts_enabled = BooleanField("Travelpayouts", default=False)
    travelpayouts_token = StringField("Travelpayouts API Token")


class ScheduleSettingsForm(FlaskForm):
    schedule_enabled = BooleanField("Enable Scheduled Searches", default=False)
    schedule_hour = IntegerField(
        "Run at hour (0-23)",
        default=21,
        validators=[NumberRange(min=0, max=23)],
    )
