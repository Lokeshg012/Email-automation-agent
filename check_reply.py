# check_reply.py
import os
import imaplib
import email
from email.utils import parsedate_to_datetime, parseaddr
import mysql.connector
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# --- DB env ---
DB_HOST = os.getenv("DB_HOST")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_NAME = os.getenv("DB_NAME")
DB_SSL_CA = os.getenv("DB_SSL_CA")  # e.g., "ca.pem" in project root

# --- IMAP / mailbox env ---
IMAP_HOST = os.getenv("IMAP_HOST")
IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
MAIL_USER = os.getenv("EMAIL_ADDRESS")
MAIL_PASS = os.getenv("EMAIL_PASSWORD")

def connect_db():
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        ssl_ca=DB_SSL_CA
    )

def connect_imap():
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    imap.login(MAIL_USER, MAIL_PASS)
    imap.select("INBOX")
    return imap

def find_reply_for_contact(imap, contact_email, last_sent_dt):
    """
    Search IMAP for messages FROM contact_email.
    If last_sent_dt is provided, only consider emails strictly after that time.
    Returns True if a qualifying reply is found.
    """
    if not contact_email:
        return False

    # Build IMAP SEARCH criteria: FROM + optional SINCE (by date)
    # Note: IMAP SINCE uses only date (ignores time); we still validate with header Date later.
    criteria = ['FROM', f'"{contact_email}"']
    if last_sent_dt:
        since_str = last_sent_dt.strftime("%d-%b-%Y")
        criteria += ['SINCE', since_str]

    status, data = imap.search(None, *criteria)
    if status != "OK" or not data or not data[0]:
        return False

    msg_ids = data[0].split()
    # Check newest first for speed
    for mid in reversed(msg_ids):
        res, msg_data = imap.fetch(mid, "(RFC822)")
        if res != "OK" or not msg_data or not isinstance(msg_data[0], tuple):
            continue

        msg = email.message_from_bytes(msg_data[0][1])
        from_addr = parseaddr(msg.get("From", ""))[1].lower()

        # Strict match with the contact email
        if from_addr != contact_email.lower():
            continue

        # Parse Date header robustly
        email_dt = None
        try:
            hdr_dt = parsedate_to_datetime(msg.get("Date"))
            # compare as naive (MySQL DATETIME is naive)
            email_dt = hdr_dt.replace(tzinfo=None) if hdr_dt.tzinfo else hdr_dt
        except Exception:
            # If we cannot parse Date, treat as reply (conservative) only when last_sent_dt is None
            if last_sent_dt is None:
                return True
            continue

        # If we have a last_sent_dt, require reply strictly after it
        if last_sent_dt:
            if email_dt and email_dt > last_sent_dt:
                return True
        else:
            # No last sent timestamp recorded: any message from them counts as reply
            return True

    return False

def main():
    # 1) DB connection
    db = connect_db()
    cur = db.cursor(dictionary=True)

    # 2) Pull contacts that are not marked Replied
    cur.execute("""
        SELECT id, email, last_email_sent
        FROM contacts
        WHERE (status IS NULL OR status <> 'Replied')
          AND email IS NOT NULL
          AND email <> ''
    """)
    contacts = cur.fetchall()

    if not contacts:
        print("No pending contacts to check.")
        cur.close(); db.close()
        return

    # 3) Connect IMAP
    imap = connect_imap()

    updated = 0
    checked = 0

    for c in contacts:
        checked += 1
        cid = c["id"]
        cem = c["email"]
        last_sent = c["last_email_sent"]  # Python datetime or None

        print(f" Checking contact #{cid} <{cem}> (last_email_sent={last_sent})")

        replied = find_reply_for_contact(imap, cem, last_sent)

        if replied:
            cur.execute(
                "UPDATE contacts SET status=%s, reply_date=%s, updated_at=%s WHERE id=%s",
                ("Replied", datetime.now(), datetime.now(), cid)
            )
            db.commit()
            updated += 1
            print(f" Marked as Replied: {cem}")
        else:
            print(f"— No reply found for: {cem}")

    # 4) Cleanup
    imap.close(); imap.logout()
    cur.close(); db.close()
    print(f"\nDone. Checked {checked} contacts, updated {updated} to Replied.")

if __name__ == "__main__":
    main()