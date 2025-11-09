"""
Axis – Smart Ticket Management System (Production-Ready Streamlit Application)

Features:
- Multi-user authentication with persistent per-user data
- AI-powered ticket intelligence (auto-completion, validation, prioritization)
- Full Jira integration (create, sync, export)
- Smart priority scoring system
- Ticket lifecycle management
- Activity audit log per user
- CSV bulk import/export with Jira-compatible format
- Email export functionality
- Runtime Jira, Email, and OpenRouter configuration
- Rack visualization
- OpenRouter integration with intelligent fallback
"""

import streamlit as st
import pandas as pd
import json, os, requests, uuid, time, io, smtplib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
import plotly.graph_objects as go
from pathlib import Path
from typing import List, Dict, Optional
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

load_dotenv()

# -------------------------
# Configuration
# -------------------------
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-nano-12b-v2-vl:free")
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "").strip()
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "").strip()
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "").strip()
JIRA_PROJECT_KEY = os.getenv("JIRA_PROJECT_KEY", "AXIS").strip()

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "").strip()
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "").strip()

# Demo users with role-based permissions
USERS = {
    "tech1": {
        "password": "tech123", 
        "role": "Technician", 
        "name": "Alex Rivera",
        "permissions": ["create", "view", "start", "complete", "comment"],
        "description": "Field technician - Creates tickets, works on approved tasks"
    },
    "tech2": {
        "password": "tech123", 
        "role": "Technician", 
        "name": "Jordan Chen",
        "permissions": ["create", "view", "start", "complete", "comment"],
        "description": "Field technician - Creates tickets, works on approved tasks"
    },
    "engineer1": {
        "password": "eng123", 
        "role": "Engineer", 
        "name": "Sam Taylor",
        "permissions": ["create", "view", "approve", "edit", "prioritize", "assign", "comment"],
        "description": "Data center engineer - Reviews AI suggestions, approves tickets, assigns priority"
    },
    "admin": {
        "password": "admin123", 
        "role": "Admin", 
        "name": "Admin User",
        "permissions": ["all"],
        "description": "System administrator - Full access to all features and user management"
    }
}

DATA_DIR = Path("user_data")
DATA_DIR.mkdir(exist_ok=True)

# Priority scoring weights
PRIORITY_WEIGHTS = {
    "impact_scope": {"single_server": 1, "rack": 3, "row": 5, "datacenter": 10},
    "service_impact": {"none": 0, "degraded": 2, "partial_outage": 5, "full_outage": 10},
    "urgency": {"scheduled": 1, "next_maintenance": 2, "within_24h": 5, "immediate": 10},
    "safety": {"none": 0, "minor": 3, "moderate": 7, "critical": 10}
}

# Jira priority mapping
JIRA_PRIORITY_MAP = {
    "Critical": "Highest",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low"
}

# Jira issue type mapping
JIRA_ISSUE_TYPE = "Task"  # Can be customized: Task, Bug, Story, etc.

# -------------------------
# Page Configuration
# -------------------------
st.set_page_config(layout="wide", page_title="Axis", page_icon="📋")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f8f9fa;
  --bg-tertiary: #e9ecef;
  --border-color: #dee2e6;
  --text-primary: #212529;
  --text-secondary: #6c757d;
  --text-muted: #adb5bd;
  --accent-primary: #0d6efd;
  --accent-hover: #0b5ed7;
  --success: #198754;
  --warning: #ffc107;
  --danger: #dc3545;
  --info: #0dcaf0;
  --critical: #dc3545;
  --high: #fd7e14;
  --medium: #ffc107;
  --low: #198754;
  --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
  --shadow-lg: 0 10px 15px rgba(0,0,0,0.1);
}

* {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
}

body {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.stApp {
  background: var(--bg-secondary);
}

/* Headers */
h1, h2, h3 {
  color: var(--text-primary) !important;
  font-weight: 600 !important;
  letter-spacing: -0.5px;
}

h1 {
  font-size: 2rem !important;
}

h2 {
  font-size: 1.5rem !important;
}

h3 {
  font-size: 1.25rem !important;
}

/* Cards */
.card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 16px;
  box-shadow: var(--shadow-sm);
  transition: all 0.2s ease;
}

.card:hover {
  box-shadow: var(--shadow-md);
}

/* Ticket cards */
.ticket-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: var(--shadow-sm);
}

.ticket-card:hover {
  border-color: var(--accent-primary);
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.ticket-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}

.ticket-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
  line-height: 1.5;
}

.ticket-meta {
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.ticket-meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

/* Priority badges */
.priority-badge {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.priority-critical {
  background: var(--critical);
  color: white;
}

.priority-high {
  background: var(--high);
  color: white;
}

.priority-medium {
  background: var(--medium);
  color: var(--text-primary);
}

.priority-low {
  background: var(--low);
  color: white;
}

/* Status badges */
.status-badge {
  display: inline-block;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.status-draft { 
  background: var(--bg-tertiary); 
  color: var(--text-secondary); 
}

.status-ai-review { 
  background: #e0cffc; 
  color: #6f42c1; 
}

.status-approved { 
  background: #d1e7dd; 
  color: var(--success); 
}

.status-in-progress { 
  background: #cfe2ff; 
  color: var(--accent-primary); 
}

.status-completed { 
  background: #d1e7dd; 
  color: var(--success); 
}

.status-blocked { 
  background: #f8d7da; 
  color: var(--danger); 
}

/* Jira badge */
.jira-badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  background: #0052cc;
  color: white;
  gap: 4px;
}

/* Buttons */
.stButton>button {
  background: var(--accent-primary);
  color: white;
  border: none;
  border-radius: 6px;
  padding: 10px 20px;
  font-weight: 500;
  transition: all 0.2s;
  box-shadow: var(--shadow-sm);
}

.stButton>button:hover {
  background: var(--accent-hover);
  box-shadow: var(--shadow-md);
}

.stButton>button[kind="secondary"] {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.stButton>button[kind="secondary"]:hover {
  background: var(--border-color);
}

/* Score display */
.score-display {
  background: var(--bg-secondary);
  border: 2px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  margin: 16px 0;
}

.score-number {
  font-size: 48px;
  font-weight: 700;
  color: var(--accent-primary);
  margin-bottom: 8px;
}

.score-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
  font-weight: 600;
}

/* AI insights */
.ai-insight {
  background: #f8f9ff;
  border-left: 4px solid var(--accent-primary);
  border-radius: 6px;
  padding: 16px;
  margin: 16px 0;
}

.ai-insight-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 600;
  color: var(--accent-primary);
  font-size: 14px;
}

/* Activity log */
.log-container {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  font-family: 'SF Mono', 'Monaco', 'Courier New', monospace;
  font-size: 13px;
}

.log-line {
  padding: 8px 0;
  border-bottom: 1px solid var(--bg-secondary);
  color: var(--text-secondary);
}

.log-line:last-child {
  border-bottom: none;
}

.log-timestamp {
  color: var(--accent-primary);
  margin-right: 12px;
  font-weight: 500;
}

/* Metrics */
.metric-card {
  background: var(--bg-primary);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: 20px;
  text-align: center;
  box-shadow: var(--shadow-sm);
}

.metric-value {
  font-size: 36px;
  font-weight: 700;
  color: var(--accent-primary);
  margin-bottom: 8px;
}

.metric-label {
  font-size: 13px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  font-weight: 500;
}

/* Info boxes */
.info-box {
  background: var(--bg-secondary);
  border-radius: 6px;
  padding: 16px;
  margin: 12px 0;
  font-size: 14px;
  color: var(--text-secondary);
}

.info-box-success {
  background: #d1e7dd;
  color: var(--success);
  border-left: 4px solid var(--success);
}

.info-box-warning {
  background: #fff3cd;
  color: #997404;
  border-left: 4px solid var(--warning);
}

.info-box-error {
  background: #f8d7da;
  color: var(--danger);
  border-left: 4px solid var(--danger);
}

/* Scrollbar styling */
::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: var(--bg-secondary);
}

::-webkit-scrollbar-thumb {
  background: var(--border-color);
  border-radius: 5px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--text-muted);
}

/* Input fields */
.stTextInput>div>div>input,
.stTextArea>div>div>textarea,
.stSelectbox>div>div>select {
  background: var(--bg-primary) !important;
  border: 1px solid var(--border-color) !important;
  color: var(--text-primary) !important;
  border-radius: 6px !important;
}

.stTextInput>div>div>input:focus,
.stTextArea>div>div>textarea:focus,
.stSelectbox>div>div>select:focus {
  border-color: var(--accent-primary) !important;
  box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.1) !important;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  gap: 8px;
  background: var(--bg-primary);
  padding: 8px;
  border-radius: 8px;
  border: 1px solid var(--border-color);
}

.stTabs [data-baseweb="tab"] {
  border-radius: 6px;
  padding: 12px 24px;
  font-weight: 500;
}

/* Header section */
.header-section {
  background: var(--bg-primary);
  padding: 20px 24px;
  border-radius: 8px;
  margin-bottom: 24px;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
}

