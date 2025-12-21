import streamlit as st
import pandas as pd
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import List, Dict, Any, Optional

st.set_page_config(page_title="Startup Outreach Mailer", layout="wide")

# ---------------- SESSION STATE ----------------
if "sent_this_session" not in st.session_state:
    st.session_state.sent_this_session = set()

if "emails_sent" not in st.session_state:
    st.session_state.emails_sent = 0


# ---------------- DATA LOADERS ----------------
@st.cache_data
def load_uploaded_csv(file) -> pd.DataFrame:
    return pd.read_csv(file)


@st.cache_data
def load_master_csv() -> pd.DataFrame:
    return pd.read_csv("data/master_companies.csv")


# ---------------- EMAIL UTIL ----------------
def safe_format(template: str, ctx: Dict[str, Any]) -> str:
    try:
        return template.format(**ctx)
    except Exception:
        return template


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

    # ---- NAME ----
    if name_col and name_col in row.index and str(row[name_col]).strip():
        context["name"] = str(row[name_col]).strip()
    else:
        context["name"] = "there"

    # ---- COMPANY ----
    if company_col and company_col in row.index and str(row[company_col]).strip():
        context["company"] = str(row[company_col]).strip()
    else:
        context["company"] = "your company"

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = recipient
    msg["Subject"] = safe_format(subject_template, context)
    msg.set_content(safe_format(body_template, context))
    return msg


# ---------------- SMTP SENDER ----------------
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

        total = len(recipients_rows)

        for idx, row in enumerate(recipients_rows):
            recipient = str(row[email_col]).strip()
            if not recipient:
                continue

            msg = build_email(
                sender=email_address,
                recipient=recipient,
                subject_template=subject_template,
                body_template=body_template,
                row=row,
                name_col=name_col,
                company_col=company_col,
            )

            try:
                server.send_message(msg)
                sent_count += 1
            except Exception as e:
                st.error(f"Failed to send to {recipient}: {e}")

            progress_bar.progress((idx + 1) / total)

            if delay_seconds > 0:
                time.sleep(delay_seconds)

    except Exception as e:
        st.error(f"SMTP error: {e}")

    finally:
        if server:
            server.quit()

    return sent_count


# ---------------- MAIN APP ----------------
def main():
    st.title("🚀 Startup Outreach Email Automation")

    # ---- VIDEO ----
    st.subheader("🎥 Quick Tutorial")
    st.components.v1.iframe(
        "https://drive.google.com/file/d/1EG3EIA-JOh0FDqH85ei1RTWsTMwtr3hI/preview",
        height=480,
    )

    st.write(
        "Send personalised outreach emails using company-based selection "
        "or manual CSV upload with safe multi-account sending."
    )

    # ---- INPUT MODE ----
    st.subheader("1️⃣ Select Lead Input Method")
    mode = st.radio(
        "Choose how you want to provide email leads:",
        ["Generate from Platform Data", "Upload CSV Manually"],
    )

    df = None
    email_col = name_col = company_col = None

    # ---- PLATFORM DATA MODE ----
    if mode == "Generate from Platform Data":
        st.subheader("2️⃣ Select Companies")

        master_df = load_master_csv()

        companies = sorted(master_df["company"].dropna().unique())
        selected_companies = st.multiselect(
            "Select up to 5 companies",
            companies,
            max_selections=5,
        )

        limit = st.number_input(
            "Number of emails to use",
            min_value=1,
            max_value=50,
            value=10,
        )

        if selected_companies:
            df = (
                master_df[master_df["company"].isin(selected_companies)]
                .head(limit)
                .copy()
            )

            # EXACT CSV COLUMN NAMES
            email_col = "email"
            name_col = "name"
            company_col = "company"

            st.success(f"Selected {len(df)} emails")
            st.dataframe(df)

            df = st.data_editor(df, num_rows="dynamic")

    # ---- MANUAL CSV MODE ----
    if mode == "Upload CSV Manually":
        st.subheader("2️⃣ Upload CSV")
        uploaded = st.file_uploader("Upload CSV file", type=["csv"])

        if uploaded:
            df = load_uploaded_csv(uploaded)
            st.write(f"Loaded **{len(df)}** rows")
            st.dataframe(df.head())

            # FIXED column mapping
            email_col = "email"
            name_col = "name"
            company_col = "company"

    # ---- TEMPLATE ----
    st.subheader("3️⃣ Email Template")

    subject_template = st.text_input(
        "Subject",
        "Exploring opportunities to contribute at {company}",
    )

    body_template = st.text_area(
        "Body",
        height=260,
        value=(
            "Hi {name},\n\n"
            "I came across {company} and really liked how you’re building technology "
            "to streamline restaurant operations at scale.\n\n"
            "I’m a B.Tech student at BIT Mesra with strong exposure to supply chain "
            "management, operations, and data-driven analysis, and I’m exploring "
            "internship opportunities at a fast-growing B2B startup.\n\n"
            "I’d love to connect and learn if there’s an opportunity to contribute "
            "to your team.\n\n"
            "Best regards,\n"
            "Shyam Kumar\n"
            "BIT Mesra"
        ),
    )

    # ---- ACCOUNTS ----
    st.subheader("4️⃣ Sender Accounts")
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

    # ---- DELAY ----
    st.subheader("5️⃣ Delay Between Emails")
    delay_seconds = st.number_input("Delay (seconds)", 1.0, value=2.0, step=0.5)
    
      # ---- PREVIEW ----
    st.subheader("3️⃣ Preview Email")

    if df is not None and len(df) > 0:
        preview_row = df.iloc[0]
        ctx = build_context(preview_row)

        with st.expander("👀 Click to preview first email"):
            st.markdown("**Subject**")
            st.code(safe_format(subject_template, ctx))

            st.markdown("**Body**")
            st.code(safe_format(body_template, ctx))
    else:
        st.info("Upload/select data to enable preview.")


    # ---- SEND ----
    st.subheader("6️⃣ Send Emails")

    if st.button("🚀 Start Sending"):
        if df is None or email_col is None:
            st.error("No email data available.")
            return

        if not accounts:
            st.error("Add at least one sender account.")
            return

        rows = [row for _, row in df.iterrows() if str(row[email_col]).strip()]

        progress_bar = st.progress(0)
        buckets = {i: [] for i in range(len(accounts))}

        for idx, row in enumerate(rows):
            buckets[idx % len(accounts)].append(row)

        total_sent = 0
        status = st.empty()

        for i, batch in buckets.items():
            status.text(f"📨 Sending using {accounts[i]['email']}...")
            total_sent += send_batch_for_account(
                accounts[i],
                batch,
                email_col,
                subject_template,
                body_template,
                name_col,
                company_col,
                delay_seconds,
                progress_bar,
            )

        status.text("🎉 Done!")
        st.success(f"Sent **{total_sent} / {len(rows)}** emails successfully.")


if __name__ == "__main__":
    main()
