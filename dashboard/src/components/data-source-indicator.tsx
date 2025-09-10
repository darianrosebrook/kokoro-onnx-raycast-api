/**
 * Data source indicator component
 * Shows whether the dashboard is using real or mock data
 * @author @darianrosebrook
 */

"use client";

import React, { useState, useEffect } from "react";
import { Badge } from "@/components/ui/badge";

export function DataSourceIndicator() {
  const [dataSource, setDataSource] = useState<"real" | "mock" | "loading">(
    "loading"
  );
  const [benchmarkCount, setBenchmarkCount] = useState<number>(0);

  useEffect(() => {
    const checkDataSource = async () => {
      try {
        const response = await fetch("/api/benchmarks");
        if (response.ok) {
          const result = await response.json();
          setDataSource(result.source);
          setBenchmarkCount(result.count);
        }
      } catch (error) {
        console.error("Failed to check data source:", error);
        setDataSource("mock");
      }
    };

    checkDataSource();
  }, []);

  if (dataSource === "loading") {
    return (
      <Badge variant="outline" className="animate-pulse">
        Loading...
      </Badge>
    );
  }

  return (
    <div className="flex items-center space-x-2">
      <Badge
        variant={dataSource === "real" ? "default" : "secondary"}
        className={
          dataSource === "real" ? "bg-green-600 hover:bg-green-700" : ""
        }
      >
        {dataSource === "real" ? "✅ Real Data" : " Mock Data"}
      </Badge>
      <span className="text-sm text-muted-foreground">
        {benchmarkCount} benchmark{benchmarkCount !== 1 ? "s" : ""}
      </span>
    </div>
  );
}
