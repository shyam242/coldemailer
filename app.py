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
    except:
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
    if name_col and name_col in row.index:
        context["name"] = row[name_col]
    if company_col and company_col in row.index:
        context["company"] = row[company_col]

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

    server = smtplib.SMTP(
        account_config["smtp_server"],
        int(account_config["smtp_port"]),
    )
    server.starttls(context=ssl.create_default_context())
    server.login(account_config["email"], account_config["password"])

    for row in recipients_rows:
        recipient = str(row[email_col]).strip()
        if not recipient or recipient in st.session_state.sent_this_session:
            continue

        msg = build_email(
            account_config["email"],
            recipient,
            subject_template,
            body_template,
            row,
            name_col,
            company_col,
        )

        try:
            server.send_message(msg)
            sent_count += 1
            st.session_state.sent_this_session.add(recipient)
            st.session_state.emails_sent += 1
            progress_bar.progress(
                st.session_state.emails_sent / st.session_state.total_emails
            )
        except Exception as e:
            st.error(f"Failed to send to {recipient}: {e}")

        time.sleep(delay_seconds)

    server.quit()
    return sent_count


# ---------------- MAIN APP ----------------
def main():
    st.title("🚀 Startup Outreach Email Automation")

    # ---- VIDEO ----
    st.subheader("🎥 Quick Tutorial")
    st.markdown("Watch this short guide on how to use this tool:")
    st.components.v1.iframe(
        "https://drive.google.com/file/d/1EG3EIA-JOh0FDqH85ei1RTWsTMwtr3hI/preview",
        height=480,
    )

    st.write(
        "Send personalised outreach emails using **company-based selection** "
        "or **manual CSV upload**, with **safe multi-account sending**."
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

        companies = sorted(master_df["Company"].dropna().unique())
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
                master_df[master_df["Company"].isin(selected_companies)]
                .head(limit)
                .copy()
            )

            email_col = "email"
            name_col = "name"
            company_col = "Company"

            st.success(f"Selected {len(df)} emails")
            st.dataframe(df)

            st.write("✏️ Edit or remove rows before sending")
            df = st.data_editor(df, num_rows="dynamic")

            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download Generated CSV",
                csv,
                "generated_leads.csv",
                "text/csv",
            )

    # ---- MANUAL CSV MODE ----
    if mode == "Upload CSV Manually":
        st.subheader("2️⃣ Upload CSV")
        uploaded = st.file_uploader("Upload CSV file", type=["csv"])

        if uploaded:
            df = load_uploaded_csv(uploaded)
            st.write(f"Loaded **{len(df)}** rows")
            st.dataframe(df.head())

            cols = list(df.columns)
            email_col = st.selectbox("Email column", cols)

            name_col = st.selectbox("Name column (optional)", ["(none)"] + cols)
            company_col = st.selectbox("Company column (optional)", ["(none)"] + cols)

            if name_col == "(none)":
                name_col = None
            if company_col == "(none)":
                company_col = None

    # ---- TEMPLATE ----
    st.subheader("3️⃣ Email Template")

    subject_template = st.text_input(
        "Subject",
        "Exploring opportunities to contribute at your startup",
    )

    body_template = st.text_area(
        "Body",
        height=260,
        value=(
            "Hi {name},\n\n"
            "I came across {company} and really liked what you're building.\n"
            "I'm exploring opportunities at fast-moving startups.\n\n"
            "Would love to connect and see if I can add value.\n\n"
            "Best regards,\nYour Name"
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
    st.subheader("📝 Email Preview")
    if df is not None and email_col is not None:
        idx = st.number_input(
            "Preview email for row",
            min_value=0,
            max_value=len(df) - 1,
            value=0,
        )

        row = df.iloc[int(idx)]
        preview_email = build_email(
            sender=accounts[0]["email"] if accounts else "example@example.com",
            recipient=str(row[email_col]),
            subject_template=subject_template,
            body_template=body_template,
            row=row,
            name_col=name_col,
            company_col=company_col,
        )

        st.markdown("**Subject**")
        st.code(preview_email["Subject"])

        st.markdown("**Body**")
        st.code(preview_email.get_content())

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
        st.session_state.total_emails = len(rows)
        st.session_state.emails_sent = 0

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
