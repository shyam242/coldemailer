import streamlit as st
import pandas as pd
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import List, Dict, Any, Optional

st.set_page_config(page_title="Startup Outreach Mailer", layout="wide")

# --- SESSION STATE SETUP ---
# This stores which recipients have already received an email IN THIS RUN.
if "sent_this_session" not in st.session_state:
    st.session_state.sent_this_session = set()

# This stores per-email progress
if "emails_sent" not in st.session_state:
    st.session_state.emails_sent = 0


@st.cache_data
def load_data(file) -> pd.DataFrame:
    return pd.read_csv(file)


def build_email(
    sender: str,
    recipient: str,
    subject_template: str,
    body_template: str,
    row: pd.Series,
    name_col: Optional[str],
    company_col: Optional[str],
) -> EmailMessage:

    context = {}

    if name_col and name_col in row.index:
        context["name"] = row[name_col]

    if company_col and company_col in row.index:
        context["company"] = row[company_col]

    # Safe formatting
    def safe_format(template: str, ctx: Dict[str, Any]) -> str:
        try:
            return template.format(**ctx)
        except:
            return template

    subject = safe_format(subject_template, context)
    body = safe_format(body_template, context)

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = subject
    msg.set_content(body)
    return msg


def send_batch_for_account(
    account_config: Dict[str, str],
    recipients_rows: List[pd.Series],
    email_col: str,
    subject_template: str,
    body_template: str,
    name_col: Optional[str],
    company_col: Optional[str],
    delay_seconds: float,
    progress_bar,
) -> int:

    sent_count = 0

    smtp_server = account_config["smtp_server"]
    smtp_port = int(account_config["smtp_port"])
    email_address = account_config["email"]
    password = account_config["password"]

    server = None

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls(context=ssl.create_default_context())
        server.login(email_address, password)

        for i, row in enumerate(recipients_rows):

            recipient = str(row[email_col]).strip()
            if not recipient:
                continue

            # --- DUPLICATE PREVENTION ---
            if recipient in st.session_state.sent_this_session:
                continue

            # Build email
            msg = build_email(
                sender=email_address,
                recipient=recipient,
                subject_template=subject_template,
                body_template=body_template,
                row=row,
                name_col=name_col,
                company_col=company_col,
            )

            # Attempt send
            try:
                server.send_message(msg)
                sent_count += 1

                # Mark this recipient as emailed
                st.session_state.sent_this_session.add(recipient)

                # Update global progress
                st.session_state.emails_sent += 1
                progress_bar.progress(
                    st.session_state.emails_sent / st.session_state.total_emails
                )

            except Exception as e:
                st.error(f"Failed to send to {recipient}: {e}")

            # Delay between emails
            if delay_seconds > 0:
                time.sleep(delay_seconds)

    except Exception as e:
        st.error(f"Error using {email_address}: {e}")

    finally:
        if server is not None:
            try:
                server.quit()
            except:
                pass

    return sent_count


