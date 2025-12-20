/**
 * Enhanced State Management for Raycast Kokoro TTS
 *
 * This module provides enhanced state management utilities that leverage
 * @raycast/utils for optimal performance and user experience.
 *
 * Features:
 * - Persistent preference caching with useCachedState
 * - Server health monitoring with useCachedPromise
 * - Optimized HTTP requests with useFetch
 * - Preference validation with safe defaults
 * - Fast equality checks for state updates
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import { useCachedState, useFetch, useCachedPromise } from "@raycast/utils";
import { showToast, Toast, getPreferenceValues } from "@raycast/api";
import { useCallback, useMemo } from "react";
import isEqual from "fast-deep-equal";
import type { TTSProcessorConfig, VoiceOption } from "../validation/tts-types.js";
import { cacheManager, type CachedServerHealth } from "./cache.js";

/**
 * Default TTS configuration with safe defaults
 */
const DEFAULT_TTS_CONFIG: TTSProcessorConfig = {
  voice: "af_heart",
  speed: 1.0,
  serverUrl: "http://localhost:8080",
  daemonUrl: "http://localhost:8081",
  useStreaming: true,
  sentencePauses: false,
  maxSentenceLength: 0,
  format: "wav",
  developmentMode: false,
  performanceProfile: "balanced",
  autoSelectProfile: true,
  showPerformanceMetrics: false,
  onStatusUpdate: () => {},
};

/**
 * Enhanced preference validation with safe defaults and bounds checking
 */
const validatePreferences = (prefs: Partial<TTSProcessorConfig>): TTSProcessorConfig => {
  const validated: TTSProcessorConfig = {
    voice: prefs.voice ?? DEFAULT_TTS_CONFIG.voice,
    speed: Math.max(
      0.1,
      Math.min(3.0, parseFloat(String(prefs.speed)) || DEFAULT_TTS_CONFIG.speed)
    ),
    serverUrl: prefs.serverUrl?.replace(/\/+$/, "") ?? DEFAULT_TTS_CONFIG.serverUrl,
    daemonUrl: prefs.daemonUrl?.replace(/\/+$/, "") ?? DEFAULT_TTS_CONFIG.daemonUrl,
    useStreaming: prefs.useStreaming ?? DEFAULT_TTS_CONFIG.useStreaming,
    sentencePauses: prefs.sentencePauses ?? DEFAULT_TTS_CONFIG.sentencePauses,
    maxSentenceLength: Math.max(
      0,
      parseInt(String(prefs.maxSentenceLength)) || DEFAULT_TTS_CONFIG.maxSentenceLength
    ),
    format: prefs.format ?? DEFAULT_TTS_CONFIG.format,
    developmentMode: prefs.developmentMode ?? DEFAULT_TTS_CONFIG.developmentMode,
    performanceProfile: prefs.performanceProfile ?? DEFAULT_TTS_CONFIG.performanceProfile,
    autoSelectProfile: prefs.autoSelectProfile ?? DEFAULT_TTS_CONFIG.autoSelectProfile,
    showPerformanceMetrics:
      prefs.showPerformanceMetrics ?? DEFAULT_TTS_CONFIG.showPerformanceMetrics,
    onStatusUpdate: prefs.onStatusUpdate ?? DEFAULT_TTS_CONFIG.onStatusUpdate,
  };

  return validated;
};

/**
 * Custom hook for persistent TTS preferences with validation
 */
