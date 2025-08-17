/**
 * Real benchmark data loader for Kokoro TTS dashboard
 * Loads actual benchmark data from artifacts/bench directory
 * @author @darianrosebrook
 */

import { BenchmarkResult, ProcessedBenchmark } from "@/types/benchmark";
import { processBenchmark } from "@/lib/benchmark-parser";
import fs from "fs";
import path from "path";

/**
 * Load benchmark files from the artifacts directory
 * @returns Array of processed benchmark results
 */
export async function loadRealBenchmarkData(): Promise<ProcessedBenchmark[]> {
  const benchmarks: ProcessedBenchmark[] = [];

  try {
    // Get the artifacts directory path relative to the project root
    const artifactsPath = path.resolve(process.cwd(), "../artifacts/bench");

    if (!fs.existsSync(artifactsPath)) {
      console.warn(
        "Artifacts directory not found, falling back to empty array"
      );
      return [];
    }

    // Get all date directories (e.g., 2025-08-16)
    const dateDirs = fs
      .readdirSync(artifactsPath, { withFileTypes: true })
      .filter((dirent) => dirent.isDirectory())
      .map((dirent) => dirent.name)
      .sort((a, b) => b.localeCompare(a)); // Latest dates first

    for (const dateDir of dateDirs) {
      const datePath = path.join(artifactsPath, dateDir);

      // Get all JSON benchmark files
      const files = fs
        .readdirSync(datePath)
        .filter((file) => file.endsWith(".json") && file.startsWith("bench_"))
        .sort((a, b) => b.localeCompare(a)); // Latest files first

      for (const file of files) {
        try {
          const filePath = path.join(datePath, file);
          const content = fs.readFileSync(filePath, "utf-8");
          const rawData: BenchmarkResult = JSON.parse(content);

          // Extract timestamp from file path for better timestamp handling
          const timestampMatch = file.match(/(\d{6})\.json$/);
          let timestamp = new Date().toISOString();

          if (timestampMatch) {
            const timeStr = timestampMatch[1];
            const hours = timeStr.substring(0, 2);
            const minutes = timeStr.substring(2, 4);
            const seconds = timeStr.substring(4, 6);

            // Use date from directory name
            const dateParts = dateDir.split("-");
            if (dateParts.length === 3) {
              const year = parseInt(dateParts[0]);
              const month = parseInt(dateParts[1]) - 1; // JS months are 0-indexed
              const day = parseInt(dateParts[2]);

              const benchmarkDate = new Date(
                year,
                month,
                day,
                parseInt(hours),
                parseInt(minutes),
                parseInt(seconds)
              );

              timestamp = benchmarkDate.toISOString();
            }
          }

          // Override the timestamp in metadata if available
          if (rawData.metadata) {
            rawData.metadata.timestamp = timestamp;
          } else {
            rawData.metadata = { timestamp };
          }

          const processed = processBenchmark(rawData, file);
          benchmarks.push(processed);
        } catch (error) {
          console.error(`Failed to process benchmark file ${file}:`, error);
        }
      }
    }

    // Sort by timestamp (newest first)
    return benchmarks.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  } catch (error) {
    console.error("Error loading real benchmark data:", error);
    return [];
  }
}

/**
 * Get the latest benchmark data for server-side rendering
 * This is a synchronous version for use in getStaticProps or getServerSideProps
 */
export function loadRealBenchmarkDataSync(): ProcessedBenchmark[] {
  const benchmarks: ProcessedBenchmark[] = [];

  try {
    // Get the artifacts directory path relative to the project root
    const artifactsPath = path.resolve(process.cwd(), "../artifacts/bench");

    if (!fs.existsSync(artifactsPath)) {
      console.warn(
        "Artifacts directory not found, falling back to empty array"
      );
      return [];
    }

    // Get all date directories (e.g., 2025-08-16)
    const dateDirs = fs
      .readdirSync(artifactsPath, { withFileTypes: true })
      .filter((dirent) => dirent.isDirectory())
      .map((dirent) => dirent.name)
      .sort((a, b) => b.localeCompare(a)); // Latest dates first

    for (const dateDir of dateDirs) {
      const datePath = path.join(artifactsPath, dateDir);

      // Get all JSON benchmark files
      const files = fs
        .readdirSync(datePath)
        .filter((file) => file.endsWith(".json") && file.startsWith("bench_"))
        .sort((a, b) => b.localeCompare(a)); // Latest files first

      for (const file of files) {
        try {
          const filePath = path.join(datePath, file);
          const content = fs.readFileSync(filePath, "utf-8");
          const rawData: BenchmarkResult = JSON.parse(content);

          // Extract timestamp from file path for better timestamp handling
          const timestampMatch = file.match(/(\d{6})\.json$/);
          let timestamp = new Date().toISOString();

          if (timestampMatch) {
            const timeStr = timestampMatch[1];
            const hours = timeStr.substring(0, 2);
            const minutes = timeStr.substring(2, 4);
            const seconds = timeStr.substring(4, 6);

            // Use date from directory name
            const dateParts = dateDir.split("-");
            if (dateParts.length === 3) {
              const year = parseInt(dateParts[0]);
              const month = parseInt(dateParts[1]) - 1; // JS months are 0-indexed
              const day = parseInt(dateParts[2]);

              const benchmarkDate = new Date(
                year,
                month,
                day,
                parseInt(hours),
                parseInt(minutes),
                parseInt(seconds)
              );

              timestamp = benchmarkDate.toISOString();
            }
          }

          // Override the timestamp in metadata if available
          if (rawData.metadata) {
            rawData.metadata.timestamp = timestamp;
          } else {
            rawData.metadata = { timestamp };
          }

          const processed = processBenchmark(rawData, file);
          benchmarks.push(processed);
        } catch (error) {
          console.error(`Failed to process benchmark file ${file}:`, error);
        }
      }
    }

    // Sort by timestamp (newest first)
    return benchmarks.sort(
      (a, b) =>
        new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
    );
  } catch (error) {
    console.error("Error loading real benchmark data:", error);
    return [];
  }
}

/**
 * Check if real benchmark data is available
 * @returns true if artifacts directory exists and contains data
 */
export function hasRealBenchmarkData(): boolean {
  try {
    const artifactsPath = path.resolve(process.cwd(), "../artifacts/bench");

    if (!fs.existsSync(artifactsPath)) {
      return false;
    }

    const dateDirs = fs
      .readdirSync(artifactsPath, { withFileTypes: true })
      .filter((dirent) => dirent.isDirectory());

    // Check if any date directory has benchmark JSON files
    for (const dateDir of dateDirs) {
      const datePath = path.join(artifactsPath, dateDir.name);
      const files = fs
        .readdirSync(datePath)
        .filter((file) => file.endsWith(".json") && file.startsWith("bench_"));

      if (files.length > 0) {
        return true;
      }
    }

    return false;
  } catch (error) {
    console.error("Error checking for real benchmark data:", error);
    return false;
  }
}