.brand-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
  letter-spacing: -0.5px;
  line-height: 1.2;
}

.brand-subtitle {
  color: var(--text-secondary);
  font-size: 13px;
  margin-top: 2px;
  line-height: 1.4;
}

/* Status indicator */
.status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  background: var(--bg-secondary);
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot-active {
  background: var(--success);
}

.status-dot-inactive {
  background: var(--text-muted);
}

/* Hide Streamlit branding and reduce top padding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.main .block-container {
  padding-top: 1rem;
  padding-bottom: 2rem;
  max-width: 100%;
}

/* Reduce excessive spacing */
.element-container {
  margin-bottom: 0.25rem;
}

/* Fix the empty expander/container on login page */
[data-testid="stVerticalBlock"] > [data-testid="element-container"]:first-child {
  min-height: 0 !important;
  height: 0 !important;
  overflow: hidden;
}

[data-testid="stVerticalBlock"] > [data-testid="element-container"]:first-child > div {
  display: none !important;
}
</style>
"""

st.markdown(CSS, unsafe_allow_html=True)

# -------------------------
# Helper Functions
# -------------------------
def get_openrouter_config():
    """Get OpenRouter configuration from session state or env."""
    api_key = st.session_state.get('openrouter_api_key', OPENROUTER_KEY).strip()
    model = st.session_state.get('openrouter_model', OPENROUTER_MODEL).strip()
    use_mock = not bool(api_key)
    return api_key, model, use_mock

def get_jira_config():
    """Get Jira configuration status."""
    jira_base = st.session_state.get('jira_base_url', JIRA_BASE_URL).strip()
    jira_email = st.session_state.get('jira_email', JIRA_EMAIL).strip()
    jira_token = st.session_state.get('jira_api_token', JIRA_API_TOKEN).strip()
    jira_project = st.session_state.get('jira_project_key', JIRA_PROJECT_KEY).strip()
    
    is_configured = bool(jira_base and jira_email and jira_token)
    return jira_base, jira_email, jira_token, jira_project, is_configured

def get_email_config():
    """Get email configuration status."""
    smtp_server = st.session_state.get('smtp_server', SMTP_SERVER)
    smtp_port = st.session_state.get('smtp_port', SMTP_PORT)
    email_addr = st.session_state.get('email_address', EMAIL_ADDRESS).strip()
    email_pass = st.session_state.get('email_password', EMAIL_PASSWORD).strip()
    
    is_configured = bool(email_addr and email_pass)
    return smtp_server, smtp_port, email_addr, email_pass, is_configured

# -------------------------
# Email Functions
# -------------------------
def send_email_with_attachment(recipient_email: str, subject: str, body: str, 
                                attachment_buffer: io.BytesIO = None, 
                                attachment_filename: str = None) -> bool:
    """Send email with optional attachment."""
    smtp_server, smtp_port, sender_email, sender_password, is_configured = get_email_config()
    
    if not is_configured:
        st.error("Email credentials not configured. Please configure in Settings.")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(body, 'plain'))
        
        # Attach file if provided
        if attachment_buffer and attachment_filename:
            attachment_buffer.seek(0)
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment_buffer.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename={attachment_filename}')
            msg.attach(part)
        
        # Send email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        return True
    except Exception as e:
        st.error(f"Failed to send email: {e}")
        return False

def send_jira_ticket_email(ticket: Dict, recipient_email: str) -> bool:
    """Send email with Jira ticket summary and link."""
    jira_base, _, _, _, is_configured = get_jira_config()
    
    if not is_configured:
        st.warning("Jira not configured. Cannot send Jira ticket email.")
        return False
    
    jira_key = ticket.get('jira_key')
    if not jira_key:
        st.warning("Ticket not synced to Jira yet.")
        return False
    
    jira_url = f"{jira_base}/browse/{jira_key}"
    
    subject = f"Jira Ticket: {jira_key} - {ticket.get('summary', 'Ticket')}"
    
    body = f"""
Hello,

A new Jira ticket has been created:

Ticket: {jira_key}
Summary: {ticket.get('summary', 'N/A')}
Priority: {ticket.get('calculated_priority', ticket.get('priority', 'Medium'))}
Priority Score: {ticket.get('priority_score', 0):.1f}/10
Status: {ticket.get('status', 'N/A')}

Server: {ticket.get('server', 'N/A')}
Rack: {ticket.get('rack', 'N/A')}

Description:
{ticket.get('description', 'No description provided')}

AI Analysis:
{ticket.get('priority_analysis', {}).get('reasoning', 'N/A')}

View in Jira: {jira_url}

Created by: {ticket.get('created_by', 'Unknown')}
Created at: {ticket.get('created_at', 'Unknown')}

---
This email was sent by Axis Ticket Management System
"""
    
    return send_email_with_attachment(recipient_email, subject, body)

# -------------------------
# Jira Integration Functions
# -------------------------
def get_jira_auth():
    """Get Jira authentication headers."""
    _, jira_email, jira_token, _, is_configured = get_jira_config()
    
    if not is_configured:
        return None
    
    auth_string = f"{jira_email}:{jira_token}"
    auth_bytes = auth_string.encode('ascii')
    auth_base64 = base64.b64encode(auth_bytes).decode('ascii')
    
    return {
        "Authorization": f"Basic {auth_base64}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

def create_jira_issue(ticket: Dict) -> Optional[str]:
    """Create a Jira issue from a ticket."""
    jira_base, _, _, jira_project, is_configured = get_jira_config()
    
    if not is_configured:
        return None
    
    try:
        headers = get_jira_auth()
        if not headers:
            return None
        
        # Map priority
        jira_priority = JIRA_PRIORITY_MAP.get(
            ticket.get("calculated_priority", ticket.get("priority", "Medium")),
            "Medium"
        )
        
        # Safely get values with defaults
        ticket_id = ticket.get('id', 'unknown')
        server = ticket.get('server', 'N/A')
        rack = ticket.get('rack', 'N/A')
        priority_score = ticket.get('priority_score', 0)
        if isinstance(priority_score, dict):
            priority_score = 0
        description_text = ticket.get('description', '')
        reasoning = ticket.get('priority_analysis', {}).get('reasoning', 'N/A')
        created_by = ticket.get('created_by', 'System')
        created_at = ticket.get('created_at', '')
        
        # Prepare description
        description = f"""*Ticket ID:* {ticket_id}

*Server:* {server}
*Rack:* {rack}
*Priority Score:* {float(priority_score):.1f}/10

*Description:*
{description_text}

*AI Analysis:*
{reasoning}

*Created by:* {created_by}
*Created at:* {created_at}
"""
        
        # Prepare Jira payload
        payload = {
            "fields": {
                "project": {
                    "key": jira_project
                },
                "summary": ticket.get('summary', 'Untitled Ticket'),
                "description": description,
                "issuetype": {
                    "name": JIRA_ISSUE_TYPE
                },
                "priority": {
                    "name": jira_priority
                }
            }
        }
        
        # Add labels if available
        labels = [f"axis-{ticket['id']}", "data-center"]
        if ticket.get('server'):
            labels.append(f"server-{ticket['server']}")
        if ticket.get('rack'):
            labels.append(f"rack-{ticket['rack']}")
        
        payload["fields"]["labels"] = labels
        
        # Create issue
        url = f"{jira_base}/rest/api/3/issue"
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        
        jira_data = response.json()
        jira_key = jira_data.get("key")
        
        return jira_key
        
    except Exception as e:
        st.error(f"Jira API Error: {e}")
        return None

def sync_ticket_to_jira(ticket: Dict, username: str) -> bool:
    """Sync a ticket to Jira."""
    _, _, _, _, is_configured = get_jira_config()
    
    if not is_configured:
        st.warning("Jira integration is not configured. Please configure in Settings.")
        return False
    
    with st.spinner("Syncing to Jira..."):
        jira_key = create_jira_issue(ticket)
        
        if jira_key:
            ticket["jira_key"] = jira_key
            ticket["jira_synced_at"] = datetime.now(timezone.utc).isoformat()
            save_user_tickets(username, st.session_state.tickets)
            append_audit_log(username, f"Synced ticket {ticket['id']} to Jira as {jira_key}")
            return True
    
    return False

def export_to_jira_csv(tickets: List[Dict]) -> io.BytesIO:
    """Export tickets in Jira-compatible CSV format."""
    if not tickets:
        return io.BytesIO(b"")
    
    # Jira CSV format
    jira_data = []
    for t in tickets:
        jira_priority = JIRA_PRIORITY_MAP.get(
            t.get("calculated_priority", t.get("priority", "Medium")),
            "Medium"
        )
        
        description = f"""Server: {t.get('server', 'N/A')}
Rack: {t.get('rack', 'N/A')}
Priority Score: {t.get('priority_score', 0):.1f}/10

{t.get('description', '')}

