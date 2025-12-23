# Grafana Setup Guide - Step by Step

## Quick Access

**URL:** http://localhost:3001
**Username:** admin
**Password:** admin

---

## Step 1: Initial Login

1. Open your browser and go to: **http://localhost:3001**
2. Enter credentials:
   - Username: `admin`
   - Password: `admin`
3. Click **Log in**
4. You'll be prompted to change password - you can click **Skip** for now

---

## Step 2: Add Prometheus Data Source

### Method 1: Using the UI

1. Click the **hamburger menu (☰)** on the left sidebar
2. Navigate to **Connections** → **Data sources**
3. Click the blue **Add data source** button
4. Find and click **Prometheus**
5. Configure:
   - **Name:** Leave as `Prometheus` (default)
   - **URL:** `http://prometheus:9090`
   - Leave other settings as default
6. Scroll down and click **Save & test**
7. You should see: ✅ **"Data source is working"**

### Method 2: Quick Configuration File

If the UI method doesn't work, create this file:

**File:** `grafana/provisioning/datasources/prometheus.yml`

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
```

Then restart Grafana:
```bash
docker-compose restart grafana
```

---

## Step 3: Create Your First Dashboard

### Quick Dashboard Import (Recommended)

1. **Create the dashboard JSON file:**

**File:** `fraud-detection-dashboard.json`

```json
{
  "annotations": {
    "list": []
  },
  "editable": true,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 0,
  "id": null,
  "links": [],
  "liveNow": false,
  "panels": [
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "tooltip": false,
              "viz": false,
              "legend": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "short"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 0
      },
      "id": 1,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(transactions_processed_total[5m])",
          "refId": "A",
          "legendFormat": "Transactions/sec"
        }
      ],
      "title": "Transaction Processing Rate",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 80
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 6,
        "x": 12,
        "y": 0
      },
      "id": 2,
      "options": {
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "anomalies_detected_total",
          "refId": "A"
        }
      ],
      "title": "Total Anomalies Detected",
      "type": "gauge"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "tooltip": false,
              "viz": false,
              "legend": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 6,
        "x": 18,
        "y": 0
      },
      "id": 3,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(anomalies_detected_total[5m])",
          "refId": "A",
          "legendFormat": "Anomalies/sec"
        }
      ],
      "title": "Anomaly Detection Rate",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisCenteredZero": false,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "tooltip": false,
              "viz": false,
              "legend": false
            },
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "never",
            "spanNulls": false,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              },
              {
                "color": "red",
                "value": 0.1
              }
            ]
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 0,
        "y": 8
      },
      "id": 4,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": true
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "rate(transaction_processing_errors_total[5m])",
          "refId": "A",
          "legendFormat": "Errors/sec"
        }
      ],
      "title": "Processing Error Rate",
      "type": "timeseries"
    },
    {
      "datasource": {
        "type": "prometheus",
        "uid": "prometheus"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "thresholds"
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": null
              }
            ]
          },
          "unit": "percentunit"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 8,
        "w": 12,
        "x": 12,
        "y": 8
      },
      "id": 5,
      "options": {
        "orientation": "auto",
        "reduceOptions": {
          "values": false,
          "calcs": [
            "lastNotNull"
          ],
          "fields": ""
        },
        "showThresholdLabels": false,
        "showThresholdMarkers": true
      },
      "pluginVersion": "10.0.0",
      "targets": [
        {
          "datasource": {
            "type": "prometheus",
            "uid": "prometheus"
          },
          "expr": "(anomalies_detected_total / transactions_processed_total)",
          "refId": "A"
        }
      ],
      "title": "Anomaly Detection Percentage",
      "type": "gauge"
    }
  ],
  "refresh": "5s",
  "schemaVersion": 38,
  "style": "dark",
  "tags": ["fraud-detection"],
  "templating": {
    "list": []
  },
  "time": {
    "from": "now-15m",
    "to": "now"
  },
  "timepicker": {},
  "timezone": "",
  "title": "Fraud Detection System",
  "uid": "fraud-detection",
  "version": 0,
  "weekStart": ""
}
```

2. **Import the dashboard:**
   - In Grafana, click **Dashboards** (left sidebar)
   - Click **New** → **Import**
   - Click **Upload JSON file**
   - Select the `fraud-detection-dashboard.json` file you just created
   - Click **Import**

3. **View your dashboard:**
   - You should now see 5 panels:
     - Transaction Processing Rate
     - Total Anomalies Detected
     - Anomaly Detection Rate
     - Processing Error Rate
     - Anomaly Detection Percentage

---

## Step 4: Understanding Your Dashboard

### Panel Explanations

1. **Transaction Processing Rate**
   - Shows transactions processed per second
   - Updates every 5 seconds
   - Calculated from last 5 minutes

2. **Total Anomalies Detected**
   - Gauge showing cumulative anomalies
   - Red threshold at 80+

3. **Anomaly Detection Rate**
   - Anomalies detected per second
   - Line graph over time

4. **Processing Error Rate**
   - Errors per second
   - Should ideally be near zero

5. **Anomaly Detection Percentage**
   - Percentage of transactions flagged
   - Typical range: 0.5% - 2%

---

## Step 5: Verify Data is Flowing

### Check if metrics are being collected:

1. **In Grafana:**
   - Click on any panel
   - Click **Edit** (pencil icon)
   - You should see data in the graph

2. **In Prometheus (http://localhost:9090):**
   - Go to **Graph**
   - Query: `transactions_processed_total`
   - Click **Execute**
   - You should see a number

### If no data appears:

```bash
# Check if detection service is running
docker-compose ps detection_service

