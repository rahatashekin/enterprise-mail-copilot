"""
Google Cloud Function / Cloud Run Serverless Entrypoint
Enterprise Trading Corporation — 24/7 Autonomous Tender Copilot

Triggered via HTTP by Google Cloud Scheduler every 5 minutes.
Executes autonomous watch, ingestion, OCR, Excel sync, and WhatsApp dispatch.
Runs 24/7 in Google Cloud even when your laptop is completely powered off.
"""

import os, json, time
import functions_framework
from flask import Request, jsonify
from src.main_worker import TenderCopilotWorker

@functions_framework.http
def handle_tender_watch(request: Request):
    """HTTP Cloud Function triggered by Cloud Scheduler."""
    start_time = time.time()
    try:
        worker = TenderCopilotWorker()
        
        # 1. Query for incoming power plant emails
        if not worker.gmail_service:
            return jsonify({"status": "error", "message": "Gmail credentials missing"}), 500

        # Query only power plant domains
        query = "from:power-plant.gov.bd OR from:energy-utility.com"
        watermark = worker.state_mgr.get_watermark()
        if watermark:
            query += f" after:{watermark}"

        res = worker.gmail_service.users().messages().list(
            userId='me', q=query, maxResults=15
        ).execute()

        messages = res.get('messages', [])
        processed_summary = []

        for m_ref in messages:
            mid = m_ref['id']
            if worker.state_mgr.is_processed(mid):
                continue

            # Fetch full message
            msg_full = worker.gmail_service.users().messages().get(
                userId='me', id=mid, format='full'
            ).execute()

            # Execute pipeline
            p_res = worker.process_message(mid, msg_full, attachment_files=[])
            processed_summary.append(p_res)

        # Update high-watermark
        worker.state_mgr.set_watermark(time.strftime("%Y/%m/%d %H:%M:%S"))

        elapsed = round(time.time() - start_time, 2)
        return jsonify({
            "status": "success",
            "messages_checked": len(messages),
            "newly_processed": len(processed_summary),
            "elapsed_seconds": elapsed,
            "details": processed_summary
        }), 200

    except Exception as e:
        return jsonify({"status": "error", "exception": str(e)}), 500
