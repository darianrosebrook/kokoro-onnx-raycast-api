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
import {
  Form,
  ActionPanel,
  showToast,
  Toast,
  Clipboard,
  getPreferenceValues,
  Action,
} from "@raycast/api";
import { useState, useEffect, useRef } from "react";
import { TTSSpeechProcessor } from "./utils/tts-processor";
import type { VoiceOption, TTSConfig, StatusUpdate } from "./types";
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
} from "./voices";

/**
 * Generate voice options from the VOICES catalog, organized by language
 */
const generateVoiceOptions = (): { value: VoiceOption; title: string }[] => {
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
const VOICE_OPTIONS = generateVoiceOptions();

/**
 * Simple TTS form component using the processor
 */
export default function SpeakTextSimple() {
  const [text, setText] = useState("");
  const [voice, setVoice] = useState<VoiceOption>("af_heart");
  const [speed, setSpeed] = useState("1.2");
  const [useStreaming, setUseStreaming] = useState(true);
  const [isProcessing, setIsProcessing] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const processorRef = useRef<TTSSpeechProcessor | null>(null);
  const toastRef = useRef<Toast | null>(null);

  // Load preferences
  useEffect(() => {
    try {
      const prefs = getPreferenceValues<Partial<TTSConfig>>();
      if (prefs.voice) setVoice(prefs.voice);
      if (prefs.speed) setSpeed(prefs.speed.toString());
      if (prefs.useStreaming) setUseStreaming(prefs.useStreaming);
    } catch {
      // Use defaults
    }
  }, []);

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

    const speedNum = parseFloat(speed);
    if (isNaN(speedNum) || speedNum < 0.1 || speedNum > 3.0) {
      await showToast({
        style: Toast.Style.Failure,
        title: "Invalid speed",
        message: "Speed must be between 0.1 and 3.0",
      });
      return;
    }

    setIsProcessing(true);
    setIsPaused(false);
    console.log("useStreaming", useStreaming);
    const prefs = getPreferenceValues();
    const newProcessor = new TTSSpeechProcessor({
      ...prefs,
      speed,
      voice,
      onStatusUpdate,
      useStreaming,
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
          showToast({
            style: Toast.Style.Failure,
            title: "Speech failed",
            message: error instanceof Error ? error.message : "Unknown error",
          });
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

  const onStatusUpdate = async (status: StatusUpdate) => {
    const { message, style = Toast.Style.Animated, primaryAction, secondaryAction } = status;

    const options: Toast.Options = {
      style,
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
      isLoading={isProcessing && !isPaused}
      actions={
        <ActionPanel>
          {!isProcessing ? (
            <Action.SubmitForm title="Speak" onSubmit={handleStart} />
          ) : (
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
          )}

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
        onChange={(value) => setVoice(value as VoiceOption)}
      >
        {VOICE_OPTIONS.map((option) => (
          <Form.Dropdown.Item key={option.value} value={option.value} title={option.title} />
        ))}
      </Form.Dropdown>

      <Form.TextField
        id="speed"
        title="Speed"
        placeholder="1.0"
        value={speed}
        onChange={setSpeed}
        info="Range: 0.1 - 3.0 (1.0 = normal speed)"
      />

      <Form.Checkbox
        id="useStreaming"
        label="Use Streaming"
        value={useStreaming}
        onChange={setUseStreaming}
      />
    </Form>
  );
}
