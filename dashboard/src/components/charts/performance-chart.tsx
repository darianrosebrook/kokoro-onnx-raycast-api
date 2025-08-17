/**
 * Performance chart component using D3 for Kokoro TTS benchmarks
 * @author @darianrosebrook
 */

"use client";

import React, { useEffect, useRef } from "react";
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
  width = 800,
}: PerformanceChartProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || benchmarks.length === 0) return;

    // Clear previous chart
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current);
    const margin = { top: 20, right: 30, bottom: 40, left: 50 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    // Create chart group
    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

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

    const yScale = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => Math.max(d.value, d.p95Value)) as number])
      .nice()
      .range([chartHeight, 0]);

    // Color scale for different benchmark types
    const colorScale = d3
      .scaleOrdinal(d3.schemeCategory10)
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
          .tickFormat((d) => d3.timeFormat("%m/%d %H:%M")(d as Date))
      );

    g.append("g").call(d3.axisLeft(yScale));

    // Add axis labels
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left)
      .attr("x", 0 - chartHeight / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .text(getYAxisLabel(metric));

    g.append("text")
      .attr(
        "transform",
        `translate(${chartWidth / 2}, ${chartHeight + margin.bottom - 5})`
      )
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .text("Time");

    // Group data by benchmark type
    const groupedData = d3.group(
      data,
      (d) => `${d.benchmark.config.preset}_${d.benchmark.config.stream}`
    );

    // Add lines for each benchmark type
    groupedData.forEach((typeData, type) => {
      const color = colorScale(type);

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
        .attr("opacity", 0.7)
        .on("mouseover", function (event, d) {
          // Tooltip on hover
          const tooltip = d3
            .select("body")
            .append("div")
            .attr("class", "tooltip")
            .style("position", "absolute")
            .style("background", "rgba(0, 0, 0, 0.8)")
            .style("color", "white")
            .style("padding", "8px")
            .style("border-radius", "4px")
            .style("font-size", "12px")
            .style("pointer-events", "none")
            .style("z-index", 1000);

          tooltip
            .html(
              `
            <div><strong>${type}</strong></div>
            <div>Time: ${d3.timeFormat("%m/%d %H:%M")(d.date)}</div>
            <div>Mean: ${d.value.toFixed(2)}</div>
            <div>P95: ${d.p95Value.toFixed(2)}</div>
          `
            )
            .style("left", event.pageX + 10 + "px")
            .style("top", event.pageY - 10 + "px");
        })
        .on("mouseout", function () {
          d3.selectAll(".tooltip").remove();
        });
    });

    // Add legend
    const legend = g
      .append("g")
      .attr("transform", `translate(${chartWidth - 150}, 20)`);

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
  }, [benchmarks, metric, height, width]);

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="w-full overflow-x-auto">
          <svg
            ref={svgRef}
            width={width}
            height={height}
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
