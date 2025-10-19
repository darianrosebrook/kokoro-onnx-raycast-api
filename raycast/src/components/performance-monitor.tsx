/**
 * Real-Time Performance Monitor Component
 *
 * Displays live performance metrics during TTS processing including
 * buffer health, network latency, audio streaming stats, and system performance.
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import React, { useState, useEffect, useRef } from "react";

import type {
  PerformanceMetrics,
  BufferHealth,
  NetworkConditions,
} from "../utils/validation/tts-types";

type FixedFromReactNativeProps = {
  children: React.ReactNode;
  style: React.CSSProperties;
  onClick?: () => void;
};

const View = ({ children, style, onClick }: FixedFromReactNativeProps) => {
  return (
    <div style={style} onClick={onClick}>
      {children}
    </div>
  );
};

const Text = ({ children, style, onClick }: FixedFromReactNativeProps) => {
  return (
    <div style={style} onClick={onClick}>
      {children}
    </div>
  );
};

const StyleSheet = {
  create: (styles: Record<string, React.CSSProperties>) => styles,
};

/**
 * Performance metric display component
 */
interface MetricDisplayProps {
  label: string;
  value: string | number;
  unit?: string;
  status?: "good" | "warning" | "critical";
  trend?: "up" | "down" | "stable";
}

const MetricDisplay: React.FC<MetricDisplayProps> = ({
  label,
  value,
  unit = "",
  status = "good",
  trend,
}) => {
  const getStatusColor = () => {
    switch (status) {
      case "good":
        return "#10B981";
      case "warning":
        return "#F59E0B";
      case "critical":
        return "#EF4444";
      default:
        return "#6B7280";
    }
  };

  const getTrendIcon = () => {
    switch (trend) {
      case "up":
        return "↗";
      case "down":
        return "↘";
      case "stable":
        return "→";
      default:
        return "";
    }
  };

  return (
    <View style={styles.metricContainer}>
      <Text style={styles.metricLabel}>{label}</Text>
      <View style={styles.metricValueContainer}>
        <Text style={{ ...styles.metricValue, color: getStatusColor() }}>
          {value}
          {unit}
        </Text>
        {trend && (
          <Text style={{ ...styles.trendIcon, color: getStatusColor() }}>{getTrendIcon()}</Text>
        )}
      </View>
    </View>
  );
};

/**
 * Buffer health indicator component
 */
interface BufferHealthIndicatorProps {
  health: BufferHealth;
}

