/**
 * Command: "Speak Selected Text"
 *
 * This is a Raycast command to speak the currently selected text using the TTS processor.
 * Select any text in any app, run this command, and it will speak the text.
 * If you want, you can also set a shortcut for this command in Raycast.
 *
 * Author: @darianrosebrook
 * Date: 2025-07-08
 * Version: 1.0.0
 * License: MIT
 *
 * This code is provided as-is, without any warranty. Use at your own risk.
 */

import { getSelectedText, showToast, Toast, getPreferenceValues } from "@raycast/api";

import { TTSSpeechProcessor } from "./utils/tts/tts-processor";
import { getValidatedVoice } from "./utils/tts/voice-manager";
import type { StatusUpdate } from "./types";
import { logger } from "./utils/core/logger";
/**
 * Raycast command to speak currently selected text using the TTS processor
 */
export default async function SpeakSelection() {
  let processor: TTSSpeechProcessor | undefined;
  logger.consoleDebug("SpeakSelection");

  const onStatusUpdate = (status: StatusUpdate) => {
    const toastOptions: Toast.Options = {
      style: status.style,
      title: status.message,
      message: status.message,
    };

    if (status.primaryAction) {
      toastOptions.primaryAction = status.primaryAction;
    }

    if (status.secondaryAction) {
      toastOptions.secondaryAction = status.secondaryAction;
    }

    showToast(toastOptions);
  };

  try {
    // Get selected text first (before closing window)
    let text: string;
    try {
      text = await getSelectedText();
      logger.debug("[SPEAK-SELECTION] Selected text:", {
        length: text.length,
        preview: text.substring(0, 100) + (text.length > 100 ? "..." : ""),
      });
      logger.consoleDebug("Text successfully retrieved from selection");
    } catch {
      await showToast({
        style: Toast.Style.Failure,
        title: "Failed to read selection",
        message: "Could not access selected text",
      });
      return;
    }

    if (!text?.trim()) {
      await showToast({
        style: Toast.Style.Failure,
        title: "No text selected",
        message: "Please select some text first",
      });
      return;
    }

    await showToast({
      title: "Processing text for speech...",
    });

    // Get user preferences with enhanced validation
    const prefs = getPreferenceValues();
    const serverUrl = prefs.serverUrl || "http://localhost:8000";
    logger.consoleDebug("Validating voice configuration");
    // Validate and get the best available voice
    const validatedVoice = await getValidatedVoice(prefs.voice || "af_heart", serverUrl);

    // Create processor with validated voice and speed (minimum 1.25 for API)
    const validatedSpeed = Math.max(1.25, parseFloat(prefs.speed || "1.0"));
    processor = new TTSSpeechProcessor({
      voice: validatedVoice,
      speed: String(validatedSpeed),
      serverUrl: serverUrl,
      useStreaming: prefs.useStreaming ?? true,
      sentencePauses: prefs.sentencePauses ?? false,
      maxSentenceLength: prefs.maxSentenceLength || "0",
      onStatusUpdate,
    });

    logger.debug("[SPEAK-SELECTION] === START TTS ===");
    logger.debug("[SPEAK-SELECTION] Selected text:", {
      length: text.length,
      preview: text.substring(0, 100) + (text.length > 100 ? "..." : ""),
    });
    logger.debug("[SPEAK-SELECTION] TTS processor created with config");

    // This will await until playback is completely finished
    await processor.speak(text);
    logger.info("[SPEAK-SELECTION] ✅ TTS processing completed successfully");

    // The 'speak' method now resolves when finished, paused, or stopped.
    // We only show "Finished" if it wasn't stopped.
    if (processor.playing) {
      await showToast({
        style: Toast.Style.Success,
        title: "Finished speaking",
        message: "Completed playback of selected text.",
      });
    }
  } catch (error) {
    logger.error("[SPEAK-SELECTION] TTS processing failed:", {}, error as Error);

    await showToast({
      style: Toast.Style.Failure,
      title: "Command failed",
      message: error instanceof Error ? error.message : "Unknown error",
    });
  } finally {
    // The processor will handle its own cleanup when playback completes naturally
    // Calling processor.stop() here would prematurely terminate ongoing playback
    logger.debug("[SPEAK-SELECTION] === END TTS ===");
  }
}
