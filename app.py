import streamlit as st
import pandas as pd
import os
import time
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from typing import List, Dict, Any, Optional

st.set_page_config(page_title="Startup Outreach Mailer", layout="wide")

# ---------------- SESSION STATE ----------------
if "sent_this_session" not in st.session_state:
    st.session_state.sent_this_session = set()

if "emails_sent" not in st.session_state:
    st.session_state.emails_sent = 0


@st.cache_data
def load_data(file) -> pd.DataFrame:
    return pd.read_csv(file)


def safe_format(template: str, ctx: Dict[str, Any]) -> str:
    try:
        return template.format(**ctx)
    except:
        return template


# ---------------- BREVO SEND FUNCTION ----------------
def send_batch_for_account(
    account_config,
    recipients_rows,
    email_col,
    subject_template,
    body_template,
    name_col,
    company_col,
    delay_seconds,
    progress_bar,
):

    sent_count = 0

    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key["api-key"] = os.environ.get("BREVO_API_KEY")

    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
        sib_api_v3_sdk.ApiClient(configuration)
    )

    sender_email = account_config["email"]

    for row in recipients_rows:
        recipient = str(row[email_col]).strip()
        if not recipient:
            continue

        if recipient in st.session_state.sent_this_session:
            continue

        context = {}
        if name_col and name_col in row.index:
            context["name"] = row[name_col]
        if company_col and company_col in row.index:
            context["company"] = row[company_col]

        subject = safe_format(subject_template, context)
        body = safe_format(body_template, context)

        email = sib_api_v3_sdk.SendSmtpEmail(
            to=[{"email": recipient}],
            sender={"email": sender_email},
            subject=subject,
            text_content=body,
        )

        try:
            api_instance.send_transac_email(email)
            sent_count += 1
            st.session_state.sent_this_session.add(recipient)
            st.session_state.emails_sent += 1
            progress_bar.progress(
                st.session_state.emails_sent / st.session_state.total_emails
            )
        except ApiException as e:
            st.error(f"Failed to send to {recipient}: {e}")

        if delay_seconds > 0:
            time.sleep(delay_seconds)

    return sent_count


# ---------------- MAIN APP ----------------
def main():

    st.title("🚀 Startup Outreach Email Automation (Brevo)")
    st.write("Cold outreach tool using **Brevo API** (SMTP-free, Render-safe)")

    # 1️⃣ CSV Upload
    st.subheader("1️⃣ Upload CSV")
    uploaded = st.file_uploader("Upload CSV file", type=["csv"])

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

    # 2️⃣ Email Template
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
            "I came across {company} and really liked what you're building.\n"
            "I'm exploring opportunities at fast-moving startups.\n\n"
            "Would love to connect and see if I can add value.\n\n"
            "Best regards,\nYour Name\n\n"
            "If you'd prefer not to receive emails, just reply 'unsubscribe'."
        ),
    )

    # 3️⃣ Sender Account
    st.subheader("3️⃣ Sender Email (Brevo Verified)")

    accounts = []
    sender_email = st.text_input("Sender Email (must be verified in Brevo)")

    if sender_email:
        accounts.append({"email": sender_email})

    # 4️⃣ Delay
    st.subheader("4️⃣ Delay Between Emails")
    delay_seconds = st.number_input("Delay (seconds)", min_value=0.0, value=2.0, step=0.5)

    # 5️⃣ Preview
    st.subheader("5️⃣ Preview")
    if df is not None and email_col and accounts:
        idx = st.number_input("Preview row", 0, len(df) - 1, 0)
        row = df.iloc[int(idx)]

        ctx = {}
        if name_col:
            ctx["name"] = row[name_col]
        if company_col:
            ctx["company"] = row[company_col]

        st.code(safe_format(subject_template, ctx))
        st.code(safe_format(body_template, ctx))

    # 6️⃣ Send Emails
    st.subheader("6️⃣ Send Emails")

    if st.button("🚀 Start Sending"):

        if df is None:
            st.error("Upload a CSV first.")
            return

        if not accounts:
            st.error("Enter a sender email.")
            return

        rows = [row for _, row in df.iterrows() if str(row[email_col]).strip()]
        total = len(rows)

        st.session_state.total_emails = total
        st.session_state.emails_sent = 0
        st.write(f"Total valid recipients: **{total}**")

        progress_bar = st.progress(0)
        status = st.empty()

        status.text("📨 Sending emails...")

        total_sent = send_batch_for_account(
            account_config=accounts[0],
            recipients_rows=rows,
            email_col=email_col,
            subject_template=subject_template,
            body_template=body_template,
            name_col=name_col,
            company_col=company_col,
            delay_seconds=delay_seconds,
            progress_bar=progress_bar,
        )

        status.text("🎉 Done!")
        st.success(f"Sent **{total_sent} / {total}** emails successfully.")


if __name__ == "__main__":
    main()
