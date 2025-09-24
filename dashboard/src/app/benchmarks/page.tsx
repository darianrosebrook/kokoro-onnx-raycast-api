/**
 * Detailed Benchmarks Page
 * @author @darianrosebrook
 */

"use client";

import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { MemoryTimeline } from "@/components/charts/memory-timeline";
import { ProcessedBenchmark } from "@/types/benchmark";
import { formatDistanceToNow } from "date-fns";

export default function BenchmarksPage() {
  const [benchmarks, setBenchmarks] = useState<ProcessedBenchmark[]>([]);
  const [selectedBenchmark, setSelectedBenchmark] =
    useState<ProcessedBenchmark | null>(null);
  const [loading, setLoading] = useState(true);

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
            Detailed Benchmarks
          </h1>
          <p className="text-muted-foreground mt-2">
            Complete benchmark results with detailed analysis
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Benchmarks Table */}
          <Card>
            <CardHeader>
              <CardTitle>All Benchmark Results</CardTitle>
              <CardDescription>
                Click on a benchmark to view detailed memory timeline
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="max-h-[600px] overflow-y-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Configuration</TableHead>
                      <TableHead>TTFA (P95)</TableHead>
                      <TableHead>RTF (P95)</TableHead>
                      <TableHead>Memory Peak</TableHead>
                      <TableHead>Time</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {benchmarks.map((benchmark) => (
                      <TableRow
                        key={benchmark.id}
                        className={`cursor-pointer hover:bg-muted/50 ${
                          selectedBenchmark?.id === benchmark.id
                            ? "bg-muted"
                            : ""
                        }`}
                        onClick={() => setSelectedBenchmark(benchmark)}
                      >
                        <TableCell>
                          <div className="space-y-1">
                            <div className="flex items-center space-x-2">
                              <Badge variant="outline">
                                {benchmark.config.preset}
                              </Badge>
                              <Badge
                                variant={
                                  benchmark.config.stream
                                    ? "default"
                                    : "secondary"
                                }
                              >
                                {benchmark.config.stream
                                  ? "stream"
                                  : "non-stream"}
                              </Badge>
                            </div>
                            <div className="text-sm text-muted-foreground">
                              {benchmark.config.base_payload.voice}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>
                          <span className="font-mono">
                            {benchmark.stats.ttfa.p95.toFixed(1)}ms
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="font-mono">
                            {benchmark.stats.rtf.p95.toFixed(2)}
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="font-mono">
                            {benchmark.stats.memory.peak_rss_mb.toFixed(1)}MB
                          </span>
                        </TableCell>
                        <TableCell>
                          <span className="text-sm">
                            {formatDistanceToNow(new Date(benchmark.timestamp))}{" "}
                            ago
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          {/* Selected Benchmark Details */}
          <Card>
            <CardHeader>
              <CardTitle>Benchmark Details</CardTitle>
              <CardDescription>
                {selectedBenchmark
                  ? `${selectedBenchmark.config.preset} ${
                      selectedBenchmark.config.stream
                        ? "streaming"
                        : "non-streaming"
                    } - ${selectedBenchmark.config.base_payload.voice}`
                  : "Select a benchmark to view details"}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {selectedBenchmark ? (
                <div className="space-y-6">
                  {/* Configuration */}
                  <div>
                    <h3 className="text-lg font-semibold mb-3">
                      Configuration
                    </h3>
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-muted-foreground">Preset:</span>
                        <span className="ml-2 font-medium">
                          {selectedBenchmark.config.preset}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">
                          Streaming:
                        </span>
                        <span className="ml-2 font-medium">
                          {selectedBenchmark.config.stream ? "Yes" : "No"}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Voice:</span>
                        <span className="ml-2 font-medium">
                          {selectedBenchmark.config.base_payload.voice}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Trials:</span>
                        <span className="ml-2 font-medium">
                          {selectedBenchmark.config.trials}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Language:</span>
                        <span className="ml-2 font-medium">
                          {selectedBenchmark.config.base_payload.lang}
                        </span>
                      </div>
                      <div>
                        <span className="text-muted-foreground">Format:</span>
                        <span className="ml-2 font-medium">
                          {selectedBenchmark.config.base_payload.format}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Performance Metrics */}
                  <div>
                    <h3 className="text-lg font-semibold mb-3">
                      Performance Metrics
                    </h3>
                    <div className="grid grid-cols-1 gap-4">
                      {/* TTFA Stats */}
                      <div className="p-4 border rounded-lg">
                        <h4 className="font-medium mb-2">
                          Time to First Audio
                        </h4>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          <div>
                            <span className="text-muted-foreground">Mean:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.ttfa.mean.toFixed(1)}ms
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">P95:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.ttfa.p95.toFixed(1)}ms
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">P99:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.ttfa.p99.toFixed(1)}ms
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* RTF Stats */}
                      <div className="p-4 border rounded-lg">
                        <h4 className="font-medium mb-2">Real-Time Factor</h4>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          <div>
                            <span className="text-muted-foreground">Mean:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.rtf.mean.toFixed(2)}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">P95:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.rtf.p95.toFixed(2)}
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">P99:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.rtf.p99.toFixed(2)}
                            </span>
                          </div>
                        </div>
                      </div>

                      {/* Memory Stats */}
                      <div className="p-4 border rounded-lg">
                        <h4 className="font-medium mb-2">Memory Usage</h4>
                        <div className="grid grid-cols-3 gap-2 text-sm">
                          <div>
                            <span className="text-muted-foreground">
                              Average:
                            </span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.memory.avg_rss_mb.toFixed(
                                1
                              )}
                              MB
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">Peak:</span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.memory.peak_rss_mb.toFixed(
                                1
                              )}
                              MB
                            </span>
                          </div>
                          <div>
                            <span className="text-muted-foreground">
                              Avg CPU:
                            </span>
                            <span className="ml-1 font-mono">
                              {selectedBenchmark.stats.memory.avg_cpu_pct.toFixed(
                                1
                              )}
                              %
                            </span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center py-16 text-muted-foreground">
                  Select a benchmark from the table to view detailed metrics
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Memory Timeline */}
        {selectedBenchmark && (
          <div className="mt-8">
            <MemoryTimeline
              benchmark={selectedBenchmark}
              height={400}
              width={1200}
            />
          </div>
        )}
      </div>
    </div>
  );
}