AI Analysis:
{t.get('priority_analysis', {}).get('reasoning', 'N/A')}"""
        
        jira_data.append({
            "Summary": t.get('summary', 'Untitled'),
            "Issue Type": JIRA_ISSUE_TYPE,
            "Priority": jira_priority,
            "Status": t.get('status', 'Draft'),
            "Description": description,
            "Labels": f"axis-{t['id']},data-center,server-{t.get('server', '')},rack-{t.get('rack', '')}",
            "Reporter": t.get('created_by', ''),
            "Created": t.get('created_at', ''),
            "Custom Field (Axis ID)": t['id'],
            "Custom Field (Server)": t.get('server', ''),
            "Custom Field (Rack)": t.get('rack', ''),
            "Custom Field (Priority Score)": t.get('priority_score', 0)
        })
    
    df = pd.DataFrame(jira_data)
    
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return buffer

# -------------------------
# Data Persistence Functions
# -------------------------
def get_user_file(username: str, file_type: str = "tickets") -> Path:
    """Get path to user-specific data file."""
    return DATA_DIR / f"{file_type}_{username}.json"

def load_user_tickets(username: str) -> List[Dict]:
    """Load tickets for a specific user."""
    file_path = get_user_file(username, "tickets")
    if file_path.exists():
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            st.error(f"Error loading tickets: {e}")
            return []
    return []

def save_user_tickets(username: str, tickets: List[Dict]):
    """Save tickets for a specific user."""
    file_path = get_user_file(username, "tickets")
    file_path.write_text(json.dumps(tickets, indent=2, ensure_ascii=False), encoding="utf-8")

def append_audit_log(username: str, action: str, details: str = ""):
    """Append to user's audit log."""
    log_file = get_user_file(username, "audit_log")
    timestamp = datetime.now(timezone.utc).isoformat()
    log_entry = f"[{timestamp}] {action}"
    if details:
        log_entry += f" | {details}"
    log_entry += "\n"
    
    existing = ""
    if log_file.exists():
        existing = log_file.read_text(encoding="utf-8")
    
    log_file.write_text(existing + log_entry, encoding="utf-8")

def get_audit_log(username: str, limit: int = 100) -> List[str]:
    """Get recent audit log entries - always fresh from disk."""
    log_file = get_user_file(username, "audit_log")
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().split("\n")
        return lines[-limit:]
    return []

# -------------------------
# AI Functions
# -------------------------
def call_ai(system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
    """Call OpenRouter API or return mock response."""
    api_key, model, use_mock = get_openrouter_config()
    
    if use_mock:
        # Intelligent mock based on prompt content
        if "calculate priority score" in user_prompt.lower():
            return json.dumps({
                "calculated_priority": "High",
                "priority_score": 8.5,
                "reasoning": "Multiple servers affected with potential safety concerns. Impact scope is significant.",
                "factors": {
                    "impact_scope": "rack",
                    "service_impact": "partial_outage",
                    "urgency": "within_24h",
                    "safety": "moderate"
                },
                "recommended_actions": [
                    "Immediate assessment of affected rack",
                    "Check power distribution and cooling",
                    "Verify network connectivity",
                    "Schedule maintenance window if needed"
                ]
            })
        elif "validate" in user_prompt.lower() or "complete" in user_prompt.lower():
            return json.dumps({
                "is_complete": False,
                "completeness_score": 0.65,
                "missing_fields": ["root_cause_analysis", "estimated_time", "required_parts"],
                "suggestions": {
                    "summary": "Add specific server IDs and error codes",
                    "description": "Include recent logs, error patterns, and troubleshooting steps already attempted",
                    "priority": "Consider impact on critical services"
                },
                "auto_enhanced": {
                    "summary": "GPU Server Cluster Offline - Rack 3B-04 - Thermal Event",
                    "description": "Multiple GPU servers in rack 3B-04 have gone offline. Initial assessment suggests cooling system failure. Requires immediate investigation to prevent hardware damage. Affected: srv-gpu-301 through srv-gpu-308.",
                    "estimated_duration": "2-4 hours",
                    "required_skills": ["thermal management", "GPU hardware", "HVAC systems"]
                }
            })
        else:
            return json.dumps({
                "summary": "Server hardware issue requiring attention",
                "priority": "Medium",
                "description": "Issue detected requiring technical investigation and resolution.",
                "steps": [
                    "Verify server status in monitoring system",
                    "Check physical connections and indicators",
                    "Review system logs for errors",
                    "Test hardware components",
                    "Document findings and resolution"
                ],
                "confidence": 0.75
            })
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature
    }
    
    try:
        response = requests.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            content = "\n".join([item.get("text", "") for item in content if item.get("type") == "text"])
        
        return content or "{}"
    except Exception as e:
        st.error(f"AI API Error: {e}")
        return "{}"

def calculate_priority_score(ticket: Dict) -> Dict:
    """Calculate intelligent priority score based on ticket content."""
    system_prompt = """You are an expert data center operations AI. Analyze tickets and calculate objective priority scores.
    
Consider:
1. Impact Scope: How many systems/services affected?
2. Service Impact: Is service degraded or completely down?
3. Urgency: Is this causing active issues or preventive?
4. Safety: Any safety concerns for personnel or equipment?

Return JSON with: calculated_priority, priority_score (0-10), reasoning, factors, recommended_actions"""

    user_prompt = f"""Analyze this ticket and calculate objective priority:

Summary: {ticket.get('summary', '')}
Description: {ticket.get('description', '')}
User Priority: {ticket.get('user_priority', 'Not specified')}
Location: {ticket.get('rack', '')} / {ticket.get('server', '')}

Calculate the actual priority score based on objective factors."""

    response = call_ai(system_prompt, user_prompt)
    
    try:
        if "{" in response:
            json_str = response[response.find("{"):response.rfind("}")+1]
            return json.loads(json_str)
    except Exception:
        pass
    
    return {
        "calculated_priority": ticket.get("user_priority", "Medium"),
        "priority_score": 5.0,
        "reasoning": "Unable to calculate detailed score",
        "factors": {},
        "recommended_actions": []
    }

def validate_and_enhance_ticket(ticket: Dict) -> Dict:
    """Use AI to validate ticket completeness and suggest enhancements."""
    system_prompt = """You are an expert data center ticket quality analyst. Evaluate tickets for completeness and suggest enhancements.

Check for:
- Clear, specific problem description
- Actionable information
- Relevant technical details
- Proper categorization

Return JSON with: is_complete, completeness_score, missing_fields, suggestions, auto_enhanced"""

    user_prompt = f"""Validate and enhance this ticket:

Summary: {ticket.get('summary', '')}
Description: {ticket.get('description', '')}
Server: {ticket.get('server', '')}
Rack: {ticket.get('rack', '')}
Priority: {ticket.get('priority', '')}

Provide specific suggestions for improvement."""

    response = call_ai(system_prompt, user_prompt)
    
    try:
        if "{" in response:
            json_str = response[response.find("{"):response.rfind("}")+1]
            return json.loads(json_str)
    except Exception:
        pass
    
    return {
        "is_complete": True,
        "completeness_score": 0.7,
        "missing_fields": [],
        "suggestions": {},
        "auto_enhanced": {}
    }

