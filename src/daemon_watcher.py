"""
Business Mail Copilot — Gmail Polling Daemon
Enterprise Trading Corporation

Real-time email monitoring daemon that:
1. Polls Gmail API every 60 seconds for new incoming emails
2. Classifies each email via DomainRouter (BUYER/SUPPLIER/BANK/IGNORE)
3. Routes to tier-specific extraction via TenderCopilotWorker
4. Syncs to Excel tracker + sends WhatsApp alert
5. Guarantees zero duplicate processing via StateManager

CRITICAL CONSTRAINTS:
- ZERO historical email alerts — only emails arriving AFTER daemon start
- Idempotent: StateManager prevents re-processing
- Executive's WhatsApp (+8801700000000) receives alerts
- Test phone (+8801600000000) for development testing
"""

import os, sys, json, time, logging
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Load environment variables from .env
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from src.main_worker import TenderCopilotWorker
from src.domain_router import DomainRouter
from src.state_manager import StateManager

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

import base64

CONFIG_DIR = PROJECT_ROOT / "config"
TOKEN_FILE = CONFIG_DIR / "gmail_token.json"
DATA_DIR = PROJECT_ROOT / "data"

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(DATA_DIR / "daemon.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DaemonWatcher")

POLL_INTERVAL_SECONDS = 60