export const useTTSPreferences = () => {
  // Get initial preferences from Raycast
  const initialPrefs = useMemo(() => {
    try {
      const prefs = getPreferenceValues<Partial<TTSProcessorConfig>>();
      return validatePreferences(prefs);
    } catch (error) {
      console.warn("Failed to load preferences, using defaults:", error);
      return DEFAULT_TTS_CONFIG;
    }
  }, []);

  // Use cached state for persistent preferences
  const [preferences, setPreferences] = useCachedState<TTSProcessorConfig>(
    "tts-preferences-v2",
    initialPrefs
  );

  // Validated setter that ensures preferences are always valid
  const updatePreferences = useCallback(
    (newPrefs: Partial<TTSProcessorConfig>) => {
      const currentPrefs = preferences;
      const mergedPrefs = { ...currentPrefs, ...newPrefs };
      const validatedPrefs = validatePreferences(mergedPrefs);

      // Only update if preferences actually changed (avoid unnecessary re-renders)
      if (!isEqual(currentPrefs, validatedPrefs)) {
        setPreferences(validatedPrefs);

        // Cache the preferences for faster access
        cacheManager.cachePreferences("user", validatedPrefs);
      }
    },
    [preferences, setPreferences]
  );

  // Reset to defaults
  const resetPreferences = useCallback(() => {
    setPreferences(DEFAULT_TTS_CONFIG);
    cacheManager.clearCache("preferences");
  }, [setPreferences]);

  return {
    preferences,
    updatePreferences,
    resetPreferences,
    isValid: true, // Always valid due to validation
  };
};

export const useDaemonHealth = () => {
  const { preferences } = useTTSPreferences();

  const healthCheckFn = useCallback(async (): Promise<CachedServerHealth> => {
    // Check cache first
    const cachedHealth = cacheManager.getCachedServerHealth(preferences.daemonUrl);
    if (cachedHealth) {
      return cachedHealth;
    }

    const startTime = Date.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000); // 3 second timeout for daemon

      // Try to connect to the daemon's health endpoint
      const response = await fetch(`${preferences.daemonUrl}/health`, {
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
      });

      clearTimeout(timeoutId);

      const latency = Date.now() - startTime;
      const health: CachedServerHealth = {
        status: response.ok ? "healthy" : "unhealthy",
        latency,
        timestamp: Date.now(),
        version: response.headers.get("X-Daemon-Version") || undefined,
      };

      // Cache the result
      cacheManager.cacheServerHealth(preferences.daemonUrl, health);

      return health;
    } catch {
      // Don't log errors for daemon health checks - they're expected when daemon isn't running
      const health: CachedServerHealth = {
        status: "unhealthy",
        latency: Date.now() - startTime,
        timestamp: Date.now(),
      };

      // Cache the error result too (with shorter TTL)
      cacheManager.cacheServerHealth(preferences.daemonUrl, health);

      return health;
    }
  }, [preferences.daemonUrl]);

  const {
    data: daemonHealth,
    isLoading: daemonLoading,
    error: daemonError,
    revalidate: daemonRevalidate,
  } = useCachedPromise(healthCheckFn, [], {
    initialData: null,
    keepPreviousData: true,
    // Delay the initial health check to avoid running it immediately
    execute: false,
  });

  return {
    daemonHealth,
    isLoading: daemonLoading,
    error: daemonError,
    revalidate: daemonRevalidate,
    isHealthy: daemonHealth?.status === "healthy",
    latency: daemonHealth?.latency ?? 0,
  };
};

/**
 * Custom hook for server health monitoring with caching
 */
export const useServerHealth = (serverUrl: string) => {
  const healthCheckFn = useCallback(async (): Promise<CachedServerHealth> => {
    // Check cache first
    const cachedHealth = cacheManager.getCachedServerHealth(serverUrl);
    if (cachedHealth) {
      return cachedHealth;
    }

    const startTime = Date.now();

    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 5000); // 5 second timeout

      const response = await fetch(`${serverUrl}/health`, {
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
      });

      clearTimeout(timeoutId);

      const latency = Date.now() - startTime;
      const health: CachedServerHealth = {
        status: response.ok ? "healthy" : "unhealthy",
        latency,
        timestamp: Date.now(),
        version: response.headers.get("X-API-Version") || undefined,
      };

      // Cache the result
      cacheManager.cacheServerHealth(serverUrl, health);

      return health;
    } catch {
      const health: CachedServerHealth = {
        status: "unhealthy",
        latency: Date.now() - startTime,
        timestamp: Date.now(),
      };

      // Cache the error result too (with shorter TTL)
      cacheManager.cacheServerHealth(serverUrl, health);

      return health;
    }
  }, [serverUrl]);

  // Use cached promise for server health with automatic refreshing
  const {
    data: serverHealth,
    isLoading,
    error: _error,
    revalidate,
  } = useCachedPromise(healthCheckFn, [], {
    initialData: null,
    keepPreviousData: true,
  });

  return {
    serverHealth,
    isLoading,
    error: _error,
    revalidate,
    isHealthy: serverHealth?.status === "healthy",
    latency: serverHealth?.latency ?? 0,
  };
};

