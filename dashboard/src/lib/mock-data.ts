/**
 * Mock data for development and testing
 * @author @darianrosebrook
 */

import { BenchmarkResult } from "@/types/benchmark";

/**
 * Generate mock benchmark data for development
 */
export function generateMockBenchmarkData(): BenchmarkResult[] {
  const presets: ("short" | "long")[] = ["short", "long"];
  const streams = [true, false];
  const voices = ["af_heart", "af_bella", "af_sarah"];

  const mockData: BenchmarkResult[] = [];

  // Generate data for the last 7 days
  const now = new Date();
  const daysBack = 7;

  for (let day = 0; day < daysBack; day++) {
    for (const preset of presets) {
      for (const stream of streams) {
        for (const voice of voices) {
          const date = new Date(now);
          date.setDate(date.getDate() - day);
          date.setHours(Math.floor(Math.random() * 24));
          date.setMinutes(Math.floor(Math.random() * 60));
          date.setSeconds(Math.floor(Math.random() * 60));
          date.setMilliseconds(Math.floor(Math.random() * 1000));

          // Generate realistic TTFA values
          const baseTTFA = preset === "short" ? 150 : 2000;
          const ttfaVariation = baseTTFA * 0.2;
          const ttfa_ms = Array.from({ length: 5 }, () =>
            Math.max(0.1, baseTTFA + (Math.random() - 0.5) * ttfaVariation)
          );

          // Generate realistic RTF values
          const baseRTF = stream
            ? preset === "short"
              ? 0.8
              : 1.2
            : preset === "short"
            ? 0.6
            : 1.0;
          const rtfVariation = baseRTF * 0.3;
          const rtf = Array.from({ length: 3 }, () =>
            Math.max(0.1, baseRTF + (Math.random() - 0.5) * rtfVariation)
          );

          // Generate memory samples (simulating 30 seconds of monitoring)
          const memSamples = [];
          const baseTime = date.getTime() / 1000;
          const baseMemory = 45 + Math.random() * 10; // 45-55 MB base

          for (let i = 0; i < 60; i++) {
            // 30 seconds, 0.5s intervals
            const time = baseTime + i * 0.5;
            const memoryNoise = (Math.random() - 0.5) * 5;
            const cpuSpike =
              i > 20 && i < 30 ? Math.random() * 100 : Math.random() * 20;

            memSamples.push({
              t: time,
              rss_mb: Math.max(
                30,
                baseMemory + memoryNoise + (i > 20 && i < 30 ? 5 : 0)
              ),
              cpu_pct: cpuSpike,
            });
          }

          const benchmark: BenchmarkResult = {
            config: {
              url: "http://localhost:8000/v1/audio/speech",
              headers: {},
              base_payload: {
                voice,
                speed: 1.0,
                lang: "en-us",
                format: "wav",
              },
              trials: 5,
              stream,
              preset,
              timeout_s: 120,
              concurrency: 1,
              soak_iterations: 600,
            },
            measurements: {
              ttfa_ms,
              rtf,
              lufs: [-16.2, -15.8, -16.1], // Mock loudness values
              dbtp: [-1.2, -0.8, -1.1], // Mock true peak values
              mem_samples: memSamples,
            },
            metadata: {
              timestamp: date.toISOString(),
              duration_ms: 30000,
              success_rate: 0.95 + Math.random() * 0.05,
              error_count: Math.floor(Math.random() * 3),
            },
          };

          mockData.push(benchmark);
        }
      }
    }
  }

  return mockData;
}

/**
 * Load benchmark data from localStorage or generate mock data
 */
export function loadBenchmarkData(): BenchmarkResult[] {
  if (typeof window === "undefined") {
    return generateMockBenchmarkData();
  }

  // For development: clear cache if data exists to regenerate with new unique IDs
  const isDevelopment = process.env.NODE_ENV === "development";
  if (isDevelopment) {
    try {
      localStorage.removeItem("kokoro-benchmark-data");
    } catch (error) {
      // Ignore localStorage errors
    }
  }

  try {
    const stored = localStorage.getItem("kokoro-benchmark-data");
    if (stored && !isDevelopment) {
      return JSON.parse(stored);
    }
  } catch (error) {
    console.error("Error loading stored benchmark data:", error);
  }

  const mockData = generateMockBenchmarkData();

  // Store mock data for consistency (only in production)
  if (!isDevelopment) {
    try {
      localStorage.setItem("kokoro-benchmark-data", JSON.stringify(mockData));
    } catch (error) {
      console.error("Error storing mock benchmark data:", error);
    }
  }

  return mockData;
}

/**
 * Save benchmark data to localStorage
 */
export function saveBenchmarkData(data: BenchmarkResult[]): void {
  if (typeof window === "undefined") return;

  try {
    localStorage.setItem("kokoro-benchmark-data", JSON.stringify(data));
  } catch (error) {
    console.error("Error saving benchmark data:", error);
  }
}
