/**
 * Benchmark summary dashboard component
 * @author @darianrosebrook
 */

"use client";

import React from "react";
import { ProcessedBenchmark } from "@/types/benchmark";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatDistanceToNow } from "date-fns";

interface BenchmarkSummaryProps {
  /** Latest benchmark results */
  benchmarks: ProcessedBenchmark[];
  /** Maximum number of recent benchmarks to show */
  maxRecent?: number;
}

/**
 * Summary component showing key metrics and recent benchmark results
 */
export function BenchmarkSummary({
  benchmarks,
  maxRecent = 5,
}: BenchmarkSummaryProps) {
  const recentBenchmarks = benchmarks.slice(0, maxRecent);

  // Calculate overall statistics
  const totalBenchmarks = benchmarks.length;
  const avgTTFA =
    benchmarks.reduce((sum, b) => sum + b.stats.ttfa.mean, 0) /
      totalBenchmarks || 0;
  const avgRTF =
    benchmarks.reduce((sum, b) => sum + b.stats.rtf.mean, 0) /
      totalBenchmarks || 0;
  const avgMemory =
    benchmarks.reduce((sum, b) => sum + b.stats.memory.avg_rss_mb, 0) /
      totalBenchmarks || 0;

  // Get latest benchmark for comparison
  const latest = benchmarks[0];
  const previous = benchmarks[1];

  /**
   * Calculate trend indicator for a metric
   */
  const getTrend = (
    current: number,
    previous: number
  ): "improving" | "degrading" | "stable" => {
    if (!previous) return "stable";
    const change = ((current - previous) / previous) * 100;
    if (Math.abs(change) < 5) return "stable";
    return change < 0 ? "improving" : "degrading";
  };

  const ttfaTrend =
    latest && previous
      ? getTrend(latest.stats.ttfa.p95, previous.stats.ttfa.p95)
      : "stable";
  const rtfTrend =
    latest && previous
      ? getTrend(latest.stats.rtf.p95, previous.stats.rtf.p95)
      : "stable";
  const memoryTrend =
    latest && previous
      ? getTrend(
          latest.stats.memory.peak_rss_mb,
          previous.stats.memory.peak_rss_mb
        )
      : "stable";

  /**
   * Get badge variant based on trend
   */
  const getTrendVariant = (trend: "improving" | "degrading" | "stable") => {
    switch (trend) {
      case "improving":
        return "default";
      case "degrading":
        return "destructive";
      case "stable":
        return "secondary";
    }
  };

  /**
   * Get trend icon
   */
  const getTrendIcon = (trend: "improving" | "degrading" | "stable") => {
    switch (trend) {
      case "improving":
        return "↓";
      case "degrading":
        return "↑";
      case "stable":
        return "→";
    }
  };

  return (
    <div className="space-y-6">
      {/* Overview Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Total Benchmarks
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalBenchmarks}</div>
            <p className="text-xs text-muted-foreground">
              {latest &&
                `Latest: ${formatDistanceToNow(
                  new Date(latest.timestamp)
                )} ago`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">
              Avg TTFA (P95)
            </CardTitle>
            <Badge variant={getTrendVariant(ttfaTrend)}>
              {getTrendIcon(ttfaTrend)} {ttfaTrend}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgTTFA.toFixed(1)}ms</div>
            <p className="text-xs text-muted-foreground">
              {latest && `Latest: ${latest.stats.ttfa.p95.toFixed(1)}ms`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg RTF (P95)</CardTitle>
            <Badge variant={getTrendVariant(rtfTrend)}>
              {getTrendIcon(rtfTrend)} {rtfTrend}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgRTF.toFixed(2)}</div>
            <p className="text-xs text-muted-foreground">
              {latest && `Latest: ${latest.stats.rtf.p95.toFixed(2)}`}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Memory</CardTitle>
            <Badge variant={getTrendVariant(memoryTrend)}>
              {getTrendIcon(memoryTrend)} {memoryTrend}
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{avgMemory.toFixed(1)}MB</div>
            <p className="text-xs text-muted-foreground">
              {latest &&
                `Peak: ${latest.stats.memory.peak_rss_mb.toFixed(1)}MB`}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Recent Benchmarks */}
      <Card>
        <CardHeader>
          <CardTitle>Recent Benchmarks</CardTitle>
          <CardDescription>
            Latest {maxRecent} benchmark results
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {recentBenchmarks.map((benchmark) => (
              <div
                key={benchmark.id}
                className="flex items-center justify-between p-4 border rounded-lg"
              >
                <div className="space-y-1">
                  <div className="flex items-center space-x-2">
                    <Badge variant="outline">{benchmark.config.preset}</Badge>
                    <Badge
                      variant={
                        benchmark.config.stream ? "default" : "secondary"
                      }
                    >
                      {benchmark.config.stream ? "streaming" : "non-streaming"}
                    </Badge>
                    <span className="text-sm text-muted-foreground">
                      {benchmark.config.base_payload.voice}
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground">
                    {formatDistanceToNow(new Date(benchmark.timestamp))} ago
                  </div>
                </div>

                <div className="text-right space-y-1">
                  <div className="flex space-x-4 text-sm">
                    <span>
                      TTFA:{" "}
                      <strong>{benchmark.stats.ttfa.p95.toFixed(1)}ms</strong>
                    </span>
                    <span>
                      RTF: <strong>{benchmark.stats.rtf.p95.toFixed(2)}</strong>
                    </span>
                    <span>
                      Mem:{" "}
                      <strong>
                        {benchmark.stats.memory.peak_rss_mb.toFixed(1)}MB
                      </strong>
                    </span>
                  </div>
                  <div className="text-xs text-muted-foreground">
                    {benchmark.stats.ttfa.count} trials
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
