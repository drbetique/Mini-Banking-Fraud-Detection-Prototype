import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import requests
import time 

# --- Configuration ---
st.set_page_config(
    page_title="Mini Banking Fraud Detection Prototype",
    layout="wide"
)

# Database constants (Only needed for load_all_transactions)
DB_NAME = 'bank_data.db'
TABLE_NAME = 'transactions'

# CRITICAL API URL: This must be updated with the public URL of your deployed FastAPI service!
API_URL = "https://mini-fraud-api-vib-c7ehh4h6aqd0bxbb.swedencentral-01.azurewebsites.net/api/v1/anomalies"

# --- API KEY (MUST match the AZURE_API_KEY environment variable set in Azure) ---
API_KEY = "s3cr3t-pr0t0typ3-k3y-2025" # **REPLACE WITH YOUR ACTUAL SECRET KEY**
HEADERS = {"X-API-Key": API_KEY}


# --- Action Function: Update Status ---

def update_transaction_status(transaction_id, status):
    """Sends a PUT request to the API to update a transaction's status."""
    
    # Base URL is everything up to /api/v1/
    api_base_url = API_URL.rsplit('/', 1)[0] # Trims '/anomalies'
    put_url = f"{api_base_url}/{transaction_id}"
    
    try:
        with st.spinner(f"Updating status for {transaction_id}..."):
            response = requests.put(
                put_url, 
                params={"new_status": status.upper()},
                headers=HEADERS
            )
            response.raise_for_status()
            
            # Clear the cache so the dashboard reloads data immediately
            st.cache_data.clear()
            
            st.toast(f"Status for {transaction_id[:8]}... updated to {status.upper()}", icon="✅")
            time.sleep(1) # Wait for toast to display
            st.rerun() # Force Streamlit to rerun and display the updated data/alerts
            
    except requests.exceptions.RequestException as e:
        st.error(f"Error updating status for {transaction_id}. Details: {e}")


# --- Helper Function for Color Coding ---

def color_score(score):
    """Returns an HTML string to display the score with a colored background."""
    
    # 1. Define Risk Tiers
    if score >= 0.8:
        color = "#ff4b4b"  # Bright Red for High Risk
        risk_level = "HIGH"
    elif score >= 0.5:
        color = "#ffbd59"  # Amber/Yellow for Medium Risk
        risk_level = "MEDIUM"
    else:
        color = "#008000"  # Dark Green for Low/No Risk
        risk_level = "LOW"
        
    # 2. Return styled HTML
    html_code = (
        f'<div style="background-color: {color}; color: white; padding: 4px; '
        f'border-radius: 4px; text-align: center; font-weight: bold; '
        f'font-size: 13px; line-height: 1.2;">'
        f'{score:.3f} ({risk_level})'
        f'</div>'
    )
    return html_code


# --- Data Loading (Caching for performance) ---

@st.cache_data(ttl=600)
def load_anomalies():
    """Fetches anomaly data from the decoupled FastAPI backend via HTTP request."""
    st.info(f"Fetching anomaly data from API: {API_URL}")
    try:
        # Pass the headers with the API key
        response = requests.get(API_URL, headers=HEADERS) 
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        data = response.json().get('data', [])
        
        # Convert the returned JSON list back into a DataFrame
        anomaly_df = pd.DataFrame(data)
        
        # Ensure the score is numerical before being passed to color_score()
        if 'ml_anomaly_score' in anomaly_df.columns:
            # CLEANUP STEP 1: Remove any potential '\n' characters and convert to numeric
            anomaly_df['ml_anomaly_score'] = anomaly_df['ml_anomaly_score'].astype(str).str.replace('\n', '', regex=False).str.strip()
            anomaly_df['ml_anomaly_score'] = pd.to_numeric(anomaly_df['ml_anomaly_score'], errors='coerce').fillna(0)
        
        # CLEANUP STEP 2: Remove any potential '\n' characters from location column
        if 'location' in anomaly_df.columns:
            anomaly_df['location'] = anomaly_df['location'].astype(str).str.replace('\n', '', regex=False).str.strip()

        # Fill missing 'status' column if it's not provided by the API (or is null)
        if 'status' not in anomaly_df.columns:
             anomaly_df['status'] = 'NEW'
        else:
             anomaly_df['status'] = anomaly_df['status'].fillna('NEW').str.upper() # Ensure status is not NA

        return anomaly_df
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to API backend. Ensure 'uvicorn api:app' is running and the API_URL is correct. Error: {e}")
        return pd.DataFrame() # Return empty DataFrame on failure

