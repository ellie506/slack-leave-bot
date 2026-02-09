"""
Slack Leave Management Bot
Handles leave requests, approvals/declines, and generates records
"""

import os
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from slack_bolt import App
from slack_bolt.adapter.flask import SlackRequestHandler
import sqlite3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Slack app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize Flask
flask_app = Flask(__name__)
handler = SlackRequestHandler(app)

# Database setup
DB_PATH = "leave_records.db"

def init_db():
    """Initialize the database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Leave requests table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            user_name TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            days INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            manager_id TEXT,
            manager_name TEXT,
            requested_at TEXT NOT NULL,
            responded_at TEXT,
            response_note TEXT
        )
    """)
    
    # Leave balances table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leave_balances (
            user_id TEXT PRIMARY KEY,
            user_name TEXT NOT NULL,
            annual_leave INTEGER DEFAULT 20,
            sick_leave INTEGER DEFAULT 10,
            personal_leave INTEGER DEFAULT 5,
            updated_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()

init_db()

# Helper functions
def get_leave_balance(user_id):
    """Get user's leave balance"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM leave_balances WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()
    conn.close()
    return balance

def create_leave_balance(user_id, user_name):
    """Create initial leave balance for new user"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leave_balances (user_id, user_name, updated_at)
        VALUES (?, ?, ?)
    """, (user_id, user_name, datetime.now().isoformat()))
    conn.commit()
    conn.close()

def calculate_business_days(start_date, end_date):
    """Calculate number of business days between two dates"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # Monday = 0, Sunday = 6
            days += 1
        current += timedelta(days=1)
    return days