def main():

    st.title("🚀 Startup Outreach Email Automation (Multi-Account, Safe Mode)")
    st.subheader("🎥 Quick Tutorial")
    st.markdown("Watch this short guide on how to use this tool:")

    st.video("https://youtu.be/-0KNYZsAIkI")
    st.write("Send personalised outreach emails using up to 4 email accounts with **no duplicate sending**.")

    # -------------------
    # 1. UPLOAD CSV
    # -------------------
    st.subheader("1️⃣ Upload CSV")
    uploaded = st.file_uploader("Upload your CSV file", type=["csv"])

    df = None
    email_col = name_col = company_col = None

    if uploaded:
        df = load_data(uploaded)
        st.write(f"Loaded **{len(df)}** rows")
        st.dataframe(df.head())

        cols = list(df.columns)

        email_col = st.selectbox("Email column", cols)

        name_opt = st.selectbox("Name column (optional)", ["(none)"] + cols)
        if name_opt != "(none)":
            name_col = name_opt

        comp_opt = st.selectbox("Company column (optional)", ["(none)"] + cols)
        if comp_opt != "(none)":
            company_col = comp_opt

    # -------------------
    # 2. TEMPLATE
    # -------------------
    st.subheader("2️⃣ Email Template")

    subject_template = st.text_input(
        "Subject",
        "Exploring opportunities to contribute at your startup",
    )

    body_template = st.text_area(
        "Body",
        height=260,
        value=(
            "Hi {name},\n\n"
            "I came across {company} and really liked the problem you're solving.\n"
            "I'm a final-year student exploring opportunities at fast-moving startups.\n\n"
            "- Add 1–2 highlights here\n"
            "- Add 1–2 relevant skills here\n\n"
            "Would love to connect and explore if I can add value.\n\n"
            "Best,\nYour Name"
        ),
    )

    # -------------------
    # 3. ACCOUNTS
    # -------------------
    st.subheader("3️⃣ Sender Accounts")

    accounts = []
    for i in range(1, 5):
        with st.expander(f"Sender {i}"):
            use = st.checkbox(f"Use sender {i}", value=(i == 1))
            if not use:
                continue

            email = st.text_input(f"Email {i}")
            password = st.text_input(f"App Password {i}", type="password")
            smtp = st.text_input(f"SMTP Server {i}", value="smtp.gmail.com")
            port = st.text_input(f"Port {i}", value="587")

            if email and password:
                accounts.append(
                    {
                        "email": email,
                        "password": password,
                        "smtp_server": smtp,
                        "smtp_port": port,
                    }
                )

    # -------------------
    # 4. DELAY & PREVIEW
    # -------------------
    st.subheader("4️⃣ Delay Between Emails")
    delay_seconds = st.number_input("Delay (seconds)", min_value=0.0, value=2.0, step=0.5)

    st.subheader("5️⃣ Preview")
    if df is not None and email_col:
        idx = st.number_input("Preview row", 0, len(df) - 1, 0)
        row = df.iloc[int(idx)]
        preview = build_email(
            sender=accounts[0]["email"] if accounts else "example@example.com",
            recipient=str(row[email_col]),
            subject_template=subject_template,
            body_template=body_template,
            row=row,
            name_col=name_col,
            company_col=company_col,
        )
        st.code(preview["Subject"])
        st.code(preview.get_content())

    # -------------------
    # 6. SEND EMAILS
    # -------------------
    st.subheader("6️⃣ Send Emails")

    if st.button("🚀 Start Sending"):

        if df is None:
            st.error("Upload a CSV first.")
            return

        if not accounts:
            st.error("Add at least one sender email.")
            return

        # All valid rows
        rows = [row for _, row in df.iterrows() if str(row[email_col]).strip()]
        total = len(rows)

        st.session_state.total_emails = total
        st.session_state.emails_sent = 0
        st.write(f"Total valid recipients: **{total}**")

        # Progress bar
        progress_bar = st.progress(0)

        # Round-robin distribution
        buckets = {i: [] for i in range(len(accounts))}
        for idx, row in enumerate(rows):
            buckets[idx % len(accounts)].append(row)

        total_sent = 0
        status = st.empty()

        for i, batch in buckets.items():
            if not batch:
                continue

            acc = accounts[i]
            status.text(f"📨 Sending using {acc['email']}...")

            sent_now = send_batch_for_account(
                account_config=acc,
                recipients_rows=batch,
                email_col=email_col,
                subject_template=subject_template,
                body_template=body_template,
                name_col=name_col,
                company_col=company_col,
                delay_seconds=delay_seconds,
                progress_bar=progress_bar,
            )

            total_sent += sent_now

        status.text("🎉 Done!")
        st.success(f"Sent **{total_sent} / {total}** emails successfully.")


if __name__ == "__main__":
    main()
