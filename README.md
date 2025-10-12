# Mini Banking Fraud Detection Prototype 🛡️

This project is a prototype for a real-time anomaly detection system in banking transactions. It is built using a decoupled architecture, consisting of a **FastAPI backend** hosted on Azure and a **Streamlit frontend** hosted on Streamlit Community Cloud.

## 🚀 Architecture Overview

The system architecture is a standard two-tier deployment:

1.  **Backend (FastAPI):** Hosts the anomaly detection logic and serves the results via a REST API endpoint. It's containerized using Docker and deployed to Azure App Service.
2.  **Frontend (Streamlit):** A web dashboard that consumes the anomaly data from the live Azure API and presents it for review.

## 🌐 Live Application Links

| Component | Status | Live URL |
| :--- | :--- | :--- |
| **Streamlit Dashboard** | Operational | **[Insert your Streamlit Cloud App URL Here]** |
| **FastAPI Backend (API)** | Running | **[Insert your Azure API Base URL Here]** |

### API Endpoint for Anomaly Data

To view the raw JSON data that powers the dashboard, access the full endpoint:
# Mini Banking Fraud Detection Prototype 🛡️

This project is a prototype for a real-time anomaly detection system in banking transactions. It is built using a decoupled architecture, consisting of a **FastAPI backend** hosted on Azure and a **Streamlit frontend** hosted on Streamlit Community Cloud.

## 🚀 Architecture Overview

The system architecture is a standard two-tier deployment:

1.  **Backend (FastAPI):** Hosts the anomaly detection logic and serves the results via a REST API endpoint. It's containerized using Docker and deployed to Azure App Service.
2.  **Frontend (Streamlit):** A web dashboard that consumes the anomaly data from the live Azure API and presents it for review.

## 🌐 Live Application Links

| Component | Status | Live URL |
| :--- | :--- | :--- |
| **Streamlit Dashboard** | Operational | **https://mini-banking-fraud-detection-prototype-fzb9mjdkc5yplhjozc2h7h.streamlit.app/** |
| **FastAPI Backend (API)** | Running | **https://mini-fraud-api-vib-c7ehh4h6aqd0bxbb.azurewebsites.net/api/v1/anomalies
** |

### API Endpoint for Anomaly Data

To view the raw JSON data that powers the dashboard, access the full endpoint:

## 🛠️ Deployment Details

### 1. Azure FastAPI Backend

* **Service:** Azure App Service (Linux)
* **Hosting Plan:** Free F1 Tier (`FraudAppServicePlan`)
* **Container Image:** Pulled from Docker Hub (`index.docker.io/drbetique/mini-fraud-api:latest`)
* **Startup Command:** `uvicorn api:app --host 0.0.0.0 --port 8000`
* **Azure Domain Example:** `mini-fraud-api-vib-c7ehh4h6aqd0bxbb.swedencentral-01.azurewebsites.net`

### 2. Streamlit Frontend

* **Service:** Streamlit Community Cloud
* **Repository Source:** `drbetique/Mini-Banking-Fraud-Detection-Prototype`
* **Main File:** `app.py`
* **Dependencies:** Managed via `requirements.txt` (including `pandas`, `plotly`, `requests`).

## ⚙️ Running Locally (Development)

### Prerequisites

* Docker (for the API)
* Python 3.8+ (for the Streamlit app)

### Steps

1.  **Clone the Repository:**
    ```bash
    git clone [https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype.git](https://github.com/drbetique/Mini-Banking-Fraud-Detection-Prototype.git)
    cd Mini-Banking-Fraud-Detection-Prototype
    ```

2.  **Run the API Backend (Using Docker):**
    The API must be running for the dashboard to function.
    ```bash
    # Pull the public image
    docker pull drbetique/mini-fraud-api:latest

    # Run the container locally (Note: API URL in app.py must be changed for local testing)
    docker run -d -p 8000:8000 --name fraud-api drbetique/mini-fraud-api:latest
    ```

3.  **Run the Streamlit Frontend:**
    You must update the `API_URL` variable in `app.py` to point to your local API (e.g., `http://localhost:8000/api/v1/anomalies`) before running this step.
    ```bash
    pip install -r requirements.txt
    streamlit run app.py
    ```

---
**Developed by Victor Ifeoluwa Betiku**