const BufferHealthIndicator: React.FC<BufferHealthIndicatorProps> = ({ health }) => {
  const getHealthColor = () => {
    switch (health.status) {
      case "healthy":
        return "#10B981";
      case "degraded":
        return "#F59E0B";
      case "poor":
        return "#EF4444";
      default:
        return "#6B7280";
    }
  };

  const getHealthIcon = () => {
    switch (health.status) {
      case "healthy":
        return "●";
      case "degraded":
        return "●";
      case "poor":
        return "●";
      default:
        return "○";
    }
  };

  return (
    <View style={styles.healthContainer}>
      <Text style={{ ...styles.healthIcon, color: getHealthColor() }}>{getHealthIcon()}</Text>
      <View style={styles.healthInfo}>
        <Text style={styles.healthStatus}>{health.status.toUpperCase()}</Text>
        <Text style={styles.healthScore}>Score: {health.score.toFixed(1)}</Text>
      </View>
      {health.issues.length > 0 && (
        <View style={styles.issuesContainer}>
          <Text style={styles.issuesTitle}>Issues:</Text>
          {health.issues.map((issue, index) => (
            <Text key={index} style={styles.issueText}>
              • {issue}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
};

/**
 * Network conditions display component
 */
interface NetworkConditionsDisplayProps {
  conditions: NetworkConditions;
}

const NetworkConditionsDisplay: React.FC<NetworkConditionsDisplayProps> = ({ conditions }) => {
  const getLatencyStatus = (latency: number) => {
    if (latency < 50) return "good";
    if (latency < 150) return "warning";
    return "critical";
  };

  const getBandwidthStatus = (bandwidth: number) => {
    if (bandwidth > 1000) return "good";
    if (bandwidth > 500) return "warning";
    return "critical";
  };

  return (
    <View style={styles.networkContainer}>
      <Text style={styles.sectionTitle}>Network Conditions</Text>
      <View style={styles.networkMetrics}>
        <MetricDisplay
          label="Latency"
          value={conditions.latency.toFixed(0)}
          unit="ms"
          status={getLatencyStatus(conditions.latency)}
        />
        <MetricDisplay
          label="Bandwidth"
          value={(conditions.bandwidth / 1000).toFixed(1)}
          unit="Mbps"
          status={getBandwidthStatus(conditions.bandwidth)}
        />
        <MetricDisplay
          label="Packet Loss"
          value={(conditions.packetLoss * 100).toFixed(1)}
          unit="%"
          status={conditions.packetLoss < 0.01 ? "good" : "warning"}
        />
      </View>
    </View>
  );
};

/**
 * TODO: Enhance performance monitoring UI components
 * - [ ] Implement interactive charts with zoom, pan, and filtering
 * - [ ] Add real-time data streaming and updates
 * - [ ] Implement multiple chart types (line, bar, scatter, histogram)
 * - [ ] Add data export functionality (CSV, JSON, PNG)
 * - [ ] Implement alert visualization and threshold indicators
 * - [ ] Add comparative analysis between different time periods
 */
interface PerformanceChartProps {
  data: Array<{ timestamp: number; value: number; label: string }>;
  title: string;
  maxPoints?: number;
}

const PerformanceChart: React.FC<PerformanceChartProps> = ({ data, title, maxPoints = 20 }) => {
  const recentData = data.slice(-maxPoints);

  if (recentData.length === 0) {
    return (
      <View style={styles.chartContainer}>
        <Text style={styles.chartTitle}>{title}</Text>
        <Text style={styles.noDataText}>No data available</Text>
      </View>
    );
  }

  const maxValue = Math.max(...recentData.map((d) => d.value));
  const minValue = Math.min(...recentData.map((d) => d.value));

  return (
    <View style={styles.chartContainer}>
      <Text style={styles.chartTitle}>{title}</Text>
      <View style={styles.chartContent}>
        {recentData.map((point, index) => {
          const height =
            maxValue > minValue ? ((point.value - minValue) / (maxValue - minValue)) * 100 : 50;

          return (
            <View key={index} style={styles.chartBar}>
              <View style={{ ...styles.chartBarFill, height: `${height}%` }}>
                <Text style={styles.chartLabel}>{point.label}</Text>
              </View>
              <Text style={styles.chartLabel}>{point.label}</Text>
            </View>
          );
        })}
      </View>
    </View>
  );
};

/**
 * Main performance monitor component
 */
interface PerformanceMonitorProps {
  metrics: PerformanceMetrics | null;
  bufferHealth: BufferHealth | null;
  networkConditions: NetworkConditions | null;
  isVisible: boolean;
  onClose?: () => void;
}

export const PerformanceMonitor: React.FC<PerformanceMonitorProps> = ({
  metrics,
  bufferHealth,
  networkConditions,
  isVisible,
  onClose,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [historicalData, setHistoricalData] = useState<{
    latency: Array<{ timestamp: number; value: number; label: string }>;
    bufferUtilization: Array<{ timestamp: number; value: number; label: string }>;
    audioChunks: Array<{ timestamp: number; value: number; label: string }>;
  }>({
    latency: [],
    bufferUtilization: [],
    audioChunks: [],
  });

  const updateInterval = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (isVisible && metrics) {
      // Update historical data
      const timestamp = Date.now();
      const timeLabel = new Date(timestamp).toLocaleTimeString();

      setHistoricalData((prev) => ({
        latency: [...prev.latency, { timestamp, value: metrics.averageLatency, label: timeLabel }],
        bufferUtilization: [
          ...prev.bufferUtilization,
          { timestamp, value: metrics.adaptiveBufferMs, label: timeLabel },
        ],
        audioChunks: [
          ...prev.audioChunks,
          { timestamp, value: metrics.completedSegments, label: timeLabel },
        ],
      }));

      // Start update interval
      updateInterval.current = setInterval(() => {
        // This would be updated with real-time data
      }, 1000);
    } else {
      // Clear interval when not visible
      if (updateInterval.current) {
        clearInterval(updateInterval.current);
        updateInterval.current = null;
      }
    }

    return () => {
      if (updateInterval.current) {
        clearInterval(updateInterval.current);
      }
    };
  }, [isVisible, metrics]);

  if (!isVisible) {
    return null;
  }

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Performance Monitor</Text>
        <View style={styles.headerActions}>
          <Text style={styles.expandButton} onClick={() => setIsExpanded(!isExpanded)}>
            {isExpanded ? "▼" : "▲"}
          </Text>
          {onClose && (
            <Text style={styles.closeButton} onClick={onClose}>
              ×
            </Text>
          )}
        </View>
      </View>

      <View style={styles.content}>
        {/* Key Metrics */}
        <View style={styles.metricsSection}>
          <Text style={styles.sectionTitle}>Key Metrics</Text>
          <View style={styles.metricsGrid}>
            {metrics && (
              <>
                <MetricDisplay
                  label="Time to First Audio"
                  value={metrics.timeToFirstAudio.toFixed(0)}
                  unit="ms"
                  status={metrics.timeToFirstAudio < 100 ? "good" : "warning"}
                />
                <MetricDisplay
                  label="Buffer Adjustments"
                  value={metrics.bufferAdjustments}
                  status={metrics.bufferAdjustments < 5 ? "good" : "warning"}
                />
                <MetricDisplay
                  label="Cache Hit Rate"
                  value={
                    metrics.cacheHits > 0
                      ? (
                          (metrics.cacheHits / (metrics.cacheHits + metrics.cacheMisses)) *
                          100
                        ).toFixed(1)
                      : "0"
                  }
                  unit="%"
                  status={metrics.cacheHits > metrics.cacheMisses ? "good" : "warning"}
                />
                <MetricDisplay
                  label="Streaming Success"
                  value={metrics.streamingSuccesses}
                  status={
                    metrics.streamingSuccesses > metrics.streamingFailures ? "good" : "critical"
                  }
                />
              </>
            )}
          </View>
        </View>

        {/* Buffer Health */}
        {bufferHealth && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Buffer Health</Text>
            <BufferHealthIndicator health={bufferHealth} />
          </View>
        )}

        {/* Network Conditions */}
        {networkConditions && <NetworkConditionsDisplay conditions={networkConditions} />}

        {/* Historical Charts (expanded view) */}
        {isExpanded && (
          <View style={styles.chartsSection}>
            <Text style={styles.sectionTitle}>Performance Trends</Text>
            <PerformanceChart data={historicalData.latency} title="Network Latency" />
            <PerformanceChart data={historicalData.bufferUtilization} title="Buffer Utilization" />
            <PerformanceChart data={historicalData.audioChunks} title="Audio Chunks Processed" />
          </View>
        )}
      </View>
    </View>
  );
};

/**
 * Styles for the performance monitor
 */
const styles = StyleSheet.create({
  container: {
    backgroundColor: "#1F2937",
    borderRadius: 8,
    margin: 8,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: "#374151",
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 12,
    backgroundColor: "#111827",
    borderBottomWidth: 1,
    borderBottomColor: "#374151",
  },
  title: {
    fontSize: 16,
    fontWeight: "600",
    color: "#F9FAFB",
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
  },
  expandButton: {
    fontSize: 14,
    color: "#9CA3AF",
    marginRight: 8,
    padding: 4,
  },
  closeButton: {
    fontSize: 14,
    color: "#9CA3AF",
    padding: 4,
  },
  content: {
    padding: 12,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#F9FAFB",
    marginBottom: 8,
  },
  metricsSection: {
    marginBottom: 16,
  },
  metricsGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
  },
  metricContainer: {
    width: "48%",
    marginBottom: 12,
    padding: 8,
    backgroundColor: "#374151",
    borderRadius: 6,
  },
  metricLabel: {
    fontSize: 12,
    color: "#9CA3AF",
    marginBottom: 4,
  },
  metricValueContainer: {
    flexDirection: "row",
    alignItems: "center",
  },
  metricValue: {
    fontSize: 16,
    fontWeight: "600",
  },
  trendIcon: {
    fontSize: 12,
    marginLeft: 4,
  },
  healthContainer: {
    flexDirection: "row",
    alignItems: "center",
    padding: 12,
    backgroundColor: "#374151",
    borderRadius: 6,
  },
  healthIcon: {
    fontSize: 20,
    marginRight: 12,
  },
  healthInfo: {
    flex: 1,
  },
  healthStatus: {
    fontSize: 14,
    fontWeight: "600",
    color: "#F9FAFB",
  },
  healthScore: {
    fontSize: 12,
    color: "#9CA3AF",
  },
  issuesContainer: {
    marginTop: 8,
  },
  issuesTitle: {
    fontSize: 12,
    fontWeight: "600",
    color: "#F9FAFB",
    marginBottom: 4,
  },
  issueText: {
    fontSize: 11,
    color: "#EF4444",
    marginBottom: 2,
  },
  networkContainer: {
    marginBottom: 16,
  },
  networkMetrics: {
    flexDirection: "row",
    justifyContent: "space-between",
  },
  chartsSection: {
    marginTop: 16,
  },
  chartContainer: {
    marginBottom: 16,
    padding: 12,
    backgroundColor: "#374151",
    borderRadius: 6,
  },
  chartTitle: {
    fontSize: 14,
    fontWeight: "600",
    color: "#F9FAFB",
    marginBottom: 8,
  },
  chartContent: {
    flexDirection: "row",
    alignItems: "flex-end",
    height: 100,
    justifyContent: "space-between",
  },
  chartBar: {
    flex: 1,
    alignItems: "center",
    marginRight: 2,
  },
  chartBarFill: {
    width: "80%",
    backgroundColor: "#10B981",
    borderRadius: 2,
    marginBottom: 4,
  },
  chartLabel: {
    fontSize: 10,
    color: "#9CA3AF",
    textAlign: "center",
  },
  noDataText: {
    fontSize: 12,
    color: "#9CA3AF",
    textAlign: "center",
    fontStyle: "italic",
  },
});

export default PerformanceMonitor;
