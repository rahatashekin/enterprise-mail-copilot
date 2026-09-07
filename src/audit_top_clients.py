"""
Audit Top Clients & Counterparties
Enterprise Trading Corporation

Analyzes Executive's Sent Items over the last 2 years (after:2024/09/01) using lightweight metadata.
Identifies Top 10-15 client organizations, transaction volume, and percentage share.
"""

import os, json, sys, re
from collections import Counter, defaultdict
from pathlib import Path
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
TOKEN_FILE = CONFIG_DIR / "gmail_token.json"
REPORT_FILE = DATA_DIR / "client_portfolio_report.json"

QUERY = "in:sent after:2024/09/01"

def extract_domain(email_str):
    """Extract domain from an email address or string."""
    m = re.findall(r'[\w\.-]+@([\w\.-]+)', email_str.lower())
    return [d.strip() for d in m if d.strip()]

def main():
    print("=" * 65)
    print("Enterprise Trading Corporation — TOP CLIENT PORTFOLIO AUDIT")
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

    print(f"\n🔍 Searching Executive's Sent Items for the last 2 years:")
    print(f"   Query: [{QUERY}]")
    sys.stdout.flush()

    # Get sent message IDs
    all_msgs = []
    page_token = None

    while True:
        res = service.users().messages().list(
            userId='me',
            q=QUERY,
            pageToken=page_token,
            maxResults=500
        ).execute()

        msgs = res.get('messages', [])
        all_msgs.extend(msgs)
        page_token = res.get('nextPageToken')
        sys.stdout.write(f"\r   Found {len(all_msgs)} sent messages...")
        sys.stdout.flush()
        if not page_token:
            break

    print(f"\n✅ Total sent messages in last 2 years: {len(all_msgs)}")
    if not all_msgs:
        print("No sent messages found.")
        return

    print("\n⚡ Fetching lightweight metadata (To, CC, Subject, Date)...")
    domain_counts = Counter()
    domain_subjects = defaultdict(list)
    email_recipients = Counter()
    total_processed = 0

    for idx, m_ref in enumerate(all_msgs, 1):
        mid = m_ref['id']
        if idx % 100 == 0 or idx == len(all_msgs):
            sys.stdout.write(f"\r   Processed [{idx}/{len(all_msgs)}] messages...")
            sys.stdout.flush()

        try:
            msg = service.users().messages().get(
                userId='me',
                id=mid,
                format='metadata',
                metadataHeaders=['To', 'Cc', 'Subject', 'Date']
            ).execute()

            headers = {h['name'].lower(): h['value'] for h in msg.get('payload', {}).get('headers', [])}
            to_val = headers.get('to', '')
            cc_val = headers.get('cc', '')
            subj = headers.get('subject', 'No Subject')
            combined_recipients = f"{to_val}, {cc_val}"

            domains = extract_domain(combined_recipients)
            for d in set(domains):
                domain_counts[d] += 1
                if len(domain_subjects[d]) < 3:
                    domain_subjects[d].append(subj)

            raw_emails = re.findall(r'[\w\.-]+@[\w\.-]+', combined_recipients.lower())
            for em in set(raw_emails):
                email_recipients[em] += 1

            total_processed += 1

        except Exception as e:
            continue

    print("\n\n📊 Aggregating and classifying client domains...")

    # Filter out common mail domains for separate inspection
    institutional_domains = {}
    generic_emails = Counter()

    for domain, count in domain_counts.items():
        if domain in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com']:
            pass
        else:
            institutional_domains[domain] = count

    for em, count in email_recipients.items():
        d = em.split('@')[-1]
        if d in ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']:
            generic_emails[em] = count

    # Calculate percentages
    total_sent = total_processed or 1

    report_data = {
        'total_sent_analyzed': total_sent,
        'top_institutional_domains': [
            {'domain': d, 'count': c, 'percentage': round((c / total_sent) * 100, 2), 'sample_subjects': domain_subjects[d]}
            for d, c in sorted(institutional_domains.items(), key=lambda x: x[1], reverse=True)[:25]
        ],
        'top_individual_emails': [
            {'email': em, 'count': c, 'percentage': round((c / total_sent) * 100, 2)}
            for em, c in generic_emails.most_common(15)
        ]
    }

    with open(REPORT_FILE, 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 70)
    print("🏆 TOP INSTITUTIONAL CLIENTS & COUNTERPARTIES (LAST 2 YEARS)")
    print("=" * 70)
    print(f"{'Rank':<5} {'Domain / Organization':<30} {'Sent Count':<12} {'Share (%)':<10}")
    print("-" * 70)

    for rank, item in enumerate(report_data['top_institutional_domains'][:15], 1):
        print(f"#{rank:<4} {item['domain']:<30} {item['count']:<12} {item['percentage']}%")

    print("=" * 70)
    print(f"\nFull report saved to: {REPORT_FILE}")

if __name__ == "__main__":
    main()
