/**
 * Kokoro TTS Benchmark Dashboard - Main Page
 * @author @darianrosebrook
 */

"use client";

import React, { useState, useEffect } from "react";
import { BenchmarkSummary } from "@/components/benchmark-summary";
import { PerformanceChart } from "@/components/charts/performance-chart";
import { MemoryTimeline } from "@/components/charts/memory-timeline";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { filterBenchmarks } from "@/lib/benchmark-parser";
import { ProcessedBenchmark } from "@/types/benchmark";

export default function Home() {
  const [benchmarks, setBenchmarks] = useState<ProcessedBenchmark[]>([]);
  const [filteredBenchmarks, setFilteredBenchmarks] = useState<
    ProcessedBenchmark[]
  >([]);
  const [selectedBenchmark, setSelectedBenchmark] =
    useState<ProcessedBenchmark | null>(null);
  const [filter, setFilter] = useState({
    preset: "all" as "all" | "short" | "long",
    stream: "all" as "all" | "true" | "false",
    voice: "all" as string,
  });
  const [loading, setLoading] = useState(true);

  // Load and process benchmark data
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const response = await fetch("/api/benchmarks");

        if (!response.ok) {
          throw new Error(`Failed to fetch benchmarks: ${response.statusText}`);
        }

        const result = await response.json();
        const processed = result.data;

        setBenchmarks(processed);
        setFilteredBenchmarks(processed);
        if (processed.length > 0) {
          setSelectedBenchmark(processed[0]);
        }

        console.log(
          `Loaded ${processed.length} benchmarks from ${result.source} data source`
        );
      } catch (error) {
        console.error("Error loading benchmark data:", error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, []);

  // Apply filters
  useEffect(() => {
    const filters: {
      preset?: "short" | "long";
      stream?: boolean;
      voice?: string;
    } = {};

    if (filter.preset !== "all") {
      filters.preset = filter.preset;
    }

    if (filter.stream !== "all") {
      filters.stream = filter.stream === "true";
    }

    if (filter.voice !== "all") {
      filters.voice = filter.voice;
    }

    const filtered = filterBenchmarks(benchmarks, filters);
    setFilteredBenchmarks(filtered);
  }, [benchmarks, filter]);

  // Get unique voices for filter
  const uniqueVoices = [
    ...new Set(benchmarks.map((b) => b.config.base_payload.voice)),
  ];

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary mx-auto"></div>
          <p className="mt-4 text-lg">Loading benchmark data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-4xl font-bold tracking-tight">
            Kokoro TTS Benchmark Dashboard
          </h1>
          <p className="text-muted-foreground mt-2">
            Performance monitoring and analysis for Kokoro TTS optimization
          </p>
        </div>

        {/* Filters */}
        <Card className="mb-8">
          <CardHeader>
            <CardTitle>Filters</CardTitle>
            <CardDescription>
              Filter benchmark results by configuration
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Preset</label>
                <Select
                  value={filter.preset}
                  onValueChange={(value: "all" | "short" | "long") =>
                    setFilter({ ...filter, preset: value })
                  }
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="short">Short</SelectItem>
                    <SelectItem value="long">Long</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Streaming</label>
                <Select
                  value={filter.stream}
                  onValueChange={(value: "all" | "true" | "false") =>
                    setFilter({ ...filter, stream: value })
                  }
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    <SelectItem value="true">Streaming</SelectItem>
                    <SelectItem value="false">Non-streaming</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium">Voice</label>
                <Select
                  value={filter.voice}
                  onValueChange={(value) =>
                    setFilter({ ...filter, voice: value })
                  }
                >
                  <SelectTrigger className="w-[140px]">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All</SelectItem>
                    {uniqueVoices.map((voice) => (
                      <SelectItem key={voice} value={voice}>
                        {voice}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-end">
                <Button
                  variant="outline"
                  onClick={() =>
                    setFilter({ preset: "all", stream: "all", voice: "all" })
                  }
                >
                  Clear Filters
                </Button>
              </div>
            </div>

            <div className="mt-4 flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                Showing {filteredBenchmarks.length} of {benchmarks.length}{" "}
                benchmarks
              </span>
              {filter.preset !== "all" && (
                <Badge variant="secondary">{filter.preset}</Badge>
              )}
              {filter.stream !== "all" && (
                <Badge variant="secondary">
                  {filter.stream === "true" ? "streaming" : "non-streaming"}
                </Badge>
              )}
              {filter.voice !== "all" && (
                <Badge variant="secondary">{filter.voice}</Badge>
              )}
            </div>
          </CardContent>
        </Card>

        {filteredBenchmarks.length === 0 ? (
          <Card>
            <CardContent className="text-center py-16">
              <p className="text-lg text-muted-foreground">
                No benchmark data matches the current filters.
              </p>
              <Button
                className="mt-4"
                onClick={() =>
                  setFilter({ preset: "all", stream: "all", voice: "all" })
                }
              >
                Clear Filters
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-8">
            {/* Summary */}
            <BenchmarkSummary benchmarks={filteredBenchmarks} />

            {/* Performance Charts */}
            <div className="grid grid-cols-1 xl:grid-cols-2 gap-8">
              <PerformanceChart
                benchmarks={filteredBenchmarks}
                metric="ttfa"
                title="Time to First Audio (TTFA)"
                description="Time from request to first audio chunk delivery"
                height={400}
                width={600}
              />

              <PerformanceChart
                benchmarks={filteredBenchmarks}
                metric="rtf"
                title="Real-Time Factor (RTF)"
                description="Processing time relative to audio duration"
                height={400}
                width={600}
              />
            </div>

            <PerformanceChart
              benchmarks={filteredBenchmarks}
              metric="memory"
              title="Memory Usage"
              description="RSS memory consumption during benchmark runs"
              height={400}
              width={1200}
            />

            {/* Memory Timeline for Selected Benchmark */}
            {selectedBenchmark && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <h2 className="text-2xl font-bold">Memory Timeline</h2>
                  <Select
                    value={selectedBenchmark.id}
                    onValueChange={(value) => {
                      const benchmark = filteredBenchmarks.find(
                        (b) => b.id === value
                      );
                      if (benchmark) setSelectedBenchmark(benchmark);
                    }}
                  >
                    <SelectTrigger className="w-[300px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {filteredBenchmarks.map((benchmark) => (
                        <SelectItem key={benchmark.id} value={benchmark.id}>
                          {benchmark.config.preset} -{" "}
                          {benchmark.config.stream ? "stream" : "non-stream"} -{" "}
                          {benchmark.config.base_payload.voice}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <MemoryTimeline
                  benchmark={selectedBenchmark}
                  height={300}
                  width={1200}
                />
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
