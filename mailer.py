from __future__ import annotations
import os, smtplib, ssl, time, logging
from email.message import EmailMessage
from typing import Optional, Iterable, Tuple

log = logging.getLogger(__name__)

class SMTPSender:
    """
    Production-grade SMTP sender using stdlib smtplib.
    Supports TLS or SSL with retries and timeouts.
    Environment variables (required unless noted):
      - SMTP_HOST
      - SMTP_PORT
      - SMTP_USERNAME
      - SMTP_PASSWORD
      - SMTP_USE_TLS (true/false)        # optional if SSL used
      - SMTP_USE_SSL (true/false)        # optional if TLS used
      - SMTP_FROM (e.g., '별내위키 <no-reply@bl-m.kr>')
      - SMTP_REPLY_TO (optional)
      - SMTP_TIMEOUT (seconds, default 15)
      - SMTP_MAX_RETRIES (default 3)
      - SMTP_RETRY_BACKOFF (seconds, default 2)
    """
    def __init__(self):
        self.host = os.getenv("SMTP_HOST")
        self.port = int(os.getenv("SMTP_PORT", "0"))
        self.user = os.getenv("SMTP_USERNAME")
        self.password = os.getenv("SMTP_PASSWORD")
        self.use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("1","true","yes","y")
        self.use_ssl = os.getenv("SMTP_USE_SSL", "false").lower() in ("1","true","yes","y")
        self.from_addr = os.getenv("SMTP_FROM") or self.user
        self.reply_to = os.getenv("SMTP_REPLY_TO")
        self.timeout = int(os.getenv("SMTP_TIMEOUT", "15"))
        self.max_retries = int(os.getenv("SMTP_MAX_RETRIES", "3"))
        self.backoff = int(os.getenv("SMTP_RETRY_BACKOFF", "2"))
        if not (self.host and self.port and self.user and self.password and self.from_addr):
            raise RuntimeError("SMTP env vars missing: please set SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM")

    def _connect(self):
        if self.use_ssl:
            context = ssl.create_default_context()
            server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout, context=context)
        else:
            server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
            if self.use_tls:
                context = ssl.create_default_context()
                server.starttls(context=context)
        server.login(self.user, self.password)
        return server

    def send(self, subject: str, body_text: str, to: Iterable[str], body_html: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = ", ".join(to)
        if self.reply_to:
            msg["Reply-To"] = self.reply_to

        if body_html:
            # multipart/alternative
            msg.set_content(body_text)
            msg.add_alternative(body_html, subtype="html")
        else:
            msg.set_content(body_text)

        attempt = 0
        last_err = None
        while attempt < self.max_retries:
            try:
                with self._connect() as server:
                    server.send_message(msg)
                return True, None
            except Exception as e:
                last_err = str(e)
                log.exception("SMTP send failed (attempt %s/%s): %s", attempt+1, self.max_retries, e)
                attempt += 1
                if attempt < self.max_retries:
                    time.sleep(self.backoff * attempt)
        return False, last_err
