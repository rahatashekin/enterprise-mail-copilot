"""
Step 1.2: Targeted Power Plant Email Extractor (powergen_b & powergen_a)
Enterprise Trading Corporation

Extracts all incoming & outgoing emails for:
  - powergen_b (facility_b 1320MW Power Plant) -> @power-plant.gov.bd
  - powergen_a (facility_a 1320MW Power Plant) -> @energy-utility.com

Captures full body, headers, dates, and attachment metadata.
"""

import os, json, base64, sys
from pathlib import Path
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
TOKEN_FILE = CONFIG_DIR / "gmail_token.json"
OUTPUT_FILE = DATA_DIR / "powerplant_emails.json"

QUERY = (
    "from:power-plant.gov.bd OR from:energy-utility.com OR "
    "to:power-plant.gov.bd OR to:energy-utility.com"
)

def get_body_text(payload):
    """Recursively extract plain text or decoded HTML body from message payload."""
    body = ""
    if 'parts' in payload:
        for p in payload['parts']:
            m = p.get('mimeType', '')
            if m == 'text/plain':
                data = p.get('body', {}).get('data', '')
                if data:
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            elif m == 'text/html' and not body:
                data = p.get('body', {}).get('data', '')
                if data:
                    body += base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
            elif 'parts' in p:
                body += get_body_text(p)
    else:
        data = payload.get('body', {}).get('data', '')
        if data:
            body += base64.urlsafe_b64decode(data).decode('utf-8', errors='replace')
    return body

def get_attachment_metadata(payload):
    """Extract list of attachments with metadata without downloading data."""
    attachments = []
    if 'parts' in payload:
        for p in payload['parts']:
            fn = p.get('filename', '')
            if fn:
                attachments.append({
                    'filename': fn,
                    'attachment_id': p.get('body', {}).get('attachmentId', ''),
                    'size': p.get('body', {}).get('size', 0),
                    'mime_type': p.get('mimeType', '')
                })
            if 'parts' in p:
                attachments.extend(get_attachment_metadata(p))
    return attachments

def main():
    print("=" * 65)
    print("Enterprise Trading Corporation — STEP 1.2: POWER PLANT EMAIL EXTRACTION")
    print("=" * 65)

    if not TOKEN_FILE.exists():
        print(f"❌ Token file not found at: {TOKEN_FILE}")
        sys.exit(1)

    with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get('access_token') or token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ.get('GMAIL_CLIENT_ID'),
        client_secret=os.environ.get('GMAIL_CLIENT_SECRET'),
    )
    service = build('gmail', 'v1', credentials=creds)

    print(f"\n🔍 Searching Gmail with targeted query:")
    print(f"   [{QUERY}]")
    sys.stdout.flush()

    # Fetch all matching message IDs
    all_msg_refs = []
    page_token = None

    while True:
        res = service.users().messages().list(
            userId='me',
            q=QUERY,
            pageToken=page_token,
            maxResults=100
        ).execute()

        msgs = res.get('messages', [])
        all_msg_refs.extend(msgs)
        page_token = res.get('nextPageToken')
        print(f"   Found {len(msgs)} messages (Total so far: {len(all_msg_refs)})")
        if not page_token:
            break

    print(f"\n✅ Total messages found matching query: {len(all_msg_refs)}")
    if not all_msg_refs:
        print("No matching emails found.")
        return

    print("\n📥 Extracting full email contents, bodies & attachments metadata...")
    extracted_emails = []

    powergen_b_in = 0
    powergen_b_out = 0
    powergen_a_in = 0
    powergen_a_out = 0
    total_attachments = 0

    for i, m_ref in enumerate(all_msg_refs, 1):
        mid = m_ref['id']
        sys.stdout.write(f"\r   [{i}/{len(all_msg_refs)}] Fetching email ID: {mid}...")
        sys.stdout.flush()

        try:
            full_msg = service.users().messages().get(
                userId='me',
                id=mid,
                format='full'
            ).execute()

            payload = full_msg.get('payload', {})
            headers = {}
            for h in payload.get('headers', []):
                k = h.get('name', '').lower()
                if k in ['from', 'to', 'cc', 'subject', 'date', 'message-id', 'reply-to']:
                    headers[k] = h.get('value', '')

            body_text = get_body_text(payload)
            attachments = get_attachment_metadata(payload)
            total_attachments += len(attachments)

            # Categorize
            from_str = headers.get('from', '').lower()
            to_str = headers.get('to', '').lower()

            if 'power-plant.gov.bd' in from_str: powergen_b_in += 1
            if 'power-plant.gov.bd' in to_str: powergen_b_out += 1
            if 'energy-utility.com' in from_str: powergen_a_in += 1
            if 'energy-utility.com' in to_str: powergen_a_out += 1

            extracted_emails.append({
                'id': mid,
                'thread_id': full_msg.get('threadId'),
                'snippet': full_msg.get('snippet', ''),
                'headers': headers,
                'body': body_text,
                'attachments': attachments,
                'internal_date': full_msg.get('internalDate', '')
            })

        except Exception as e:
            print(f"\n   ⚠️ Error fetching email {mid}: {e}")

    print("\n\n💾 Saving structured data to JSON...")
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(extracted_emails, f, ensure_ascii=False, indent=2)

    print(f"✅ Data saved to: {OUTPUT_FILE}")

    # Print Summary Report
    print("\n" + "=" * 65)
    print("📊 POWER PLANT EMAIL EXTRACTION SUMMARY")
    print("=" * 65)
    print(f"  • Total Emails Processed:  {len(extracted_emails)}")
    print(f"  • powergen_b (facility_b) Incoming:  {powergen_b_in}")
    print(f"  • powergen_b (facility_b) Outgoing:  {powergen_b_out}")
    print(f"  • powergen_a (facility_a) Incoming:{powergen_a_in}")
    print(f"  • powergen_a (facility_a) Outgoing:{powergen_a_out}")
    print(f"  • Total Attachments Found: {total_attachments} (Excel / PDF / BOQs)")
    print("=" * 65)
    print("\n[Step 1.2 Complete] Ready for attachment download (Step 1.3).")

if __name__ == "__main__":
    main()
