import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
import requests # Used to fetch data from the FastAPI API

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
API_KEY = "s3cr3t-pr0t0typ3-k3y-2025" # USED OUR ACTUAL SECRET HERE!
HEADERS = {"X-API-Key": API_KEY}


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
        # Make the HTTP request to your backend API
        response = requests.get(API_URL)
        response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
        
        data = response.json().get('data', [])
        
        # Convert the returned JSON list back into a DataFrame
        anomaly_df = pd.DataFrame(data)
        
        # Ensure the score is numerical before being passed to color_score()
        if 'ml_anomaly_score' in anomaly_df.columns:
            # CLEANUP STEP 1: Remove any potential '\n' characters from ml_anomaly_score string before converting to numeric
            anomaly_df['ml_anomaly_score'] = anomaly_df['ml_anomaly_score'].astype(str).str.replace('\n', '', regex=False).str.strip()
            anomaly_df['ml_anomaly_score'] = pd.to_numeric(anomaly_df['ml_anomaly_score'], errors='coerce')
        
        # CLEANUP STEP 2: Remove any potential '\n' characters from location column
        if 'location' in anomaly_df.columns:
            anomaly_df['location'] = anomaly_df['location'].astype(str).str.replace('\n', '', regex=False).str.strip()
        
        return anomaly_df
        
    except requests.exceptions.RequestException as e:
        st.error(f"Error connecting to API backend. Ensure 'uvicorn api:app' is running and the API_URL is correct. Error: {e}")
        return pd.DataFrame() # Return empty DataFrame on failure

@st.cache_data(ttl=600)
def load_all_transactions():
    """Loads all transactions directly from the local DB for summary stats."""
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
            category_counts = anomaly_df['merchant_category'].value_counts().reset_index()
            category_counts.columns = ['Merchant Category', 'Count']
            
            fig_bar = px.bar(
                category_counts,
                x='Merchant Category',
                y='Count',
                color='Merchant Category',
                title='Flagged Anomalies by Type',
                template='plotly_dark'
            )
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("No anomalies to display.")

    with col_map:
        st.subheader("Anomalies by Location")
        if not anomaly_df.empty:
            location_counts = anomaly_df['location'].value_counts().reset_index()
            location_counts.columns = ['Location', 'Count']
            
            st.dataframe(location_counts, use_container_width=True, hide_index=True)
        else:
            st.warning("No anomalies to display.")


with tab2:
    st.header(f"Review Queue: {total_anomalies} Anomalies Found")
    
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

        # Apply Filters
        filtered_df = anomaly_df[
            (anomaly_df['amount'] >= amount_range[0]) & 
            (anomaly_df['amount'] <= amount_range[1])
        ]
        
        if selected_reason != 'All':
            filtered_df = filtered_df[filtered_df['alert_reason'] == selected_reason]

        # Display filtered count
        st.info(f"Displaying {len(filtered_df):,.0f} Anomalies for Review")


        # --- MANUAL HTML TABLE DISPLAY (FIXED LOGIC) ---
        
        # 1. Define the final columns to show
        display_cols = [
            'ml_anomaly_score', 'timestamp', 'alert_reason', 
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
        html += '</tr>'
        
        # 3. Add data rows
        for index, row in filtered_df.iterrows():
            
            # Alternate row background for better readability
            row_style = 'background-color: #1e1e1e;' if index % 2 == 0 else 'background-color: #2a2a2a;'
            html += f'<tr style="border-bottom: 1px solid #444; {row_style}">'
            
            # --- CUSTOM CELL RENDERING ---
            for col in display_cols:
                
                cell_content = row[col]
                
                # Apply color styling to the ML score column
                if col == 'ml_anomaly_score':
                    # The value is already a float, remove the unnecessary .item() call.
                    # Use .fillna(0) in case the cleanup failed to parse a value
                    score = row['ml_anomaly_score'] if pd.notna(row['ml_anomaly_score']) else 0
                    styled_content = color_score(score)
                    html += f'<td style="padding: 4px 8px;">{styled_content}</td>'
                
                # Format currency for the amount column
                elif col == 'amount':
                    formatted_amount = f"€{cell_content:,.2f}"
                    html += f'<td style="padding: 8px; color: #78a9ff;">{formatted_amount}</td>'
                
                # Format timestamp
                elif col == 'timestamp':
                    try:
                        formatted_time = pd.to_datetime(cell_content).strftime('%Y-%m-%d %H:%M')
                    except:
                        formatted_time = str(cell_content) # Fallback if parsing fails
                    html += f'<td style="padding: 8px;">{formatted_time}</td>'
                
                # Standard text cell for all other columns
                else:
                    html += f'<td style="padding: 8px;">{cell_content}</td>'
            
            html += '</tr>' # End of row
            
        html += '</table>' # End of table

        # 4. Render the final, correctly structured HTML table
        st.markdown(html, unsafe_allow_html=True)


# --- Footer ---
st.markdown("---")
# REMEMBER TO REPLACE "[Your Name]" with your actual name
st.caption("Developed by **Victor Ifeoluwa Betiku** | Prototype built using Python, SQLite, and Streamlit.")

