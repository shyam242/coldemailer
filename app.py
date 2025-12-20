import streamlit as st
import pandas as pd
import smtplib
import ssl
import time
from email.message import EmailMessage

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(page_title="ColdMail Automation", layout="wide")

# =========================
# UI (GLASS + DARK)
# =========================
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
    border-radius: 18px;
    padding: 2rem;
    margin-bottom: 2rem;
    border: 1px solid rgba(255,255,255,0.15);
    box-shadow: 0 25px 50px rgba(0,0,0,0.5);
}
h1, h2, h3 { color: #f9fafb; }
p, label, span { color: #d1d5db !important; }
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    color: white;
    border-radius: 12px;
    padding: 0.7rem 1.6rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

# =========================
# HELPERS
# =========================
def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

@st.cache_data
def load_master_csv():
    return normalize_df(pd.read_csv("data/master_companies.csv"))

@st.cache_data
def load_uploaded_csv(file):
    return normalize_df(pd.read_csv(file))

def build_email(sender, recipient, subject, body, row, name_col, company_col):
    ctx = {}
    if name_col and name_col in row:
        ctx["name"] = row[name_col]
    if company_col and company_col in row:
        ctx["company"] = row[company_col]

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject.format(**ctx)
    msg.set_content(body.format(**ctx))
    return msg

def send_batch(account, rows, email_col, subject, body, name_col, company_col, delay, progress):
    server = smtplib.SMTP(account["smtp"], account["port"])
    server.starttls(context=ssl.create_default_context())
    server.login(account["email"], account["password"])

    sent = 0
    total = len(rows)

    for i, row in enumerate(rows):
        recipient = str(row[email_col]).strip()
        if not recipient:
            continue

        msg = build_email(
            account["email"], recipient,
            subject, body, row,
            name_col, company_col
        )

        server.send_message(msg)
        sent += 1
        progress.progress((i + 1) / total)
        time.sleep(delay)

    server.quit()
    return sent

# =========================
# MAIN APP
# =========================
def main():

    # HERO
    st.markdown("""
    <div class="glass">
        <h1>🚀 ColdMail Automation Platform</h1>
        <p>
            Send <b>personalised cold emails</b> using platform leads
            or your own CSV — safely and cleanly.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # MODE
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    mode = st.radio(
        "Choose lead source",
        ["Generate from Platform Data", "Upload CSV Manually"],
        horizontal=True
    )
    st.markdown('</div>', unsafe_allow_html=True)

    df = None
    email_col = name_col = company_col = None

    # =========================
    # PLATFORM DATA MODE
    # =========================
    if "Platform" in mode:
        master = load_master_csv()

        possible_company_cols = [
            "company", "company_name",
            "startup", "organisation", "organization"
        ]

        company_col_master = None
        for c in possible_company_cols:
            if c in master.columns:
                company_col_master = c
                break

        if not company_col_master:
            st.error("❌ No company column found in master CSV")
            return

        st.markdown('<div class="glass">', unsafe_allow_html=True)

        companies = sorted(master[company_col_master].dropna().unique())
        selected = st.multiselect("Select companies (max 5)", companies, max_selections=5)
        limit = st.number_input("Number of emails", 1, 50, 10)

        if selected:
            df = master[master[company_col_master].isin(selected)].head(limit).copy()
            email_col = "email"
            name_col = "name" if "name" in df.columns else None
            company_col = company_col_master
            df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

    # =========================
    # MANUAL CSV MODE
    # =========================
    if "Upload" in mode:
        st.markdown('<div class="glass">', unsafe_allow_html=True)
        uploaded = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded:
            df = load_uploaded_csv(uploaded)
            st.dataframe(df.head(), use_container_width=True)

            cols = df.columns.tolist()
            email_col = st.selectbox("Email column", cols)
            name_col = st.selectbox("Name column", ["(none)"] + cols)
            company_col = st.selectbox("Company column", ["(none)"] + cols)

            if name_col == "(none)":
                name_col = None
            if company_col == "(none)":
                company_col = None

        st.markdown('</div>', unsafe_allow_html=True)

    # =========================
    # TEMPLATE
    # =========================
    st.markdown('<div class="glass">', unsafe_allow_html=True)
    subject = st.text_input("Email subject", "Exploring opportunities at {company}")
    body = st.text_area(
        "Email body",
        height=220,
        value=(
            "Hi {name},\n\n"
            "I came across {company} and really liked what you're building.\n\n"
            "Would love to connect.\n\n"
            "Best,\nYour Name"
        )
    )
    st.markdown('</div>', unsafe_allow_html=True)

    # =========================
    # SEND
    # =========================
    if df is not None and email_col:
        st.markdown('<div class="glass">', unsafe_allow_html=True)

        sender_email = st.text_input("Sender email")
        app_password = st.text_input("Gmail App Password", type="password")
        delay = st.number_input("Delay between emails (seconds)", 1.0, 10.0, 2.0)

        if st.button("🚀 Start Sending"):
            if not sender_email or not app_password:
                st.error("Enter sender email and app password")
            else:
                account = {
                    "email": sender_email,
                    "password": app_password,
                    "smtp": "smtp.gmail.com",
                    "port": 587
                }
                rows = [r for _, r in df.iterrows()]
                progress = st.progress(0)
                sent = send_batch(
                    account, rows, email_col,
                    subject, body, name_col, company_col,
                    delay, progress
                )
                st.success(f"🎉 Sent {sent} emails successfully!")

        st.markdown('</div>', unsafe_allow_html=True)

# =========================
if __name__ == "__main__":
    main()