def update_leave_balance(user_id, leave_type, days, operation='subtract'):
    """Update user's leave balance"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    balance = get_leave_balance(user_id)
    if not balance:
        return False
    
    column_map = {
        'annual': 'annual_leave',
        'sick': 'sick_leave',
        'personal': 'personal_leave'
    }
    
    column = column_map.get(leave_type)
    if not column:
        conn.close()
        return False
    
    if operation == 'subtract':
        cursor.execute(f"""
            UPDATE leave_balances 
            SET {column} = {column} - ?,
                updated_at = ?
            WHERE user_id = ?
        """, (days, datetime.now().isoformat(), user_id))
    else:  # add back
        cursor.execute(f"""
            UPDATE leave_balances 
            SET {column} = {column} + ?,
                updated_at = ?
            WHERE user_id = ?
        """, (days, datetime.now().isoformat(), user_id))
    
    conn.commit()
    conn.close()
    return True

# Slack command handlers

@app.command("/leave")
def handle_leave_command(ack, command, client):
    """Handle the /leave slash command"""
    ack()
    
    user_id = command['user_id']
    user_info = client.users_info(user=user_id)
    user_name = user_info['user']['real_name']
    
    # Check if user has a balance record
    if not get_leave_balance(user_id):
        create_leave_balance(user_id, user_name)
    
    # Open modal for leave request
    client.views_open(
        trigger_id=command['trigger_id'],
        view={
            "type": "modal",
            "callback_id": "leave_request_modal",
            "title": {"type": "plain_text", "text": "Request Leave"},
            "submit": {"type": "plain_text", "text": "Submit"},
            "blocks": [
                {
                    "type": "section",
                    "block_id": "leave_type_block",
                    "text": {"type": "mrkdwn", "text": "Select leave type:"},
                    "accessory": {
                        "type": "static_select",
                        "action_id": "leave_type",
                        "placeholder": {"type": "plain_text", "text": "Choose leave type"},
                        "options": [
                            {"text": {"type": "plain_text", "text": "Annual Leave"}, "value": "annual"},
                            {"text": {"type": "plain_text", "text": "Sick Leave"}, "value": "sick"},
                            {"text": {"type": "plain_text", "text": "Personal Leave"}, "value": "personal"}
                        ]
                    }
                },
                {
                    "type": "input",
                    "block_id": "start_date_block",
                    "element": {
                        "type": "datepicker",
                        "action_id": "start_date",
                        "placeholder": {"type": "plain_text", "text": "Select start date"}
                    },
                    "label": {"type": "plain_text", "text": "Start Date"}
                },
                {
                    "type": "input",
                    "block_id": "end_date_block",
                    "element": {
                        "type": "datepicker",
                        "action_id": "end_date",
                        "placeholder": {"type": "plain_text", "text": "Select end date"}
                    },
                    "label": {"type": "plain_text", "text": "End Date"}
                },
                {
                    "type": "input",
                    "block_id": "reason_block",
                    "element": {
                        "type": "plain_text_input",
                        "action_id": "reason",
                        "multiline": True,
                        "placeholder": {"type": "plain_text", "text": "Enter reason (optional)"}
                    },
                    "label": {"type": "plain_text", "text": "Reason"},
                    "optional": True
                },
                {
                    "type": "input",
                    "block_id": "manager_block",
                    "element": {
                        "type": "users_select",
                        "action_id": "manager",
                        "placeholder": {"type": "plain_text", "text": "Select your manager"}
                    },
                    "label": {"type": "plain_text", "text": "Manager"}
                }
            ]
        }
    )

@app.view("leave_request_modal")
def handle_leave_request_submission(ack, body, client, view):
    """Handle leave request form submission"""
    ack()
    
    user_id = body['user']['id']
    user_info = client.users_info(user=user_id)
    user_name = user_info['user']['real_name']
    
    # Extract form values
    values = view['state']['values']
    leave_type = values['leave_type_block']['leave_type']['selected_option']['value']
    start_date = values['start_date_block']['start_date']['selected_date']
    end_date = values['end_date_block']['end_date']['selected_date']
    reason = values['reason_block']['reason'].get('value', '')
    manager_id = values['manager_block']['manager']['selected_user']
    
    manager_info = client.users_info(user=manager_id)
    manager_name = manager_info['user']['real_name']
    
    # Calculate business days
    days = calculate_business_days(start_date, end_date)
    
    # Check leave balance
    balance = get_leave_balance(user_id)
    if balance:
        column_map = {'annual': 2, 'sick': 3, 'personal': 4}
        available = balance[column_map[leave_type]]
        
        if available < days:
            client.chat_postMessage(
                channel=user_id,
                text=f"❌ Insufficient leave balance. You have {available} days of {leave_type} leave, but requested {days} days."
            )
            return
    
    # Save to database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO leave_requests 
        (user_id, user_name, leave_type, start_date, end_date, days, reason, manager_id, manager_name, requested_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, user_name, leave_type, start_date, end_date, days, reason, manager_id, manager_name, datetime.now().isoformat()))
    
    request_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    # Send approval request to manager
    leave_type_display = {
        'annual': 'Annual Leave',
        'sick': 'Sick Leave',
        'personal': 'Personal Leave'
    }
    
    client.chat_postMessage(
        channel=manager_id,
        text=f"New leave request from {user_name}",
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🏖️ New Leave Request"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Employee:*\n{user_name}"},
                    {"type": "mrkdwn", "text": f"*Leave Type:*\n{leave_type_display[leave_type]}"},
                    {"type": "mrkdwn", "text": f"*Start Date:*\n{start_date}"},
                    {"type": "mrkdwn", "text": f"*End Date:*\n{end_date}"},
                    {"type": "mrkdwn", "text": f"*Duration:*\n{days} business days"},
                    {"type": "mrkdwn", "text": f"*Reason:*\n{reason or 'Not provided'}"}
                ]
            },
            {
                "type": "actions",
                "block_id": f"approval_actions_{request_id}",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "value": str(request_id),
                        "action_id": "approve_leave"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Decline"},
                        "style": "danger",
                        "value": str(request_id),
                        "action_id": "decline_leave"
                    }
                ]
            }
        ]
    )
    
    # Confirm to employee
    client.chat_postMessage(
        channel=user_id,
        text=f"✅ Your leave request has been submitted to {manager_name} for approval.\n\n*Details:*\n• Type: {leave_type_display[leave_type]}\n• Dates: {start_date} to {end_date}\n• Duration: {days} business days"
    )

@app.action("approve_leave")
def handle_approve_leave(ack, body, client):
    """Handle leave approval"""
    ack()
    
    request_id = int(body['actions'][0]['value'])
    manager_id = body['user']['id']
    manager_info = client.users_info(user=manager_id)
    manager_name = manager_info['user']['real_name']
    
    # Update database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get request details
    cursor.execute("SELECT * FROM leave_requests WHERE id = ?", (request_id,))
    request = cursor.fetchone()
    
    if not request or request[8] != 'pending':  # status column
        conn.close()
        return
    
    user_id = request[1]
    leave_type = request[3]
    days = request[6]
    start_date = request[4]
    end_date = request[5]
    
    # Update request status
    cursor.execute("""
        UPDATE leave_requests 
        SET status = 'approved', 
            responded_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), request_id))
    
    conn.commit()
    conn.close()
    
    # Deduct from leave balance
    update_leave_balance(user_id, leave_type, days, 'subtract')
    
    # Update manager's message
    client.chat_update(
        channel=body['channel']['id'],
        ts=body['message']['ts'],
        text=f"Leave request approved by {manager_name}",
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "✅ Leave Request Approved"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Approved by:* {manager_name}\n*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
            }
        ] + body['message']['blocks'][1:2]  # Keep the details section
    )
    
    # Notify employee
    client.chat_postMessage(
        channel=user_id,
        text=f"🎉 Your leave request has been approved by {manager_name}!\n\n*Dates:* {start_date} to {end_date}\n*Duration:* {days} business days\n\nEnjoy your time off!"
    )

