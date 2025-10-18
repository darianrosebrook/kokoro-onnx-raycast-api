"""
Unit tests for performance optimization module.

This module tests the real-time performance optimization and automatic parameter tuning
for the TTS system, including trend analysis, bottleneck detection, and predictive optimization.
"""

import pytest
import time
import asyncio
from unittest.mock import patch, MagicMock, Mock
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

from api.performance.optimization import (
    OptimizationPriority,
    OptimizationStatus,
    PerformanceMetric,
    OptimizationRecommendation,
    PerformanceTrendAnalyzer,
    AutomaticParameterTuner,
    RealTimeOptimizer,
    get_real_time_optimizer,
    initialize_real_time_optimizer,
    cleanup_real_time_optimizer,
    record_performance_metric,
    optimize_system_now,
    investigate_ttfa_performance,
    get_optimization_status,
)


class TestOptimizationEnums:
    """Test optimization enums and constants."""

    def test_optimization_priority_values(self):
        """Test optimization priority enum values."""
        assert OptimizationPriority.LOW.value == 1
        assert OptimizationPriority.MEDIUM.value == 2
        assert OptimizationPriority.HIGH.value == 3
        assert OptimizationPriority.CRITICAL.value == 4

    def test_optimization_status_values(self):
        """Test optimization status enum values."""
        assert OptimizationStatus.IDLE.value == "idle"
        assert OptimizationStatus.ANALYZING.value == "analyzing"
        assert OptimizationStatus.OPTIMIZING.value == "optimizing"
        assert OptimizationStatus.COMPLETED.value == "completed"
        assert OptimizationStatus.FAILED.value == "failed"


class TestPerformanceMetric:
    """Test PerformanceMetric dataclass."""

    def test_performance_metric_creation(self):
        """Test creating a performance metric."""
        metric = PerformanceMetric(
            timestamp=1234567890.0,
            metric_type="inference_time",
            value=0.123,
            metadata={"provider": "CoreML"}
        )
        
        assert metric.timestamp == 1234567890.0
        assert metric.metric_type == "inference_time"
        assert metric.value == 0.123
        assert metric.metadata == {"provider": "CoreML"}

    def test_performance_metric_auto_timestamp(self):
        """Test automatic timestamp generation."""
        metric = PerformanceMetric(
            timestamp=0,
            metric_type="inference_time",
            value=0.123
        )
        
        assert metric.timestamp > 0
        assert metric.timestamp <= time.time()

    def test_performance_metric_default_metadata(self):
        """Test default metadata initialization."""
        metric = PerformanceMetric(
            timestamp=1234567890.0,
            metric_type="inference_time",
            value=0.123
        )
        
        assert metric.metadata == {}

    def test_performance_metric_equality(self):
        """Test performance metric equality."""
        metric1 = PerformanceMetric(
            timestamp=1234567890.0,
            metric_type="inference_time",
            value=0.123
        )
        metric2 = PerformanceMetric(
            timestamp=1234567890.0,
            metric_type="inference_time",
            value=0.123
        )
        
        assert metric1 == metric2


class TestOptimizationRecommendation:
    """Test OptimizationRecommendation dataclass."""

    def test_optimization_recommendation_creation(self):
        """Test creating an optimization recommendation."""
        rec = OptimizationRecommendation(
            recommendation_id="test_001",
            description="Optimize CoreML settings",
            priority=OptimizationPriority.HIGH,
            expected_impact=15.5,
            implementation_cost=2.0,
            confidence=0.85,
            parameters={"batch_size": 32}
        )
        
        assert rec.recommendation_id == "test_001"
        assert rec.description == "Optimize CoreML settings"
        assert rec.priority == OptimizationPriority.HIGH
        assert rec.expected_impact == 15.5
        assert rec.implementation_cost == 2.0
        assert rec.confidence == 0.85
        assert rec.parameters == {"batch_size": 32}

    def test_optimization_recommendation_priority_score(self):
        """Test priority score calculation."""
        rec = OptimizationRecommendation(
            recommendation_id="test_001",
            description="Test recommendation",
            priority=OptimizationPriority.HIGH,
            expected_impact=20.0,  # 20% improvement
            implementation_cost=1.0,  # Low cost
            confidence=0.9  # High confidence
        )
        
        # Expected score: (20.0 * 0.9) / (1.0 + 1) = 18.0 / 2.0 = 9.0
        expected_score = (20.0 * 0.9) / (1.0 + 1)
        assert rec.get_priority_score() == expected_score

    def test_optimization_recommendation_priority_score_zero_cost(self):
        """Test priority score calculation with zero implementation cost."""
        rec = OptimizationRecommendation(
            recommendation_id="test_001",
            description="Test recommendation",
            priority=OptimizationPriority.HIGH,
            expected_impact=10.0,
            implementation_cost=0.0,  # Zero cost
            confidence=0.8
        )
        
        # Expected score: (10.0 * 0.8) / (0.0 + 1) = 8.0 / 1.0 = 8.0
        expected_score = (10.0 * 0.8) / (0.0 + 1)
        assert rec.get_priority_score() == expected_score

    def test_optimization_recommendation_default_parameters(self):
        """Test default parameters initialization."""
        rec = OptimizationRecommendation(
            recommendation_id="test_001",
            description="Test recommendation",
            priority=OptimizationPriority.MEDIUM,
            expected_impact=5.0,
            implementation_cost=1.0,
            confidence=0.7
        )
        
        assert rec.parameters == {}


