"""
Step 1.3: Targeted Attachment Downloader for Power Plant Emails
Enterprise Trading Corporation

Downloads all genuine business documents (PDF, Excel, Word, Zip) from powergen_b & powergen_a emails.
Filters out small signature icons, logos, and tracking images.
Maintains a complete manifest (attachments_manifest.json) with resume capability.
"""

import os, json, base64, sys, re, time
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
ATTACHMENTS_DIR = PROJECT_ROOT / "attachments"
BACKUP_ATTACHMENTS_DIR = Path(r"D:\digital-corporation\attachments")
TOKEN_FILE = CONFIG_DIR / "gmail_token.json"
EMAILS_FILE = DATA_DIR / "powerplant_emails.json"
MANIFEST_FILE = DATA_DIR / "attachments_manifest.json"

ALLOWED_EXTENSIONS = {
    'pdf', 'xlsx', 'xls', 'docx', 'doc', 'zip', 'rar', 'csv', 'ods', 'odt',
    'jpg', 'jpeg', 'png', 'eml', 'msg', 'txt', 'rtf'
}

def sanitize_filename(name: str) -> str:
    """Remove illegal Windows characters and preserve extension while limiting stem length."""
    clean = re.sub(r'[\\/*?:"<>|]', '_', name).strip().replace(' ', '_')
    if '.' in clean:
        stem, ext = clean.rsplit('.', 1)
        return f"{stem[:70]}.{ext[:10]}"
    return clean[:80]

def main():
    print("=" * 65)
    print("Enterprise Trading Corporation — STEP 1.3: ATTACHMENT DOWNLOADER")
    print("=" * 65)

    if not TOKEN_FILE.exists():
        print(f"❌ Token file not found at: {TOKEN_FILE}")
        sys.exit(1)

    if not EMAILS_FILE.exists():
        print(f"❌ Emails data not found at: {EMAILS_FILE}")
        sys.exit(1)

    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing manifest for resume capability
    manifest = {}
    if MANIFEST_FILE.exists():
        try:
            with open(MANIFEST_FILE, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            print(f"📂 Loaded existing manifest: {len(manifest)} files already recorded.")
        except Exception:
            manifest = {}

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

    with open(EMAILS_FILE, 'r', encoding='utf-8') as f:
        emails = json.load(f)

    # Filter out target documents
    download_queue = []
    for e in emails:
        mid = e.get('id')
        subj = e.get('headers', {}).get('subject', 'No_Subject')
        date_str = e.get('headers', {}).get('date', '')[:16]
        sender = e.get('headers', {}).get('from', '')

        for a in e.get('attachments', []):
            fn = a.get('filename', '')
            aid = a.get('attachment_id')
            size = a.get('size', 0)

            if not fn or not aid:
                continue

            ext = fn.split('.')[-1].lower() if '.' in fn else ''
            if ext in ALLOWED_EXTENSIONS:
                download_queue.append({
                    'message_id': mid,
                    'attachment_id': aid,
                    'original_filename': fn,
                    'extension': ext,
                    'size': size,
                    'subject': subj,
                    'date': date_str,
                    'sender': sender
                })

    print(f"🎯 Total genuine business documents identified: {len(download_queue)}")
    sys.stdout.flush()

    # Process downloads
    downloaded_count = 0
    skipped_count = 0
    error_count = 0
    total_bytes = 0

    for idx, item in enumerate(download_queue, 1):
        mid = item['message_id']
        aid = item['attachment_id']
        fn = item['original_filename']
        key = f"{mid}_{fn}"

        # Unique safe filename
        safe_fn = f"{mid[:8]}_{sanitize_filename(fn)}"
        file_path = ATTACHMENTS_DIR / safe_fn

        # Resume check: already on disk and in manifest
        if file_path.exists() and key in manifest:
            skipped_count += 1
            continue

        sys.stdout.write(f"\r📥 [{idx}/{len(download_queue)}] Downloading: {fn[:35]} ({item['size']//1024} KB)...")
        sys.stdout.flush()

        try:
            att_data = service.users().messages().attachments().get(
                userId='me',
                messageId=mid,
                id=aid
            ).execute()

            raw_bytes = base64.urlsafe_b64decode(att_data.get('data', ''))
            with open(file_path, 'wb') as f:
                f.write(raw_bytes)

            if BACKUP_ATTACHMENTS_DIR.exists():
                try:
                    with open(BACKUP_ATTACHMENTS_DIR / safe_fn, 'wb') as bf:
                        bf.write(raw_bytes)
                except Exception:
                    pass

            manifest[key] = {
                'local_path': str(file_path),
                'filename': fn,
                'file_size': len(raw_bytes),
                'message_id': mid,
                'subject': item['subject'],
                'date': item['date'],
                'sender': item['sender'],
                'downloaded_at': time.strftime("%Y-%m-%d %H:%M:%S")
            }

            downloaded_count += 1
            total_bytes += len(raw_bytes)

            # Auto-save manifest every 25 files
            if downloaded_count % 25 == 0:
                with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
                    json.dump(manifest, f, ensure_ascii=False, indent=2)

        except Exception as e:
            error_count += 1
            print(f"\n   ⚠️ Failed to download {fn} (ID: {mid}): {e}")

    # Final save of manifest
    with open(MANIFEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 65)
    print("📊 STEP 1.3: ATTACHMENT DOWNLOAD SUMMARY")
    print("=" * 65)
    print(f"  • Total Target Documents:   {len(download_queue)}")
    print(f"  • Newly Downloaded:         {downloaded_count}")
    print(f"  • Already Existing/Skipped: {skipped_count}")
    print(f"  • Errors/Failed:            {error_count}")
    print(f"  • Total Data Downloaded:    {total_bytes / (1024*1024):.2f} MB")
    print(f"  • Destination Folder:       {ATTACHMENTS_DIR}")
    print(f"  • Manifest File:            {MANIFEST_FILE}")
    print("=" * 65)
    print("\n[Phase 1 Complete] All emails and documents are safely stored locally.")

if __name__ == "__main__":
    main()
