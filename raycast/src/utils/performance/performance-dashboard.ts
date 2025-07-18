/**
 * Performance Dashboard Utility
 *
 * Manages real-time performance metrics collection and provides
 * data to the monitoring component. Handles metric aggregation,
 * trend analysis, and alert generation.
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import type {
  PerformanceMetrics,
  BufferHealth,
  NetworkConditions,
} from "../validation/tts-types.js";
/**
 * Performance alert types
 */
export interface PerformanceAlert {
  id: string;
  type: "warning" | "critical" | "info";
  message: string;
  timestamp: number;
  metric: string;
  value: number;
  threshold: number;
  resolved: boolean;
}

/**
 * Performance trend data
 */
export interface PerformanceTrend {
  metric: string;
  currentValue: number;
  previousValue: number;
  change: number;
  changePercent: number;
  trend: "improving" | "declining" | "stable";
  confidence: number; // 0-1
}

/**
 * Dashboard configuration
 */
export interface DashboardConfig {
  updateInterval: number; // ms
  maxDataPoints: number;
  alertThresholds: {
    timeToFirstAudio: number;
    bufferUnderruns: number;
    cacheMissRate: number;
    networkLatency: number;
  };
  enableTrendAnalysis: boolean;
  enableAlerts: boolean;
}

/**
 * Historical metric data point
 */
export interface MetricDataPoint {
  timestamp: number;
  value: number;
  label: string;
  metadata?: Record<string, unknown>;
}

/**
 * Performance dashboard class
 */
export class PerformanceDashboard {
  private static instance: PerformanceDashboard;
  private config: DashboardConfig;
  private metrics: PerformanceMetrics | null = null;
  private bufferHealth: BufferHealth | null = null;
  private networkConditions: NetworkConditions | null = null;
  private historicalData: Map<string, MetricDataPoint[]> = new Map();
  private alerts: PerformanceAlert[] = [];
  private trends: PerformanceTrend[] = [];
  private updateInterval: ReturnType<typeof setInterval> | null = null;
  private listeners: Set<(data: unknown) => void> = new Set();

  private constructor() {
    this.config = {
      updateInterval: 1000, // 1 second
      maxDataPoints: 100,
      alertThresholds: {
        timeToFirstAudio: 150,
        bufferUnderruns: 5,
        cacheMissRate: 0.3,
        networkLatency: 200,
      },
      enableTrendAnalysis: true,
      enableAlerts: true,
    };
  }

  /**
   * Get singleton instance
   */
  static getInstance(): PerformanceDashboard {
    if (!PerformanceDashboard.instance) {
      PerformanceDashboard.instance = new PerformanceDashboard();
    }
    return PerformanceDashboard.instance;
  }

  /**
   * Start the dashboard
   */
  start(): void {
    if (this.updateInterval) {
      return; // Already running
    }

    this.updateInterval = setInterval(() => {
      this.updateMetrics();
    }, this.config.updateInterval);

    console.log("Performance dashboard started");
  }

  /**
   * Stop the dashboard
   */
  stop(): void {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
      this.updateInterval = null;
    }