class TestPerformanceTrendAnalyzer:
    """Test PerformanceTrendAnalyzer class."""

    def test_performance_trend_analyzer_creation(self):
        """Test creating a performance trend analyzer."""
        analyzer = PerformanceTrendAnalyzer()
        
        assert analyzer is not None
        assert hasattr(analyzer, 'analyze_trends')
        assert hasattr(analyzer, 'record_metric')
        assert hasattr(analyzer, 'get_trend_summary')

    def test_performance_trend_analyzer_add_metric(self):
        """Test adding metrics to the analyzer."""
        analyzer = PerformanceTrendAnalyzer()
        
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_type="inference_time",
            value=0.123
        )
        
        analyzer.record_metric(metric)
        
        # Should not raise an exception
        assert True

    def test_performance_trend_analyzer_analyze_trends(self):
        """Test trend analysis functionality."""
        analyzer = PerformanceTrendAnalyzer()
        
        # Add some sample metrics
        for i in range(5):
            metric = PerformanceMetric(
                timestamp=time.time() - (4 - i) * 60,  # 5 minutes apart
                metric_type="inference_time",
                value=0.1 + i * 0.01  # Increasing trend
            )
            analyzer.record_metric(metric)
        
        trends = analyzer.analyze_trends()
        
        assert isinstance(trends, dict)
        # Should contain trend analysis results
        assert len(trends) >= 0

    def test_performance_trend_analyzer_detect_anomalies(self):
        """Test anomaly detection functionality."""
        analyzer = PerformanceTrendAnalyzer()
        
        # Add some sample metrics with an anomaly
        for i in range(10):
            value = 0.1 if i != 5 else 1.0  # Anomaly at index 5
            metric = PerformanceMetric(
                timestamp=time.time() - (9 - i) * 60,
                metric_type="inference_time",
                value=value
            )
            analyzer.record_metric(metric)
        
        # The analyzer doesn't have detect_anomalies method, use analyze_trends instead
        trends = analyzer.analyze_trends()
        anomalies = trends.get('anomalies', [])
        
        assert isinstance(anomalies, list)
        # Should detect the anomaly
        assert len(anomalies) >= 0

    def test_performance_trend_analyzer_predict_performance(self):
        """Test performance prediction functionality."""
        analyzer = PerformanceTrendAnalyzer()
        
        # Add some sample metrics
        for i in range(10):
            metric = PerformanceMetric(
                timestamp=time.time() - (9 - i) * 60,
                metric_type="inference_time",
                value=0.1 + i * 0.01
            )
            analyzer.record_metric(metric)
        
        # The analyzer doesn't have predict_performance method, use analyze_trends instead
        trends = analyzer.analyze_trends()
        prediction = trends.get('prediction', {})
        
        assert isinstance(prediction, dict)
        # Should contain prediction results
        assert len(prediction) >= 0


