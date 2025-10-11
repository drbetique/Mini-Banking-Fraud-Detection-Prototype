# 🚨 Mini Banking Fraud Detection Prototype (Python + SQL + Streamlit)

## 🎯 Project Overview

This project is a full-stack prototype designed to showcase skills in data handling, SQL integration, Python data logic, and professional UI development—directly relevant to Anti-Financial Crime (AFC) development roles. It demonstrates both the data processing backend and the analyst-facing UI.

The application simulates a banking environment by generating synthetic transaction data, storing it in an SQL database, applying rule-based anomaly detection, and visualizing the results in an interactive web dashboard.

## 🛠️ Tech Stack

| Component | Technology | Rationale & Relevance |
| :--- | :--- | :--- |
| **Backend & Logic** | **Python**, Pandas, NumPy | Core programming language requirement for data manipulation and fraud detection algorithms. |
| **Database** | **SQLite** (local), **SQL** | Demonstrates strong SQL skills for data querying and management. |
| **Frontend & UI** | **Streamlit** | Showcases rapid UI development skills for building analyst dashboards. |
| **Deployment** | Streamlit Community Cloud | Proves ability to take a project from local development to a live, shareable application. |

***

## ✨ Key Features & Demo

The dashboard is split into two main sections using tabs to serve an AFC analyst's workflow:

1.  **Dashboard Summary:** Provides high-level metrics (Total Transactions, Anomaly Rate) and **contextual charts** (Daily Volume Trend, Anomaly Location Heatmap).
2.  **Anomaly Review:** Presents a filterable, sortable **data table** of all flagged transactions, including the calculated **`Alert Reason`**.

### 🔍 Detection Logic

The anomaly detection logic (`detection_logic.py`) employs the following business rules:

* **Rule 1: High-Value Transaction:** Any transaction amount **greater than or equal to €5,000**.
* **Rule 2: Suspicious Combo:** Any transaction at a **'Gambling'** merchant occurring **outside of 'Helsinki'**.

**🔗 Live Demo:** [https://mini-banking-fraud-detection-prototype-fzb9mjdkc5yplhjozc2h7h.streamlit.app/]
(https:/mini-banking-fraud-detection-prototype-fzb9mjdkc5yplhjozc2h7h.streamlit.app/)

***

## 🚀 Getting Started (Local Setup)

Follow these steps to set up and run the project locally.

### Prerequisites

You need **Python 3.8+** installed.

### 1. Clone the Repository

```bash
git clone [https://github.com/drbetique/mini-fraud-detection-prototype.git](https://github.com/drbetique/mini-fraud-detection-prototype.git)
cd mini-fraud-detection-prototype