@app.action("decline_leave")
def handle_decline_leave(ack, body, client):
    """Handle leave decline"""
    ack()
    
    request_id = int(body['actions'][0]['value'])
    manager_id = body['user']['id']
    manager_info = client.users_info(user=manager_id)
    manager_name = manager_info['user']['real_name']
    
    # Update database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get request details
    cursor.execute("SELECT * FROM leave_requests WHERE id = ?", (request_id,))
    request = cursor.fetchone()
    
    if not request or request[8] != 'pending':
        conn.close()
        return
    
    user_id = request[1]
    start_date = request[4]
    end_date = request[5]
    days = request[6]
    
    # Update request status
    cursor.execute("""
        UPDATE leave_requests 
        SET status = 'declined', 
            responded_at = ?
        WHERE id = ?
    """, (datetime.now().isoformat(), request_id))
    
    conn.commit()
    conn.close()
    
    # Update manager's message
    client.chat_update(
        channel=body['channel']['id'],
        ts=body['message']['ts'],
        text=f"Leave request declined by {manager_name}",
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "❌ Leave Request Declined"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Declined by:* {manager_name}\n*Date:* {datetime.now().strftime('%Y-%m-%d %H:%M')}"}
            }
        ] + body['message']['blocks'][1:2]
    )
    
    # Notify employee
    client.chat_postMessage(
        channel=user_id,
        text=f"Your leave request has been declined by {manager_name}.\n\n*Dates:* {start_date} to {end_date}\n*Duration:* {days} business days\n\nPlease contact your manager for more information."
    )

@app.command("/leave-balance")
def handle_balance_command(ack, command, client):
    """Show user's leave balance"""
    ack()
    
    user_id = command['user_id']
    user_info = client.users_info(user=user_id)
    user_name = user_info['user']['real_name']
    
    balance = get_leave_balance(user_id)
    
    if not balance:
        create_leave_balance(user_id, user_name)
        balance = get_leave_balance(user_id)
    
    client.chat_postMessage(
        channel=user_id,
        text="Your Leave Balance",
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "📊 Your Leave Balance"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Annual Leave:*\n{balance[2]} days"},
                    {"type": "mrkdwn", "text": f"*Sick Leave:*\n{balance[3]} days"},
                    {"type": "mrkdwn", "text": f"*Personal Leave:*\n{balance[4]} days"}
                ]
            }
        ]
    )

@app.command("/leave-report")
def handle_report_command(ack, command, client):
    """Generate leave report (for managers/admins)"""
    ack()
    
    user_id = command['user_id']
    
    # Get all leave requests
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_name, leave_type, start_date, end_date, days, status, requested_at
        FROM leave_requests
        ORDER BY requested_at DESC
        LIMIT 20
    """)
    requests = cursor.fetchall()
    conn.close()
    
    if not requests:
        client.chat_postMessage(
            channel=user_id,
            text="No leave requests found in the system."
        )
        return
    
    # Format report
    report_text = "*Recent Leave Requests:*\n\n"
    
    for req in requests:
        status_emoji = {"pending": "⏳", "approved": "✅", "declined": "❌"}
        emoji = status_emoji.get(req[6], "❓")
        
        report_text += f"{emoji} *{req[1]}* - {req[2].title()} Leave\n"
        report_text += f"   {req[3]} to {req[4]} ({req[5]} days) - Status: {req[6].title()}\n\n"
    
    client.chat_postMessage(
        channel=user_id,
        text=report_text
    )

# Flask routes
@flask_app.route("/slack/events", methods=["POST"])
def slack_events():
    """Handle Slack events"""
    return handler.handle(request)

@flask_app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy"}), 200

if __name__ == "__main__":
    try:
        port = int(os.environ.get("PORT", 3000))
        print(f"Starting app on port {port}", flush=True)
        flask_app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        print(f"ERROR: {e}", flush=True)
        import traceback
        traceback.print_exc()