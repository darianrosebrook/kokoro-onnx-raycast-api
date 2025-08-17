/**
 * Benchmark data parsing utilities for Kokoro TTS dashboard
 * @author @darianrosebrook
 */

import {
  BenchmarkResult,
  BenchmarkStats,
  ProcessedBenchmark,
} from "@/types/benchmark";
import { format } from "date-fns";

/**
 * Calculate percentile statistics from a numeric array
 * @param values - Array of numeric values
 * @returns Statistical summary including percentiles
 */
export function calculateStats(values: number[]): BenchmarkStats {
  if (values.length === 0) {
    return {
      p50: 0,
      p95: 0,
      p99: 0,
      min: 0,
      max: 0,
      mean: 0,
      std: 0,
      count: 0,
    };
  }

  const sorted = [...values].sort((a, b) => a - b);
  const count = sorted.length;

  const percentile = (p: number) => {
    const index = Math.ceil((p / 100) * count) - 1;
    return sorted[Math.max(0, Math.min(index, count - 1))];
  };

  const mean = values.reduce((sum, val) => sum + val, 0) / count;
  const variance =
    values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / count;
  const std = Math.sqrt(variance);

  return {
    p50: percentile(50),
    p95: percentile(95),
    p99: percentile(99),
    min: Math.min(...values),
    max: Math.max(...values),
    mean,
    std,
    count,
  };
}

/**
 * Extract timestamp from filename or use current date
 * @param filename - Benchmark filename
 * @returns ISO timestamp string
 */
export function extractTimestamp(filename: string): string {
  // Extract timestamp from filename like "bench_stream_long_224748.json"
  const timestampMatch = filename.match(/(\d{6})\.json$/);

  if (timestampMatch) {
    const timeStr = timestampMatch[1];
    // Assume format is HHMMSS
    const hours = timeStr.substring(0, 2);
    const minutes = timeStr.substring(2, 4);
    const seconds = timeStr.substring(4, 6);

    // Use today's date with extracted time
    const today = new Date();
    const extractedDate = new Date(
      today.getFullYear(),
      today.getMonth(),
      today.getDate(),
      parseInt(hours),
      parseInt(minutes),
      parseInt(seconds)
    );

    return extractedDate.toISOString();
  }

  return new Date().toISOString();
}

/**
 * Generate unique ID for benchmark result
 * @param config - Benchmark configuration
 * @param timestamp - Benchmark timestamp
 * @returns Unique identifier
 */
export function generateBenchmarkId(
  config: BenchmarkResult["config"],
  timestamp: string
): string {
  const preset = config.preset;
  const stream = config.stream ? "stream" : "nonstream";
  const voice = config.base_payload.voice;
  const date = format(new Date(timestamp), "yyyyMMdd_HHmmss");

  // Add milliseconds and random suffix to ensure uniqueness
  const ms = new Date(timestamp).getMilliseconds().toString().padStart(3, "0");
  const randomSuffix = Math.random().toString(36).substring(2, 8);

  return `${preset}_${stream}_${voice}_${date}_${ms}_${randomSuffix}`;
}

/**
 * Process raw benchmark data into structured format
 * @param rawData - Raw benchmark JSON data
 * @param filename - Original filename for timestamp extraction
 * @returns Processed benchmark with statistics
 */
export function processBenchmark(
  rawData: BenchmarkResult,
  filename?: string
): ProcessedBenchmark {
  // Use metadata timestamp if available, otherwise extract from filename
  const timestamp = rawData.metadata?.timestamp
    ? rawData.metadata.timestamp
    : filename
    ? extractTimestamp(filename)
    : new Date().toISOString();

  const id = generateBenchmarkId(rawData.config, timestamp);

  // Calculate TTFA statistics - handle potential empty arrays
  const ttfaMeasurements = rawData.measurements.ttfa_ms ?? [];
  const ttfaStats = calculateStats(ttfaMeasurements);

  // Calculate RTF statistics - handle potential empty arrays
  const rtfMeasurements = rawData.measurements.rtf ?? [];
  const rtfStats = calculateStats(rtfMeasurements);

  // Calculate memory statistics
  const memSamples = rawData.measurements.mem_samples ?? [];
  const rssSamples = memSamples
    .map((sample) => sample.rss_mb)
    .filter((val) => !isNaN(val));
  const cpuSamples = memSamples
    .map((sample) => sample.cpu_pct)
    .filter((val) => !isNaN(val));

  const memoryStats = {
    peak_rss_mb: rssSamples.length > 0 ? Math.max(...rssSamples) : 0,
    avg_rss_mb:
      rssSamples.length > 0
        ? rssSamples.reduce((sum, val) => sum + val, 0) / rssSamples.length
        : 0,
    avg_cpu_pct:
      cpuSamples.length > 0
        ? cpuSamples.reduce((sum, val) => sum + val, 0) / cpuSamples.length
        : 0,
  };

  return {
    id,
    timestamp,
    config: rawData.config,
    stats: {
      ttfa: ttfaStats,
      rtf: rtfStats,
      memory: memoryStats,
    },
    raw: rawData,
  };
}

/**
 * Parse multiple benchmark files from a directory structure
 * @param benchmarkFiles - Array of {filename, content} objects
 * @returns Array of processed benchmarks
 */
export function parseBenchmarkFiles(
  benchmarkFiles: { filename: string; content: string }[]
): ProcessedBenchmark[] {
  const processed: ProcessedBenchmark[] = [];

  for (const file of benchmarkFiles) {
    try {
      const rawData: BenchmarkResult = JSON.parse(file.content);
      const processedBenchmark = processBenchmark(rawData, file.filename);
      processed.push(processedBenchmark);
    } catch (error) {
      console.error(`Failed to parse benchmark file ${file.filename}:`, error);
    }
  }

  // Sort by timestamp (newest first)
  return processed.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}

/**
 * Filter benchmarks by criteria
 * @param benchmarks - Array of processed benchmarks
 * @param filters - Filter criteria
 * @returns Filtered benchmark array
 */
export function filterBenchmarks(
  benchmarks: ProcessedBenchmark[],
  filters: {
    preset?: "short" | "long";
    stream?: boolean;
    voice?: string;
    dateRange?: { start: Date; end: Date };
  }
): ProcessedBenchmark[] {
  return benchmarks.filter((benchmark) => {
    if (filters.preset && benchmark.config.preset !== filters.preset) {
      return false;
    }

    if (
      filters.stream !== undefined &&
      benchmark.config.stream !== filters.stream
    ) {
      return false;
    }

    if (
      filters.voice &&
      benchmark.config.base_payload.voice !== filters.voice
    ) {
      return false;
    }

    if (filters.dateRange) {
      const benchmarkDate = new Date(benchmark.timestamp);
      if (
        benchmarkDate < filters.dateRange.start ||
        benchmarkDate > filters.dateRange.end
      ) {
        return false;
      }
    }

    return true;
  });
}

/**
 * Group benchmarks by configuration type
 * @param benchmarks - Array of processed benchmarks
 * @returns Grouped benchmarks by preset and stream type
 */
export function groupBenchmarksByType(
  benchmarks: ProcessedBenchmark[]
): Record<string, ProcessedBenchmark[]> {
  const groups: Record<string, ProcessedBenchmark[]> = {};

  for (const benchmark of benchmarks) {
    const key = `${benchmark.config.preset}_${
      benchmark.config.stream ? "stream" : "nonstream"
    }`;
    if (!groups[key]) {
      groups[key] = [];
    }
    groups[key].push(benchmark);
  }

  return groups;
}