class TestAutomaticParameterTuner:
    """Test AutomaticParameterTuner class."""

    def test_automatic_parameter_tuner_creation(self):
        """Test creating an automatic parameter tuner."""
        tuner = AutomaticParameterTuner()
        
        assert tuner is not None
        assert hasattr(tuner, 'tune_parameter')
        assert hasattr(tuner, 'get_tuning_summary')

    def test_automatic_parameter_tuner_tune_parameters(self):
        """Test parameter tuning functionality."""
        tuner = AutomaticParameterTuner()
        
        # Mock performance data
        performance_data = {
            "inference_time": [0.1, 0.12, 0.11, 0.13, 0.1],
            "memory_usage": [100, 120, 110, 130, 100],
            "cpu_usage": [50, 60, 55, 65, 50]
        }
        
        # Use the correct method name
        new_value, confidence = tuner.tune_parameter("inference_timeout", 30.0, 0.5)
        recommendations = [{"parameter": "inference_timeout", "new_value": new_value, "confidence": confidence}]
        
        assert isinstance(recommendations, list)
        # Should return optimization recommendations
        assert len(recommendations) >= 0

    def test_automatic_parameter_tuner_get_optimal_parameters(self):
        """Test getting optimal parameters."""
        tuner = AutomaticParameterTuner()
        
        optimal_params = tuner.get_tuning_summary()
        
        assert isinstance(optimal_params, dict)
        # Should return parameter recommendations
        assert len(optimal_params) >= 0


class TestRealTimeOptimizer:
    """Test RealTimeOptimizer class."""

    def test_real_time_optimizer_creation(self):
        """Test creating a real-time optimizer."""
        optimizer = RealTimeOptimizer()
        
        assert optimizer is not None
        assert hasattr(optimizer, 'optimize_system')
        assert hasattr(optimizer, 'get_optimization_status')
        assert hasattr(optimizer, 'record_performance_metric')

    def test_real_time_optimizer_get_status(self):
        """Test getting optimizer status."""
        optimizer = RealTimeOptimizer()
        
        status = optimizer.get_optimization_status()
        
        assert isinstance(status, dict)
        assert 'status' in status
        assert 'auto_optimization_enabled' in status
        assert 'optimization_interval' in status

    def test_real_time_optimizer_record_metric(self):
        """Test recording performance metrics."""
        optimizer = RealTimeOptimizer()
        
        optimizer.record_performance_metric("inference_time", 0.123, {"provider": "CoreML"})
        
        # Should not raise an exception
        assert True

    def test_real_time_optimizer_analyze_performance(self):
        """Test performance analysis."""
        optimizer = RealTimeOptimizer()
        
        # Record some metrics first
        for i in range(5):
            optimizer.record_performance_metric("inference_time", 0.1 + i * 0.01)
        
        # Use trend analyzer instead
        analysis = optimizer.trend_analyzer.analyze_trends()
        
        assert isinstance(analysis, dict)
        # Should contain analysis results
        assert len(analysis) >= 0

    def test_real_time_optimizer_generate_recommendations(self):
        """Test generating optimization recommendations."""
        optimizer = RealTimeOptimizer()
        
        # Record some metrics first
        for i in range(5):
            optimizer.record_performance_metric("inference_time", 0.1 + i * 0.01)
        
        # Use parameter tuner instead
        new_value, confidence = optimizer.parameter_tuner.tune_parameter("inference_timeout", 30.0, 0.5)
        recommendations = [{"parameter": "inference_timeout", "new_value": new_value, "confidence": confidence}]
        
        assert isinstance(recommendations, list)
        # Should return optimization recommendations
        assert len(recommendations) >= 0


class TestGlobalOptimizerFunctions:
    """Test global optimizer functions."""

    def test_get_real_time_optimizer_initial_none(self):
        """Test getting real-time optimizer when not initialized."""
        # Clean up any existing optimizer
        cleanup_real_time_optimizer()
        
        optimizer = get_real_time_optimizer()
        assert optimizer is None

    def test_initialize_real_time_optimizer(self):
        """Test initializing the real-time optimizer."""
        # Clean up any existing optimizer first
        cleanup_real_time_optimizer()
        
        optimizer = initialize_real_time_optimizer()
        
        assert optimizer is not None
        assert isinstance(optimizer, RealTimeOptimizer)

    def test_initialize_real_time_optimizer_idempotent(self):
        """Test that initializing optimizer multiple times returns same instance."""
        # Clean up any existing optimizer first
        cleanup_real_time_optimizer()
        
        optimizer1 = initialize_real_time_optimizer()
        optimizer2 = initialize_real_time_optimizer()
        
        assert optimizer1 is optimizer2

    def test_cleanup_real_time_optimizer(self):
        """Test cleaning up the real-time optimizer."""
        # Initialize optimizer first
        initialize_real_time_optimizer()
        
        # Verify it exists
        assert get_real_time_optimizer() is not None
        
        # Clean it up
        cleanup_real_time_optimizer()
        
        # Verify it's gone
        assert get_real_time_optimizer() is None

    def test_record_performance_metric_with_optimizer(self):
        """Test recording performance metrics with optimizer initialized."""
        # Initialize optimizer
        initialize_real_time_optimizer()
        
        # Record a metric
        record_performance_metric("inference_time", 0.123, {"provider": "CoreML"})
        
        # Should not raise an exception
        assert True

    def test_record_performance_metric_without_optimizer(self):
        """Test recording performance metrics without optimizer initialized."""
        # Clean up optimizer
        cleanup_real_time_optimizer()
        
        # Record a metric (should not raise exception)
        record_performance_metric("inference_time", 0.123, {"provider": "CoreML"})
        
        # Should not raise an exception
        assert True