/**
 * Custom hook for voice configuration with caching
 */
export const useVoiceConfig = (serverUrl: string) => {
  const _voicesFetchFn = useCallback(async () => {
    try {
      const response = await fetch(`${serverUrl}/voices`, {
        headers: {
          Accept: "application/json",
        },
      });

      if (!response.ok) {
        throw new Error(`Failed to fetch voices: ${response.status}`);
      }

      const voices = await response.json();

      // Cache voice configurations
      voices.forEach((voice: unknown) => {
        const voiceObj = voice as { name: string };
        cacheManager.cacheVoiceConfig(voiceObj.name as VoiceOption, voice);
      });

      return voices;
    } catch (error) {
      console.warn("Failed to fetch voices from server:", error);
      // Return empty array as fallback
      return [];
    }
  }, [serverUrl]);

  const {
    data: voices,
    isLoading,
    error,
  } = useFetch(`${serverUrl}/voices`, {
    parseResponse: async (response) => {
      if (!response.ok) {
        throw new Error(`Failed to fetch voices: ${response.status}`);
      }
      return response.json();
    },
    initialData: [],
    keepPreviousData: true,
  });

  return {
    voices: voices ?? [],
    isLoading,
    error,
    hasVoices: (voices?.length ?? 0) > 0,
  };
};

/**
 * Custom hook for TTS request state management
 */
export const useTTSRequestState = () => {
  const [requestHistory, setRequestHistory] = useCachedState<
    Array<{
      text: string;
      voice: VoiceOption;
      timestamp: number;
    }>
  >("tts-request-history", []);

  const addToHistory = useCallback(
    (text: string, voice: VoiceOption) => {
      const newEntry = {
        text: text.substring(0, 100), // Truncate long texts
        voice,
        timestamp: Date.now(),
      };

      setRequestHistory((prev) => {
        const updated = [newEntry, ...prev].slice(0, 10); // Keep only last 10 requests
        return updated;
      });
    },
    [setRequestHistory]
  );

  const clearHistory = useCallback(() => {
    setRequestHistory([]);
  }, [setRequestHistory]);

  return {
    requestHistory,
    addToHistory,
    clearHistory,
  };
};

/**
 * Enhanced error handling with toast notifications
 */
export const useErrorHandler = () => {
  const handleError = useCallback(async (error: Error, context: string) => {
    console.error(`Error in ${context}:`, error);

    let title = "An error occurred";
    let message = error.message;

    // Customize error messages based on context
    if (context.includes("network") || context.includes("fetch")) {
      title = "Network Error";
      message = "Failed to connect to TTS server. Please check your connection and server URL.";
    } else if (context.includes("audio") || context.includes("playback")) {
      title = "Audio Error";
      message = "Failed to play audio. Please try again.";
    } else if (context.includes("preferences")) {
      title = "Settings Error";
      message = "Failed to save preferences. Using defaults.";
    }

    await showToast({
      style: Toast.Style.Failure,
      title,
      message,
    });
  }, []);

  return { handleError };
};

/**
 * Performance monitoring hook for debugging
 */
export const usePerformanceMonitor = () => {
  const getCacheStats = useCallback(() => {
    return cacheManager.getStats();
  }, []);

  const clearAllCaches = useCallback(() => {
    cacheManager.clearAll();
    showToast({
      style: Toast.Style.Success,
      title: "Caches cleared",
      message: "All caches have been cleared successfully.",
    });
  }, []);

  return {
    getCacheStats,
    clearAllCaches,
  };
};

// Export validation function for external use
export { validatePreferences, DEFAULT_TTS_CONFIG };