class DaemonWatcher:
    """Polls Gmail for new emails and routes them through the copilot pipeline."""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self.worker = TenderCopilotWorker()
        self.router = DomainRouter()
        self.state_mgr = StateManager()

        # Gmail API setup
        self.gmail_service = self._build_gmail_service()
        if not self.gmail_service:
            raise RuntimeError("Gmail service failed to initialize. Check gmail_token.json.")

        # CRITICAL: Baseline timestamp — only process emails AFTER this moment
        self.baseline_time = datetime.now(timezone.utc)
        self.baseline_epoch_ms = int(self.baseline_time.timestamp() * 1000)
        logger.info(f"Daemon initialized. Baseline: {self.baseline_time.isoformat()}")
        logger.info(f"Test mode: {self.test_mode}")
        logger.info(f"Only emails AFTER {self.baseline_time.strftime('%Y-%m-%d %H:%M:%S UTC')} will be processed.")

    def _build_gmail_service(self):
        """Build Gmail API service from stored OAuth tokens."""
        if not TOKEN_FILE.exists():
            logger.error(f"Token file not found: {TOKEN_FILE}")
            return None

        try:
            token_data = json.loads(TOKEN_FILE.read_text(encoding='utf-8'))
            creds = Credentials(
                token=token_data.get('access_token') or token_data.get('token'),
                refresh_token=token_data.get('refresh_token'),
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ.get('GMAIL_CLIENT_ID'),
                client_secret=os.environ.get('GMAIL_CLIENT_SECRET'),
            )

            if creds.expired and creds.refresh_token:
                creds.refresh(Request())
                # Save refreshed token
                new_token_data = {
                    'access_token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                }
                TOKEN_FILE.write_text(json.dumps(new_token_data, indent=2), encoding='utf-8')
                logger.info("OAuth token refreshed and saved.")

            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Gmail service init failed: {e}")
            return None

    def _fetch_new_messages(self):
        """Fetch message IDs of emails received AFTER baseline."""
        try:
            # Gmail query: after baseline, only inbox, exclude sent
            after_epoch_sec = int(self.baseline_epoch_ms / 1000)
            query = f"after:{after_epoch_sec} in:inbox -from:me"

            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=20
            ).execute()

            messages = results.get('messages', [])
            return [m['id'] for m in messages]
        except Exception as e:
            logger.error(f"Failed to fetch messages: {e}")
            return []

    def _get_email_object(self, msg_id: str) -> dict:
        """Fetch full email content from Gmail API."""
        try:
            msg = self.gmail_service.users().messages().get(
                userId='me',
                id=msg_id,
                format='full'
            ).execute()

            headers_raw = msg.get('payload', {}).get('headers', [])
            headers = {}
            for h in headers_raw:
                name = h['name'].lower()
                if name in ['subject', 'from', 'to', 'date']:
                    headers[name] = h['value']

            # Extract body text
            body = self._extract_body(msg.get('payload', {}))

            return {
                'id': msg_id,
                'thread_id': msg.get('threadId', ''),
                'headers': headers,
                'body': body,
                'internal_date': int(msg.get('internalDate', 0)),
            }
        except Exception as e:
            logger.error(f"Failed to get email {msg_id}: {e}")
            return None

    def _extract_body(self, payload: dict) -> str:
        """Recursively extract plain text body from MIME structure."""
        mime = payload.get('mimeType', '')
        if mime == 'text/plain':
            data = payload.get('body', {}).get('data', '')
            if data:
                return base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
        if 'parts' in payload:
            for part in payload['parts']:
                text = self._extract_body(part)
                if text:
                    return text
        return ''

    def _download_attachments(self, msg_id: str, payload: dict) -> list:
        """Download all attachments from an email and save to temp directory.
        Returns list of Path objects pointing to downloaded files."""
        import tempfile
        attachment_files = []
        temp_dir = Path(tempfile.mkdtemp(prefix=f"copilot_{msg_id[:8]}_"))

        def _find_parts(part):
            """Recursively find attachment parts in MIME structure."""
            filename = part.get('filename', '')
            body = part.get('body', {})
            attachment_id = body.get('attachmentId')

            if filename and attachment_id:
                try:
                    att = self.gmail_service.users().messages().attachments().get(
                        userId='me', messageId=msg_id, id=attachment_id
                    ).execute()
                    file_data = base64.urlsafe_b64decode(att['data'])
                    file_path = temp_dir / filename
                    file_path.write_bytes(file_data)
                    attachment_files.append(file_path)
                    logger.info(f"  📎 Downloaded: {filename} ({len(file_data)//1024}KB)")
                except Exception as e:
                    logger.error(f"  ❌ Attachment download failed [{filename}]: {e}")

            # Recurse into nested parts
            for sub_part in part.get('parts', []):
                _find_parts(sub_part)

        _find_parts(payload)
        return attachment_files

    def run_once(self):
        """Single polling cycle — fetch new emails and process them."""
        msg_ids = self._fetch_new_messages()
        new_count = 0

        for msg_id in msg_ids:
            if self.state_mgr.is_processed(msg_id):
                continue

            email_obj = self._get_email_object(msg_id)
            if not email_obj:
                continue

            # Verify it's actually after baseline (double check)
            if email_obj['internal_date'] < self.baseline_epoch_ms:
                continue

            sender = email_obj.get('headers', {}).get('from', '')
            subject = email_obj.get('headers', {}).get('subject', '')

            logger.info(f"Processing: [{sender}] {subject[:60]}")

            # Download attachments from Gmail
            try:
                raw_msg = self.gmail_service.users().messages().get(
                    userId='me', id=msg_id, format='full'
                ).execute()
                attachment_files = self._download_attachments(msg_id, raw_msg.get('payload', {}))
            except Exception as e:
                logger.error(f"  Attachment download error: {e}")
                attachment_files = []

            try:
                result = self.worker.process_message(
                    message_id=msg_id,
                    email_obj=email_obj,
                    attachment_files=attachment_files
                )
                status = result.get('status', 'unknown')
                tier = result.get('tier', result.get('lifecycle_stage', 'N/A'))
                logger.info(f"  → {status} (tier: {tier})")
                new_count += 1
            except Exception as e:
                logger.error(f"  → ERROR processing {msg_id}: {e}")

        return new_count

    def run_forever(self):
        """Main daemon loop — polls every POLL_INTERVAL_SECONDS."""
        logger.info("="*60)
        logger.info("🚀 Business Mail Copilot Daemon Started")
        logger.info(f"   Polling interval: {POLL_INTERVAL_SECONDS}s")
        logger.info(f"   Baseline: {self.baseline_time.isoformat()}")
        logger.info(f"   Test mode: {self.test_mode}")
        logger.info("="*60)

        cycle = 0
        while True:
            cycle += 1
            try:
                new_count = self.run_once()
                if new_count > 0:
                    logger.info(f"Cycle {cycle}: processed {new_count} new email(s)")
                else:
                    # Silent on zero — only log every 10th cycle
                    if cycle % 10 == 0:
                        logger.info(f"Cycle {cycle}: no new emails")
            except KeyboardInterrupt:
                logger.info("Daemon stopped by user (Ctrl+C).")
                break
            except Exception as e:
                logger.error(f"Cycle {cycle} error: {e}")

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Business Mail Copilot Daemon")
    parser.add_argument('--test', action='store_true', help='Run in test mode (alerts go to test phone)')
    parser.add_argument('--once', action='store_true', help='Run single polling cycle then exit')
    args = parser.parse_args()

    daemon = DaemonWatcher(test_mode=args.test)

    if args.once:
        count = daemon.run_once()
        logger.info(f"Single cycle complete: {count} emails processed.")
    else:
        daemon.run_forever()
