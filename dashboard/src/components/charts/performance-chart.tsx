/**
 * Performance chart component using D3 for Kokoro TTS benchmarks
 * @author @darianrosebrook
 */

"use client";

import React, { useEffect, useRef, useState } from "react";
import * as d3 from "d3";
import { ProcessedBenchmark } from "@/types/benchmark";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface PerformanceChartProps {
  /** Benchmark data to visualize */
  benchmarks: ProcessedBenchmark[];
  /** Metric to display */
  metric: "ttfa" | "rtf" | "memory";
  /** Chart title */
  title: string;
  /** Chart description */
  description?: string;
  /** Chart height in pixels */
  height?: number;
  /** Chart width in pixels */
  width?: number;
  /** Whether to show performance threshold lines */
  showThresholds?: boolean;
}

/**
 * Performance chart component for visualizing benchmark metrics over time
 */
export function PerformanceChart({
  benchmarks,
  metric,
  title,
  description,
  height = 400,
  width,
  showThresholds = true,
}: PerformanceChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 800, height });

  // Handle responsive sizing
  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      const container = entries[0];
      if (container) {
        const containerWidth = container.contentRect.width;
        const effectiveWidth = width || Math.max(containerWidth - 32, 400); // Account for padding
        setDimensions({ width: effectiveWidth, height });
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, [width, height]);

  useEffect(() => {
    if (!svgRef.current || benchmarks.length === 0) return;

    // Clear previous chart
    d3.select(svgRef.current).selectAll("*").remove();

    // Performance thresholds from expected_bands.json
    const getThreshold = (metric: "ttfa" | "rtf" | "memory"): number | null => {
      switch (metric) {
        case "ttfa":
          return 500; // P95 threshold in ms
        case "rtf":
          return 0.6; // P95 threshold
        case "memory":
          return 300; // RSS envelope in MB
        default:
          return null;
      }
    };

    const svg = d3.select(svgRef.current);
    const margin = {
      top: 20,
      right: dimensions.width < 600 ? 20 : 30,
      bottom: 40,
      left: dimensions.width < 600 ? 40 : 50,
    };
    const chartWidth = dimensions.width - margin.left - margin.right;
    const chartHeight = dimensions.height - margin.top - margin.bottom;

    // Create chart group
    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // No zoom/pan functionality - removed for cleaner interaction

    // Prepare data
    const data = benchmarks
      .map((benchmark) => {
        let value: number;
        let p95Value: number;

        switch (metric) {
          case "ttfa":
            value = benchmark.stats.ttfa.mean;
            p95Value = benchmark.stats.ttfa.p95;
            break;
          case "rtf":
            value = benchmark.stats.rtf.mean;
            p95Value = benchmark.stats.rtf.p95;
            break;
          case "memory":
            value = benchmark.stats.memory.avg_rss_mb;
            p95Value = benchmark.stats.memory.peak_rss_mb;
            break;
          default:
            value = 0;
            p95Value = 0;
        }

        return {
          date: new Date(benchmark.timestamp),
          value,
          p95Value,
          benchmark,
        };
      })
      .sort((a, b) => a.date.getTime() - b.date.getTime());

    // Scales
    const xScale = d3
      .scaleTime()
      .domain(d3.extent(data, (d) => d.date) as [Date, Date])
      .range([0, chartWidth]);

    const threshold = getThreshold(metric);
    const maxValue = d3.max(data, (d) =>
      Math.max(d.value, d.p95Value)
    ) as number;
    const yDomain = threshold
      ? [0, Math.max(maxValue, threshold * 1.1)]
      : [0, maxValue];

    const yScale = d3
      .scaleLinear()
      .domain(yDomain)
      .nice()
      .range([chartHeight, 0]);

    // Accessible color scale for different benchmark types
    const accessibleColors = [
      "#1f77b4", // blue (safe for colorblind)
      "#ff7f0e", // orange
      "#2ca02c", // green
      "#d62728", // red
      "#9467bd", // purple
      "#8c564b", // brown
      "#e377c2", // pink
      "#7f7f7f", // gray
      "#bcbd22", // olive
      "#17becf", // cyan
    ];

    const colorScale = d3
      .scaleOrdinal(accessibleColors)
      .domain([
        ...new Set(
          data.map(
            (d) => `${d.benchmark.config.preset}_${d.benchmark.config.stream}`
          )
        ),
      ]);

    // Line generators
    const meanLine = d3
      .line<(typeof data)[0]>()
      .x((d) => xScale(d.date))
      .y((d) => yScale(d.value))
      .curve(d3.curveMonotoneX);

    const p95Line = d3
      .line<(typeof data)[0]>()
      .x((d) => xScale(d.date))
      .y((d) => yScale(d.p95Value))
      .curve(d3.curveMonotoneX);

    // Add axes
    g.append("g")
      .attr("transform", `translate(0,${chartHeight})`)
      .call(
        d3
          .axisBottom(xScale)
          .tickFormat((d) => {
            const format = dimensions.width < 600 ? "%m/%d" : "%m/%d %H:%M";
            return d3.timeFormat(format)(d as Date);
          })
          .ticks(dimensions.width < 600 ? 4 : 8)
      )
      .selectAll("text")
      .style("font-size", "11px")
      .style("fill", "#374151");

    g.append("g")
      .call(d3.axisLeft(yScale))
      .selectAll("text")
      .style("font-size", "11px")
      .style("fill", "#374151");

    // Style axis lines for better visibility
    g.selectAll(".domain").style("stroke", "#6b7280").style("stroke-width", 1);

    g.selectAll(".tick line")
      .style("stroke", "#e5e7eb")
      .style("stroke-width", 1);

    // Add axis labels with better styling
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left)
      .attr("x", 0 - chartHeight / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .style("font-weight", "500")
      .style("fill", "#374151")
      .text(getYAxisLabel(metric));

    g.append("text")
      .attr(
        "transform",
        `translate(${chartWidth / 2}, ${chartHeight + margin.bottom - 5})`
      )
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .style("font-weight", "500")
      .style("fill", "#374151")
      .text("Time");

    // Add threshold line
    if (showThresholds && threshold) {
      const thresholdY = yScale(threshold);

      // Threshold line
      g.append("line")
        .attr("x1", 0)
        .attr("x2", chartWidth)
        .attr("y1", thresholdY)
        .attr("y2", thresholdY)
        .attr("stroke", "#ef4444")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "8,4")
        .attr("opacity", 0.8);

      // Threshold label
      g.append("text")
        .attr("x", chartWidth - 5)
        .attr("y", thresholdY - 5)
        .style("text-anchor", "end")
        .style("font-size", "11px")
        .style("font-weight", "bold")
        .style("fill", "#ef4444")
        .text(`Threshold: ${threshold}${getThresholdUnit(metric)}`);

      // Threshold zone (area above threshold)
      g.append("rect")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", chartWidth)
        .attr("height", thresholdY)
        .attr("fill", "#ef4444")
        .attr("opacity", 0.05);
    }

    // Group data by benchmark type
    const groupedData = d3.group(
      data,
      (d) => `${d.benchmark.config.preset}_${d.benchmark.config.stream}`
    );

    // Add lines for each benchmark type
    groupedData.forEach((typeData, type) => {
      const color = colorScale(type);

      // Calculate linear regression for trend analysis
      const sortedData = typeData.sort(
        (a, b) => a.date.getTime() - b.date.getTime()
      );
      const trendData = calculateLinearRegression(
        sortedData.map((d, i) => ({
          x: i,
          y: d.p95Value,
        }))
      );

      // Create trend line data points
      const trendLine = d3
        .line<{ x: number; y: number }>()
        .x((d, i) => xScale(sortedData[i].date))
        .y((d) => yScale(d.y));

      // Trend line (subtle)
      if (trendData.length > 1) {
        g.append("path")
          .datum(trendData)
          .attr("fill", "none")
          .attr("stroke", color)
          .attr("stroke-width", 1)
          .attr("stroke-dasharray", "2,3")
          .attr("opacity", 0.4)
          .attr("d", trendLine);
      }

      // Mean line
      g.append("path")
        .datum(typeData)
        .attr("fill", "none")
        .attr("stroke", color)
        .attr("stroke-width", 2)
        .attr("opacity", 0.8)
        .attr("d", meanLine);

      // P95 line (dashed)
      g.append("path")
        .datum(typeData)
        .attr("fill", "none")
        .attr("stroke", color)
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "5,5")
        .attr("opacity", 0.6)
        .attr("d", p95Line);

      // Add dots for each data point
      g.selectAll(`.dot-${type.replace(/[^a-zA-Z0-9]/g, "")}`)
        .data(typeData)
        .enter()
        .append("circle")
        .attr("class", `dot-${type.replace(/[^a-zA-Z0-9]/g, "")}`)
        .attr("cx", (d) => xScale(d.date))
        .attr("cy", (d) => yScale(d.value))
        .attr("r", 4)
        .attr("fill", color)
        .attr("stroke", "#ffffff")
        .attr("stroke-width", 1.5)
        .attr("opacity", 0.9)
        .style("cursor", "pointer")
        .on("mouseover", function (event, d) {
          // Highlight the hovered point
          d3.select(this)
            .transition()
            .duration(150)
            .attr("r", 6)
            .attr("stroke-width", 2);
          // Tooltip on hover
          const tooltip = d3
            .select("body")
            .append("div")
            .attr("class", "tooltip")
            .style("position", "absolute")
            .style("background", "rgba(0, 0, 0, 0.9)")
            .style("color", "white")
            .style("padding", "12px")
            .style("border-radius", "6px")
            .style("font-size", "12px")
            .style("pointer-events", "none")
            .style("z-index", 1000)
            .style("box-shadow", "0 4px 6px rgba(0, 0, 0, 0.1)");

          // Performance analysis
          const avgP95 =
            data.reduce((sum, item) => sum + item.p95Value, 0) / data.length;
          const isAboveAverage = d.p95Value > avgP95;
          const percentDiff = (((d.p95Value - avgP95) / avgP95) * 100).toFixed(
            1
          );

          // Trend analysis for this type
          const typeDataSorted = typeData.sort(
            (a, b) => a.date.getTime() - b.date.getTime()
          );
          const trendPoints = calculateLinearRegression(
            typeDataSorted.map((d, i) => ({
              x: i,
              y: d.p95Value,
            }))
          );
          const trendDirection =
            trendPoints.length > 1
              ? trendPoints[1].y > trendPoints[0].y
                ? "increasing"
                : "decreasing"
              : "stable";

          const thresholdInfo = threshold
            ? `<div style="margin-top: 4px; padding-top: 4px; border-top: 1px solid rgba(255,255,255,0.2);">
                <span style="color: ${
                  d.p95Value > threshold ? "#ef4444" : "#22c55e"
                };">
                  ${
                    d.p95Value > threshold ? "⚠️ Above" : "✅ Within"
                  } threshold (${threshold}${getThresholdUnit(metric)})
                </span>
               </div>`
            : "";

          const comparisonInfo = `
            <div style="margin-top: 4px; font-size: 11px; opacity: 0.8;">
              <div>vs. Average: <span style="color: ${
                isAboveAverage ? "#ef4444" : "#22c55e"
              };">
                ${isAboveAverage ? "+" : ""}${percentDiff}%</span></div>
              <div>Trend: <span style="color: ${
                trendDirection === "increasing" ? "#ef4444" : "#22c55e"
              };">
                ${
                  trendDirection === "increasing"
                    ? "📈"
                    : trendDirection === "decreasing"
                    ? "📉"
                    : "➡️"
                } ${trendDirection}</span></div>
              <div>Config: ${d.benchmark.config.preset} | ${
            d.benchmark.config.stream ? "streaming" : "non-streaming"
          }</div>
            </div>`;

          tooltip
            .html(
              `
            <div><strong>${type}</strong></div>
            <div>Time: ${d3.timeFormat("%m/%d %H:%M")(d.date)}</div>
            <div>Mean: ${d.value.toFixed(2)}${getThresholdUnit(metric)}</div>
            <div>P95: ${d.p95Value.toFixed(2)}${getThresholdUnit(metric)}</div>
            <div>Trials: ${d.benchmark.stats.ttfa.count}</div>
            ${thresholdInfo}
            ${comparisonInfo}
          `
            )
            .style("left", event.pageX + 10 + "px")
            .style("top", event.pageY - 10 + "px");
        })
        .on("mouseout", function () {
          // Reset point appearance
          d3.select(this)
            .transition()
            .duration(150)
            .attr("r", 4)
            .attr("stroke-width", 1.5);

          d3.selectAll(".tooltip").remove();
        });
    });

    // Add legend
    const legendX = dimensions.width < 600 ? 10 : chartWidth - 150;
    const legendY = dimensions.width < 600 ? chartHeight + 60 : 20;
    const legend = g
      .append("g")
      .attr("transform", `translate(${legendX}, ${legendY})`);

    const legendData = Array.from(groupedData.keys());

    legendData.forEach((type, i) => {
      const legendRow = legend
        .append("g")
        .attr("transform", `translate(0, ${i * 20})`);

      // Solid line for mean
      legendRow
        .append("line")
        .attr("x1", 0)
        .attr("x2", 15)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", colorScale(type))
        .attr("stroke-width", 2);

      // Dashed line for P95
      legendRow
        .append("line")
        .attr("x1", 20)
        .attr("x2", 35)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", colorScale(type))
        .attr("stroke-width", 1.5)
        .attr("stroke-dasharray", "3,3");

      legendRow
        .append("text")
        .attr("x", 40)
        .attr("y", 0)
        .attr("dy", "0.35em")
        .style("font-size", "10px")
        .text(type);
    });

    // Legend labels
    legend
      .append("text")
      .attr("x", 0)
      .attr("y", -10)
      .style("font-size", "10px")
      .style("font-weight", "bold")
      .text("Mean — P95");

    // Add threshold legend if applicable
    if (showThresholds && threshold) {
      const thresholdLegend = legend
        .append("g")
        .attr("transform", `translate(0, ${legendData.length * 20 + 10})`);

      thresholdLegend
        .append("line")
        .attr("x1", 0)
        .attr("x2", 20)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", "#ef4444")
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", "8,4");

      thresholdLegend
        .append("text")
        .attr("x", 25)
        .attr("y", 0)
        .attr("dy", "0.35em")
        .style("font-size", "10px")
        .style("fill", "#ef4444")
        .text(`Threshold: ${threshold}${getThresholdUnit(metric)}`);
    }
  }, [benchmarks, metric, dimensions, showThresholds]);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div ref={containerRef} className="w-full overflow-x-auto">
          <svg
            ref={svgRef}
            width={dimensions.width}
            height={dimensions.height + (dimensions.width < 600 ? 80 : 0)} // Extra space for mobile legend
            className="border rounded"
          />
        </div>
      </CardContent>
    </Card>
  );
}

