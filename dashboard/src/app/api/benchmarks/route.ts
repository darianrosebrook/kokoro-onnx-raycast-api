/**
 * API route for serving real benchmark data
 * @author @darianrosebrook
 */

import { NextResponse } from "next/server";
import {
  loadRealBenchmarkDataSync,
  hasRealBenchmarkData,
} from "@/lib/real-data-loader";
import { generateMockBenchmarkData } from "@/lib/mock-data";
import { processBenchmark } from "@/lib/benchmark-parser";

export async function GET() {
  try {
    // Check if real benchmark data is available
    const hasRealData = hasRealBenchmarkData();

    if (hasRealData) {
      console.log("Loading real benchmark data from artifacts directory");
      const realData = loadRealBenchmarkDataSync();

      if (realData.length > 0) {
        return NextResponse.json({
          source: "real",
          data: realData,
          count: realData.length,
        });
      }
    }

    // Fall back to mock data if no real data is available
    console.log("Falling back to mock benchmark data");
    const mockData = generateMockBenchmarkData();
    const processedMockData = mockData.map((raw, index) =>
      processBenchmark(raw, `mock_benchmark_${index}.json`)
    );

    return NextResponse.json({
      source: "mock",
      data: processedMockData,
      count: processedMockData.length,
    });
  } catch (error) {
    console.error("Error in benchmarks API route:", error);
    return NextResponse.json(
      { error: "Failed to load benchmark data" },
      { status: 500 }
    );
  }
}
