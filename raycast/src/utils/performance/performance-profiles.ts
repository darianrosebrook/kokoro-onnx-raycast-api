/**
 * Performance Profile Manager
 *
 * Manages predefined performance profiles for the TTS system.
 * Provides optimal buffer configurations for different use cases and system capabilities.
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import type { PerformanceProfile, BufferConfig } from "../validation/tts-types.js";

/**
 * Predefined performance profiles with optimized buffer configurations
 */
export const PERFORMANCE_PROFILES: Record<string, PerformanceProfile> = {
  conservative: {
    name: "Conservative",
    description:
      "High stability, lower latency tolerance. Best for unreliable networks or older systems.",
    priority: "conservative",
    autoSelect: false,
    bufferConfig: {
      targetBufferMs: 200,
      bufferSize: 19200, // 19.2KB
      chunkSize: 2400, // 2.4KB
      deliveryRate: 20, // 20ms
      minBufferChunks: 8,
      maxLatency: 500,
      targetUtilization: 0.7,
      minBufferMs: 200,
      maxBufferMs: 1000,
    },
  },

  balanced: {
    name: "Balanced",
    description: "Optimal balance of performance and stability. Recommended for most users.",
    priority: "balanced",
    autoSelect: true,
    bufferConfig: {
      targetBufferMs: 100,
      bufferSize: 9600, // 9.6KB
      chunkSize: 1200, // 1.2KB
      deliveryRate: 10, // 10ms
      minBufferChunks: 8,
      maxLatency: 300,
      targetUtilization: 0.8,
      minBufferMs: 200,
      maxBufferMs: 1000,
    },
  },

  aggressive: {
    name: "Aggressive",
    description: "Low latency, high performance. Best for fast networks and modern systems.",
    priority: "aggressive",
    autoSelect: false,
    bufferConfig: {
      targetBufferMs: 50,
      bufferSize: 4800, // 4.8KB
      chunkSize: 600, // 600B
      deliveryRate: 5, // 5ms
      minBufferChunks: 8,
      maxLatency: 150,
      targetUtilization: 0.9,
      minBufferMs: 200,
      maxBufferMs: 1000,
    },
  },

  "network-optimized": {
    name: "Network Optimized",
    description: "Optimized for high-latency or unstable networks. Larger buffers for reliability.",
    priority: "network-optimized",
    autoSelect: false,
    bufferConfig: {
      targetBufferMs: 300,
      bufferSize: 38400, // 38.4KB
      chunkSize: 4800, // 4.8KB
      deliveryRate: 30, // 30ms
      minBufferChunks: 8,
      maxLatency: 800,
      targetUtilization: 0.6,
      minBufferMs: 200,
      maxBufferMs: 1000,
    },
  },
};

/**
 * System capability assessment for automatic profile selection
 */
export interface SystemCapabilities {
  memoryGB: number;
  cpuCores: number;
  networkLatency: number;
  networkStability: number; // 0-1, higher is more stable
  isAppleSilicon: boolean;
  isHighEndSystem: boolean;
}

/**
 * Performance profile manager class
 */
export class PerformanceProfileManager {
  private static instance: PerformanceProfileManager;
  private currentProfile: string = "balanced";
  private systemCapabilities: SystemCapabilities | null = null;

  private constructor() {}

  /**
   * Get singleton instance
   */
  static getInstance(): PerformanceProfileManager {
    if (!PerformanceProfileManager.instance) {
      PerformanceProfileManager.instance = new PerformanceProfileManager();
    }
    return PerformanceProfileManager.instance;
  }

  /**
   * Get all available performance profiles
   */
  getProfiles(): PerformanceProfile[] {
    return Object.values(PERFORMANCE_PROFILES);
  }

  /**
   * Get a specific profile by name
   */
  getProfile(name: string): PerformanceProfile | null {
    return PERFORMANCE_PROFILES[name] || null;
  }

  /**
   * Get the current active profile
   */
  getCurrentProfile(): PerformanceProfile {
    return PERFORMANCE_PROFILES[this.currentProfile] || PERFORMANCE_PROFILES.balanced;
  }

  /**
   * Set the current profile
   */
  setProfile(name: string): boolean {
    if (PERFORMANCE_PROFILES[name]) {
      this.currentProfile = name;
      return true;
    }
    return false;
  }

