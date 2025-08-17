/**
 * Memory timeline chart component for detailed memory usage visualization
 * @author @darianrosebrook
 */

"use client";

import React, { useEffect, useRef } from "react";
import * as d3 from "d3";
import { ProcessedBenchmark, MemorySample } from "@/types/benchmark";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

interface MemoryTimelineProps {
  /** Single benchmark to visualize memory timeline */
  benchmark: ProcessedBenchmark;
  /** Chart height in pixels */
  height?: number;
  /** Chart width in pixels */
  width?: number;
}

/**
 * Detailed memory usage timeline for a single benchmark run
 */
export function MemoryTimeline({
  benchmark,
  height = 300,
  width = 800,
}: MemoryTimelineProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || !benchmark.raw.measurements.mem_samples?.length)
      return;

    // Clear previous chart
    d3.select(svgRef.current).selectAll("*").remove();

    const svg = d3.select(svgRef.current);
    const margin = { top: 20, right: 60, bottom: 40, left: 60 };
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;

    // Create chart group
    const g = svg
      .append("g")
      .attr("transform", `translate(${margin.left},${margin.top})`);

    // Prepare data
    const memSamples = benchmark.raw.measurements.mem_samples;
    const startTime = memSamples[0].t;

    const data = memSamples.map((sample: MemorySample) => ({
      time: sample.t - startTime, // Relative time in seconds
      rss_mb: sample.rss_mb,
      cpu_pct: sample.cpu_pct,
    }));

    // Scales
    const xScale = d3
      .scaleLinear()
      .domain(d3.extent(data, (d) => d.time) as [number, number])
      .range([0, chartWidth]);

    const yScaleMemory = d3
      .scaleLinear()
      .domain(d3.extent(data, (d) => d.rss_mb) as [number, number])
      .nice()
      .range([chartHeight, 0]);

    const yScaleCPU = d3
      .scaleLinear()
      .domain([0, d3.max(data, (d) => d.cpu_pct) as number])
      .nice()
      .range([chartHeight, 0]);

    // Line generators
    const memoryLine = d3
      .line<(typeof data)[0]>()
      .x((d) => xScale(d.time))
      .y((d) => yScaleMemory(d.rss_mb))
      .curve(d3.curveMonotoneX);

    const cpuLine = d3
      .line<(typeof data)[0]>()
      .x((d) => xScale(d.time))
      .y((d) => yScaleCPU(d.cpu_pct))
      .curve(d3.curveMonotoneX);

    // Add X axis
    g.append("g")
      .attr("transform", `translate(0,${chartHeight})`)
      .call(d3.axisBottom(xScale).tickFormat((d) => `${d}s`));

    // Add Y axis for memory (left)
    g.append("g").call(d3.axisLeft(yScaleMemory)).attr("color", "#2563eb");

    // Add Y axis for CPU (right)
    g.append("g")
      .attr("transform", `translate(${chartWidth}, 0)`)
      .call(d3.axisRight(yScaleCPU))
      .attr("color", "#dc2626");

    // Add axis labels
    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", 0 - margin.left + 15)
      .attr("x", 0 - chartHeight / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .style("fill", "#2563eb")
      .text("Memory Usage (MB)");

    g.append("text")
      .attr("transform", "rotate(-90)")
      .attr("y", chartWidth + margin.right - 15)
      .attr("x", 0 - chartHeight / 2)
      .attr("dy", "1em")
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .style("fill", "#dc2626")
      .text("CPU Usage (%)");

    g.append("text")
      .attr(
        "transform",
        `translate(${chartWidth / 2}, ${chartHeight + margin.bottom - 5})`
      )
      .style("text-anchor", "middle")
      .style("font-size", "12px")
      .text("Time (seconds)");

    // Add memory line
    g.append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", "#2563eb")
      .attr("stroke-width", 2)
      .attr("d", memoryLine);

    // Add CPU line
    g.append("path")
      .datum(data)
      .attr("fill", "none")
      .attr("stroke", "#dc2626")
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "5,5")
      .attr("d", cpuLine);

    // Add area under memory curve
    const area = d3
      .area<(typeof data)[0]>()
      .x((d) => xScale(d.time))
      .y0(chartHeight)
      .y1((d) => yScaleMemory(d.rss_mb))
      .curve(d3.curveMonotoneX);

    g.append("path")
      .datum(data)
      .attr("fill", "#2563eb")
      .attr("fill-opacity", 0.1)
      .attr("d", area);

    // Add dots for significant events (high CPU usage)
    const significantEvents = data.filter((d) => d.cpu_pct > 50);

    g.selectAll(".cpu-event")
      .data(significantEvents)
      .enter()
      .append("circle")
      .attr("class", "cpu-event")
      .attr("cx", (d) => xScale(d.time))
      .attr("cy", (d) => yScaleCPU(d.cpu_pct))
      .attr("r", 4)
      .attr("fill", "#dc2626")
      .attr("opacity", 0.8)
      .on("mouseover", function (event, d) {
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
          <div><strong>High CPU Activity</strong></div>
          <div>Time: ${d.time.toFixed(1)}s</div>
          <div>Memory: ${d.rss_mb.toFixed(1)} MB</div>
          <div>CPU: ${d.cpu_pct.toFixed(1)}%</div>
        `
          )
          .style("left", event.pageX + 10 + "px")
          .style("top", event.pageY - 10 + "px");
      })
      .on("mouseout", function () {
        d3.selectAll(".tooltip").remove();
      });

    // Add legend
    const legend = g
      .append("g")
      .attr("transform", `translate(${chartWidth - 120}, 20)`);

    const legendData = [
      { color: "#2563eb", label: "Memory (MB)", style: "solid" },
      { color: "#dc2626", label: "CPU (%)", style: "dashed" },
    ];

    legendData.forEach((item, i) => {
      const legendRow = legend
        .append("g")
        .attr("transform", `translate(0, ${i * 20})`);

      legendRow
        .append("line")
        .attr("x1", 0)
        .attr("x2", 20)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", item.color)
        .attr("stroke-width", 2)
        .attr("stroke-dasharray", item.style === "dashed" ? "5,5" : "none");

      legendRow
        .append("text")
        .attr("x", 25)
        .attr("y", 0)
        .attr("dy", "0.35em")
        .style("font-size", "12px")
        .text(item.label);
    });

    // Add summary statistics
    const stats = g.append("g").attr("transform", `translate(10, 20)`);

    const memStats = [
      `Peak: ${benchmark.stats.memory.peak_rss_mb.toFixed(1)} MB`,
      `Avg: ${benchmark.stats.memory.avg_rss_mb.toFixed(1)} MB`,
      `CPU Avg: ${benchmark.stats.memory.avg_cpu_pct.toFixed(1)}%`,
    ];

    memStats.forEach((stat, i) => {
      stats
        .append("text")
        .attr("x", 0)
        .attr("y", i * 15)
        .style("font-size", "10px")
        .style("font-weight", "bold")
        .style("fill", "#374151")
        .text(stat);
    });
  }, [benchmark, height, width]);

  if (!benchmark.raw.measurements.mem_samples?.length) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Memory Timeline</CardTitle>
          <CardDescription>
            No memory data available for this benchmark
          </CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>Memory Timeline</CardTitle>
        <CardDescription>
          Memory and CPU usage over time for {benchmark.config.preset} benchmark
        </CardDescription>
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
