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
st.set_page_config(page_title="Startup Outreach Mailer", layout="wide")

# -------------------------------------------------
# GLOBAL UI STYLES
# -------------------------------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.5rem;
    padding-bottom: 2rem;
}

.section {
    padding: 1.5rem;
    border-radius: 14px;
    background-color: #ffffff;
    box-shadow: 0 6px 18px rgba(0,0,0,0.06);
    margin-bottom: 1.5rem;
}

.stButton > button {
    background-color: #4F46E5;
    color: white;
    border-radius: 10px;
    padding: 0.6rem 1.4rem;
    font-weight: 600;
}
.stButton > button:hover {
    background-color: #4338CA;
}

.stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
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
def normalize_df(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(" ", "_")
    )
    return df

@st.cache_data
def load_master_csv() -> pd.DataFrame:
    df = pd.read_csv("data/master_companies.csv")
    return normalize_df(df)

@st.cache_data
def load_uploaded_csv(file) -> pd.DataFrame:
    df = pd.read_csv(file)
    return normalize_df(df)

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

# -------------------------------------------------
# MAIN APP
# -------------------------------------------------
def main():

    # HERO
    st.markdown("""
    <div class="section">
        <h1>🚀 Startup Outreach Email Automation</h1>
        <p style="font-size:1.05rem;color:#444;">
        Send <b>personalised cold emails</b> safely using company-based lead selection
        or your own CSV — with preview and sender rotation.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # VIDEO
    with st.container():
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("🎥 How to Use This Tool")
        st.components.v1.iframe(
            "https://drive.google.com/file/d/1EG3EIA-JOh0FDqH85ei1RTWsTMwtr3hI/preview",
            height=420,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # INPUT MODE
    with st.container():
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("1️⃣ Choose Lead Source")

        mode = st.radio(
            "How would you like to add email leads?",
            ["📂 Generate from Platform Data", "📄 Upload CSV Manually"],
            horizontal=True,
        )
        st.markdown('</div>', unsafe_allow_html=True)

    df = None
    email_col = name_col = company_col = None

    # PLATFORM DATA MODE
    if "Platform" in mode:
        master_df = load_master_csv()

        with st.container():
            st.markdown('<div class="section">', unsafe_allow_html=True)
            st.subheader("2️⃣ Select Companies")

            col1, col2 = st.columns([2, 1])
            with col1:
                companies = sorted(master_df["company"].dropna().unique())
                selected_companies = st.multiselect(
                    "Choose up to 5 companies",
                    companies,
                    max_selections=5,
                )

            with col2:
                limit = st.number_input(
                    "Emails to use",
                    min_value=1,
                    max_value=50,
                    value=10,
                )

            st.markdown('</div>', unsafe_allow_html=True)

        if selected_companies:
            df = (
                master_df[master_df["company"].isin(selected_companies)]
                .head(limit)
                .copy()
            )
            email_col = "email"
            name_col = "name"
            company_col = "company"

    # MANUAL CSV MODE
    if "Upload" in mode:
        with st.container():
            st.markdown('<div class="section">', unsafe_allow_html=True)
            st.subheader("2️⃣ Upload CSV")

            uploaded = st.file_uploader("Upload CSV file", type=["csv"])
            if uploaded:
                df = load_uploaded_csv(uploaded)
                st.dataframe(df.head(), use_container_width=True)

                cols = list(df.columns)
                email_col = st.selectbox("Email column", cols)
                name_col = st.selectbox("Name column (optional)", ["(none)"] + cols)
                company_col = st.selectbox("Company column (optional)", ["(none)"] + cols)

                if name_col == "(none)":
                    name_col = None
                if company_col == "(none)":
                    company_col = None

            st.markdown('</div>', unsafe_allow_html=True)

    # DATA PREVIEW
    if df is not None:
        with st.container():
            st.markdown('<div class="section">', unsafe_allow_html=True)
            st.subheader("📊 Selected Leads")
            df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)

    # EMAIL TEMPLATE
    with st.container():
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("3️⃣ Email Content")

        subject_template = st.text_input(
            "Email Subject",
            "Exploring opportunities at {company}",
        )

        body_template = st.text_area(
            "Email Body",
            height=240,
            help="Use {name} and {company} for personalization",
            value=(
                "Hi {name},\n\n"
                "I came across {company} and really liked what you're building.\n"
                "I'm exploring opportunities at fast-moving startups.\n\n"
                "Would love to connect.\n\n"
                "Best regards,\nYour Name"
            ),
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # SENDER ACCOUNTS
    with st.container():
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("4️⃣ Sender Accounts")

        accounts = []
        for i in range(1, 5):
            with st.expander(f"📧 Sender Account {i}", expanded=(i == 1)):
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
        st.markdown('</div>', unsafe_allow_html=True)

    # PREVIEW
    if df is not None and email_col:
        with st.container():
            st.markdown('<div class="section">', unsafe_allow_html=True)
            st.subheader("📝 Email Preview")

            idx = st.number_input(
                "Preview email for row",
                0,
                len(df) - 1,
                0,
            )

            row = df.iloc[int(idx)]
            preview_email = build_email(
                accounts[0]["email"] if accounts else "example@example.com",
                str(row[email_col]),
                subject_template,
                body_template,
                row,
                name_col,
                company_col,
            )

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Subject**")
                st.code(preview_email["Subject"])
            with col2:
                st.markdown("**Body**")
                st.code(preview_email.get_content())

            st.markdown('</div>', unsafe_allow_html=True)

    # SEND
    with st.container():
        st.markdown('<div class="section">', unsafe_allow_html=True)
        st.subheader("🚀 Launch Campaign")

        delay_seconds = st.number_input(
            "Delay between emails (seconds)",
            min_value=1.0,
            value=2.0,
            step=0.5,
        )

        if st.button("🚀 Start Sending Emails"):
            if df is None or not accounts:
                st.error("Please add leads and sender accounts.")
                return

            rows = [row for _, row in df.iterrows() if str(row[email_col]).strip()]
            st.session_state.total_emails = len(rows)
            st.session_state.emails_sent = 0

            progress_bar = st.progress(0)
            buckets = {i: [] for i in range(len(accounts))}
            for i, row in enumerate(rows):
                buckets[i % len(accounts)].append(row)

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

            st.success(f"🎉 Sent {total_sent} emails successfully!")
        st.markdown('</div>', unsafe_allow_html=True)

# -------------------------------------------------
if __name__ == "__main__":
    main()