  /**
   * Get buffer configuration for current profile
   */
  getCurrentBufferConfig(): BufferConfig {
    return this.getCurrentProfile().bufferConfig;
  }

  /**
   * Assess system capabilities for automatic profile selection
   */
  async assessSystemCapabilities(): Promise<SystemCapabilities> {
    if (this.systemCapabilities) {
      return this.systemCapabilities;
    }

    try {
      // Get system information - Node.js compatible
      let memoryGB = 8;
      let cpuCores = 4;
      let isAppleSilicon = false;

      // Try to get system information from Node.js
      // eslint-disable-next-line no-undef
      if (typeof process !== "undefined" && process.platform) {
        // Use Node.js APIs for system detection
        // eslint-disable-next-line @typescript-eslint/no-require-imports, no-undef
        const os = require("os");
        cpuCores = os.cpus().length;

        // Estimate memory (Node.js doesn't have direct access to total system memory)
        // eslint-disable-next-line no-undef
        const nodeMemoryUsage = process.memoryUsage();
        memoryGB = Math.round((nodeMemoryUsage.heapTotal || 0) / (1024 * 1024 * 1024)) || 8;

        // Detect Apple Silicon
        // eslint-disable-next-line no-undef
        isAppleSilicon = process.platform === "darwin" && process.arch === "arm64";
      } else if (typeof navigator !== "undefined") {
        // Fallback to browser APIs if available
        memoryGB =
          Math.round(
            (performance as { memory?: { totalJSHeapSize: number } }).memory?.totalJSHeapSize /
              (1024 * 1024 * 1024)
          ) || 8;
        cpuCores = navigator.hardwareConcurrency || 4;
        isAppleSilicon =
          navigator.userAgent.includes("Mac") && navigator.userAgent.includes("AppleWebKit");
      }

      // Estimate network capabilities (this would be more sophisticated in practice)
      const networkLatency = await this.measureNetworkLatency();
      const networkStability = await this.assessNetworkStability();

      // Determine if high-end system
      const isHighEndSystem = memoryGB >= 16 && cpuCores >= 8;

      this.systemCapabilities = {
        memoryGB,
        cpuCores,
        networkLatency,
        networkStability,
        isAppleSilicon,
        isHighEndSystem,
      };

      return this.systemCapabilities;
    } catch (error) {
      console.warn("Failed to assess system capabilities:", error);

      // Return conservative defaults
      this.systemCapabilities = {
        memoryGB: 8,
        cpuCores: 4,
        networkLatency: 100,
        networkStability: 0.7,
        isAppleSilicon: false,
        isHighEndSystem: false,
      };

      return this.systemCapabilities;
    }
  }

  /**
   * Automatically select the best profile based on system capabilities
   */
  async autoSelectProfile(): Promise<string> {
    const capabilities = await this.assessSystemCapabilities();

    // Network-based selection
    if (capabilities.networkLatency > 200 || capabilities.networkStability < 0.5) {
      return "network-optimized";
    }

    // System capability-based selection
    if (capabilities.isHighEndSystem && capabilities.networkLatency < 50) {
      return "aggressive";
    }

    if (capabilities.memoryGB < 8 || capabilities.cpuCores < 4) {
      return "conservative";
    }

    // Default to balanced
    return "balanced";
  }

  /**
   * Get profile recommendations based on current system state
   */
  async getProfileRecommendations(): Promise<{
    recommended: string;
    alternatives: string[];
    reasoning: string;
  }> {
    const capabilities = await this.assessSystemCapabilities();
    const recommendations = {
      recommended: "balanced",
      alternatives: [] as string[],
      reasoning: "",
    };

    // Network-based recommendations
    if (capabilities.networkLatency > 200) {
      recommendations.recommended = "network-optimized";
      recommendations.alternatives = ["conservative", "balanced"];
      recommendations.reasoning =
        "High network latency detected. Network-optimized profile recommended for better reliability.";
    } else if (capabilities.networkLatency < 50 && capabilities.networkStability > 0.8) {
      recommendations.recommended = "aggressive";
      recommendations.alternatives = ["balanced", "conservative"];
      recommendations.reasoning =
        "Low latency, stable network detected. Aggressive profile recommended for optimal performance.";
    } else if (capabilities.memoryGB < 8) {
      recommendations.recommended = "conservative";
      recommendations.alternatives = ["balanced"];
      recommendations.reasoning =
        "Limited system memory detected. Conservative profile recommended for stability.";
    } else if (capabilities.isHighEndSystem) {
      recommendations.recommended = "balanced";
      recommendations.alternatives = ["aggressive", "conservative"];
      recommendations.reasoning =
        "High-end system detected. Balanced profile recommended with aggressive as alternative.";
    } else {
      recommendations.recommended = "balanced";
      recommendations.alternatives = ["conservative", "network-optimized"];
      recommendations.reasoning =
        "Standard system configuration. Balanced profile recommended for optimal performance.";
    }

    return recommendations;
  }

