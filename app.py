import streamlit as st
import pandas as pd
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import List, Dict, Any, Optional

# -------------------------------------------------
# PAGE CONFIG
# -------------------------------------------------
st.set_page_config(page_title="ColdMail Automation", layout="wide")

# -------------------------------------------------
# GLASSMORPHISM + DARK UI
# -------------------------------------------------
st.markdown("""
<style>
.stApp {
    background: radial-gradient(circle at top left, #1f2933, #0b0f14 65%);
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 3rem;
}

.glass {
    background: rgba(255,255,255,0.08);
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border-radius: 18px;
    padding: 2rem;
    margin-bottom: 2rem;
    border: 1px solid rgba(255,255,255,0.15);
    box-shadow: 0 25px 50px rgba(0,0,0,0.5);
}

h1 {
    font-size: 2.4rem;
    font-weight: 800;
    color: #f9fafb;
}

h2, h3 {
    color: #f3f4f6;
    font-weight: 700;
}

p, label, span {
    color: #d1d5db !important;
}

.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border-radius: 12px;
    padding: 0.7rem 1.6rem;
    font-weight: 700;
    border: none;
}

.stButton > button:hover {
    box-shadow: 0 12px 35px rgba(99,102,241,0.45);
    transform: translateY(-1px);
}

input, textarea {
    background: rgba(255,255,255,0.08) !important;
    color: #f9fafb !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255,255,255,0.15) !important;
}

[data-testid="stDataFrame"] {
    background: rgba(255,255,255,0.05);
    border-radius: 14px;
}
</style>
""", unsafe_allow_html=True)

# -------------------------------------------------
# SESSION STATE
# -------------------------------------------------
if "sent_this_session" not in st.session_state:
    st.session_state.sent_this_session = set()
if "emails_sent" not in st.session_state:
    st.session_state.emails_sent = 0

# -------------------------------------------------
# HELPERS
# -------------------------------------------------
def normalize_df(df):
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

@st.cache_data
def load_master_csv():
    return normalize_df(pd.read_csv("data/master_companies.csv"))

@st.cache_data
def load_uploaded_csv(file):
    return normalize_df(pd.read_csv(file))

def safe_format(tpl, ctx):
    try:
        return tpl.format(**ctx)
    except:
        return tpl

def build_email(sender, recipient, subject, body, row, name_col, company_col):
    ctx = {}
    if name_col and name_col in row:
        ctx["name"] = row[name_col]
    if company_col and company_col in row:
        ctx["company"] = row[company_col]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = safe_format(subject, ctx)
    msg.set_content(safe_format(body, ctx))
    return msg

def send_batch(account, rows, email_col, subject, body, name_col, company_col, delay, bar):
    server = smtplib.SMTP(account["smtp_server"], int(account["smtp_port"]))
    server.starttls(context=ssl.create_default_context())
    server.login(account["email"], account["password"])

    sent = 0
    for row in rows:
        recipient = str(row[email_col]).strip()
        if not recipient or recipient in st.session_state.sent_this_session:
            continue

        msg = build_email(
            account["email"], recipient,
            subject, body, row,
            name_col, company_col
        )

        try:
            server.send_message(msg)
            sent += 1
            st.session_state.sent_this_session.add(recipient)
            st.session_state.emails_sent += 1
            bar.progress(st.session_state.emails_sent / st.session_state.total_emails)
        except Exception as e:
            st.error(f"Failed: {recipient} — {e}")

        time.sleep(delay)

    server.quit()
    return sent