@st.cache_data(ttl=600)
def load_all_transactions():
    """Loads all transactions directly from the local DB for summary stats."""
    # This function is not affected by the API key, but kept for completeness
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()
    return df


# --- Main Application ---

st.title("Mini Banking Fraud Detection Prototype 🛡️")

# Load dataframes
anomaly_df = load_anomalies()
all_df = load_all_transactions()
total_transactions = len(all_df)
total_anomalies = len(anomaly_df)

# --- NEW: Global Alert System ---
high_risk_new_anomalies = anomaly_df[
    (anomaly_df['ml_anomaly_score'] >= 0.8) & 
    (anomaly_df['status'] == 'NEW')
]
num_alerts = len(high_risk_new_anomalies)

if num_alerts > 0:
    st.error(
        f"🚨 **ACTIVE HIGH-RISK ALERT:** {num_alerts} unreviewed anomalies require immediate attention!", 
        icon="⚠️"
    )
else:
    st.success("System Status: All high-risk anomalies have been reviewed.")


# Tabs
tab1, tab2 = st.tabs(["Summary Dashboard", "Anomaly Review Queue"])

with tab1:
    st.header("Risk Overview")
    
    col1, col2, col3 = st.columns(3)
    
    # KIP 1: Total Transactions
    with col1:
        st.metric(label="Total Transactions Analyzed", value=f"{total_transactions:,.0f}")

    # KIP 2: Total Anomalies Found
    with col2:
        # Highlighted if anomalies exist
        metric_style = "color: #ff4b4b;" if total_anomalies > 0 else "color: #008000;"
        st.markdown(f'<p style="{metric_style} font-size: 1.5em; font-weight: bold;">{total_anomalies:,.0f}</p>', unsafe_allow_html=True)
        st.markdown('<p style="font-size: 0.8em; margin-top: -1.5em;">Total Anomalies Flagged</p>', unsafe_allow_html=True)
        
    # KIP 3: Fraud Rate
    with col3:
        fraud_rate = (total_anomalies / total_transactions) * 100 if total_transactions else 0
        st.metric(label="Anomaly Rate", value=f"{fraud_rate:.2f}%")
        
    st.markdown("---")

    col_chart, col_map = st.columns([1, 1])

    with col_chart:
        st.subheader("Anomalies by Merchant Category")
        if not anomaly_df.empty:
            # Filter only NEW or INVESTIGATED anomalies for charts
            chart_df = anomaly_df[anomaly_df['status'] != 'DISMISSED']
            
            category_counts = chart_df['merchant_category'].value_counts().reset_index()
            category_counts.columns = ['Merchant Category', 'Count']
            
            fig_bar = px.bar(
                category_counts,
                x='Merchant Category',
                y='Count',
                color='Merchant Category',
                title='Flagged Anomalies by Type (Active)',
                template='plotly_dark'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("No anomalies to display.")

    with col_map:
        st.subheader("Anomalies by Status")
        if not anomaly_df.empty:
            status_counts = anomaly_df['status'].value_counts().reset_index()
            status_counts.columns = ['Status', 'Count']
            
            fig_pie = px.pie(
                status_counts,
                values='Count',
                names='Status',
                title='Anomaly Status Distribution',
                template='plotly_dark'
            )
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.warning("No anomalies to display.")


with tab2:
    st.header(f"Review Queue: {total_anomalies} Anomalies Flagged")
    
    if anomaly_df.empty:
        st.success("No anomalies currently flagged for review.")
    else:
        # --- Sidebar Filters ---
        st.sidebar.header("Filter Anomalies")
        
        # Filter 1: Transaction Amount
        min_amount = anomaly_df['amount'].min()
        max_amount = anomaly_df['amount'].max()
        amount_range = st.sidebar.slider(
            "Transaction Amount (€)",
            float(min_amount),
            float(max_amount),
            (float(min_amount), float(max_amount))
        )

        # Filter 2: Alert Reason
        reasons = ['All'] + anomaly_df['alert_reason'].unique().tolist()
        selected_reason = st.sidebar.selectbox("Alert Reason", options=reasons)
        
        # Filter 3: Status
        # 1. Define the full list of available status options from the data
        statuses = ['All'] + anomaly_df['status'].unique().tolist()
        
        # 2. Define desired defaults and filter them against the available statuses
        desired_defaults = ['NEW', 'INVESTIGATED']
        valid_defaults = [s for s in desired_defaults if s in statuses]

        # 3. Use the filtered list as the default
        selected_status = st.sidebar.multiselect(
            "Review Status", 
            options=statuses, 
            default=valid_defaults # Use the list guaranteed to be valid
        )

        # Apply Filters
        filtered_df = anomaly_df[
            (anomaly_df['amount'] >= amount_range[0]) & 
            (anomaly_df['amount'] <= amount_range[1])
        ]
        
        if selected_reason != 'All':
            filtered_df = filtered_df[filtered_df['alert_reason'] == selected_reason]
        
        if 'All' not in selected_status:
             filtered_df = filtered_df[filtered_df['status'].isin([s.upper() for s in selected_status])]


        # Display filtered count
        st.info(f"Displaying {len(filtered_df):,.0f} Anomalies for Review")


        # --- MANUAL HTML TABLE DISPLAY ---
        
        # 1. Define the final columns to show
        # ADD 'status' and 'action' columns
        display_cols = [
            'status', 'ml_anomaly_score', 'timestamp', 'alert_reason', 
            'amount', 'account_id', 'merchant_category', 'location', 
            'transaction_id'
        ]
        
        # 2. Start the HTML table structure
        html = '<table style="width:100%; border-collapse: collapse; font-size: 14px;">'
        
        # Add the header row (Styling for dark background header)
        html += '<tr style="background-color: #333; color: white; border-bottom: 2px solid #555;">'
        
        for col in display_cols:
            header_name = col.replace('_', ' ').title().replace('Ml ', 'ML ')
            html += f'<th style="padding: 10px 8px; text-align: left; font-weight: bold;">{header_name}</th>'
            
        # Add a header for the new Action column
        html += f'<th style="padding: 10px 8px; text-align: center; font-weight: bold; width: 200px;">Action</th>'
        
        html += '</tr>'
        
        # 3. Add data rows
        for index, row in filtered_df.iterrows():
            
            # Alternate row background for better readability
            row_style = 'background-color: #1e1e1e;' if index % 2 == 0 else 'background-color: #2a2a2a;'
            html += f'<tr style="border-bottom: 1px solid #444; {row_style}">'
            
            # --- CUSTOM CELL RENDERING ---
            for col in display_cols:
                
                cell_content = row[col]
                
                if col == 'status':
                    # Apply color styling to the status
                    status_color = {'NEW': '#FF6347', 'INVESTIGATED': '#1E90FF', 'FRAUD': '#FF4500', 'DISMISSED': '#008000'}
                    bg_color = status_color.get(str(cell_content).upper(), '#555555')
                    styled_content = (
                         f'<div style="background-color: {bg_color}; color: white; padding: 4px; '
                         f'border-radius: 4px; text-align: center; font-weight: bold; '
                         f'font-size: 13px; line-height: 1.2;">'
                         f'{str(cell_content).upper()}'
                         f'</div>'
                    )
                    html += f'<td style="padding: 4px 8px;">{styled_content}</td>'
                
                elif col == 'ml_anomaly_score':
                    score = row['ml_anomaly_score'] if pd.notna(row['ml_anomaly_score']) else 0
                    styled_content = color_score(score)
                    html += f'<td style="padding: 4px 8px;">{styled_content}</td>'
                
                elif col == 'amount':
                    formatted_amount = f"€{cell_content:,.2f}"
                    html += f'<td style="padding: 8px; color: #78a9ff;">{formatted_amount}</td>'
                
                elif col == 'timestamp':
                    try:
                        formatted_time = pd.to_datetime(cell_content).strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_time = str(cell_content) 
                    html += f'<td style="padding: 8px;">{formatted_time}</td>'
                
                else:
                    html += f'<td style="padding: 8px;">{cell_content}</td>'
            
            # --- NEW: Action Button Column ---
            html += f'<td style="padding: 8px; text-align: center;">'
            
            # Use Streamlit buttons and key to ensure unique action per row
            if row['status'] == 'NEW' or row['status'] == 'INVESTIGATED':
                
                # Button 1: Mark as Fraud (High-Risk)
                # Buttons must be rendered outside the HTML string, then wrapped
                st.session_state[f'fraud_{row.transaction_id}'] = False
                st.session_state[f'dismiss_{row.transaction_id}'] = False
                
                # Check for button clicks here (Streamlit renders all buttons before running code)
                # The st.button calls must happen immediately after st.markdown(html, ...)
                # To handle buttons inside a loop, we collect the necessary data here
                
                # NOTE: Because Streamlit cannot mix st.markdown (HTML) with st.button 
                # inside a single cell/column in this way, we render the HTML first 
                # and use a hidden mechanism to process the button actions later. 
                # However, for a fully functional solution in the standard Streamlit way,
                # we must use st.columns() for layout, not a raw HTML table.
                
                # For the purposes of deployment, we must remove the HTML structure 
                # and switch back to st.data_editor or st.dataframe + st.columns 
                # to allow the buttons to function correctly.
                
                # Since the current HTML table is a requirement for styling, 
                # we will use st.button *outside* the HTML string and assign 
                # a unique key for processing.
                
                pass # Placeholder: The actual button logic runs outside the HTML string

            elif row['status'] == 'FRAUD':
                html += '<span style="color: red; font-weight: bold;">CONFIRMED FRAUD</span>'
            
            elif row['status'] == 'DISMISSED':
                html += '<span style="color: green;">DISMISSED</span>'
                
            html += '</td>'
            
            html += '</tr>' # End of row
            
        html += '</table>' # End of table

        # 4. Render the final, correctly structured HTML table
        st.markdown(html, unsafe_allow_html=True)

        # 5. Process Button Actions (REQUIRED TO MAKE BUTTONS WORK WITH HTML TABLE)
        # We must iterate over the filtered DataFrame AGAIN to place the buttons
        # adjacent to the HTML table, as Streamlit buttons won't render inside raw HTML.
        
        st.markdown("<h4 style='color:#ccc; margin-top:20px;'>Transaction Actions</h4>", unsafe_allow_html=True)
        for index, row in filtered_df.iterrows():
            if row['status'] == 'NEW' or row['status'] == 'INVESTIGATED':
                
                col_id, col_fraud, col_dismiss = st.columns([1, 1, 1])
                
                with col_id:
                    st.markdown(f"**ID: `{row.transaction_id[:10]}...`**")

                with col_fraud:
                    if st.button('Confirm Fraud', key=f'fraud_action_{row.transaction_id}'):
                        update_transaction_status(row.transaction_id, 'FRAUD')

                with col_dismiss:
                    if st.button('Dismiss', key=f'dismiss_action_{row.transaction_id}'):
                        update_transaction_status(row.transaction_id, 'DISMISSED')
                
                st.markdown("---") # Separator for actions


# --- Footer ---
st.markdown("---")
st.caption("Developed by **Victor Ifeoluwa Betiku** | Prototype built using Python, SQLite, and Streamlit.")