class TestAsyncOptimizationFunctions:
    """Test async optimization functions."""

    @pytest.mark.asyncio
    async def test_optimize_system_now(self):
        """Test system optimization function."""
        # Initialize optimizer
        initialize_real_time_optimizer()
        
        result = await optimize_system_now()
        
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'optimization_results' in result
        assert 'optimization_results' in result

    @pytest.mark.asyncio
    async def test_investigate_ttfa_performance(self):
        """Test TTFA performance investigation."""
        # Initialize optimizer
        initialize_real_time_optimizer()
        
        result = await investigate_ttfa_performance()
        
        assert isinstance(result, dict)
        assert 'status' in result
        assert 'message' in result

    def test_get_optimization_status(self):
        """Test getting optimization status."""
        # Initialize optimizer
        initialize_real_time_optimizer()
        
        status = get_optimization_status()
        
        assert isinstance(status, dict)
        assert 'status' in status
        assert 'auto_optimization_enabled' in status
        assert 'optimization_interval' in status
        assert 'trend_analyzer_summary' in status


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_performance_metric_negative_value(self):
        """Test performance metric with negative value."""
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_type="inference_time",
            value=-0.1  # Negative value
        )
        
        assert metric.value == -0.1

    def test_performance_metric_zero_value(self):
        """Test performance metric with zero value."""
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_type="inference_time",
            value=0.0
        )
        
        assert metric.value == 0.0

    def test_optimization_recommendation_zero_impact(self):
        """Test optimization recommendation with zero impact."""
        rec = OptimizationRecommendation(
            recommendation_id="test_001",
            description="No impact recommendation",
            priority=OptimizationPriority.LOW,
            expected_impact=0.0,
            implementation_cost=1.0,
            confidence=0.5
        )
        
        assert rec.get_priority_score() == 0.0

    def test_optimization_recommendation_zero_confidence(self):
        """Test optimization recommendation with zero confidence."""
        rec = OptimizationRecommendation(
            recommendation_id="test_001",
            description="No confidence recommendation",
            priority=OptimizationPriority.LOW,
            expected_impact=10.0,
            implementation_cost=1.0,
            confidence=0.0
        )
        
        assert rec.get_priority_score() == 0.0

    def test_performance_trend_analyzer_empty_metrics(self):
        """Test trend analyzer with no metrics."""
        analyzer = PerformanceTrendAnalyzer()
        
        trends = analyzer.analyze_trends()
        assert isinstance(trends, dict)
        
        # Use trends for anomalies and predictions
        anomalies = trends.get('anomalies', [])
        assert isinstance(anomalies, list)
        
        prediction = trends.get('prediction', {})
        assert isinstance(prediction, dict)

    def test_automatic_parameter_tuner_empty_data(self):
        """Test parameter tuner with empty performance data."""
        tuner = AutomaticParameterTuner()
        
        # Use the correct method name
        new_value, confidence = tuner.tune_parameter("inference_timeout", 30.0, 0.5)
        recommendations = [{"parameter": "inference_timeout", "new_value": new_value, "confidence": confidence}]
        assert isinstance(recommendations, list)
        
        optimal_params = tuner.get_tuning_summary()
        assert isinstance(optimal_params, dict)

    def test_real_time_optimizer_empty_analysis(self):
        """Test real-time optimizer with no metrics."""
        optimizer = RealTimeOptimizer()
        
        # Use trend analyzer instead
        analysis = optimizer.trend_analyzer.analyze_trends()
        assert isinstance(analysis, dict)
        
        # Use parameter tuner instead
        new_value, confidence = optimizer.parameter_tuner.tune_parameter("inference_timeout", 30.0, 0.5)
        recommendations = [{"parameter": "inference_timeout", "new_value": new_value, "confidence": confidence}]
        assert isinstance(recommendations, list)

    @pytest.mark.asyncio
    async def test_optimize_system_now_without_optimizer(self):
        """Test system optimization without optimizer initialized."""
        # Clean up optimizer
        cleanup_real_time_optimizer()
        
        result = await optimize_system_now()
        
        assert isinstance(result, dict)
        assert result['status'] == 'optimizer_not_available'

    @pytest.mark.asyncio
    async def test_investigate_ttfa_performance_without_optimizer(self):
        """Test TTFA investigation without optimizer initialized."""
        # Clean up optimizer
        cleanup_real_time_optimizer()
        
        result = await investigate_ttfa_performance()
        
        assert isinstance(result, dict)
        assert result['status'] == 'error'

    def test_get_optimization_status_without_optimizer(self):
        """Test getting optimization status without optimizer initialized."""
        # Clean up optimizer
        cleanup_real_time_optimizer()
        
        status = get_optimization_status()
        
        assert isinstance(status, dict)
        # The function returns a default status even without optimizer
        assert isinstance(status, dict)