    console.log("Performance dashboard stopped");
  }

  /**
   * Update metrics with new data
   */
  updateMetrics(): void {
    if (!this.metrics) {
      return;
    }

    // Update historical data
    this.updateHistoricalData();

    // Analyze trends
    if (this.config.enableTrendAnalysis) {
      this.analyzeTrends();
    }

    // Check for alerts
    if (this.config.enableAlerts) {
      this.checkAlerts();
    }

    // Notify listeners
    this.notifyListeners();
  }

  /**
   * Set current performance metrics
   */
  setMetrics(metrics: PerformanceMetrics): void {
    this.metrics = metrics;
    this.updateMetrics();
  }

  /**
   * Set buffer health data
   */
  setBufferHealth(health: BufferHealth): void {
    this.bufferHealth = health;
    this.notifyListeners();
  }

  /**
   * Set network conditions
   */
  setNetworkConditions(conditions: NetworkConditions): void {
    this.networkConditions = conditions;
    this.notifyListeners();
  }

  /**
   * Get current dashboard state
   */
  getDashboardState(): {
    metrics: PerformanceMetrics | null;
    bufferHealth: BufferHealth | null;
    networkConditions: NetworkConditions | null;
    historicalData: Map<string, MetricDataPoint[]>;
    alerts: PerformanceAlert[];
    trends: PerformanceTrend[];
  } {
    return {
      metrics: this.metrics,
      bufferHealth: this.bufferHealth,
      networkConditions: this.networkConditions,
      historicalData: this.historicalData,
      alerts: this.alerts,
      trends: this.trends,
    };
  }

  /**
   * Get historical data for a specific metric
   */
  getHistoricalData(metric: string): MetricDataPoint[] {
    return this.historicalData.get(metric) || [];
  }

  /**
   * Get active alerts
   */
  getActiveAlerts(): PerformanceAlert[] {
    return this.alerts.filter((alert) => !alert.resolved);
  }

  /**
   * Get performance trends
   */
  getTrends(): PerformanceTrend[] {
    return this.trends;
  }

  /**
   * Add event listener
   */
  addListener(callback: (data: unknown) => void): void {
    this.listeners.add(callback);
  }

  /**
   * Remove event listener
   */
  removeListener(callback: (data: unknown) => void): void {
    this.listeners.delete(callback);
  }

  /**
   * Update configuration
   */
  updateConfig(config: Partial<DashboardConfig>): void {
    this.config = { ...this.config, ...config };

    // Restart with new interval if needed
    if (this.updateInterval && config.updateInterval) {
      this.stop();
      this.start();
    }
  }

  /**
   * Clear historical data
   */
  clearHistoricalData(): void {
    this.historicalData.clear();
    this.alerts = [];
    this.trends = [];
  }

  /**
   * Update historical data with current metrics
   */
  private updateHistoricalData(): void {
    if (!this.metrics) return;

    const timestamp = Date.now();
    const timeLabel = new Date(timestamp).toLocaleTimeString();

    const metricsToTrack = [
      { key: "timeToFirstAudio", value: this.metrics.timeToFirstAudio },
      { key: "averageLatency", value: this.metrics.averageLatency },
      { key: "bufferAdjustments", value: this.metrics.bufferAdjustments },
      { key: "adaptiveBufferMs", value: this.metrics.adaptiveBufferMs },
      { key: "completedSegments", value: this.metrics.completedSegments },
      {
        key: "cacheHitRate",
        value:
          this.metrics.cacheHits > 0
            ? (this.metrics.cacheHits / (this.metrics.cacheHits + this.metrics.cacheMisses)) * 100
            : 0,
      },
    ];

    metricsToTrack.forEach(({ key, value }) => {
      const data = this.historicalData.get(key) || [];
      data.push({ timestamp, value, label: timeLabel });

      // Keep only the most recent data points
      if (data.length > this.config.maxDataPoints) {
        data.splice(0, data.length - this.config.maxDataPoints);
      }

      this.historicalData.set(key, data);
    });
  }

  /**
   * Analyze performance trends
   */
  private analyzeTrends(): void {
    this.trends = [];

    const metricsToAnalyze = [
      "timeToFirstAudio",
      "averageLatency",
      "bufferAdjustments",
      "cacheHitRate",
    ];

    metricsToAnalyze.forEach((metric) => {
      const data = this.getHistoricalData(metric);
      if (data.length < 2) return;

      const recent = data.slice(-5); // Last 5 data points
      const previous = data.slice(-10, -5); // Previous 5 data points

      if (recent.length === 0 || previous.length === 0) return;

      const currentAvg = recent.reduce((sum, d) => sum + d.value, 0) / recent.length;
      const previousAvg = previous.reduce((sum, d) => sum + d.value, 0) / previous.length;

      const change = currentAvg - previousAvg;
      const changePercent = previousAvg > 0 ? (change / previousAvg) * 100 : 0;

      let trend: "improving" | "declining" | "stable" = "stable";
      if (Math.abs(changePercent) > 5) {
        trend = changePercent < 0 ? "improving" : "declining";
      }

      // Calculate confidence based on data consistency
      const variance =
        recent.reduce((sum, d) => sum + Math.pow(d.value - currentAvg, 2), 0) / recent.length;
      const confidence = Math.max(0, 1 - variance / (currentAvg * currentAvg));

      this.trends.push({
        metric,
        currentValue: currentAvg,
        previousValue: previousAvg,
        change,
        changePercent,
        trend,
        confidence,
      });
    });
  }

  /**
   * Check for performance alerts
   */
  private checkAlerts(): void {
    if (!this.metrics) return;

    const checks = [
      {
        metric: "timeToFirstAudio",
        value: this.metrics.timeToFirstAudio,
        threshold: this.config.alertThresholds.timeToFirstAudio,
        message: "Time to first audio is high",
      },
      {
        metric: "bufferUnderruns",
        value: this.metrics.underrunCount,
        threshold: this.config.alertThresholds.bufferUnderruns,
        message: "Buffer underruns detected",
      },
      {
        metric: "cacheMissRate",
        value:
          this.metrics.cacheMisses > 0
            ? this.metrics.cacheMisses / (this.metrics.cacheHits + this.metrics.cacheMisses)
            : 0,
        threshold: this.config.alertThresholds.cacheMissRate,
        message: "High cache miss rate",
      },
    ];

    checks.forEach((check) => {
      if (check.value > check.threshold) {
        this.createAlert(check.metric, check.value, check.threshold, check.message);
      }
    });

    // Check network conditions
    if (
      this.networkConditions &&
      this.networkConditions.latency > this.config.alertThresholds.networkLatency
    ) {
      this.createAlert(
        "networkLatency",
        this.networkConditions.latency,
        this.config.alertThresholds.networkLatency,
        "High network latency"
      );
    }
  }

  /**
   * Create a new performance alert
   */
  private createAlert(metric: string, value: number, threshold: number, message: string): void {
    const alert: PerformanceAlert = {
      id: `${metric}-${Date.now()}`,
      type: value > threshold * 1.5 ? "critical" : "warning",
      message,
      timestamp: Date.now(),
      metric,
      value,
      threshold,
      resolved: false,
    };

    // Check if similar alert already exists
    const existingAlert = this.alerts.find(
      (a) => a.metric === metric && !a.resolved && Math.abs(a.value - value) < threshold * 0.1
    );

    if (!existingAlert) {
      this.alerts.push(alert);
      console.warn(`Performance alert: ${message} (${value} > ${threshold})`);
    }
  }

  /**
   * Resolve an alert
   */
  resolveAlert(alertId: string): void {
    const alert = this.alerts.find((a) => a.id === alertId);
    if (alert) {
      alert.resolved = true;
    }
  }

  /**
   * Notify all listeners
   */
  private notifyListeners(): void {
    const data = this.getDashboardState();
    this.listeners.forEach((listener) => {
      try {
        listener(data);
      } catch (error) {
        console.error("Error in dashboard listener:", error);
      }
    });
  }

  /**
   * Get performance summary
   */
  getPerformanceSummary(): {
    overallHealth: "excellent" | "good" | "fair" | "poor";
    score: number;
    recommendations: string[];
    topIssues: string[];
  } {
    if (!this.metrics) {
      return {
        overallHealth: "fair",
        score: 0,
        recommendations: ["No performance data available"],
        topIssues: [],
      };
    }

    let score = 100;
    const issues: string[] = [];
    const recommendations: string[] = [];

    // Score based on time to first audio
    if (this.metrics.timeToFirstAudio > 200) {
      score -= 20;
      issues.push("High time to first audio");
      recommendations.push("Consider using a more conservative performance profile");
    } else if (this.metrics.timeToFirstAudio > 100) {
      score -= 10;
    }

    // Score based on buffer adjustments
    if (this.metrics.bufferAdjustments > 10) {
      score -= 15;
      issues.push("Frequent buffer adjustments");
      recommendations.push("Network conditions may be unstable, try network-optimized profile");
    }

    // Score based on cache performance
    const cacheHitRate =
      this.metrics.cacheHits > 0
        ? this.metrics.cacheHits / (this.metrics.cacheHits + this.metrics.cacheMisses)
        : 0;
    if (cacheHitRate < 0.5) {
      score -= 10;
      issues.push("Low cache hit rate");
      recommendations.push("Consider caching more frequently used content");
    }

    // Score based on streaming success
    const totalStreaming = this.metrics.streamingSuccesses + this.metrics.streamingFailures;
    if (totalStreaming > 0) {
      const successRate = this.metrics.streamingSuccesses / totalStreaming;
      if (successRate < 0.8) {
        score -= 15;
        issues.push("Streaming failures detected");
        recommendations.push("Check network stability and consider conservative profile");
      }
    }

    // Determine overall health
    let overallHealth: "excellent" | "good" | "fair" | "poor";
    if (score >= 90) overallHealth = "excellent";
    else if (score >= 75) overallHealth = "good";
    else if (score >= 60) overallHealth = "fair";
    else overallHealth = "poor";

    return {
      overallHealth,
      score: Math.max(0, score),
      recommendations,
      topIssues: issues.slice(0, 3),
    };
  }

  /**
   * Export performance data for analysis
   */
  exportData(): {
    metrics: PerformanceMetrics | null;
    historicalData: Record<string, MetricDataPoint[]>;
    alerts: PerformanceAlert[];
    trends: PerformanceTrend[];
    summary: ReturnType<typeof this.getPerformanceSummary>;
    timestamp: number;
  } {
    return {
      metrics: this.metrics,
      historicalData: Object.fromEntries(this.historicalData),
      alerts: this.alerts,
      trends: this.trends,
      summary: this.getPerformanceSummary(),
      timestamp: Date.now(),
    };
  }
}

/**
 * Export singleton instance
 */
export const performanceDashboard = PerformanceDashboard.getInstance();
