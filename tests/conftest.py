"""Pytest configuration and shared fixtures."""
import pytest
import os
import pandas as pd
from sklearn.ensemble import IsolationForest

# Set test environment variables
os.environ['AZURE_API_KEY'] = 'test-key-for-testing'
os.environ['DATABASE_URL'] = 'postgresql://user:password@localhost/bankdb_test'


@pytest.fixture
def mock_model():
    """Fixture providing a mock ML model for testing."""
    model = IsolationForest(random_state=42, contamination=0.1)

    # Train on dummy data
    X_train = pd.DataFrame({
        'amount': [100, 150, 200, 250, 300],
        'account_avg_amount': [120, 120, 120, 120, 120],
        'deviation_from_avg': [0.1, 0.2, 0.3, 0.4, 0.5]
    })
    model.fit(X_train)

    return model


@pytest.fixture
def sample_transaction():
    """Fixture providing a sample transaction."""
    return {
        'transaction_id': 'TEST_001',
        'account_id': 'ACC_0001',
        'timestamp': '2024-01-15 10:30:00',
        'amount': 150.00,
        'merchant_category': 'Groceries',
        'location': 'Helsinki',
        'is_fraud': 0
    }


@pytest.fixture
def sample_aggregates():
    """Fixture providing sample account aggregates."""
    return {
        'account_tx_count': 50,
        'account_avg_amount': 150.0
    }


@pytest.fixture
def high_value_transaction():
    """Fixture providing a high-value transaction."""
    return {
        'transaction_id': 'TEST_002',
        'account_id': 'ACC_0001',
        'timestamp': '2024-01-15 11:30:00',
        'amount': 8000.00,
        'merchant_category': 'Electronics',
        'location': 'Helsinki',
        'is_fraud': 0
    }


@pytest.fixture
def suspicious_transaction():
    """Fixture providing a suspicious gambling transaction."""
    return {
        'transaction_id': 'TEST_003',
        'account_id': 'ACC_0001',
        'timestamp': '2024-01-15 12:30:00',
        'amount': 100.00,
        'merchant_category': 'Gambling',
        'location': 'Turku',  # Not Helsinki
        'is_fraud': 0
    }