# If not running, start it:
docker-compose up -d detection_service

# Check if producer is sending data
python producer.py
```

---

## Step 6: Set Up Alerts (Optional)

1. **Edit a panel (e.g., Error Rate)**
2. Click the **Alert** tab
3. Click **Create alert rule from this panel**
4. Configure:
   - **Name:** High Error Rate
   - **Condition:** WHEN avg() OF query(A) IS ABOVE 0.1
   - **For:** 5m
5. Click **Save**

---

## Useful Grafana Tips

### Refresh Rate
- Top right corner: Set auto-refresh (5s, 10s, 30s)
- Good for real-time monitoring

### Time Range
- Top right corner: Select time range
- Options: Last 5m, 15m, 1h, 6h, 24h, 7d

### Variables
- Add variables for dynamic dashboards
- Example: Filter by account_id

### Explore
- Click **Explore** in left sidebar
- Test Prometheus queries directly

---

## Troubleshooting

### "Data source is not working"
```bash
# Check if Prometheus is accessible from Grafana container
docker exec -it bankprototype-grafana-1 wget -O- http://prometheus:9090/api/v1/status/config

# Restart Grafana
docker-compose restart grafana
```

### "No data in panels"
```bash
# Check Prometheus targets
# Open: http://localhost:9090/targets
# Both api and detection_service should be UP

# Check if metrics exist
# Open: http://localhost:9090/graph
# Query: transactions_processed_total
```

### "Cannot import dashboard"
- Make sure JSON is valid
- Try creating panels manually instead

---

## Next Steps

1. **Customize your dashboard**
   - Add more panels
   - Change colors and thresholds
   - Add annotations

2. **Create alerts**
   - Set up email/Slack notifications
   - Configure alert channels

3. **Share dashboards**
   - Export as JSON
   - Share with team

4. **Monitor trends**
   - Look for patterns
   - Identify peak hours
   - Track anomaly rates over time

---

## Quick Reference: Prometheus Queries

```promql
# Current totals
transactions_processed_total
anomalies_detected_total
transaction_processing_errors_total

# Rates (per second)
rate(transactions_processed_total[5m])
rate(anomalies_detected_total[5m])
rate(transaction_processing_errors_total[5m])

# Increases (total in time window)
increase(transactions_processed_total[1h])
increase(anomalies_detected_total[1h])

# Percentages
(anomalies_detected_total / transactions_processed_total) * 100
(transaction_processing_errors_total / transactions_processed_total) * 100

# Aggregations
avg_over_time(rate(transactions_processed_total[5m])[1h:])
max_over_time(anomalies_detected_total[24h])
```

---

**Your Grafana is now set up! 🎉**

Access it at: **http://localhost:3001** (admin/admin)
