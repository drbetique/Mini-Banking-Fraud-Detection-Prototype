# Grafana Setup Walkthrough - Live Guide

## Step 1: Login to Grafana

**URL:** http://localhost:3001

You should see a login screen.

**Enter:**
- **Email or username:** `admin`
- **Password:** `admin`

**Click:** "Log in"

---

## Step 2: Skip Password Change

You'll see a prompt: "Change Password"

**Click:** "Skip" (bottom of the form)

*Note: In production, you should change this, but for testing, we can skip.*

---

## Step 3: You're Now on the Home Screen

You should see:
- **Welcome to Grafana** banner at the top
- Left sidebar with menu options
- Main area with "Add your first data source" prompt

---

## Step 4: Add Prometheus Data Source

### Option A: Using the Quick Link (Easiest)

1. Look for a card that says **"Add your first data source"** or **"Connections"**
2. **Click** on it

### Option B: Using the Menu

1. **Click** the hamburger menu (☰) in the top-left corner
2. **Hover** over **"Connections"**
3. **Click** **"Data sources"**

You should now see the "Data sources" page.

---

## Step 5: Click "Add Data Source"

On the Data sources page:

1. **Click** the blue button **"Add data source"** or **"Add new data source"**

You'll see a list of data source types (Prometheus, MySQL, PostgreSQL, etc.)

---

## Step 6: Select Prometheus

1. **Scroll down** or use the search box
2. **Type:** `Prometheus`
3. **Click** on the **Prometheus** card

You'll now see the Prometheus configuration page.

---

## Step 7: Configure Prometheus

You should see a form with several fields. Here's what to fill in:

### Basic Settings:

**Name:** (leave as default)
```
Prometheus
```

**URL:** (IMPORTANT - Change this!)
```
http://prometheus:9090
```

⚠️ **Important:** Use `prometheus:9090` NOT `localhost:9090`
This is because Grafana runs inside Docker and needs to use the Docker service name.

### Other Settings:

**Access:** Proxy (leave as default)

**All other fields:** Leave as default (you can scroll down to see them)

---

## Step 8: Save and Test

1. **Scroll down** to the bottom of the page
2. **Click** the green button **"Save & test"**

**You should see:**
✅ A green banner that says: **"Successfully queried the Prometheus API."**

If you see this, congratulations! Prometheus is connected! 🎉

### Troubleshooting if it fails:

If you see a red error:
```bash
# Check if Prometheus is running
docker-compose ps prometheus

# Check if it's accessible
curl http://localhost:9090/api/v1/status/config
```

---

## Step 9: Navigate to Dashboards

Now that Prometheus is connected, let's create a dashboard!

1. **Click** the hamburger menu (☰) in the top-left
2. **Click** **"Dashboards"**

You should see the Dashboards page.

---

## Step 10: Import the Dashboard

### Method 1: Upload JSON File (Easiest)

1. On the Dashboards page, **click** **"New"** (blue button on the right)
2. **Click** **"Import"** from the dropdown

You'll see the "Import dashboard" page with options:
- Import via grafana.com
- Import via panel json
- Upload JSON file

3. **Click** **"Upload JSON file"**

4. **Browse** to your project folder:
   ```
   C:\Users\victo\Desktop\Bank Prototype\grafana-dashboard.json
   ```

5. **Select** the file and **click** "Open"

6. You'll see a preview of the dashboard. **Click** **"Import"** at the bottom

**🎉 Success!** You should now see your dashboard with 4 panels!

### Method 2: Copy-Paste JSON (Alternative)

If the file upload doesn't work:

1. Open the file `grafana-dashboard.json` in Notepad
2. **Copy** all the content (Ctrl+A, Ctrl+C)
3. In Grafana, on the Import page:
   - **Paste** the JSON into the **"Import via panel json"** text box
   - **Click** **"Load"**
   - **Click** **"Import"**

---

## Step 11: View Your Dashboard!

You should now see a dashboard with 4 panels:

```
┌─────────────────────────────┬─────────────────────────────┐
│  Transaction Processing     │  Total Anomalies Detected   │
│         Rate                │          (Number)           │
│   📈 Line Graph             │      📊 Big Number          │
└─────────────────────────────┴─────────────────────────────┘

┌─────────────────────────────┬─────────────────────────────┐
│  Anomaly Detection Rate     │  Processing Error Rate      │
│   📈 Line Graph             │      📈 Line Graph          │
└─────────────────────────────┴─────────────────────────────┘
```

### What You Should See:

**If the producer is NOT running yet:**
- All panels will show **"No data"** or flat lines at 0
- This is NORMAL - we haven't started processing transactions yet

**If the producer IS running:**
- You'll see real-time data
- Lines will move and update
- Numbers will change

---

## Step 12: Understanding the Panels

### Panel 1: Transaction Processing Rate
- **What it shows:** Transactions processed per second
- **Expected:** Will be 0 until you start the producer

### Panel 2: Total Anomalies Detected
- **What it shows:** Cumulative count of anomalies
- **Expected:** Will be 0 initially, then increase as anomalies are found

### Panel 3: Anomaly Detection Rate
- **What it shows:** How many anomalies per second are being detected
- **Expected:** Spikes when anomalies are found

### Panel 4: Processing Error Rate
- **What it shows:** Errors per second
- **Expected:** Should always be near 0 (no errors)

---

## Step 13: Configure Dashboard Settings (Optional)

At the top of the dashboard, you'll see:

