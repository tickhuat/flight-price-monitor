from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flight_monitor.models import FlightOffer, SearchResult

logger = logging.getLogger(__name__)


class EmailNotifier:
    """Send HTML email alerts via SMTP (Gmail App Password recommended)."""

    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username: str,
        password: str,
        from_addr: str,
    ):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr

    def send_alert(self, recipient: str, results: list[SearchResult]) -> bool:
        """
        Send email with flight deals. Only sends if at least one watch has deals.
        Returns True if email was sent.
        """
        deals = [r for r in results if r.offers_under_threshold]
        if not deals:
            logger.info("No deals found, skipping email")
            return False

        total = sum(len(r.offers_under_threshold) for r in deals)
        subject = f"Flight Alert: {total} deal{'s' if total != 1 else ''} found!"

        html_body = self._render_html(deals)
        plain_body = self._render_plain(deals)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = recipient
        msg.attach(MIMEText(plain_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        try:
            if self.smtp_port == 465:
                with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.login(self.username, self.password)
                    server.sendmail(self.from_addr, recipient, msg.as_string())
            else:
                with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                    server.starttls()
                    server.login(self.username, self.password)
                    server.sendmail(self.from_addr, recipient, msg.as_string())

            logger.info(f"Email sent to {recipient} ({total} deals)")
            return True
        except smtplib.SMTPException as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _render_html(self, results: list[SearchResult]) -> str:
        """Render HTML email body with tables per watch."""
        sections = []

        for result in results:
            offers = result.offers_under_threshold
            if not offers:
                continue

            currency = offers[0].currency_display or offers[0].currency_original
            has_return = any(o.return_date for o in offers)
            rows = ""
            for o in offers:
                price = o.price_display if o.price_display is not None else o.price_original
                duration_str = _format_duration(o.duration_outbound_minutes)
                route = f"{o.origin} → {o.destination}"
                time_str = f"{o.departure_time} → {o.arrival_time}"

                ret_info = f"<td>{o.return_date}</td>" if o.return_date else ("" if not has_return else "<td>-</td>")

                book_link = f'<a href="{o.booking_link}">Book</a>' if o.booking_link else "-"

                airline_display = f"{o.airline} ({o.airline_code})" if o.airline != o.airline_code else o.airline

                rows += f"""<tr>
                    <td>{airline_display}</td>
                    <td>{route}</td>
                    <td>{o.departure_date}</td>
                    <td>{time_str}</td>
                    <td>{duration_str}</td>
                    {ret_info}
                    <td style="font-weight:bold;">{currency} {price:,.0f}</td>
                    <td>{book_link}</td>
                </tr>"""

            return_header = "<th>Return Date</th>" if has_return else ""

            section = f"""
            <h2>{result.watch_name}</h2>
            <p>{len(offers)} deal{'s' if len(offers) != 1 else ''} found</p>
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; font-family:sans-serif; font-size:14px;">
                <thead style="background-color:#f0f0f0;">
                    <tr>
                        <th>Airline</th>
                        <th>Route</th>
                        <th>Depart Date</th>
                        <th>Time</th>
                        <th>Duration</th>
                        {return_header}
                        <th>Price</th>
                        <th>Book</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>"""
            sections.append(section)

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family:sans-serif; padding:20px;">
    <h1>Flight Price Alert</h1>
    {''.join(sections)}
    <hr>
    <p style="color:#888; font-size:12px;">Generated by Flight Price Monitor</p>
</body>
</html>"""

    def _render_plain(self, results: list[SearchResult]) -> str:
        """Plain text fallback."""
        lines = ["FLIGHT PRICE ALERT", "=" * 40, ""]

        for result in results:
            offers = result.offers_under_threshold
            if not offers:
                continue

            currency = offers[0].currency_display or offers[0].currency_original
            lines.append(f"--- {result.watch_name} ---")
            lines.append(f"{len(offers)} deals found")
            lines.append("")

            for o in offers:
                price = o.price_display if o.price_display is not None else o.price_original
                airline_display = f"{o.airline} ({o.airline_code})" if o.airline != o.airline_code else o.airline
                line = (
                    f"  {airline_display}  {o.origin}->{o.destination}  "
                    f"{o.departure_date} {o.departure_time}"
                )
                if o.return_date:
                    line += f"  Return: {o.return_date} {o.return_departure_time or ''}"
                line += f"  {_format_duration(o.duration_outbound_minutes)}"
                line += f"  {currency} {price:,.0f}"
                if o.booking_link:
                    line += f"\n    Book: {o.booking_link}"
                lines.append(line)
                lines.append("")

        return "\n".join(lines)


def _format_duration(minutes: int | None) -> str:
    """Format minutes into 'Xh Ym' string."""
    if not minutes:
        return "-"
    h, m = divmod(minutes, 60)
    if h and m:
        return f"{h}h{m:02d}m"
    elif h:
        return f"{h}h"
    else:
        return f"{m}m"