# -------------------------------------------------
# MAIN APP
# -------------------------------------------------
def main():

    # HERO
    st.markdown("""
    <div class="glass">
        <h1>🚀 ColdMail Automation Platform</h1>
        <p>
            Send <b>personalised cold emails</b> safely using
            <b>company-based lead selection</b> or your own CSV —
            with preview, rotation and limits.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # VIDEO
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("🎥 Quick Walkthrough")
    st.components.v1.iframe(
        "https://drive.google.com/file/d/1EG3EIA-JOh0FDqH85ei1RTWsTMwtr3hI/preview",
        height=420,
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # INPUT MODE
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("1️⃣ Lead Source")
    mode = st.radio(
        "Choose how to add leads",
        ["Generate from Platform Data", "Upload CSV Manually"],
        horizontal=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    df = None
    email_col = name_col = company_col = None

    # PLATFORM DATA
    if "Platform" in mode:
        master = load_master_csv()

        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.subheader("2️⃣ Select Companies")

        companies = sorted(master["company"].unique())
        col1, col2 = st.columns([2,1])

        with col1:
            selected = st.multiselect("Companies (max 5)", companies, max_selections=5)
        with col2:
            limit = st.number_input("Emails", 1, 50, 10)

        if selected:
            df = master[master["company"].isin(selected)].head(limit).copy()
            email_col, name_col, company_col = "email", "name", "company"
            df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # MANUAL CSV
    if "Upload" in mode:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.subheader("2️⃣ Upload CSV")
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded:
            df = load_uploaded_csv(uploaded)
            st.dataframe(df.head(), use_container_width=True)
            cols = df.columns.tolist()
            email_col = st.selectbox("Email column", cols)
            name_col = st.selectbox("Name column", ["(none)"] + cols)
            company_col = st.selectbox("Company column", ["(none)"] + cols)
            if name_col == "(none)": name_col = None
            if company_col == "(none)": company_col = None
        st.markdown('</div>', unsafe_allow_html=True)

    # TEMPLATE
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("3️⃣ Email Content")
    subject = st.text_input("Subject", "Exploring opportunities at {company}")
    body = st.text_area(
        "Body", height=240,
        value="Hi {name},\n\nI came across {company} and liked what you're building.\n\nWould love to connect.\n\nBest,\nYour Name"
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # SENDERS
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("4️⃣ Sender Accounts")
    accounts = []
    for i in range(1,5):
        with st.expander(f"Sender {i}", expanded=(i==1)):
            email = st.text_input(f"Email {i}")
            pwd = st.text_input(f"App Password {i}", type="password")
            smtp = st.text_input(f"SMTP {i}", value="smtp.gmail.com")
            port = st.text_input(f"Port {i}", value="587")
            if email and pwd:
                accounts.append({
                    "email": email,
                    "password": pwd,
                    "smtp_server": smtp,
                    "smtp_port": port
                })
    st.markdown('</div>', unsafe_allow_html=True)

    # PREVIEW
    if df is not None and email_col:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        st.subheader("📝 Preview")
        idx = st.number_input("Row", 0, len(df)-1, 0)
        row = df.iloc[int(idx)]
        preview = build_email(
            accounts[0]["email"] if accounts else "example@email.com",
            row[email_col], subject, body, row, name_col, company_col
        )
        c1, c2 = st.columns(2)
        with c1: st.code(preview["Subject"])
        with c2: st.code(preview.get_content())
        st.markdown('</div>', unsafe_allow_html=True)

    # SEND
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    st.subheader("🚀 Launch Campaign")
    delay = st.number_input("Delay (seconds)", 1.0, 10.0, 2.0)
    if st.button("🚀 Start Sending"):
        if not df or not accounts:
            st.error("Missing data or sender accounts")
        else:
            rows = [r for _, r in df.iterrows() if str(r[email_col]).strip()]
            st.session_state.total_emails = len(rows)
            st.session_state.emails_sent = 0
            bar = st.progress(0)

            buckets = {i: [] for i in range(len(accounts))}
            for i, r in enumerate(rows):
                buckets[i % len(accounts)].append(r)

            total = 0
            for i, batch in buckets.items():
                total += send_batch(
                    accounts[i], batch, email_col,
                    subject, body, name_col, company_col,
                    delay, bar
                )

            st.success(f"🎉 Sent {total} emails successfully!")
    st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------
if __name__ == "__main__":
    main()