/**
 * Get appropriate Y-axis label for metric type
 */
function getYAxisLabel(metric: "ttfa" | "rtf" | "memory"): string {
  switch (metric) {
    case "ttfa":
      return "Time to First Audio (ms)";
    case "rtf":
      return "Real-Time Factor";
    case "memory":
      return "Memory Usage (MB)";
    default:
      return "Value";
  }
}

/**
 * Get threshold unit string for metric type
 */
function getThresholdUnit(metric: "ttfa" | "rtf" | "memory"): string {
  switch (metric) {
    case "ttfa":
      return "ms";
    case "rtf":
      return "";
    case "memory":
      return "MB";
    default:
      return "";
  }
}

/**
 * Calculate linear regression for trend analysis
 */
function calculateLinearRegression(
  data: { x: number; y: number }[]
): { x: number; y: number }[] {
  if (data.length < 2) return [];

  const n = data.length;
  const sumX = data.reduce((sum, point) => sum + point.x, 0);
  const sumY = data.reduce((sum, point) => sum + point.y, 0);
  const sumXY = data.reduce((sum, point) => sum + point.x * point.y, 0);
  const sumXX = data.reduce((sum, point) => sum + point.x * point.x, 0);

  const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
  const intercept = (sumY - slope * sumX) / n;

  // Return line endpoints
  const minX = Math.min(...data.map((d) => d.x));
  const maxX = Math.max(...data.map((d) => d.x));

  return [
    { x: minX, y: slope * minX + intercept },
    { x: maxX, y: slope * maxX + intercept },
  ];
}