### Time Range (top right)
- Default: "Last 15 minutes"
- Click to change to "Last 5 minutes", "Last 1 hour", etc.

### Refresh Rate (top right)
- Click the dropdown next to the time range
- Select **"5s"** for 5-second auto-refresh
- The dashboard will now update every 5 seconds automatically!

### Save Dashboard
- Click the **💾 Save** icon (top right)
- This saves any changes you make

---

## Step 14: Test with Real Data!

Now let's generate some data to see the dashboard in action!

### In a new terminal/command prompt:

```bash
cd "C:\Users\victo\Desktop\Bank Prototype"

# Start the producer (this streams transactions)
python producer.py
```

**You should see logs like:**
```
2025-12-18 10:30:45 - __main__ - INFO - Kafka Producer connected successfully
2025-12-18 10:30:46 - __main__ - INFO - Sent transaction (1/20000)
2025-12-18 10:30:47 - __main__ - INFO - Sent transaction (2/20000)
```

### Switch back to Grafana

**Within 5-10 seconds, you should see:**
- 📈 Lines start moving in the graphs
- 🔢 Numbers start increasing
- 🎨 Dashboard comes alive with real data!

---

## Step 15: Understanding What You're Seeing

### Normal Behavior:

**Transaction Processing Rate:**
- Should show ~1 transaction/second (if STREAM_DELAY_SECONDS=1)
- Smooth, steady line

**Total Anomalies Detected:**
- Will slowly increase as anomalies are found
- Typically 0.5-2% of total transactions

**Anomaly Detection Rate:**
- Will spike when anomalies are detected
- Usually low, with occasional spikes

**Processing Error Rate:**
- Should be 0 or very close to 0
- If you see errors, check the logs

---

## Step 16: Explore Grafana Features

### Click on a Panel

1. **Click** on any panel title
2. You'll see options:
   - **View** - Full-screen view
   - **Edit** - Modify the panel
   - **Share** - Get a link or embed code
   - **Explore** - Dig deeper into the data

### Try "Explore"

1. **Click** on a panel → **Explore**
2. You'll see the Prometheus query that powers the panel
3. You can modify the query and test it
4. Click **"Run query"** to see results

### Zoom In/Out

- **Click and drag** on a graph to zoom into a time range
- **Click** the "Zoom out" button to reset

---

## Common Issues and Solutions

### Issue 1: "Data source is not working"

**Solution:**
```bash
# Restart Grafana
docker-compose restart grafana

# Wait 10 seconds, then try again
```

### Issue 2: "No data" in all panels

**Possible causes:**

1. **Producer not running** (Most common)
   ```bash
   # Start the producer
   python producer.py
   ```

2. **Detection service not running**
   ```bash
   # Check if it's running
   docker-compose ps detection_service

   # If not, start it
   docker-compose up -d detection_service
   ```

3. **Prometheus not scraping metrics**
   ```bash
   # Check Prometheus targets
   # Open: http://localhost:9090/targets
   # Both should be "UP"
   ```

### Issue 3: Dashboard disappeared

**Solution:**
1. Click **Dashboards** in the left menu
2. You should see "Fraud Detection System" in the list
3. Click on it to open

---

## Step 17: Create Alerts (Advanced - Optional)

You can set up alerts to notify you when things go wrong!

1. **Click** on the "Processing Error Rate" panel
2. **Click** **Edit**
3. **Click** the **"Alert"** tab (top of the edit screen)
4. **Click** **"Create alert rule from this panel"**
5. **Configure:**
   - Name: "High Error Rate"
   - Condition: WHEN avg() IS ABOVE 0.1
   - For: 5 minutes
6. **Click** **"Save"**

Now you'll get an alert if errors exceed 0.1 per second for 5 minutes!

---

## Step 18: Add More Panels (Advanced - Optional)

Want to add your own panel?

1. **Click** the **"Add"** button (top right, looks like a + icon)
2. **Click** **"Visualization"**
3. **Select** your data source: **Prometheus**
4. **Enter a query:**
   ```promql
   transactions_processed_total
   ```
5. **Click** **"Run queries"**
6. You'll see the data visualized!
7. **Customize:**
   - Change chart type (Time series, Gauge, Stat, etc.)
   - Modify colors
   - Add thresholds
8. **Click** **Apply** to add to dashboard

---

## Quick Reference: Useful Prometheus Queries

Copy these into Grafana panels:

```promql
# Total transactions processed
transactions_processed_total

# Transactions per second (last 5 minutes)
rate(transactions_processed_total[5m])

# Total anomalies
anomalies_detected_total

# Anomalies per second
rate(anomalies_detected_total[5m])

# Anomaly percentage
(anomalies_detected_total / transactions_processed_total) * 100

# Errors per second
rate(transaction_processing_errors_total[5m])

# Average transaction rate over 1 hour
avg_over_time(rate(transactions_processed_total[5m])[1h:])
```

---

## You're Done! 🎉

Your Grafana dashboard is now set up and running!

### What You've Accomplished:

✅ Connected Grafana to Prometheus
✅ Imported a pre-built dashboard
✅ Configured auto-refresh
✅ Can view real-time metrics
✅ Can explore and customize panels

### Next Steps:

1. **Keep the producer running** to see data flow
2. **Launch Streamlit** (`streamlit run app.py`) for the analyst dashboard
3. **Explore** the other panels and features
4. **Customize** the dashboard to your needs

**Need help?** Check the troubleshooting section above or ask me!
