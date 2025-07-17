/**
 * Command: SpeakText
 *
 * This is a simple TTS form component for Raycast using the TTS processor.
 * This allows some configuration of the TTS for each time it is used, vs the extension configuration
 *
 * Author: @darianrosebrook
 * Date: 2025-07-08
 * Version: 1.0.0
 * License: MIT
 *
 * This code is provided as-is, without any warranty. Use at your own risk.
 */
import { Form, ActionPanel, showToast, Toast, Clipboard, Action } from "@raycast/api";
import { useState, useEffect, useRef } from "react";
import { TTSSpeechProcessor } from "./utils/tts/tts-processor";
import type { VoiceOption, StatusUpdate } from "./types";
import {
  useTTSPreferences,
  useServerHealth,
  useVoiceConfig,
  useTTSRequestState,
  useErrorHandler,
  usePerformanceMonitor,
  useDaemonHealth,
} from "./utils/core/state-management";
import { ttsBenchmark } from "./utils/performance/performance-benchmark";
import { generateVoiceOptions as generateDynamicVoiceOptions } from "./utils/tts/voice-manager";
import {
  performanceProfileManager,
  PERFORMANCE_PROFILES,
} from "./utils/performance/performance-profiles";
import {
  VOICES,
  getAmericanEnglishVoices,
  getBritishEnglishVoices,
  getJapaneseVoices,
  getMandarinChineseVoices,
  getSpanishVoices,
  getFrenchVoices,
  getHindiVoices,
  getItalianVoices,
  getBrazilianPortugueseVoices,
} from "./utils/tts/voices";
import { logger } from "./utils/core/logger";

/**
 * Generate voice options dynamically from server, with fallback to hardcoded voices
 */
const generateVoiceOptions = async (
  serverUrl: string
): Promise<{ value: VoiceOption; title: string }[]> => {
  try {
    // Try to get voices from server first
    return await generateDynamicVoiceOptions(serverUrl);
  } catch (error) {
    logger.consoleWarn("Falling back to hardcoded voices:", error);

    // Fallback to hardcoded voices
    return generateHardcodedVoiceOptions();
  }
};

/**
 * Generate voice options from hardcoded VOICES catalog (fallback)
 */
const generateHardcodedVoiceOptions = (): { value: VoiceOption; title: string }[] => {
  const voiceOptions: { value: VoiceOption; title: string }[] = [];

  // Helper function to format voice name for display
  const formatVoiceName = (name: string): string => {
    const parts = name.split("_");
    const voiceName = parts[1];

    // Capitalize first letter of voice name
    const capitalizedName = voiceName.charAt(0).toUpperCase() + voiceName.slice(1);

    // Determine gender from prefix
    const prefix = parts[0];
    let gender = "";
    if (prefix.includes("f")) {
      gender = "Female";
    } else if (prefix.includes("m")) {
      gender = "Male";
    }

    return `${capitalizedName} (${gender})`;
  };

  // Helper function to sort voices by quality within a language group
  const sortVoicesByQuality = (
    voices: (typeof VOICES)[keyof typeof VOICES][]
  ): (typeof VOICES)[keyof typeof VOICES][] => {
    return voices.sort((a, b) => {
      const gradeOrder = { A: 1, B: 2, C: 3, D: 4, F: 5, "": 6 };
      const aGrade = (a.targetQuality as keyof typeof gradeOrder) || "";
      const bGrade = (b.targetQuality as keyof typeof gradeOrder) || "";

      if (gradeOrder[aGrade] !== gradeOrder[bGrade]) {
        return gradeOrder[aGrade] - gradeOrder[bGrade];
      }

      // If same grade, sort by overall grade
      if (a.overallGrade !== b.overallGrade) {
        return a.overallGrade.localeCompare(b.overallGrade);
      }

      return a.name.localeCompare(b.name);
    });
  };

  // Helper function to add voices from a language group
  const addLanguageGroup = (voices: (typeof VOICES)[keyof typeof VOICES][], flag: string) => {
    const sortedVoices = sortVoicesByQuality(voices);

    sortedVoices.forEach((voice) => {
      const displayName = formatVoiceName(voice.name);
      const gradeInfo = voice.overallGrade ? ` - Grade ${voice.overallGrade}` : "";
      const traitsInfo = voice.traits ? ` ${voice.traits}` : "";

      voiceOptions.push({
        value: voice.name,
        title: `${flag} ${displayName}${traitsInfo}${gradeInfo}`,
      });
    });
  };

  // Add languages in order of preference/quality
  addLanguageGroup(getAmericanEnglishVoices(), "");
  addLanguageGroup(getBritishEnglishVoices(), "");
  addLanguageGroup(getFrenchVoices(), "");
  addLanguageGroup(getJapaneseVoices(), "");
  addLanguageGroup(getHindiVoices(), "");
  addLanguageGroup(getItalianVoices(), "");
  addLanguageGroup(getMandarinChineseVoices(), "");
  addLanguageGroup(getSpanishVoices(), "");
  addLanguageGroup(getBrazilianPortugueseVoices(), "");

  return voiceOptions;
};

