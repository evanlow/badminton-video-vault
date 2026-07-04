import logging

import requests
from flask import current_app

logger = logging.getLogger(__name__)


class EmailDeliveryError(RuntimeError):
    pass


def _required_config(name):
    value = current_app.config.get(name)
    if not value:
        raise EmailDeliveryError(f"Missing required email config: {name}")
    return value


def send_mailgun_email(recipient_email, subject, text_body, html_body=None, tag=None):
    if current_app.config.get("MAIL_SUPPRESS_SEND"):
        logger.info("MAIL_SUPPRESS_SEND=true; suppressed email to %s subject=%s", recipient_email, subject)
        return {"suppressed": True, "to": recipient_email, "subject": subject}

    api_key = _required_config("MAILGUN_API_KEY")
    domain = _required_config("MAILGUN_DOMAIN")
    sender = _required_config("MAIL_FROM")
    base_url = current_app.config.get("MAILGUN_API_BASE_URL", "https://api.mailgun.net").rstrip("/")
    timeout = current_app.config.get("MAILGUN_TIMEOUT_SECONDS", 10)

    data = {
        "from": sender,
        "to": recipient_email,
        "subject": subject,
        "text": text_body,
        "o:tracking": "no",
    }
    if html_body:
        data["html"] = html_body
    if tag:
        data["o:tag"] = tag
    if current_app.config.get("MAILGUN_TEST_MODE"):
        data["o:testmode"] = "yes"

    try:
        response = requests.post(
            f"{base_url}/v3/{domain}/messages",
            auth=("api", api_key),
            data=data,
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        status_code = getattr(getattr(exc, "response", None), "status_code", None)
        raise EmailDeliveryError(f"Mailgun request failed; status={status_code}") from exc

    try:
        return response.json()
    except ValueError:
        return {"status_code": response.status_code}
