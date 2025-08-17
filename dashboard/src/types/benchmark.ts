/**
 * Benchmark data types for Kokoro TTS performance analysis
 * @author @darianrosebrook
 */

export interface BenchmarkConfig {
  url: string;
  headers: Record<string, string>;
  base_payload: {
    voice: string;
    speed: number;
    lang: string;
    format: string;
  };
  trials: number;
  stream: boolean;
  preset: "short" | "long";
  timeout_s: number;
  concurrency: number;
  soak_iterations: number;
}

export interface MemorySample {
  /** Timestamp */
  t: number;
  /** Resident Set Size in MB */
  rss_mb: number;
  /** CPU percentage */
  cpu_pct: number;
}

export interface BenchmarkMeasurements {
  /** Time to First Audio in milliseconds */
  ttfa_ms: number[];
  /** Real-Time Factor */
  rtf: number[];
  /** Loudness Units relative to Full Scale */
  lufs: number[];
  /** True Peak in dB */
  dbtp: number[];
  /** Memory usage samples over time */
  mem_samples: MemorySample[];
}

export interface BenchmarkResult {
  config: BenchmarkConfig;
  measurements: BenchmarkMeasurements;
  /** Optional metadata */
  metadata?: {
    timestamp?: string;
    duration_ms?: number;
    success_rate?: number;
    error_count?: number;
  };
}

export interface BenchmarkStats {
  /** Percentile statistics */
  p50: number;
  p95: number;
  p99: number;
  min: number;
  max: number;
  mean: number;
  std: number;
  count: number;
}

export interface ProcessedBenchmark {
  id: string;
  timestamp: string;
  config: BenchmarkConfig;
  stats: {
    ttfa: BenchmarkStats;
    rtf: BenchmarkStats;
    memory: {
      peak_rss_mb: number;
      avg_rss_mb: number;
      avg_cpu_pct: number;
    };
  };
  raw: BenchmarkResult;
}

export interface BenchmarkSummary {
  total_benchmarks: number;
  date_range: {
    start: string;
    end: string;
  };
  performance_trends: {
    ttfa_p95_trend: "improving" | "degrading" | "stable";
    rtf_p95_trend: "improving" | "degrading" | "stable";
    memory_trend: "improving" | "degrading" | "stable";
  };
  latest_results: ProcessedBenchmark[];
}