  /**
   * Measure network latency to a test endpoint
   */
  private async measureNetworkLatency(): Promise<number> {
    try {
      const startTime = performance.now();

      // Try to measure latency to a reliable endpoint
      const _response = await fetch("https://httpbin.org/delay/0", {
        method: "HEAD",
        cache: "no-cache",
      });

      const endTime = performance.now();
      return endTime - startTime;
    } catch (error) {
      console.warn("Failed to measure network latency:", error);
      return 100; // Default assumption
    }
  }

  /**
   * Assess network stability by making multiple requests
   */
  private async assessNetworkStability(): Promise<number> {
    try {
      const latencies: number[] = [];

      // Make 3 quick requests to assess stability
      for (let i = 0; i < 3; i++) {
        const latency = await this.measureNetworkLatency();
        latencies.push(latency);
        await new Promise((resolve) => setTimeout(resolve, 100)); // Small delay
      }

      // Calculate coefficient of variation (lower is more stable)
      const mean = latencies.reduce((sum, val) => sum + val, 0) / latencies.length;
      const variance =
        latencies.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / latencies.length;
      const stdDev = Math.sqrt(variance);
      const cv = stdDev / mean;

      // Convert to stability score (0-1, higher is more stable)
      const stability = Math.max(0, 1 - cv);

      return stability;
    } catch (error) {
      console.warn("Failed to assess network stability:", error);
      return 0.7; // Default assumption
    }
  }

  /**
   * Get profile comparison data for UI display
   */
  getProfileComparison(): Array<{
    name: string;
    description: string;
    latency: string;
    stability: string;
    memoryUsage: string;
    recommended: boolean;
  }> {
    const capabilities = this.systemCapabilities;

    return Object.entries(PERFORMANCE_PROFILES).map(([key, profile]) => {
      const bufferConfig = profile.bufferConfig;
      const latency = `${bufferConfig.targetBufferMs}ms`;
      const stability =
        bufferConfig.bufferSize > 15000
          ? "High"
          : bufferConfig.bufferSize > 8000
            ? "Medium"
            : "Low";
      const memoryUsage = `${(bufferConfig.bufferSize / 1024).toFixed(1)}KB`;

      // Determine if recommended based on current system
      let recommended = false;
      if (capabilities) {
        if (capabilities.networkLatency > 200 && key === "network-optimized") {
          recommended = true;
        } else if (capabilities.networkLatency < 50 && key === "aggressive") {
          recommended = true;
        } else if (capabilities.memoryGB < 8 && key === "conservative") {
          recommended = true;
        } else if (key === "balanced") {
          recommended = true;
        }
      }

      return {
        name: profile.name,
        description: profile.description,
        latency,
        stability,
        memoryUsage,
        recommended,
      };
    });
  }

  /**
   * Reset to default profile
   */
  resetToDefault(): void {
    this.currentProfile = "balanced";
  }

  /**
   * Get profile statistics and metrics
   */
  getProfileStats(): {
    totalProfiles: number;
    currentProfile: string;
    autoSelectEnabled: boolean;
    systemCapabilities: SystemCapabilities | null;
  } {
    return {
      totalProfiles: Object.keys(PERFORMANCE_PROFILES).length,
      currentProfile: this.currentProfile,
      autoSelectEnabled: this.getCurrentProfile().autoSelect,
      systemCapabilities: this.systemCapabilities,
    };
  }
}

/**
 * Export singleton instance
 */
export const performanceProfileManager = PerformanceProfileManager.getInstance();
