import streamlit as st
import pandas as pd
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import Dict, List

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="Startup Outreach Mailer", layout="wide")

# ---------------- DATA LOADERS ----------------
@st.cache_data
def load_uploaded_csv(file):
    return pd.read_csv(file)

@st.cache_data
def load_master_csv():
    return pd.read_csv("data/master_companies.csv")

# ---------------- UTIL FUNCTIONS ----------------
def safe_format(template: str, ctx: Dict[str, str]) -> str:
    try:
        return template.format(**ctx)
    except Exception:
        return template

def build_context(row: pd.Series) -> Dict[str, str]:
    name = str(row.get("name", "")).strip()
    company = str(row.get("company", "")).strip()

    return {
        "name": name if name else "there",
        "company": company if company else "your company",
    }

def build_email(sender, recipient, subject_t, body_t, ctx):
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = safe_format(subject_t, ctx)
    msg.set_content(safe_format(body_t, ctx))
    return msg

# ---------------- SMTP SENDER ----------------
def send_batch(account, rows, subject_t, body_t, delay, progress):
    sent = 0
    try:
        server = smtplib.SMTP(account["smtp_server"], int(account["smtp_port"]))
        server.starttls(context=ssl.create_default_context())
        server.login(account["email"], account["password"])

        total = len(rows)
        for i, row in enumerate(rows):
            recipient = str(row["email"]).strip()
            if not recipient:
                continue

            ctx = build_context(row)
            msg = build_email(
                account["email"],
                recipient,
                subject_t,
                body_t,
                ctx,
            )

            try:
                server.send_message(msg)
                sent += 1
            except Exception as e:
                st.error(f"Failed to send to {recipient}: {e}")

            progress.progress((i + 1) / total)
            time.sleep(delay)

        server.quit()
    except Exception as e:
        st.error(f"SMTP error: {e}")

    return sent

# ---------------- MAIN APP ----------------
def main():
    st.title("🚀 Startup Outreach Email Automation")
    # ---- VIDEO ---- 
    st.subheader("🎥 Quick Tutorial") 
    st.markdown("Watch this short guide on how to use this tool:")
    st.components.v1.iframe( "https://drive.google.com/file/d/1EG3EIA-JOh0FDqH85ei1RTWsTMwtr3hI/preview", height=480, )

    # ---- LEAD SOURCE ----
    st.subheader("1️⃣ Lead Source")
    mode = st.radio(
        "Choose lead input method:",
        ["Generate from Platform Data", "Upload CSV Manually"],
    )

    df = None

    if mode == "Generate from Platform Data":
        master_df = load_master_csv()
        companies = sorted(master_df["company"].dropna().unique())

        selected = st.multiselect("Select up to 5 companies", companies, max_selections=5)
        limit = st.number_input("Number of emails",1,200,10)

        if selected:
            df = master_df[master_df["company"].isin(selected)].head(limit).copy()
            st.dataframe(df)
            df = st.data_editor(df, num_rows="dynamic")

    if mode == "Upload CSV Manually":
        uploaded = st.file_uploader("Upload CSV (name, email, company)", type=["csv"])
        if uploaded:
            df = load_uploaded_csv(uploaded)
            st.dataframe(df.head())

    # ---- TEMPLATE ----
    st.subheader("2️⃣ Email Template")

    subject_template = st.text_input(
        "Subject",
        "Exploring opportunities to contribute at {company}",
    )

    body_template = st.text_area(
        "Body",
        height=280,
        value=(
            "Hi {name},\n\n"
            "hope you’re doing well. I came across {company} and was impressed by the work you’re doing in (industry).\n"
            "I’m a student of (college) with strong exposure to supply chain "
            "management, operations, and data-driven analysis, and I’m exploring "
            "internship opportunities at a fast-growing B2B startup.\n\n"
            "I’d love to connect and learn if there’s an opportunity to contribute "
            "to your team.\n\n"
            "Best regards,\n"
            "Your name\n"
        ),
    )

    # ---- PREVIEW ----
    st.subheader("3️⃣ Preview Email")

    if df is not None and len(df) > 0:
        preview_row = df.iloc[0]
        ctx = build_context(preview_row)

        with st.expander("👀 Preview first email"):
            st.markdown("**Subject**")
            st.code(safe_format(subject_template, ctx))
            st.markdown("**Body**")
            st.code(safe_format(body_template, ctx))
    else:
        st.info("Upload or select leads to enable preview.")

    # ---- SENDER ACCOUNTS ----
    st.subheader("4️⃣ Sender Accounts")
    accounts = []

    for i in range(1, 4):
        with st.expander(f"Sender {i}"):
            use = st.checkbox(f"Use sender {i}", value=(i == 1))
            if not use:
                continue

            email = st.text_input(f"Email {i}")
            password = st.text_input(f"App Password {i}", type="password")
            smtp = st.text_input(f"SMTP Server {i}", value="smtp.gmail.com")
            port = st.text_input(f"Port {i}", value="587")

            if email and password:
                accounts.append({
                    "email": email,
                    "password": password,
                    "smtp_server": smtp,
                    "smtp_port": port,
                })

    # ---- SEND ----
    st.subheader("5️⃣ Send Emails")
    delay = st.number_input("Delay between emails (seconds)", 1.0, 10.0, 2.0)

    if st.button("🚀 Start Sending"):
        if df is None or not accounts:
            st.error("Missing lead data or sender account.")
            return

        rows = [row for _, row in df.iterrows() if str(row["email"]).strip()]
        progress = st.progress(0)

        buckets = {i: [] for i in range(len(accounts))}
        for idx, row in enumerate(rows):
            buckets[idx % len(accounts)].append(row)

        total_sent = 0
        for i, batch in buckets.items():
            total_sent += send_batch(
                accounts[i],
                batch,
                subject_template,
                body_template,
                delay,
                progress,
            )

        st.success(f"🎉 Sent {total_sent} emails successfully!")

# ---------------- RUN ----------------
if __name__ == "__main__":
    main()
