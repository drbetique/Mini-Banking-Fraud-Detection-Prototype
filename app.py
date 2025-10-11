import streamlit as st
import pandas as pd
import sqlite3
import os

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
        color = "#008000"  # Green for Low/No Risk (use a dark green for contrast)
        risk_level = "LOW"
        
    # 2. Return styled HTML
    html_code = f"""
    <div style="background-color: {color}; color: white; padding: 5px; border-radius: 5px; 
                text-align: center; font-weight: bold; font-size: 14px;">
        {score:.3f} ({risk_level})
    </div>
    """
    return html_code

# Import the core detection logic function from your file
from detection_logic import detect_anomalies, DB_NAME, TABLE_NAME

# --- Configuration for Streamlit App ---
st.set_page_config(
    page_title="Mini AFC Fraud Detection Prototype",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- Helper Functions (Using caching for performance) ---

@st.cache_data
def load_total_data():
    """Load all transaction data for total counts (cached)."""
    if not os.path.exists(DB_NAME):
        return pd.DataFrame()
        
    conn = sqlite3.connect(DB_NAME)
    df = pd.read_sql_query(f"SELECT * FROM {TABLE_NAME}", conn)
    conn.close()
    
    # Convert timestamp for charting
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['date'] = df['timestamp'].dt.date
    
    return df

@st.cache_data
def get_anomalies_data(total_df):
    """Run the anomaly detection logic (cached)."""
    # Note: We now pass total_df to force re-run if underlying data changes
    return detect_anomalies()

# --- Load Data Once ---
total_df = load_total_data()
if total_df.empty:
    st.error(f"Database file '{DB_NAME}' not found. Please run 'setup_db.py'.")
    st.stop() # Stop if data loading failed

anomalies_df = get_anomalies_data(total_df)

# --- Global Metrics ---
total_transactions = len(total_df)
total_anomalies = len(anomalies_df)
anomaly_rate = (total_anomalies / total_transactions) * 100 if total_transactions > 0 else 0

st.title("Mini Banking Fraud Detection Prototype")
st.markdown("---")


# ----------------------------------------------------
# 1. TABBED NAVIGATION
# ----------------------------------------------------

tab1, tab2 = st.tabs(["Dashboard Summary", "Anomaly Review"])

# ====================================================
# TAB 1: DASHBOARD SUMMARY
# ====================================================
with tab1:
    
    st.header("Overall Performance Metrics")
    
    # Enhanced Metric Cards
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Transactions Analyzed", f"{total_transactions:,}")

    with col2:
        st.metric("Potential Anomalies Detected", f"{total_anomalies:,}")
        
    with col3:
        # Highlighted metric for quick attention
        st.markdown(f"""
            <div style="background-color: #ff4b4b; padding: 10px; border-radius: 5px; color: white;">
                <p style="font-size: 14px; margin: 0;">Anomaly Rate</p>
                <h3 style="margin: 0;">{anomaly_rate:.2f} %</h3>
            </div>
            """, unsafe_allow_html=True)
        # st.metric("Anomaly Rate", f"{anomaly_rate:.2f} %") # Standard metric as alternative
        
    st.markdown("---")

    # --- Chart A: Transaction Volume Trend ---
    st.subheader("Transaction Volume Over Time (Last 30 Days)")
    
    # Group total transactions by date
    daily_volume = total_df.groupby('date').size().reset_index(name='Daily Volume')
    daily_volume['date'] = daily_volume['date'].astype(str) # Convert date to string for charting
    
    st.line_chart(daily_volume, x='date', y='Daily Volume', use_container_width=True)
    st.caption("Monitoring the general transaction baseline provides crucial context.")
    
    st.markdown("---")
    
    # --- Chart B: Anomaly Distribution by Location ---
    st.subheader("Anomaly Concentration by Location")
    
    if not anomalies_df.empty:
        location_counts = anomalies_df['location'].value_counts().reset_index()
        location_counts.columns = ['Location', 'Anomaly Count']
        st.bar_chart(location_counts, x='Location', y='Anomaly Count', use_container_width=True)
        st.caption("Helps identify geographical hotspots for potential fraud.")

# ====================================================
# TAB 2: ANOMALY REVIEW
# ====================================================
with tab2:
    st.header("Detailed Case Inspection and Filtering")
    
    if anomalies_df.empty:
        st.success("No anomalies detected in the current dataset!")
    else:
        # 2. Add Sidebar Filters (This remains the same)
        st.sidebar.header("Filter Anomalies")

        # Filter by Amount
        min_amt = float(anomalies_df['amount'].min())
        max_amt = float(anomalies_df['amount'].max())
        amount_range = st.sidebar.slider(
            "Transaction Amount ($)",
            min_value=min_amt,
            max_value=max_amt,
            value=(min_amt, max_amt)
        )

        # Filter by Alert Reason
        all_reasons = ['All'] + sorted(anomalies_df['alert_reason'].unique().tolist())
        selected_reason = st.sidebar.selectbox(
            "Alert Reason",
            options=all_reasons
        )

        # Apply Filters
        filtered_df = anomalies_df[
            (anomalies_df['amount'] >= amount_range[0]) & 
            (anomalies_df['amount'] <= amount_range[1])
        ]

        if selected_reason != 'All':
            # Use string contains for combined reasons (e.g., 'High Value & Suspicious Combo')
            filtered_df = filtered_df[filtered_df['alert_reason'].str.contains(selected_reason)]

        # 3. Display Filtered Results
        st.subheader(f"Displaying {len(filtered_df):,} Anomalies for Review")

        # Format the data for better display in the UI
        display_df = filtered_df.copy()
        # --- Apply Color Coding to ML Score ---
        display_df['ML Anomaly Score'] = display_df['ml_anomaly_score'].apply(color_score)
        
        display_df['timestamp'] = pd.to_datetime(display_df['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
        
        # Drop the original numerical column
        display_df = display_df.drop(columns=['ml_anomaly_score'])

        # Reorder and select columns for a clearer analyst view
        display_cols = [
            'ML Anomaly Score', # USE THE NEW COLUMN NAME
            'timestamp', 
            'alert_reason', 
            'amount', 
            'account_id', 
            'merchant_category', 
            'location', 
            'transaction_id'
        ]
        
        # IMPORTANT: When displaying HTML content, we must use markdown instead of st.dataframe
        # Since st.dataframe doesn't support HTML styling inside cells, we render the table manually.
        
        # Display the main table using st.dataframe for simplicity (Streamlit has been updated 
        # to sometimes handle simple HTML in dataframes, but it's not guaranteed). 
        # A more robust solution is a custom component like streamlit-aggrid, but we'll try simple st.dataframe first.

        st.dataframe(
            display_df[display_cols], 
            use_container_width=True, 
            hide_index=True,
            # CRITICAL: This is how we allow the HTML from our color_score function to render
            unsafe_allow_html=True 
        )
    
# Footer
st.markdown("---")
st.caption("Developed by **Victor Betiku** | Prototype built using Python, SQLite, and Streamlit.")
