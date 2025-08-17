# Kokoro TTS Benchmark Dashboard

A Next.js dashboard for visualizing and analyzing Kokoro TTS performance benchmarks with shadcn/ui components and D3.js charting.

## Features

- 📊 **Interactive Charts**: D3.js powered performance visualizations
- 🎯 **Real-time Metrics**: TTFA, RTF, and memory usage analysis
- 🔍 **Detailed Views**: Memory timelines and comprehensive benchmark details
- 🎛️ **Advanced Filtering**: Filter by preset, streaming mode, and voice
- 📱 **Responsive Design**: Built with shadcn/ui and Tailwind CSS
- 🚀 **Mock Data**: Development-ready with generated benchmark data

## Tech Stack

- **Framework**: Next.js 15 with App Router
- **UI Components**: shadcn/ui with Radix UI primitives
- **Styling**: Tailwind CSS
- **Charts**: D3.js for custom data visualizations
- **TypeScript**: Full type safety throughout
- **Date Handling**: date-fns for time formatting

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Navigate to dashboard directory
cd dashboard

# Install dependencies
npm install

# Start development server
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) to view the dashboard.

## Project Structure

```
dashboard/
├── src/
│   ├── app/                    # Next.js app router pages
│   │   ├── page.tsx           # Main dashboard
│   │   ├── benchmarks/        # Detailed benchmark views
│   │   └── layout.tsx         # Root layout with navigation
│   ├── components/            # Reusable components
│   │   ├── ui/               # shadcn/ui components
│   │   ├── charts/           # D3.js chart components
│   │   ├── benchmark-summary.tsx
│   │   └── navigation.tsx
│   ├── lib/                  # Utilities and helpers
│   │   ├── benchmark-parser.ts  # Data processing utilities
│   │   ├── mock-data.ts        # Development mock data
│   │   └── utils.ts           # shadcn/ui utilities
│   └── types/                # TypeScript type definitions
│       └── benchmark.ts      # Benchmark data types
```

## Data Structure

The dashboard expects benchmark data in the following format:

```typescript
interface BenchmarkResult {
  config: {
    preset: 'short' | 'long';
    stream: boolean;
    base_payload: {
      voice: string;
      speed: number;
      lang: string;
      format: string;
    };
    trials: number;
    // ... other config
  };
  measurements: {
    ttfa_ms: number[];     // Time to First Audio values
    rtf: number[];         // Real-Time Factor values
    mem_samples: Array<{   // Memory usage over time
      t: number;           // Timestamp
      rss_mb: number;      // Resident Set Size in MB
      cpu_pct: number;     // CPU percentage
    }>;
    // ... other measurements
  };
}
```

## Key Components

### Performance Charts (`PerformanceChart`)
- Line charts for TTFA, RTF, and memory metrics over time
- P95 and mean value visualization
- Interactive tooltips and legends
- Support for multiple benchmark configurations

### Memory Timeline (`MemoryTimeline`)
- Detailed memory usage for individual benchmark runs
- CPU activity correlation
- Highlighted significant events (high CPU usage)
- Area charts with dual Y-axes

### Benchmark Summary (`BenchmarkSummary`)
- Key performance indicators (KPIs)
- Trend analysis (improving/degrading/stable)
- Recent benchmark history
- Filter and sorting capabilities

## Mock Data

For development, the dashboard generates realistic mock data including:
- Multiple benchmark configurations (short/long, streaming/non-streaming)
- Various voice models (af_heart, af_bella, af_sarah)
- 7 days of sample data with realistic performance metrics
- Memory usage patterns with CPU activity spikes

## Customization

### Adding New Chart Types
1. Create new chart component in `src/components/charts/`
2. Use D3.js for custom visualizations
3. Follow existing patterns for props and TypeScript types

### Extending Data Processing
1. Add new utilities to `src/lib/benchmark-parser.ts`
2. Update types in `src/types/benchmark.ts`
3. Ensure compatibility with existing components

### UI Customization
1. Modify shadcn/ui components in `src/components/ui/`
2. Update Tailwind configuration as needed
3. Add new color schemes or themes

## Performance Considerations

- Virtual scrolling for large datasets
- Memoized chart components
- Efficient D3.js rendering patterns
- Responsive design with mobile optimization

## Future Enhancements

- [ ] Real-time data updates via WebSocket
- [ ] Export functionality for charts and data
- [ ] Advanced statistical analysis
- [ ] Benchmark comparison tools
- [ ] Custom alert thresholds
- [ ] Data persistence and backend integration

## Development Scripts

```bash
# Start development server
npm run dev

# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint

# Type checking
npm run type-check
```

## Contributing

1. Follow the existing code structure and patterns
2. Use TypeScript for all new code
3. Add JSDoc comments for complex functions
4. Test new components with mock data
5. Ensure responsive design compliance

## Author

@darianrosebrook