# -------------------------
# Authentication
# -------------------------
def login_page():
    """Display login page."""
    st.markdown("""
    <style>
    .main > div {
        display: flex;
        justify-content: center;
        align-items: center;
        min-height: 80vh;
    }
    .login-card {
        background: var(--bg-primary);
        border: 2px solid var(--border-color);
        border-radius: 12px;
        padding: 32px;
        box-shadow: var(--shadow-lg);
    }
    .login-title {
        font-size: 48px;
        font-weight: 700;
        color: var(--text-primary);
        text-align: center;
        margin-bottom: 8px;
        letter-spacing: -1px;
        display: block;
        width: 100%;
    }
    .login-subtitle {
        color: var(--text-secondary);
        font-size: 16px;
        text-align: center;
        margin-bottom: 40px;
        display: block;
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1.5, 1])
    
    with col2:
        st.markdown("<div style='width: 100%; text-align: center;'>", unsafe_allow_html=True)
        st.markdown("<h1 class='login-title'>Axis</h1>", unsafe_allow_html=True)
        st.markdown("<p class='login-subtitle'>AI-Powered Data Center Operations Platform</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div class='login-card'>", unsafe_allow_html=True)
        st.markdown("### Sign In")
        
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Sign In", key="login_btn"):
            if username in USERS and USERS[username]["password"] == password:
                st.session_state.logged_in = True
                st.session_state.username = username
                st.session_state.user_info = USERS[username]
                st.rerun()
            else:
                st.error("Invalid credentials")
        
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='margin-top: 24px; padding: 20px; background: var(--bg-primary); border: 1px solid var(--border-color); border-radius: 8px; box-shadow: var(--shadow-sm);'>", unsafe_allow_html=True)
        st.markdown("**Demo Accounts:**")
        for user_key, user_data in USERS.items():
            st.markdown(f"- `{user_key}` / `{user_data['password']}` ({user_data['role']})")
        st.markdown("</div>", unsafe_allow_html=True)

def logout():
    """Handle logout."""
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.user_info = None
    st.rerun()

# -------------------------
# Ticket Management Functions
# -------------------------
def create_ticket(username: str, ticket_data: Dict) -> Dict:
    """Create a new ticket."""
    ticket = {
        "id": str(uuid.uuid4())[:8],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": username,
        "status": "Draft",
        "user_priority": ticket_data.get("priority", "Medium"),
        **ticket_data
    }
    
    # AI validation and enhancement
    validation = validate_and_enhance_ticket(ticket)
    ticket["validation"] = validation
    
    # Calculate objective priority
    priority_analysis = calculate_priority_score(ticket)
    ticket["priority_analysis"] = priority_analysis
    ticket["calculated_priority"] = priority_analysis.get("calculated_priority", ticket["user_priority"])
    ticket["priority_score"] = priority_analysis.get("priority_score", 5.0)
    
    # If AI suggests different priority, mark for review
    if ticket["calculated_priority"] != ticket["user_priority"]:
        ticket["status"] = "AI Review"
        ticket["needs_priority_review"] = True
    
    return ticket

def export_ticket_summary(tickets: List[Dict], username: str) -> io.BytesIO:
    """Export ticket summary to CSV."""
    if not tickets:
        return io.BytesIO(b"")
    
    df_data = []
    for t in tickets:
        df_data.append({
            "Ticket ID": t["id"],
            "Jira Key": t.get("jira_key", ""),
            "Status": t["status"],
            "Priority": t.get("calculated_priority", t.get("priority", "Medium")),
            "Priority Score": t.get("priority_score", 0),
            "Summary": t["summary"],
            "Server": t.get("server", ""),
            "Rack": t.get("rack", ""),
            "Created": t["created_at"],
            "Created By": t["created_by"],
            "Completeness": f"{t.get('validation', {}).get('completeness_score', 0):.0%}"
        })
    
    df = pd.DataFrame(df_data)
    
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return buffer

def show_ticket_detail(ticket: Dict, username: str, context: str = ""):
    """Show detailed ticket information in an expandable view."""
    # Use context to make keys unique across different sections
    unique_key = f"detail_{context}_{ticket['id']}_{id(ticket)}"
    
    with st.expander(f"📋 Ticket Details: {ticket['id']}", expanded=True):
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown(f"**Summary:** {ticket['summary']}")
            st.markdown(f"**Server:** {ticket.get('server', 'N/A')}")
            st.markdown(f"**Rack:** {ticket.get('rack', 'N/A')}")
            st.markdown(f"**Status:** {ticket['status']}")
            st.markdown(f"**Created:** {ticket['created_at']}")
            st.markdown(f"**Created by:** {ticket['created_by']}")
            
            if ticket.get("jira_key"):
                jira_base, _, _, _, _ = get_jira_config()
                jira_url = f"{jira_base}/browse/{ticket['jira_key']}" if jira_base else "#"
                st.markdown(f"**Jira Issue:** [{ticket['jira_key']}]({jira_url})")
            
            st.markdown("**Description:**")
            st.text_area("", value=ticket.get('description', ''), height=150, key=f"desc_{unique_key}", disabled=True)
        
        with col2:
            # Priority analysis
            st.markdown("#### Priority Analysis")
            st.markdown(f"**User Priority:** {ticket.get('user_priority', 'N/A')}")
            st.markdown(f"**AI Priority:** {ticket.get('calculated_priority', 'N/A')}")
            
            score = ticket.get("priority_score", 0)
            if isinstance(score, dict):
                score = 0
            st.markdown("<div class='score-display'>", unsafe_allow_html=True)
            st.markdown(f"<div class='score-number'>{float(score):.1f}</div>", unsafe_allow_html=True)
            st.markdown("<div class='score-label'>Priority Score</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
            
            # Completeness
            validation = ticket.get("validation", {})
            completeness = validation.get("completeness_score", 0)
            if isinstance(completeness, dict):
                completeness = 0.7
            completeness = max(0.0, min(1.0, float(completeness)))
            
            st.markdown("#### Completeness")
            st.progress(completeness)
            st.markdown(f"{completeness:.0%}")
        
        # AI reasoning
        reasoning = ticket.get("priority_analysis", {}).get("reasoning", "")
        if reasoning:
            st.markdown("<div class='ai-insight'>", unsafe_allow_html=True)
            st.markdown("<div class='ai-insight-header'>AI Reasoning</div>", unsafe_allow_html=True)
            st.markdown(reasoning)
            st.markdown("</div>", unsafe_allow_html=True)
        
        # Recommended actions
        actions = ticket.get("priority_analysis", {}).get("recommended_actions", [])
        if actions:
            st.markdown("#### Recommended Actions")
            for i, action in enumerate(actions, 1):
                st.markdown(f"{i}. {action}")

def display_ticket_card(ticket: Dict, username: str, compact: bool = False, context: str = "main"):
    """Display a ticket card with actions."""
    ticket_id = ticket["id"]
    priority = ticket.get("calculated_priority", ticket.get("priority", "Medium"))
    
    if not isinstance(priority, str):
        priority = "Medium"
    
    priority_class = f"priority-{priority.lower()}"
    status = ticket["status"]
    
    if not isinstance(status, str):
        status = "Draft"
    
    status_class = f"status-{status.lower().replace(' ', '-')}"
    jira_key = ticket.get("jira_key", "")
    
    # Build ticket card HTML without closing divs at the end
    ticket_html = f"""
    <div class='ticket-card' id='ticket-{context}-{ticket_id}'>
        <div class='ticket-header'>
            <div style='flex: 1;'>
                <div class='ticket-title'>{ticket['summary']}</div>
                <div class='ticket-meta'>
                    <span class='ticket-meta-item'>Server: {ticket.get('server', 'N/A')}</span>
                    <span class='ticket-meta-item'>Rack: {ticket.get('rack', 'N/A')}</span>
                    <span class='ticket-meta-item'>Created by: {ticket['created_by']}</span>
                </div>
            </div>
            <div style='text-align: right; min-width: 120px;'>
                <div class='{priority_class} priority-badge'>{priority}</div>
                <div style='height: 8px;'></div>
                <div class='{status_class} status-badge'>{status}</div>
    """
    
    # Add Jira badge if exists
    if jira_key:
        ticket_html += f"""
                <div style='height: 8px;'></div>
                <div class='jira-badge'>JIRA: {jira_key}</div>
    """
    
    # Close the divs properly
    ticket_html += """
            </div>
        </div>
    </div>
    """
    
    st.markdown(ticket_html, unsafe_allow_html=True)
    
    if not compact:
        score = ticket.get("priority_score", 0)
        if isinstance(score, dict):
            score = 0
        
        st.markdown(f"<div style='margin: 12px 0; color: var(--text-secondary);'><strong>Priority Score:</strong> {float(score):.1f}/10</div>", unsafe_allow_html=True)
        
        reasoning = ticket.get("priority_analysis", {}).get("reasoning", "")
        if reasoning and len(reasoning) > 0:
            reasoning_preview = reasoning[:120] + "..." if len(reasoning) > 120 else reasoning
            st.markdown(f"<div style='margin: 8px 0; padding: 12px; background: #f8f9ff; border-left: 3px solid var(--accent-primary); border-radius: 4px; font-size: 13px;'><strong>AI Analysis:</strong> {reasoning_preview}</div>", unsafe_allow_html=True)
        
        desc = ticket.get("description", "")
        if len(desc) > 150:
            desc = desc[:150] + "..."
        st.markdown(f"<div style='color: var(--text-secondary); font-size: 14px; margin: 8px 0; line-height: 1.5;'>{desc}</div>", unsafe_allow_html=True)
        
        if ticket.get("needs_priority_review"):
            st.markdown("<div class='info-box info-box-warning'>Priority mismatch: User selected <strong>{}</strong>, AI calculated <strong>{}</strong></div>".format(
                ticket.get("user_priority", "Unknown"),
                ticket.get("calculated_priority", "Unknown")
            ), unsafe_allow_html=True)
        
        validation = ticket.get("validation", {})
        completeness = validation.get("completeness_score", 1.0)
        if completeness < 0.8:
            st.markdown(f"<div class='info-box info-box-warning'>Completeness: {completeness:.0%} - Consider adding more details</div>", unsafe_allow_html=True)
    
    # Action buttons
    if not compact:
        cols = st.columns(6)
        
        # Create unique button keys using context
        with cols[0]:
            if st.button("Details", key=f"view_{context}_{ticket_id}"):
                detail_key = f"show_detail_{context}_{ticket_id}"
                if st.session_state.get(detail_key, False):
                    st.session_state[detail_key] = False
                else:
                    st.session_state[detail_key] = True
                st.rerun()
        
        with cols[1]:
            _, _, _, _, jira_configured = get_jira_config()
            if not jira_key and jira_configured:
                if st.button("Sync Jira", key=f"jira_{context}_{ticket_id}"):
                    if sync_ticket_to_jira(ticket, username):
                        st.success(f"Synced as {ticket['jira_key']}")
                        st.rerun()
        
        with cols[2]:
            if status in ["Draft", "AI Review"]:
                if st.button("Approve", key=f"approve_{context}_{ticket_id}"):
                    ticket["status"] = "Approved"
                    ticket["needs_priority_review"] = False
                    save_user_tickets(username, st.session_state.tickets)
                    append_audit_log(username, f"Approved ticket {ticket_id}")
                    st.rerun()
        
        with cols[3]:
            if status == "Approved":
                if st.button("Start", key=f"start_{context}_{ticket_id}"):
                    ticket["status"] = "In Progress"
                    ticket["started_at"] = datetime.now(timezone.utc).isoformat()
                    save_user_tickets(username, st.session_state.tickets)
                    append_audit_log(username, f"Started work on ticket {ticket_id}")
                    st.rerun()
        
        with cols[4]:
            if status == "In Progress":
                if st.button("Complete", key=f"complete_{context}_{ticket_id}"):
                    ticket["status"] = "Completed"
                    ticket["completed_at"] = datetime.now(timezone.utc).isoformat()
                    save_user_tickets(username, st.session_state.tickets)
                    append_audit_log(username, f"Completed ticket {ticket_id}")
                    st.rerun()
        
        with cols[5]:
            if st.button("Delete", key=f"delete_{context}_{ticket_id}"):
                st.session_state.tickets = [t for t in st.session_state.tickets if t["id"] != ticket_id]
                save_user_tickets(username, st.session_state.tickets)
                append_audit_log(username, f"Deleted ticket {ticket_id}")
                st.rerun()
    
    st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
    
    # Show details if toggled - use context-specific key
    detail_key = f"show_detail_{context}_{ticket_id}"
    if st.session_state.get(detail_key, False):
        show_ticket_detail(ticket, username, context)

# -------------------------
# Main Application
# -------------------------
def main():
    # Check authentication
    if not st.session_state.get("logged_in", False):
        login_page()
        return
    
    username = st.session_state.username
    user_info = st.session_state.user_info
    
    # Load user data
    if "tickets" not in st.session_state:
        st.session_state.tickets = load_user_tickets(username)
    
    # Get configuration statuses
    _, _, _, jira_project, jira_configured = get_jira_config()
    _, _, _, _, email_configured = get_email_config()
    _, model, use_mock = get_openrouter_config()
    
    # Header
    st.markdown("<div class='header-section'>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        st.markdown(f"<h1 class='brand-title' style='margin: 0;'>Axis</h1>", unsafe_allow_html=True)
        st.markdown(f"<p class='brand-subtitle'>Welcome back, {user_info['name']} • {user_info['role']}</p>", unsafe_allow_html=True)
    
    with col2:
        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
        
        if jira_configured:
            jira_display = f"Connected to {jira_project}"
            jira_dot_class = "status-dot-active"
        else:
            jira_display = "Not Configured"
            jira_dot_class = "status-dot-inactive"
        
        st.markdown(f"""
        <div class='status-indicator' style='justify-content: center;'>
            <span class='status-dot {jira_dot_class}'></span>
            <span style='font-weight: 500;'>Jira: {jira_display}</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    
    with col3:
        st.markdown("<div style='text-align: right;'>", unsafe_allow_html=True)
        if st.button("Logout", key="logout_btn"):
            logout()
        st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Main tabs
    tabs = st.tabs(["Dashboard", "Tickets", "Create Ticket", "Import CSV", "Activity Log", "Settings"])
    
    # ===== DASHBOARD TAB =====
    with tabs[0]:
        tickets = st.session_state.tickets
        
        if not jira_configured:
            st.markdown("""
            <div class='info-box info-box-warning'>
                <strong>Jira Integration Not Configured</strong><br>
                To enable Jira syncing, configure your credentials in the <strong>Settings</strong> tab.
            </div>
            """, unsafe_allow_html=True)
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-value'>{len(tickets)}</div>", unsafe_allow_html=True)
            st.markdown("<div class='metric-label'>Total Tickets</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col2:
            active = len([t for t in tickets if t["status"] in ["Approved", "In Progress"]])
            st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-value'>{active}</div>", unsafe_allow_html=True)
            st.markdown("<div class='metric-label'>Active</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col3:
            completed = len([t for t in tickets if t["status"] == "Completed"])
            st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-value'>{completed}</div>", unsafe_allow_html=True)
            st.markdown("<div class='metric-label'>Completed</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col4:
            synced = len([t for t in tickets if t.get("jira_key")])
            st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
            st.markdown(f"<div class='metric-value'>{synced}</div>", unsafe_allow_html=True)
            st.markdown("<div class='metric-label'>Synced to Jira</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        
        # Priority distribution
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.markdown("### Priority Distribution")
            if tickets:
                priority_counts = {}
                for t in tickets:
                    p = t.get("calculated_priority", t.get("priority", "Medium"))
                    priority_counts[p] = priority_counts.get(p, 0) + 1
                
                fig = go.Figure(data=[
                    go.Bar(
                        x=list(priority_counts.keys()),
                        y=list(priority_counts.values()),
                        marker_color=['#dc3545', '#fd7e14', '#ffc107', '#198754'],
                        text=list(priority_counts.values()),
                        textposition='auto',
                    )
                ])
                fig.update_layout(
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#212529'),
                    height=300,
                    xaxis_title="Priority Level",
                    yaxis_title="Number of Tickets",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No tickets to display")
        
        with col2:
            st.markdown("### Quick Actions")
            
            if st.button("Export All Tickets", key="export_all_btn", use_container_width=True):
                if tickets:
                    csv_buffer = export_ticket_summary(tickets, username)
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.download_button(
                            "📥 Download CSV",
                            csv_buffer,
                            file_name=f"axis_tickets_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_std_csv",
                            use_container_width=True
                        )
                    
                    with col_b:
                        with st.expander("📧 Email CSV"):
                            recipient = st.text_input("Recipient Email", key="email_recipient_export")
                            if st.button("Send Email", key="send_email_export"):
                                if recipient:
                                    csv_buffer_copy = export_ticket_summary(tickets, username)
                                    if send_email_with_attachment(
                                        recipient,
                                        f"Axis Ticket Export - {len(tickets)} tickets",
                                        f"Hello,\n\nPlease find attached the Axis ticket export.\n\nExport generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nBest regards,\nAxis Ticket Management System",
                                        csv_buffer_copy,
                                        f"axis_tickets_{username}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                    ):
                                        st.success(f"✅ Sent to {recipient}")
                                else:
                                    st.warning("Please enter an email address")
                else:
                    st.warning("No tickets to export")
            
            if st.button("Export Jira CSV", key="export_jira_btn", use_container_width=True):
                if tickets:
                    jira_buffer = export_to_jira_csv(tickets)
                    
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.download_button(
                            "📥 Download Jira CSV",
                            jira_buffer,
                            file_name=f"jira_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            key="download_jira_csv",
                            use_container_width=True
                        )
                    
                    with col_b:
                        with st.expander("📧 Email Jira CSV"):
                            recipient = st.text_input("Recipient Email", key="email_recipient_jira")
                            if st.button("Send Email", key="send_email_jira"):
                                if recipient:
                                    jira_buffer_copy = export_to_jira_csv(tickets)
                                    if send_email_with_attachment(
                                        recipient,
                                        f"Jira Import CSV - {len(tickets)} tickets",
                                        f"Hello,\n\nPlease find attached the Jira-compatible CSV import file.\n\nExport generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\nBest regards,\nAxis Ticket Management System",
                                        jira_buffer_copy,
                                        f"jira_import_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                                    ):
                                        st.success(f"✅ Sent to {recipient}")
                                else:
                                    st.warning("Please enter an email address")
                else:
                    st.warning("No tickets to export")
            
            if st.button("Refresh Data", key="refresh_btn", use_container_width=True):
                st.session_state.tickets = load_user_tickets(username)
                st.rerun()
            
            st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
            
            st.markdown("### System Status")
            ai_mode = "Mock Mode" if use_mock else model.split('/')[-1][:25]
            st.markdown(f"<div class='info-box'>AI: {ai_mode}</div>", unsafe_allow_html=True)
            
            if jira_configured:
                st.markdown(f"<div class='info-box info-box-success'>Jira: {jira_project}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='info-box info-box-warning'>Jira: Not Configured</div>", unsafe_allow_html=True)
            
            if email_configured:
                st.markdown("<div class='info-box info-box-success'>Email: Configured</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='info-box info-box-warning'>Email: Not Configured</div>", unsafe_allow_html=True)
        
        st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)
        
        # Recent tickets needing attention
        st.markdown("### Tickets Needing Attention")
        
        needs_attention = [t for t in tickets if t.get("needs_priority_review") or t["status"] == "AI Review"]
        
        if needs_attention:
            for ticket in needs_attention[:5]:
                display_ticket_card(ticket, username, compact=True, context="dashboard_attention")
        else:
            st.markdown("<div class='info-box info-box-success'>All tickets are properly reviewed</div>", unsafe_allow_html=True)
    
    # ===== TICKETS TAB =====
    with tabs[1]:
        st.markdown("### All Tickets")
        
        # Filters
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "Filter by Status",
                ["All", "Draft", "AI Review", "Approved", "In Progress", "Completed", "Blocked"],
                key="status_filter"
            )
        
        with col2:
            priority_filter = st.selectbox(
                "Filter by Priority",
                ["All", "Critical", "High", "Medium", "Low"],
                key="priority_filter"
            )
        
        with col3:
            sort_by = st.selectbox(
                "Sort by",
                ["Priority Score (High→Low)", "Created (Newest)", "Created (Oldest)", "Status"],
                key="sort_by"
            )
        
        # Apply filters
        filtered_tickets = st.session_state.tickets.copy()
        
        if status_filter != "All":
            filtered_tickets = [t for t in filtered_tickets if t["status"] == status_filter]
        
        if priority_filter != "All":
            filtered_tickets = [t for t in filtered_tickets if t.get("calculated_priority", t.get("priority")) == priority_filter]
        
        # Apply sorting
        if sort_by == "Priority Score (High→Low)":
            filtered_tickets.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        elif sort_by == "Created (Newest)":
            filtered_tickets.sort(key=lambda x: x["created_at"], reverse=True)
        elif sort_by == "Created (Oldest)":
            filtered_tickets.sort(key=lambda x: x["created_at"])
        else:  # Status
            filtered_tickets.sort(key=lambda x: x["status"])
        
        st.markdown(f"<div style='color: var(--text-secondary); margin: 16px 0;'>Showing {len(filtered_tickets)} ticket(s)</div>", unsafe_allow_html=True)
        
        if filtered_tickets:
            for ticket in filtered_tickets:
                display_ticket_card(ticket, username, context="tickets_tab")
        else:
            st.info("No tickets match the selected filters")
    
    # ===== CREATE TICKET TAB =====
    with tabs[2]:
        st.markdown("### Create New Ticket")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            summary = st.text_input("Ticket Summary *", placeholder="Brief description of the issue")
            description = st.text_area(
                "Detailed Description *",
                placeholder="Describe the issue in detail. Include error messages, symptoms, affected systems, etc.",
                height=150
            )
            
            col_a, col_b = st.columns(2)
            with col_a:
                server = st.text_input("Server ID *", placeholder="e.g., srv-gpu-301")
            with col_b:
                rack = st.text_input("Rack Location *", placeholder="e.g., 3B-04")
            
            user_priority = st.select_slider(
                "Your Priority Assessment",
                options=["Low", "Medium", "High", "Critical"],
                value="Medium"
            )
            
            st.markdown("<div style='font-size: 13px; color: var(--text-secondary); margin-top: 8px;'>* Required fields</div>", unsafe_allow_html=True)
        
        with col2:
            st.markdown("<div class='ai-insight'>", unsafe_allow_html=True)
            st.markdown("<div class='ai-insight-header'>AI Assistant Tips</div>", unsafe_allow_html=True)
            st.markdown("""
            **For better AI analysis, include:**
            - Specific error codes or messages
            - When the issue started
            - Impact on services
            - Steps already taken
            - Safety concerns (if any)
            
            **The AI will automatically:**
            - Calculate objective priority
            - Validate completeness
            - Suggest improvements
            - Recommend actions
            """)
            st.markdown("</div>", unsafe_allow_html=True)
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        
        with col_btn1:
            create_clicked = st.button("Create Ticket", type="primary", key="create_ticket_btn", use_container_width=True)
        
        with col_btn2:
            create_and_sync = st.button("Create & Sync to Jira", key="create_sync_btn", disabled=not jira_configured, use_container_width=True)
        
        with col_btn3:
            create_and_email = st.button("Create & Email", key="create_email_btn", disabled=not (jira_configured and email_configured), use_container_width=True)
        
        if create_clicked or create_and_sync or create_and_email:
            if not summary or not description or not server or not rack:
                st.error("Please fill in all required fields")
            else:
                with st.spinner("AI analyzing ticket..."):
                    ticket_data = {
                        "summary": summary,
                        "description": description,
                        "server": server,
                        "rack": rack,
                        "priority": user_priority
                    }
                    
                    new_ticket = create_ticket(username, ticket_data)
                    st.session_state.tickets.insert(0, new_ticket)
                    save_user_tickets(username, st.session_state.tickets)
                    append_audit_log(username, f"Created ticket {new_ticket['id']}", new_ticket['summary'])
                
                st.success(f"Ticket {new_ticket['id']} created successfully")
                
                # Sync to Jira if requested
                if create_and_sync or create_and_email:
                    if sync_ticket_to_jira(new_ticket, username):
                        st.success(f"Synced to Jira as {new_ticket['jira_key']}")
                        
                        # Send email if requested
                        if create_and_email:
                            with st.expander("📧 Send Jira Ticket Email", expanded=True):
                                recipient = st.text_input("Recipient Email", key="create_email_recipient")
                                if st.button("Send Email", key="send_create_email"):
                                    if recipient:
                                        if send_jira_ticket_email(new_ticket, recipient):
                                            st.success(f"✅ Email sent to {recipient}")
                                    else:
                                        st.warning("Please enter an email address")
                
                # Show AI analysis
                st.markdown("---")
                st.markdown("### AI Analysis Results")
                
                col1, col2 = st.columns(2)
                
                priority_score = new_ticket.get('priority_score', 0)
                if isinstance(priority_score, dict):
                    priority_score = 5.0
                
                with col1:
                    st.markdown("<div class='score-display'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='score-number'>{float(priority_score):.1f}</div>", unsafe_allow_html=True)
                    st.markdown("<div class='score-label'>Priority Score</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    if new_ticket.get("needs_priority_review"):
                        st.markdown(f"<div class='info-box info-box-warning'>AI calculated priority: <strong>{new_ticket.get('calculated_priority', 'Unknown')}</strong> (you selected: {user_priority}). Ticket marked for review.</div>", unsafe_allow_html=True)
                
                with col2:
                    validation = new_ticket.get("validation", {})
                    completeness = validation.get("completeness_score", 0)
                    if isinstance(completeness, dict):
                        completeness = 0.7
                    
                    st.markdown("<div class='score-display'>", unsafe_allow_html=True)
                    st.markdown(f"<div class='score-number'>{float(completeness):.0%}</div>", unsafe_allow_html=True)
                    st.markdown("<div class='score-label'>Completeness</div>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    if completeness < 0.8:
                        missing = validation.get("missing_fields", [])
                        if missing:
                            st.markdown(f"<div class='info-box info-box-warning'>Consider adding: {', '.join(missing)}</div>", unsafe_allow_html=True)
                
                reasoning = new_ticket.get("priority_analysis", {}).get("reasoning", "")
                if reasoning:
                    st.markdown("<div class='ai-insight'>", unsafe_allow_html=True)
                    st.markdown("<div class='ai-insight-header'>AI Reasoning</div>", unsafe_allow_html=True)
                    st.markdown(reasoning)
                    st.markdown("</div>", unsafe_allow_html=True)
                
                # Create unique button key with timestamp
                if st.button("View Ticket Details", key=f"view_details_create_{new_ticket['id']}_{int(time.time())}"):
                    st.session_state[f"show_detail_create_{new_ticket['id']}"] = True
                    st.rerun()
    
    # ===== IMPORT CSV TAB =====
    with tabs[3]:
        st.markdown("### Bulk Import from CSV")
        
        st.markdown("""
        Upload a CSV file with the following columns:
        - `server` (required): Server ID
        - `rack` (required): Rack location
        - `issue` or `summary` (required): Issue description
        - `description` (optional): Detailed description
        - `priority` (optional): User priority (Low/Medium/High/Critical)
        """)
        
        uploaded_file = st.file_uploader("Choose CSV file", type="csv", key="csv_upload")
        
        if uploaded_file:
            try:
                df = pd.read_csv(uploaded_file)
                
                st.markdown("#### Preview")
                st.dataframe(df.head(10), use_container_width=True)
                
                st.markdown(f"<div style='color: var(--text-secondary); margin: 12px 0;'>Found {len(df)} rows</div>", unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    process_btn = st.button("Process and Import Tickets", type="primary", key="process_import_btn", use_container_width=True)
                
                with col2:
                    process_and_sync_btn = st.button("Import & Sync to Jira", key="process_sync_btn", disabled=not jira_configured, use_container_width=True)
                
                if process_btn or process_and_sync_btn:
                    with st.spinner("AI processing tickets..."):
                        progress_bar = st.progress(0)
                        imported_count = 0
                        synced_count = 0
                        
                        for idx, row in df.iterrows():
                            try:
                                ticket_data = {
                                    "server": row.get("server", "unknown"),
                                    "rack": row.get("rack", "unknown"),
                                    "summary": row.get("issue", row.get("summary", "Imported ticket")),
                                    "description": row.get("description", ""),
                                    "priority": row.get("priority", "Medium")
                                }
                                
                                new_ticket = create_ticket(username, ticket_data)
                                st.session_state.tickets.insert(0, new_ticket)
                                imported_count += 1
                                
                                if process_and_sync_btn:
                                    if sync_ticket_to_jira(new_ticket, username):
                                        synced_count += 1
                                
                                progress_bar.progress((idx + 1) / len(df))
                            except Exception as e:
                                st.error(f"Error processing row {idx}: {e}")
                        
                        save_user_tickets(username, st.session_state.tickets)
                        append_audit_log(username, f"Bulk imported {imported_count} tickets from CSV")
                        
                        progress_bar.empty()
                        st.success(f"Successfully imported {imported_count} tickets!")
                        
                        if process_and_sync_btn and synced_count > 0:
                            st.success(f"Synced {synced_count} tickets to Jira")
                        
                        if st.button("View All Tickets", key="view_all_after_import"):
                            st.rerun()
            
            except Exception as e:
                st.error(f"Error reading CSV: {e}")
        else:
            st.info("Upload a CSV file to get started")
            
            sample_data = {
                "server": ["srv-gpu-301", "srv-compute-142", "srv-storage-089"],
                "rack": ["3B-04", "2A-12", "1C-08"],
                "issue": ["GPU overheating", "Network connectivity issues", "Disk array failure"],
                "description": [
                    "Multiple GPUs showing thermal throttling. Temperature readings above 85C.",
                    "Server intermittently losing network connectivity. Requires cable inspection.",
                    "RAID array degraded. Two drives showing SMART errors."
                ],
                "priority": ["High", "Medium", "Critical"]
            }
            sample_df = pd.DataFrame(sample_data)
            
            csv_buffer = io.BytesIO()
            sample_df.to_csv(csv_buffer, index=False)
            csv_buffer.seek(0)
            
            st.download_button(
                "Download Sample CSV",
                csv_buffer,
                file_name="sample_tickets.csv",
                mime="text/csv",
                help="Download a sample CSV to see the expected format",
                key="download_sample_csv"
            )
    
    # ===== ACTIVITY LOG TAB =====
    with tabs[4]:
        st.markdown("### Activity Log")
        
        col1, col2 = st.columns([3, 1])
        
        with col2:
            # Force refresh by reading fresh from disk
            if st.button("🔄 Refresh Log", use_container_width=True, key="refresh_log_btn"):
                # Clear any cached data and read fresh
                st.rerun()
        
        # Always read fresh from disk (no caching)
        log_entries = get_audit_log(username, limit=200)
        
        if log_entries:
            st.markdown("<div class='log-container'>", unsafe_allow_html=True)
            for entry in reversed(log_entries):
                if entry.strip():
                    parts = entry.split("]", 1)
                    if len(parts) == 2:
                        timestamp = parts[0].replace("[", "")
                        message = parts[1].strip()
                        
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except:
                            time_str = timestamp
                        
                        st.markdown(f"<div class='log-line'><span class='log-timestamp'>{time_str}</span>{message}</div>", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.info("No activity logged yet")
    
    # ===== SETTINGS TAB =====
    with tabs[5]:
        st.markdown("### ⚙️ Settings")
        
        st.markdown("""
        <div class='info-box'>
        Configure your AI, Jira, and email settings here. These settings will override the .env file defaults for your session.
        Settings are session-based and will reset when you logout.
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # OpenRouter AI Settings
        with st.expander("🤖 OpenRouter AI Configuration", expanded=False):
            st.markdown("""
            **OpenRouter AI Integration**
            
            OpenRouter provides access to multiple AI models for ticket analysis, priority scoring, and validation.
            
            **How to get started:**
            1. Sign up at [openrouter.ai](https://openrouter.ai)
            2. Generate an API key from your account dashboard
            3. Choose a model (free models available)
            4. Enter credentials below
            
            **Current Status:** {}
            """.format("🟢 Using OpenRouter AI" if not use_mock else "🟡 Mock Mode (AI features simulated)"))
            
            col1, col2 = st.columns(2)
            
            with col1:
                openrouter_key_input = st.text_input(
                    "OpenRouter API Key",
                    value=st.session_state.get('openrouter_api_key', OPENROUTER_KEY),
                    type="password",
                    placeholder="sk-or-v1-...",
                    help="Your OpenRouter API key",
                    key="settings_openrouter_key"
                )
            
            with col2:
                model_options = [
                    "nvidia/nemotron-nano-12b-v2-vl:free",
                    "meta-llama/llama-3.2-3b-instruct:free",
                    "google/gemma-2-9b-it:free",
                    "anthropic/claude-3.5-sonnet",
                    "openai/gpt-4o",
                    "custom"
                ]
                
                current_model = st.session_state.get('openrouter_model', OPENROUTER_MODEL)
                
                if current_model in model_options:
                    default_index = model_options.index(current_model)
                else:
                    default_index = len(model_options) - 1
                
                model_selection = st.selectbox(
                    "AI Model",
                    options=model_options,
                    index=default_index,
                    help="Select an AI model. Free models available!",
                    key="settings_model_select"
                )
            
            # Custom model input if "custom" is selected
            if model_selection == "custom":
                custom_model = st.text_input(
                    "Custom Model Name",
                    value=current_model if current_model not in model_options[:-1] else "",
                    placeholder="provider/model-name",
                    help="Enter the full model identifier (e.g., anthropic/claude-3.5-sonnet)",
                    key="settings_custom_model"
                )
                model_to_save = custom_model
            else:
                model_to_save = model_selection
            
            if st.button("💾 Save OpenRouter Settings", key="save_openrouter_settings"):
                st.session_state['openrouter_api_key'] = openrouter_key_input
                st.session_state['openrouter_model'] = model_to_save
                st.success("✅ OpenRouter settings saved for this session!")
                st.rerun()
            
            if st.button("🧪 Test OpenRouter Connection", key="test_openrouter"):
                if openrouter_key_input:
                    with st.spinner("Testing connection..."):
                        try:
                            # Temporarily save to session state for test
                            old_key = st.session_state.get('openrouter_api_key')
                            old_model = st.session_state.get('openrouter_model')
                            
                            st.session_state['openrouter_api_key'] = openrouter_key_input
                            st.session_state['openrouter_model'] = model_to_save
                            
                            test_response = call_ai(
                                "You are a test assistant.",
                                "Respond with 'Connection successful' if you receive this message."
                            )
                            
                            if test_response and len(test_response) > 0:
                                st.success(f"✅ Connected successfully using model: {model_to_save}")
                            else:
                                st.error("❌ Connection failed")
                                if old_key: st.session_state['openrouter_api_key'] = old_key
                                if old_model: st.session_state['openrouter_model'] = old_model
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    st.warning("Please enter an API key")
            
            st.markdown("""
            <div class='info-box' style='margin-top: 16px;'>
            <strong>💡 Free Models Available:</strong><br>
            • Nvidia Nemotron Nano (12B) - Fast and efficient<br>
            • Meta Llama 3.2 (3B) - Compact and capable<br>
            • Google Gemma 2 (9B) - Balanced performance<br><br>
            <strong>Premium Models:</strong><br>
            • Claude 3.5 Sonnet - Advanced reasoning<br>
            • GPT-4o - Latest OpenAI model
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Jira Settings
        with st.expander("🔗 Jira Integration", expanded=False):
            st.markdown("""
            **Jira Integration**
            
            Connect Axis to your Jira instance to automatically create and sync tickets.
            
            **How to set up:**
            1. Go to your Jira Account Settings
            2. Navigate to Security → API tokens
            3. Click "Create API token"
            4. Copy the token and paste below
            5. Enter your Jira instance URL and project key
            
            **Current Status:** {}
            """.format("🟢 Connected to " + jira_project if jira_configured else "🔴 Not Configured"))
            
            col1, col2 = st.columns(2)
            
            with col1:
                jira_base_url = st.text_input(
                    "Jira Base URL",
                    value=st.session_state.get('jira_base_url', JIRA_BASE_URL),
                    placeholder="https://your-domain.atlassian.net",
                    help="Your Jira instance URL (without /browse or /rest)",
                    key="settings_jira_url"
                )
                
                jira_email = st.text_input(
                    "Jira Email",
                    value=st.session_state.get('jira_email', JIRA_EMAIL),
                    placeholder="your-email@company.com",
                    help="Email associated with your Jira account",
                    key="settings_jira_email"
                )
            
            with col2:
                jira_api_token = st.text_input(
                    "Jira API Token",
                    value=st.session_state.get('jira_api_token', JIRA_API_TOKEN),
                    type="password",
                    placeholder="Your Jira API token",
                    help="Generate from Jira Account Settings → Security",
                    key="settings_jira_token"
                )
                
                jira_project_key = st.text_input(
                    "Project Key",
                    value=st.session_state.get('jira_project_key', JIRA_PROJECT_KEY),
                    placeholder="AXIS",
                    help="Jira project key for ticket creation (e.g., AXIS, PROJ, DEV)",
                    key="settings_jira_project"
                )
            
            if st.button("💾 Save Jira Settings", key="save_jira_settings"):
                st.session_state['jira_base_url'] = jira_base_url
                st.session_state['jira_email'] = jira_email
                st.session_state['jira_api_token'] = jira_api_token
                st.session_state['jira_project_key'] = jira_project_key
                st.success("✅ Jira settings saved for this session!")
                st.rerun()
            
            if st.button("🧪 Test Jira Connection", key="test_jira"):
                if jira_base_url and jira_email and jira_api_token:
                    with st.spinner("Testing connection..."):
                        try:
                            old_base = st.session_state.get('jira_base_url')
                            old_email = st.session_state.get('jira_email')
                            old_token = st.session_state.get('jira_api_token')
                            
                            st.session_state['jira_base_url'] = jira_base_url
                            st.session_state['jira_email'] = jira_email
                            st.session_state['jira_api_token'] = jira_api_token
                            
                            headers = get_jira_auth()
                            response = requests.get(
                                f"{jira_base_url}/rest/api/3/myself",
                                headers=headers,
                                timeout=10
                            )
                            
                            if response.status_code == 200:
                                user_data = response.json()
                                st.success(f"✅ Connected as: {user_data.get('displayName', 'Unknown')}")
                            else:
                                st.error(f"❌ Connection failed: {response.status_code} - {response.text}")
                                if old_base: st.session_state['jira_base_url'] = old_base
                                if old_email: st.session_state['jira_email'] = old_email
                                if old_token: st.session_state['jira_api_token'] = old_token
                        except Exception as e:
                            st.error(f"❌ Error: {e}")
                else:
                    st.warning("Please fill in all Jira fields")
            
            st.markdown("""
            <div class='info-box' style='margin-top: 16px;'>
            <strong>💡 Jira Setup Tips:</strong><br>
            • URL should be your base Jira domain (e.g., https://company.atlassian.net)<br>
            • Don't include /browse, /rest, or any path after the domain<br>
            • API token is NOT your password - generate a new token in Jira settings<br>
            • Project key is usually 2-10 uppercase letters (e.g., AXIS, PROJ, DEV)
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("---")
        
        # Email Settings
        with st.expander("📧 Email Configuration", expanded=False):
            st.markdown("""
            **Email Configuration**
            
            Configure SMTP email settings to send ticket exports and Jira notifications directly from Axis.
            
            **How Email Works in Axis:**
            1. **CSV Exports**: Email ticket summaries as CSV attachments
            2. **Jira Notifications**: Send email with Jira ticket link and details
            3. **Bulk Operations**: Email exports after bulk imports
            
            **Supported Email Providers:**
            - **Gmail**: Use App Passwords (requires 2FA)
            - **Outlook/Office 365**: smtp.office365.com, port 587
            - **Yahoo**: smtp.mail.yahoo.com, port 587
            - **Custom SMTP**: Any SMTP server with TLS support
            
            **Gmail Setup (Recommended):**
            1. Enable 2-Factor Authentication on your Google account
            2. Go to Google Account → Security → App Passwords
            3. Generate an app password for "Mail"
            4. Use the 16-character password below (not your regular password)
            
            **Current Status:** {}
            """.format("🟢 Configured" if email_configured else "🔴 Not Configured"))
            
            col1, col2 = st.columns(2)
            
            with col1:
                smtp_server = st.text_input(
                    "SMTP Server",
                    value=st.session_state.get('smtp_server', SMTP_SERVER),
                    placeholder="smtp.gmail.com",
                    help="SMTP server for sending emails",
                    key="settings_smtp_server"
                )
                
                smtp_port = st.number_input(
                    "SMTP Port",
                    value=st.session_state.get('smtp_port', SMTP_PORT),
                    min_value=1,
                    max_value=65535,
                    help="Usually 587 for TLS or 465 for SSL",
                    key="settings_smtp_port"
                )
            
            with col2:
                email_address = st.text_input(
                    "Email Address",
                    value=st.session_state.get('email_address', EMAIL_ADDRESS),
                    placeholder="your-email@gmail.com",
                    help="Email address for sending exports",
                    key="settings_email_address"
                )
                
                email_password = st.text_input(
                    "Email Password / App Password",
                    value=st.session_state.get('email_password', EMAIL_PASSWORD),
                    type="password",
                    placeholder="Your email password or app password",
                    help="For Gmail, use an App Password (16 characters)",
                    key="settings_email_password"
                )
            
            if st.button("💾 Save Email Settings", key="save_email_settings"):
                st.session_state['smtp_server'] = smtp_server
                st.session_state['smtp_port'] = smtp_port
                st.session_state['email_address'] = email_address
                st.session_state['email_password'] = email_password
                st.success("✅ Email settings saved for this session!")
                st.rerun()
            
            if st.button("🧪 Test Email Connection", key="test_email_btn"):
                if email_address and email_password:
                    test_recipient = st.text_input("Send test email to:", key="test_email_recipient", placeholder="recipient@example.com")
                    if test_recipient:
                        with st.spinner("Sending test email..."):
                            old_server = st.session_state.get('smtp_server')
                            old_port = st.session_state.get('smtp_port')
                            old_email = st.session_state.get('email_address')
                            old_pass = st.session_state.get('email_password')
                            
                            st.session_state['smtp_server'] = smtp_server
                            st.session_state['smtp_port'] = smtp_port
                            st.session_state['email_address'] = email_address
                            st.session_state['email_password'] = email_password
                            
                            test_csv = io.BytesIO(b"Test,Export\n1,2\n3,4")
                            if send_email_with_attachment(
                                test_recipient, 
                                "Axis Test Email", 
                                "This is a test email from Axis Ticket Management System.\n\nIf you received this, your email configuration is working correctly!",
                                test_csv,
                                "test.csv"
                            ):
                                st.success(f"✅ Test email sent to {test_recipient}")
                            else:
                                st.error("❌ Failed to send test email")
                                if old_server: st.session_state['smtp_server'] = old_server
                                if old_port: st.session_state['smtp_port'] = old_port
                                if old_email: st.session_state['email_address'] = old_email
                                if old_pass: st.session_state['email_password'] = old_pass
                    else:
                        st.warning("Please enter a recipient email address")
                else:
                    st.warning("Please fill in email credentials")
            
            st.markdown("""
            <div class='info-box' style='margin-top: 16px;'>
            <strong>💡 Email Provider Settings:</strong><br><br>
            <strong>Gmail:</strong><br>
            • Server: smtp.gmail.com<br>
            • Port: 587<br>
            • Password: Use App Password (not your regular password)<br><br>
            <strong>Outlook/Office 365:</strong><br>
            • Server: smtp.office365.com<br>
            • Port: 587<br>
            • Password: Your account password<br><br>
            <strong>Yahoo:</strong><br>
            • Server: smtp.mail.yahoo.com<br>
            • Port: 587<br>
            • Password: Use App Password<br><br>
            <strong>⚠️ Security Note:</strong> Always use App Passwords when available for better security!
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("---")
            st.markdown("#### 📨 Email Features in Axis")
            
            st.markdown("""
            **1. CSV Export Emails**
            - Export ticket summaries and email as CSV attachments
            - Available in Dashboard → Export buttons
            - Includes all ticket data, priorities, and AI analysis
            
            **2. Jira Ticket Emails**
            - Send Jira ticket summaries with clickable links
            - Available after creating/syncing tickets to Jira
            - Includes ticket details, priority analysis, and Jira URL
            
            **3. Bulk Import Notifications**
            - Email notifications after bulk CSV imports
            - Summary of imported tickets
            - Jira sync status if applicable
            
            **How to Use:**
            1. Configure email settings above
            2. Look for "📧 Email" buttons throughout the app
            3. Enter recipient email address
            4. Click Send Email
            
            **Note:** Email configuration is required to send Jira ticket emails (Create & Email button).
            """)
        
        st.markdown("---")
        
        # Display current status
        st.markdown("#### 📊 Current Configuration Status")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if not use_mock:
                st.markdown("<div class='info-box info-box-success'>✅ OpenRouter: Active</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 12px; color: var(--text-secondary); margin-top: 8px;'>Model: {model.split('/')[-1][:30]}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='info-box info-box-warning'>⚠️ OpenRouter: Mock Mode</div>", unsafe_allow_html=True)
        
        with col2:
            if jira_configured:
                st.markdown("<div class='info-box info-box-success'>✅ Jira: Configured</div>", unsafe_allow_html=True)
                st.markdown(f"<div style='font-size: 12px; color: var(--text-secondary); margin-top: 8px;'>Project: {jira_project}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='info-box info-box-warning'>⚠️ Jira: Not Configured</div>", unsafe_allow_html=True)
        
        with col3:
            if email_configured:
                st.markdown("<div class='info-box info-box-success'>✅ Email: Configured</div>", unsafe_allow_html=True)
                _, smtp_port_display, email_addr, _, _ = get_email_config()
                st.markdown(f"<div style='font-size: 12px; color: var(--text-secondary); margin-top: 8px;'>From: {email_addr}</div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='info-box info-box-warning'>⚠️ Email: Not Configured</div>", unsafe_allow_html=True)
        
        st.markdown("""
        <div class='info-box' style='margin-top: 20px;'>
        <strong>💡 Configuration Tips:</strong><br>
        • All settings are stored in your session and will reset on logout<br>
        • For permanent configuration, set environment variables in .env file<br>
        • Test each connection after saving to verify configuration<br>
        • Session settings override .env file values<br>
        • Use the test buttons to verify connections before using features
        </div>
        """, unsafe_allow_html=True)

# -------------------------
# Run Application
# -------------------------
if __name__ == "__main__":
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    
    main()