/**
 * Available voice options for the TTS (ordered by quality)
 */
const _VOICE_OPTIONS = generateHardcodedVoiceOptions();

/**
 * Simple TTS form component using the processor
 */
export default function SpeakTextSimple() {
  // Enhanced state management with persistent caching
  const { preferences, updatePreferences } = useTTSPreferences();
  const {
    serverHealth,
    isHealthy,
    latency,
    revalidate: _revalidate,
  } = useServerHealth(preferences.serverUrl);
  const {
    daemonHealth,
    isHealthy: daemonHealthy,
    latency: daemonLatency,
    revalidate: _revalidateDaemon,
  } = useDaemonHealth();
  const {
    voices: _voices,
    isLoading: _voicesLoading,
    hasVoices: _hasVoices,
  } = useVoiceConfig(preferences.serverUrl);
  const { requestHistory, addToHistory } = useTTSRequestState();
  const { handleError } = useErrorHandler();
  const { getCacheStats: _getCacheStats, clearAllCaches: _clearAllCaches } =
    usePerformanceMonitor();

  // Local component state
  const [text, setText] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [isBenchmarking, setIsBenchmarking] = useState(false);
  const [voiceOptions, setVoiceOptions] =
    useState<{ value: VoiceOption; title: string }[]>(_VOICE_OPTIONS);
  const [_isLoadingVoices, setIsLoadingVoices] = useState(true);
  const [profileRecommendations, setProfileRecommendations] = useState<{
    recommended: string;
    alternatives: string[];
    reasoning: string;
  } | null>(null);
  const [_isLoadingProfiles, setIsLoadingProfiles] = useState(false);
  const processorRef = useRef<TTSSpeechProcessor | null>(null);
  const toastRef = useRef<Toast | null>(null);

  // Use preferences from enhanced state management
  const voice = preferences.voice;
  const speed = preferences.speed.toString();
  const useStreaming = preferences.useStreaming;
  const performanceProfile = preferences.performanceProfile;
  const autoSelectProfile = preferences.autoSelectProfile;
  const showPerformanceMetrics = preferences.showPerformanceMetrics;

  // Load voice options on component mount and when server URL changes
  useEffect(() => {
    const loadVoices = async () => {
      setIsLoadingVoices(true);
      try {
        const options = await generateVoiceOptions(preferences.serverUrl);
        setVoiceOptions(options);
      } catch (error) {
        console.error("Failed to load voice options:", error);
        // Fallback to hardcoded voices
        const fallbackOptions = generateHardcodedVoiceOptions();
        setVoiceOptions(fallbackOptions);
      } finally {
        setIsLoadingVoices(false);
      }
    };

    loadVoices();
  }, [preferences.serverUrl]);

  // Load performance profile recommendations
  useEffect(() => {
    const loadProfileRecommendations = async () => {
      if (autoSelectProfile) {
        setIsLoadingProfiles(true);
        try {
          const recommendations = await performanceProfileManager.getProfileRecommendations();
          setProfileRecommendations(recommendations);

          // Auto-select the recommended profile if different from current
          if (recommendations.recommended !== performanceProfile) {
            updatePreferences({ performanceProfile: recommendations.recommended });
          }
        } catch (error) {
          console.error("Failed to load profile recommendations:", error);
        } finally {
          setIsLoadingProfiles(false);
        }
      }
    };

    loadProfileRecommendations();
  }, [autoSelectProfile, performanceProfile, updatePreferences]);

  // Auto-populate with clipboard text
  useEffect(() => {
    const loadClipboardText = async () => {
      try {
        const clipboardText = await Clipboard.readText();
        if (clipboardText?.trim()) {
          setText(clipboardText.trim());
        }
      } catch {
        // Ignore clipboard errors
      }
    };

    loadClipboardText();
  }, []);

  // Cleanup processor on unmount
  useEffect(() => {
    return () => {
      // Only stop if the processor is still actively processing
      // Don't interrupt natural playback completion
      if (processorRef.current && isProcessing && !processorRef.current.paused) {
        logger.consoleDebug("Component unmounting, stopping active TTS processor");
        processorRef.current.stop();
      }
    };
  }, [isProcessing]);

  const handleStart = async () => {
    logger.consoleInfo(" [SPEAK-TEXT] === TTS SESSION START ===");
    logger.consoleInfo(" [SPEAK-TEXT] User initiated speech");
    logger.consoleDebug(" [SPEAK-TEXT] Current state:", {
      isProcessing,
      isPaused,
      textLength: text.length,
      voice,
      speed,
      useStreaming,
      serverUrl: preferences.serverUrl,
    });

    // Log environment info for debugging
    logger.consoleDebug(" [SPEAK-TEXT] Starting speech processing");

    if (isProcessing) {
      logger.consoleDebug(" [SPEAK-TEXT] Restarting - stopping existing processor");
      await processorRef.current?.stop();
    }

    const trimmedText = text.trim();
    if (!trimmedText) {
      logger.consoleWarn(" [SPEAK-TEXT]  No text provided");
      await showToast({
        style: Toast.Style.Failure,
        title: "Text required",
        message: "Please enter some text to speak",
      });
      return;
    }

    logger.consoleDebug(" [SPEAK-TEXT] Text to speak:", {
      length: trimmedText.length,
      preview: trimmedText.substring(0, 100) + (trimmedText.length > 100 ? "..." : ""),
    });

    // Check server health before processing
    if (!isHealthy) {
      logger.consoleWarn(" [SPEAK-TEXT]  Server health check failed");
      await showToast({
        style: Toast.Style.Failure,
        title: "Server unavailable",
        message: "TTS server is not responding. Please check your connection.",
      });
      return;
    }

    logger.consoleInfo(" [SPEAK-TEXT] ✅ Server health check passed");
    logger.consoleDebug(" [SPEAK-TEXT] Server latency:", latency + "ms");

    setIsProcessing(true);
    setIsPaused(false);

    // Add to request history
    addToHistory(trimmedText, voice);
    logger.consoleDebug(" [SPEAK-TEXT] Added to request history");

    logger.consoleDebug(" [SPEAK-TEXT] Creating TTS processor with config:", {
      voice,
      speed,
      serverUrl: preferences.serverUrl,
      useStreaming,
      sentencePauses: preferences.sentencePauses,
      maxSentenceLength: preferences.maxSentenceLength,
    });

    logger.consoleDebug(" [SPEAK-TEXT] About to create TTSSpeechProcessor...");
    const newProcessor = new TTSSpeechProcessor({
      voice,
      speed,
      serverUrl: preferences.serverUrl,
      useStreaming,
      sentencePauses: preferences.sentencePauses,
      maxSentenceLength: preferences.maxSentenceLength.toString(),
      onStatusUpdate,
    });
    logger.consoleDebug(" [SPEAK-TEXT] TTSSpeechProcessor created successfully");
    processorRef.current = newProcessor;

    logger.consoleDebug(" [SPEAK-TEXT] TTS processor created, starting speech...");

    showToast({
      style: Toast.Style.Animated,
      title: "Speaking...",
      message: "Processing text for speech...",
    });

    const startTime = performance.now();
    logger.consoleDebug(" [SPEAK-TEXT]  Speech start time:", startTime);

    newProcessor
      .speak(trimmedText)
      .then(() => {
        const endTime = performance.now();
        const duration = endTime - startTime;
        logger.consoleInfo(" [SPEAK-TEXT] ✅ Speech completed successfully");
        logger.consoleInfo(" [SPEAK-TEXT]  Total duration:", duration.toFixed(2) + "ms");
        logger.consoleInfo(" [SPEAK-TEXT] === TTS SESSION END ===");
      })
      .catch((error) => {
        const endTime = performance.now();
        const duration = endTime - startTime;
        logger.consoleError(" [SPEAK-TEXT]  Speech failed");
        logger.consoleError(" [SPEAK-TEXT]  Failed after:", duration.toFixed(2) + "ms");
        logger.consoleError(" [SPEAK-TEXT] Error:", error);
        logger.consoleError(" [SPEAK-TEXT] Error details:", {
          name: error.name,
          message: error.message,
          stack: error.stack,
          code: error.code,
        });
        logger.consoleError(" [SPEAK-TEXT] === TTS SESSION END (ERROR) ===");

        if (!newProcessor.paused && !processorRef.current?.playing) {
          handleError(
            error instanceof Error ? error : new Error("Unknown error"),
            "audio playback"
          );
        }
      })
      .finally(() => {
        if (processorRef.current === newProcessor) {
          logger.consoleDebug(" [SPEAK-TEXT] Cleaning up processor state");
          setIsProcessing(false);
          setIsPaused(false);
          // Clear processor reference after a delay to allow natural cleanup
          setTimeout(() => {
            if (processorRef.current === newProcessor) {
              logger.consoleDebug(" [SPEAK-TEXT] Clearing processor reference");
              processorRef.current = null;
            }
          }, 100);
          toastRef.current?.hide();
          toastRef.current = null;
        }
      });
  };

  const handleStop = async () => {
    logger.consoleInfo(" [SPEAK-TEXT]  User requested stop");
    if (processorRef.current) {
      logger.consoleDebug(" [SPEAK-TEXT] Stopping processor");
      await processorRef.current.stop();
      setIsProcessing(false);
      setIsPaused(false);
      processorRef.current = null;
      toastRef.current?.hide();
      toastRef.current = null;
      logger.consoleInfo(" [SPEAK-TEXT] ✅ Stop completed");
    } else {
      logger.consoleDebug(" [SPEAK-TEXT] No processor to stop");
    }
  };

  const handlePause = () => {
    logger.consoleInfo(" [SPEAK-TEXT] ⏸️ User requested pause");
    if (processorRef.current?.playing && !processorRef.current?.paused) {
      logger.consoleDebug(" [SPEAK-TEXT] Pausing processor");
      processorRef.current.pause();
      setIsPaused(true);
      logger.consoleInfo(" [SPEAK-TEXT] ✅ Pause completed");
    } else {
      logger.consoleDebug(" [SPEAK-TEXT] Cannot pause - processor not playing or already paused");
    }
  };

  const handleResume = () => {
    logger.consoleInfo(" [SPEAK-TEXT] ▶️ User requested resume");
    if (processorRef.current?.paused) {
      logger.consoleDebug(" [SPEAK-TEXT] Resuming processor");
      processorRef.current.resume();
      setIsPaused(false);
      logger.consoleInfo(" [SPEAK-TEXT] ✅ Resume completed");
    } else {
      logger.consoleDebug(" [SPEAK-TEXT] Cannot resume - processor not paused");
    }
  };

  const handleBenchmark = async () => {
    if (isBenchmarking || isProcessing) return;

    setIsBenchmarking(true);

    try {
      const stats = await ttsBenchmark.runBenchmarkSuite(preferences.serverUrl);
      ttsBenchmark.printReport(stats);

      // Show summary toast
      await showToast({
        style: Toast.Style.Success,
        title: " Benchmark Results",
        message: `Avg: ${stats.averageTotalTime.toFixed(0)}ms | Cache: ${(stats.cacheSpeedup || 1).toFixed(1)}x faster`,
      });
    } catch (error) {
      handleError(error instanceof Error ? error : new Error("Benchmark failed"), "benchmark");
    } finally {
      setIsBenchmarking(false);
    }
  };

  const handleSingleBenchmark = async () => {
    const trimmedText = text.trim();
    if (!trimmedText) {
      await showToast({
        style: Toast.Style.Failure,
        title: "Text required",
        message: "Please enter some text to benchmark",
      });
      return;
    }

    if (isBenchmarking || isProcessing) return;

    setIsBenchmarking(true);

    try {
      const request = {
        text: trimmedText,
        voice: voice,
        speed: preferences.speed,
        lang: "en-us" as const,
        stream: useStreaming,
        format: "wav" as const,
      };

      logger.consoleInfo("\n Single Request Benchmark:");
      logger.consoleInfo(
        `Text: "${trimmedText.substring(0, 50)}${trimmedText.length > 50 ? "..." : ""}"`
      );
      logger.consoleInfo(
        `Voice: ${voice}, Speed: ${preferences.speed}, Streaming: ${useStreaming}`
      );

      const metrics = await ttsBenchmark.benchmarkTTSRequest(
        request,
        preferences.serverUrl,
        (stage, elapsed) => {
          logger.consoleInfo(` ${stage}: ${elapsed.toFixed(2)}ms`);
        }
      );

      // Show detailed results
      const cacheStatus = metrics.cacheHit ? " Cache Hit" : " Network Request";
      const responseTime = metrics.totalResponseTime.toFixed(0);
      const audioSize = (metrics.audioDataSize / 1024).toFixed(1);

      await showToast({
        style: Toast.Style.Success,
        title: `${cacheStatus}: ${responseTime}ms`,
        message: `TTFB: ${metrics.timeToFirstByte.toFixed(0)}ms | Audio: ${audioSize}KB`,
      });

      // Log detailed metrics
      logger.consoleInfo("\n Detailed Metrics:");
      logger.consoleInfo(`   Request ID: ${metrics.requestId}`);
      logger.consoleInfo(`   Cache Hit: ${metrics.cacheHit ? "✅" : ""}`);
      logger.consoleInfo(`   Network Latency: ${metrics.networkLatency.toFixed(2)}ms`);
      logger.consoleInfo(`   Time to First Byte: ${metrics.timeToFirstByte.toFixed(2)}ms`);
      logger.consoleInfo(`   Time to First Audio: ${metrics.timeToFirstAudioChunk.toFixed(2)}ms`);
      logger.consoleInfo(`   Total Response Time: ${metrics.totalResponseTime.toFixed(2)}ms`);
      logger.consoleInfo(`   Audio Processing: ${metrics.audioProcessingTime.toFixed(2)}ms`);
      logger.consoleInfo(`   Audio Data Size: ${(metrics.audioDataSize / 1024).toFixed(2)}KB`);
    } catch (error) {
      handleError(
        error instanceof Error ? error : new Error("Single benchmark failed"),
        "benchmark"
      );
    } finally {
      setIsBenchmarking(false);
    }
  };

  const onStatusUpdate = async (status: StatusUpdate) => {
    logger.consoleDebug(" [SPEAK-TEXT]  Status update:", {
      message: status.message,
      style: status.style,
      isPlaying: status.isPlaying,
      isPaused: status.isPaused,
      hasActions: !!(status.primaryAction || status.secondaryAction),
    });

    const { message, style = Toast.Style.Animated, primaryAction, secondaryAction } = status;

    const options: Toast.Options = {
      style: style as Toast.Style,
      title: message,
      primaryAction,
      secondaryAction,
    };

    if (!toastRef.current) {
      toastRef.current = await showToast(options);
    } else {
      toastRef.current.title = options.title;
      toastRef.current.style = options.style;
      toastRef.current.primaryAction = options.primaryAction;
      toastRef.current.secondaryAction = options.secondaryAction;
    }
  };

  return (
    <Form
      isLoading={(isProcessing && !isPaused) || isBenchmarking}
      actions={
        <ActionPanel>
          {!isProcessing && !isBenchmarking ? (
            <Action.SubmitForm title="Speak" onSubmit={handleStart} />
          ) : isProcessing ? (
            <>
              <Action
                title="Stop"
                onAction={handleStop}
                shortcut={{ modifiers: ["cmd"], key: "." }}
              />
              {!isPaused ? (
                <Action title="Pause" onAction={handlePause} />
              ) : (
                <Action title="Resume" onAction={handleResume} />
              )}
              <Action.SubmitForm title="Restart" onSubmit={handleStart} />
            </>
          ) : null}

          <ActionPanel.Section title="Utilities">
            <Action
              title=" Run Performance Benchmark"
              onAction={handleBenchmark}
              shortcut={{ modifiers: ["cmd", "shift"], key: "b" }}
            />
            <Action
              title=" Benchmark Current Text"
              onAction={handleSingleBenchmark}
              shortcut={{ modifiers: ["cmd", "shift"], key: "t" }}
            />
            <Action
              title="Paste from Clipboard"
              icon=""
              shortcut={{ modifiers: ["cmd"], key: "v" }}
              onAction={async () => {
                try {
                  const clipboardText = await Clipboard.readText();
                  if (clipboardText) {
                    setText(clipboardText);
                  }
                } catch {
                  await showToast({
                    style: Toast.Style.Failure,
                    title: "Failed to paste",
                    message: "Could not read clipboard",
                  });
                }
              }}
            />
          </ActionPanel.Section>
        </ActionPanel>
      }
    >
      <Form.TextArea
        id="text"
        title="Text to Speak"
        placeholder="Enter or paste text here..."
        value={text}
        onChange={setText}
      />

      <Form.Dropdown
        id="voice"
        title="Voice"
        value={voice}
        onChange={(value) => updatePreferences({ voice: value as VoiceOption })}
      >
        {voiceOptions.map((option) => (
          <Form.Dropdown.Item key={option.value} value={option.value} title={option.title} />
        ))}
      </Form.Dropdown>

      <Form.TextField
        id="speed"
        title="Speed"
        placeholder="1.0"
        value={speed}
        onChange={(value) => updatePreferences({ speed: parseFloat(value) || 1.0 })}
        info="Range: 0.1 - 3.0 (1.0 = normal speed)"
      />

      <Form.Checkbox
        id="useStreaming"
        label="Use Streaming"
        value={useStreaming}
        onChange={(value) => updatePreferences({ useStreaming: value })}
      />

      <Form.Separator />

      <Form.Dropdown
        id="performanceProfile"
        title="Performance Profile"
        value={performanceProfile}
        onChange={(value) => updatePreferences({ performanceProfile: value })}
        info={
          profileRecommendations?.reasoning || "Select optimal performance settings for your system"
        }
      >
        {Object.entries(PERFORMANCE_PROFILES).map(([key, profile]) => (
          <Form.Dropdown.Item
            key={key}
            value={key}
            title={`${profile.name}${profileRecommendations?.recommended === key ? " (Recommended)" : ""}`}
          />
        ))}
      </Form.Dropdown>

      <Form.Checkbox
        id="autoSelectProfile"
        label="Auto-select Optimal Profile"
        value={autoSelectProfile}
        onChange={(value) => updatePreferences({ autoSelectProfile: value })}
        info="Automatically select the best performance profile based on your system"
      />

      <Form.Checkbox
        id="showPerformanceMetrics"
        label="Show Performance Metrics"
        value={showPerformanceMetrics}
        onChange={(value) => updatePreferences({ showPerformanceMetrics: value })}
        info="Display real-time performance metrics during TTS processing"
      />

      {profileRecommendations && (
        <Form.Description
          title="Profile Recommendation"
          text={`${profileRecommendations.reasoning} Alternatives: ${profileRecommendations.alternatives.join(", ")}`}
        />
      )}

      {serverHealth && (
        <Form.Description
          title="Server Status"
          text={`${isHealthy ? "✅ Online" : " Offline"} (${latency}ms)`}
        />
      )}

      {daemonHealth && (
        <Form.Description
          title="Daemon Status"
          text={`${daemonHealthy ? "✅ Online" : " Offline"} (${daemonLatency}ms)`}
        />
      )}

      {requestHistory.length > 0 && (
        <Form.Description
          title="Recent Requests"
          text={`${requestHistory.length} cached requests`}
        />
      )}
    </Form>
  );
}
