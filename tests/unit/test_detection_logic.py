"""Unit tests for detection_logic.py"""
import pytest
from detection_logic import score_transaction


class TestScoreTransaction:
    """Test suite for transaction scoring logic."""

    def test_normal_transaction_low_score(self, sample_transaction, sample_aggregates, mock_model):
        """Test that normal transactions receive low anomaly scores."""
        score, reason = score_transaction(
            sample_transaction,
            sample_aggregates,
            mock_model,
            min_score=-0.5,
            max_score=0.5
        )

        assert 0.0 <= score <= 1.0, "Score should be normalized between 0 and 1"
        assert score < 0.7, "Normal transaction should have low anomaly score"

    def test_high_value_transaction_flagged(self, high_value_transaction, sample_aggregates, mock_model):
        """Test that high-value transactions are flagged correctly."""
        score, reason = score_transaction(
            high_value_transaction,
            sample_aggregates,
            mock_model,
            min_score=-0.5,
            max_score=0.5
        )

        assert reason is not None, "High-value transaction should trigger an alert"
        assert "High Value" in reason or "ML" in reason, "Should flag high value or ML risk"

    def test_suspicious_gambling_combo(self, suspicious_transaction, sample_aggregates, mock_model):
        """Test suspicious merchant + location combination."""
        score, reason = score_transaction(
            suspicious_transaction,
            sample_aggregates,
            mock_model,
            min_score=-0.5,
            max_score=0.5
        )

        assert reason is not None, "Suspicious combo should trigger alert"
        assert "Suspicious Combo" in reason or "ML" in reason, "Should flag suspicious combination"

    def test_high_deviation_flagged(self, sample_transaction, mock_model):
        """Test that transactions with high deviation from average are flagged."""
        # Transaction much higher than account average
        high_deviation_transaction = sample_transaction.copy()
        high_deviation_transaction['amount'] = 1500.00  # 10x average

        aggregates = {
            'account_tx_count': 20,  # Enough history
            'account_avg_amount': 150.0
        }

        score, reason = score_transaction(
            high_deviation_transaction,
            aggregates,
            mock_model,
            min_score=-0.5,
            max_score=0.5
        )

        # High deviation should contribute to alert
        assert reason is not None, "High deviation should trigger alert"

    def test_score_normalization(self, sample_transaction, sample_aggregates, mock_model):
        """Test that scores are properly normalized to 0-1 range."""
        score, _ = score_transaction(
            sample_transaction,
            sample_aggregates,
            mock_model,
            min_score=-0.5,
            max_score=0.5
        )

        assert 0.0 <= score <= 1.0, f"Score {score} should be between 0 and 1"

    def test_missing_model_raises_error(self, sample_transaction, sample_aggregates):
        """Test that missing model raises appropriate error."""
        with pytest.raises(RuntimeError):
            score_transaction(
                sample_transaction,
                sample_aggregates,
                model=None,
                min_score=-0.5,
                max_score=0.5
            )

    def test_missing_score_boundaries_raises_error(self, sample_transaction, sample_aggregates, mock_model):
        """Test that missing score boundaries raise appropriate error."""
        with pytest.raises(RuntimeError):
            score_transaction(
                sample_transaction,
                sample_aggregates,
                mock_model,
                min_score=None,
                max_score=0.5
            )