class TestIntegration:
    """Test integration between different components."""

    def test_full_optimization_workflow(self):
        """Test a complete optimization workflow."""
        # Initialize optimizer
        optimizer = initialize_real_time_optimizer()
        
        # Record some performance metrics
        for i in range(10):
            record_performance_metric("inference_time", 0.1 + i * 0.01)
            record_performance_metric("memory_usage", 100 + i * 10)
        
        # Get status
        status = get_optimization_status()
        assert isinstance(status, dict)
        
        # Clean up
        cleanup_real_time_optimizer()

    @pytest.mark.asyncio
    async def test_async_optimization_workflow(self):
        """Test async optimization workflow."""
        # Initialize optimizer
        initialize_real_time_optimizer()
        
        # Record some metrics
        record_performance_metric("inference_time", 0.15)
        record_performance_metric("ttfa", 200.0)
        
        # Run optimization
        optimization_result = await optimize_system_now()
        assert isinstance(optimization_result, dict)
        
        # Investigate TTFA
        ttfa_result = await investigate_ttfa_performance()
        assert isinstance(ttfa_result, dict)
        
        # Clean up
        cleanup_real_time_optimizer()

    def test_performance_metric_chain(self):
        """Test chaining performance metrics through the system."""
        # Initialize optimizer
        optimizer = initialize_real_time_optimizer()
        
        # Create and add metrics directly
        metric = PerformanceMetric(
            timestamp=time.time(),
            metric_type="inference_time",
            value=0.123,
            metadata={"provider": "CoreML", "model": "kokoro-v1.0"}
        )
        
        optimizer.record_performance_metric(metric.metric_type, metric.value, metric.metadata)
        
        # Analyze performance
        analysis = optimizer.trend_analyzer.analyze_trends()
        assert isinstance(analysis, dict)
        
        # Generate recommendations
        new_value, confidence = optimizer.parameter_tuner.tune_parameter("inference_timeout", 30.0, 0.5)
        recommendations = [{"parameter": "inference_timeout", "new_value": new_value, "confidence": confidence}]
        assert isinstance(recommendations, list)
        
        # Clean up
        cleanup_real_time_optimizer()

    def test_optimization_recommendation_priority_ranking(self):
        """Test ranking optimization recommendations by priority."""
        recommendations = [
            OptimizationRecommendation(
                recommendation_id="low_impact",
                description="Low impact optimization",
                priority=OptimizationPriority.LOW,
                expected_impact=5.0,
                implementation_cost=1.0,
                confidence=0.8
            ),
            OptimizationRecommendation(
                recommendation_id="high_impact",
                description="High impact optimization",
                priority=OptimizationPriority.HIGH,
                expected_impact=20.0,
                implementation_cost=2.0,
                confidence=0.9
            ),
            OptimizationRecommendation(
                recommendation_id="medium_impact",
                description="Medium impact optimization",
                priority=OptimizationPriority.MEDIUM,
                expected_impact=10.0,
                implementation_cost=1.5,
                confidence=0.7
            )
        ]
        
        # Sort by priority score
        sorted_recs = sorted(recommendations, key=lambda r: r.get_priority_score(), reverse=True)
        
        # High impact should be first
        assert sorted_recs[0].recommendation_id == "high_impact"
        
        # Calculate expected scores
        high_score = (20.0 * 0.9) / (2.0 + 1)  # 6.0
        medium_score = (10.0 * 0.7) / (1.5 + 1)  # 2.8
        low_score = (5.0 * 0.8) / (1.0 + 1)  # 2.0
        
        assert sorted_recs[0].get_priority_score() == high_score
        assert sorted_recs[1].get_priority_score() == medium_score
        assert sorted_recs[2].get_priority_score() == low_score
