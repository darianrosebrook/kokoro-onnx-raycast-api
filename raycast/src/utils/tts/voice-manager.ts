/**
 * Voice Management Utilities
 *
 * Centralized voice management for dynamic voice fetching,
 * validation, and caching across the Raycast extension.
 *
 * Author: @darianrosebrook
 * Date: 2025-07-08
 * Version: 1.0.0
 * License: MIT
 */

import type { VoiceOption } from "../validation/tts-types";

/**
 * Cache for voice data to avoid repeated API calls
 */
interface VoiceCache {
  voices: string[];
  timestamp: number;
}

let voiceCache: VoiceCache | null = null;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

/**
 * Fetch available voices from the server
 */
export async function fetchAvailableVoices(serverUrl: string): Promise<string[]> {
  // Check cache first
  const now = Date.now();
  if (voiceCache && now - voiceCache.timestamp < CACHE_DURATION) {
    return voiceCache.voices;
  }

  try {
    const response = await fetch(`${serverUrl}/voices`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();
    const voices = data.voices || [];

    // Cache the results
    voiceCache = {
      voices,
      timestamp: now,
    };

    return voices;
  } catch (error) {
    console.warn("Failed to fetch voices from server:", error);
    return [];
  }
}

/**
 * Validate and get the best available voice
 */
export async function getValidatedVoice(
  requestedVoice: string,
  serverUrl: string
): Promise<string> {
  try {
    const availableVoices = await fetchAvailableVoices(serverUrl);

    if (availableVoices.length === 0) {
      console.warn("No voices available from server, using requested voice");
      return requestedVoice;
    }

    // Check if requested voice is available
    if (availableVoices.includes(requestedVoice)) {
      console.log(`✅ Using requested voice: ${requestedVoice}`);
      return requestedVoice;
    }

    // Find a suitable fallback voice
    console.warn(`⚠️ Requested voice '${requestedVoice}' not available`);

    // Try to find a similar voice (same gender/category if possible)
    const requestedPrefix = requestedVoice.split("_")[0];
    const similarVoices = availableVoices.filter((voice) =>
      voice.startsWith(requestedPrefix.substring(0, 2))
    );

    if (similarVoices.length > 0) {
      const fallbackVoice = similarVoices[0];
      console.log(`🔄 Using similar voice: ${fallbackVoice}`);
      return fallbackVoice;
    }

    // Default fallback - use first available voice
    const fallbackVoice = availableVoices[0];
    console.log(`🔄 Using fallback voice: ${fallbackVoice}`);
    console.log(
      `📋 Available voices: ${availableVoices.slice(0, 5).join(", ")}${availableVoices.length > 5 ? "..." : ""}`
    );

    return fallbackVoice;
  } catch (error) {
    console.error("Voice validation failed:", error);
    return requestedVoice; // Return original voice if validation fails
  }
}

/**
 * Format voice name for display
 */
export function formatVoiceName(name: string): string {
  const parts = name.split("_");
  if (parts.length < 2) return name;

  const voiceName = parts[1];
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
}

/**
 * Categorize voice by language/region
 */
export function categorizeVoice(name: string): { flag: string; category: string } {
  const prefix = name.split("_")[0];

  // American English
  if (prefix.startsWith("af") || prefix.startsWith("am")) {
    return { flag: "🇺🇸", category: "American English" };
  }
  // British English
  if (prefix.startsWith("bf") || prefix.startsWith("bm")) {
    return { flag: "🇬🇧", category: "British English" };
  }
  // Chinese
  if (prefix.startsWith("cf") || prefix.startsWith("cm")) {
    return { flag: "🇨🇳", category: "Chinese" };
  }
  // French
  if (prefix.startsWith("df") || prefix.startsWith("dm")) {
    return { flag: "🇫🇷", category: "French" };
  }
  // Other patterns - default to US English
  return { flag: "🇺🇸", category: "English" };
}

/**
 * Generate voice options for UI dropdown from server voices
 */
export async function generateVoiceOptions(
  serverUrl: string
): Promise<{ value: VoiceOption; title: string }[]> {
  const voiceOptions: { value: VoiceOption; title: string }[] = [];

  try {
    const serverVoices = await fetchAvailableVoices(serverUrl);

    if (serverVoices.length === 0) {
      throw new Error("No voices available from server");
    }

    // Group voices by category
    const voicesByCategory: Record<string, string[]> = {};

    serverVoices.forEach((voice) => {
      const { category } = categorizeVoice(voice);
      if (!voicesByCategory[category]) {
        voicesByCategory[category] = [];
      }
      voicesByCategory[category].push(voice);
    });

    // Add voices in order of preference
    const categoryOrder = ["American English", "British English", "French", "Chinese", "English"];

    categoryOrder.forEach((category) => {
      if (voicesByCategory[category]) {
        voicesByCategory[category].sort().forEach((voice) => {
          const { flag } = categorizeVoice(voice);
          const displayName = formatVoiceName(voice);
          voiceOptions.push({
            value: voice as VoiceOption,
            title: `${flag} ${displayName}`,
          });
        });
      }
    });

    // Add any remaining categories
    Object.keys(voicesByCategory).forEach((category) => {
      if (!categoryOrder.includes(category)) {
        voicesByCategory[category].sort().forEach((voice) => {
          const { flag } = categorizeVoice(voice);
          const displayName = formatVoiceName(voice);
          voiceOptions.push({
            value: voice as VoiceOption,
            title: `${flag} ${displayName}`,
          });
        });
      }
    });

    console.log(`✅ Generated ${voiceOptions.length} voice options from server`);
    return voiceOptions;
  } catch (error) {
    console.error("Failed to generate voice options from server:", error);
    throw error;
  }
}

/**
 * Clear the voice cache (useful for testing or when server changes)
 */
export function clearVoiceCache(): void {
  voiceCache = null;
}
