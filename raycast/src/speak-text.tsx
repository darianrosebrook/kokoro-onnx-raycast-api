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
} from "./utils/core/state-management";
import { ttsBenchmark } from "./utils/performance-benchmark";
import { generateVoiceOptions as generateDynamicVoiceOptions } from "./utils/tts/voice-manager";
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
    console.warn("Falling back to hardcoded voices:", error);

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
  addLanguageGroup(getAmericanEnglishVoices(), "🇺🇸");
  addLanguageGroup(getBritishEnglishVoices(), "🇬🇧");
  addLanguageGroup(getFrenchVoices(), "🇫🇷");
  addLanguageGroup(getJapaneseVoices(), "🇯🇵");
  addLanguageGroup(getHindiVoices(), "🇮🇳");
  addLanguageGroup(getItalianVoices(), "🇮🇹");
  addLanguageGroup(getMandarinChineseVoices(), "🇨🇳");
  addLanguageGroup(getSpanishVoices(), "🇪🇸");
  addLanguageGroup(getBrazilianPortugueseVoices(), "🇧🇷");

  return voiceOptions;
};

/**
 * Available voice options for the TTS (ordered by quality)
 */
const VOICE_OPTIONS = generateHardcodedVoiceOptions();

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
  const [voiceOptions, setVoiceOptions] = useState<{ value: VoiceOption; title: string }[]>([]);
  const [isLoadingVoices, setIsLoadingVoices] = useState(true);
  const processorRef = useRef<TTSSpeechProcessor | null>(null);
  const toastRef = useRef<Toast | null>(null);

  // Use preferences from enhanced state management
  const voice = preferences.voice;
  const speed = preferences.speed.toString();
  const useStreaming = preferences.useStreaming;

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
      processorRef.current?.stop();
    };
  }, []);

  const handleStart = async () => {
    if (isProcessing) {
      // Restart logic
      await processorRef.current?.stop();
    }

    const trimmedText = text.trim();
    if (!trimmedText) {
      await showToast({
        style: Toast.Style.Failure,
        title: "Text required",
        message: "Please enter some text to speak",
      });
      return;
    }

    // Check server health before processing
    if (!isHealthy) {
      await showToast({
        style: Toast.Style.Failure,
        title: "Server unavailable",
        message: "TTS server is not responding. Please check your connection.",
      });
      return;
    }

    setIsProcessing(true);
    setIsPaused(false);

    // Add to request history
    addToHistory(trimmedText, voice);

    console.log("useStreaming", useStreaming, "server latency:", latency);
    const newProcessor = new TTSSpeechProcessor({
      voice,
      speed,
      serverUrl: preferences.serverUrl,
      useStreaming,
      sentencePauses: preferences.sentencePauses,
      maxSentenceLength: preferences.maxSentenceLength.toString(),
      onStatusUpdate,
    });
    processorRef.current = newProcessor;
    showToast({
      style: Toast.Style.Animated,
      title: "Speaking...",
      message: "Processing text for speech...",
    });
    newProcessor
      .speak(trimmedText)
      .catch((error) => {
        if (!newProcessor.paused && !processorRef.current?.playing) {
          handleError(
            error instanceof Error ? error : new Error("Unknown error"),
            "audio playback"
          );
        }
      })
      .finally(() => {
        if (processorRef.current === newProcessor) {
          setIsProcessing(false);
          setIsPaused(false);
          processorRef.current = null;
          toastRef.current?.hide();
          toastRef.current = null;
        }
      });
  };

  const handleStop = async () => {
    if (processorRef.current) {
      await processorRef.current.stop();
      setIsProcessing(false);
      setIsPaused(false);
      processorRef.current = null;
      toastRef.current?.hide();
      toastRef.current = null;
    }
  };

  const handlePause = () => {
    if (processorRef.current?.playing && !processorRef.current?.paused) {
      processorRef.current.pause();
      setIsPaused(true);
    }
  };

  const handleResume = () => {
    if (processorRef.current?.paused) {
      processorRef.current.resume();
      setIsPaused(false);
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
        title: "📊 Benchmark Results",
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

      console.log("\n🎯 Single Request Benchmark:");
      console.log(`Text: "${trimmedText.substring(0, 50)}${trimmedText.length > 50 ? "..." : ""}"`);
      console.log(`Voice: ${voice}, Speed: ${preferences.speed}, Streaming: ${useStreaming}`);

      const metrics = await ttsBenchmark.benchmarkTTSRequest(
        request,
        preferences.serverUrl,
        (stage, elapsed) => {
          console.log(`📊 ${stage}: ${elapsed.toFixed(2)}ms`);
        }
      );

      // Show detailed results
      const cacheStatus = metrics.cacheHit ? "🎯 Cache Hit" : "🌐 Network Request";
      const responseTime = metrics.totalResponseTime.toFixed(0);
      const audioSize = (metrics.audioDataSize / 1024).toFixed(1);

      await showToast({
        style: Toast.Style.Success,
        title: `${cacheStatus}: ${responseTime}ms`,
        message: `TTFB: ${metrics.timeToFirstByte.toFixed(0)}ms | Audio: ${audioSize}KB`,
      });

      // Log detailed metrics
      console.log("\n📋 Detailed Metrics:");
      console.log(`   Request ID: ${metrics.requestId}`);
      console.log(`   Cache Hit: ${metrics.cacheHit ? "✅" : "❌"}`);
      console.log(`   Network Latency: ${metrics.networkLatency.toFixed(2)}ms`);
      console.log(`   Time to First Byte: ${metrics.timeToFirstByte.toFixed(2)}ms`);
      console.log(`   Time to First Audio: ${metrics.timeToFirstAudioChunk.toFixed(2)}ms`);
      console.log(`   Total Response Time: ${metrics.totalResponseTime.toFixed(2)}ms`);
      console.log(`   Audio Processing: ${metrics.audioProcessingTime.toFixed(2)}ms`);
      console.log(`   Audio Data Size: ${(metrics.audioDataSize / 1024).toFixed(2)}KB`);
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
              title="📊 Run Performance Benchmark"
              onAction={handleBenchmark}
              shortcut={{ modifiers: ["cmd", "shift"], key: "b" }}
            />
            <Action
              title="🎯 Benchmark Current Text"
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

      {serverHealth && (
        <Form.Description
          title="Server Status"
          text={`${isHealthy ? "✅ Online" : "❌ Offline"} (${latency}ms)`}
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
