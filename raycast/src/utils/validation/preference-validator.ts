/**
 * Enhanced Preference Validation for Raycast Kokoro TTS
 *
 * This module provides comprehensive validation for user preferences
 * with safe defaults, bounds checking, and error handling.
 *
 * Features:
 * - Safe defaults with fallbacks
 * - Bounds checking for numeric values
 * - URL validation and normalization
 * - Voice option validation
 * - Error handling with informative messages
 *
 * @author @darianrosebrook
 * @version 1.0.0
 * @since 2025-07-17
 */

import { showToast, Toast } from "@raycast/api";
import type { VoiceOption, TTSProcessorConfig } from "./tts-types.js";
import { VOICES } from "../tts/voices.js";

/**
 * Validation result with error information
 */
interface ValidationResult<T> {
  isValid: boolean;
  value: T;
  errors: string[];
  warnings: string[];
}

/**
 * Default TTS configuration with safe defaults
 */
export const DEFAULT_TTS_CONFIG: TTSProcessorConfig = {
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
 * Valid voice options (extracted from VOICES catalog)
 */
const VALID_VOICES = Object.keys(VOICES) as VoiceOption[];

/**
 * Validate voice option
 */
export const validateVoice = (voice: unknown): ValidationResult<VoiceOption> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!voice || typeof voice !== "string") {
    errors.push("Voice must be a string");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.voice,
      errors,
      warnings,
    };
  }

  const voiceOption = voice as VoiceOption;

  if (!VALID_VOICES.includes(voiceOption)) {
    errors.push(`Invalid voice: ${voice}. Using default voice instead.`);
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.voice,
      errors,
      warnings,
    };
  }

  // Check voice quality and add warnings for low-quality voices
  const voiceConfig = VOICES[voiceOption];
  if (voiceConfig.overallGrade === "D" || voiceConfig.overallGrade === "F") {
    warnings.push(
      `Voice "${voice}" has lower quality (${voiceConfig.overallGrade}). Consider using a higher quality voice.`
    );
  }

  return {
    isValid: true,
    value: voiceOption,
    errors,
    warnings,
  };
};

/**
 * Validate speed value
 */
export const validateSpeed = (speed: unknown): ValidationResult<number> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (speed === null || speed === undefined) {
    return {
      isValid: true,
      value: DEFAULT_TTS_CONFIG.speed,
      errors,
      warnings,
    };
  }

  let numericSpeed: number;

  if (typeof speed === "string") {
    numericSpeed = parseFloat(speed);
  } else if (typeof speed === "number") {
    numericSpeed = speed;
  } else {
    errors.push("Speed must be a number or string");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.speed,
      errors,
      warnings,
    };
  }

  if (isNaN(numericSpeed)) {
    errors.push("Speed must be a valid number");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.speed,
      errors,
      warnings,
    };
  }

  // Clamp speed to valid range
  const clampedSpeed = Math.max(0.1, Math.min(3.0, numericSpeed));

  if (clampedSpeed !== numericSpeed) {
    warnings.push(
      `Speed adjusted from ${numericSpeed} to ${clampedSpeed} (valid range: 0.1 - 3.0)`
    );
  }

  // Add performance warnings
  if (clampedSpeed < 0.5) {
    warnings.push("Very slow speech speed may impact user experience");
  } else if (clampedSpeed > 2.0) {
    warnings.push("Very fast speech speed may reduce comprehension");
  }

  return {
    isValid: true,
    value: clampedSpeed,
    errors,
    warnings,
  };
};

/**
 * Validate daemon URL
 */
export const validateDaemonUrl = (url: unknown): ValidationResult<string> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!url || typeof url !== "string") {
    errors.push("Daemon URL must be a string");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.daemonUrl,
      errors,
      warnings,
    };
  }

  let cleanUrl = url.trim();

  // Add protocol if missing
  if (!cleanUrl.startsWith("http://") && !cleanUrl.startsWith("https://")) {
    cleanUrl = `http://${cleanUrl}`;
    warnings.push("Added http:// protocol to daemon URL");
  }
};
/**
 * Validate server URL
 */
export const validateServerUrl = (url: unknown): ValidationResult<string> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!url || typeof url !== "string") {
    errors.push("Server URL must be a string");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.serverUrl,
      errors,
      warnings,
    };
  }

  let cleanUrl = url.trim();

  // Add protocol if missing
  if (!cleanUrl.startsWith("http://") && !cleanUrl.startsWith("https://")) {
    cleanUrl = `http://${cleanUrl}`;
    warnings.push("Added http:// protocol to server URL");
  }

  // Remove trailing slashes
  cleanUrl = cleanUrl.replace(/\/+$/, "");

  // Basic URL validation
  try {
    const parsedUrl = new URL(cleanUrl);

    // Check for localhost/development patterns
    if (parsedUrl.hostname === "localhost" || parsedUrl.hostname === "127.0.0.1") {
      warnings.push("Using localhost server - ensure TTS server is running locally");
    }

    // Check for common port patterns
    if (parsedUrl.port && parsedUrl.port !== "8080") {
      warnings.push(`Using non-standard port ${parsedUrl.port} - default is 8080`);
    }

    return {
      isValid: true,
      value: cleanUrl,
      errors,
      warnings,
    };
  } catch (error) {
    errors.push(`Invalid URL format: ${error instanceof Error ? error.message : "Unknown error"}`);
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.serverUrl,
      errors,
      warnings,
    };
  }
};

/**
 * Validate boolean option
 */
export const validateBoolean = (
  value: unknown,
  defaultValue: boolean,
  fieldName: string
): ValidationResult<boolean> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (value === null || value === undefined) {
    return {
      isValid: true,
      value: defaultValue,
      errors,
      warnings,
    };
  }

  if (typeof value === "boolean") {
    return {
      isValid: true,
      value,
      errors,
      warnings,
    };
  }

  // Try to parse string boolean
  if (typeof value === "string") {
    const lowerValue = value.toLowerCase().trim();
    if (lowerValue === "true" || lowerValue === "1" || lowerValue === "yes") {
      return {
        isValid: true,
        value: true,
        errors,
        warnings,
      };
    } else if (lowerValue === "false" || lowerValue === "0" || lowerValue === "no") {
      return {
        isValid: true,
        value: false,
        errors,
        warnings,
      };
    }
  }

  errors.push(`${fieldName} must be a boolean value`);
  return {
    isValid: false,
    value: defaultValue,
    errors,
    warnings,
  };
};

/**
 * Validate max sentence length
 */
export const validateMaxSentenceLength = (length: unknown): ValidationResult<number> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (length === null || length === undefined) {
    return {
      isValid: true,
      value: DEFAULT_TTS_CONFIG.maxSentenceLength,
      errors,
      warnings,
    };
  }

  let numericLength: number;

  if (typeof length === "string") {
    numericLength = parseInt(length, 10);
  } else if (typeof length === "number") {
    numericLength = Math.floor(length);
  } else {
    errors.push("Max sentence length must be a number or string");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.maxSentenceLength,
      errors,
      warnings,
    };
  }

  if (isNaN(numericLength)) {
    errors.push("Max sentence length must be a valid number");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.maxSentenceLength,
      errors,
      warnings,
    };
  }

  // Clamp to valid range
  const clampedLength = Math.max(0, Math.min(2000, numericLength));

  if (clampedLength !== numericLength) {
    warnings.push(
      `Max sentence length adjusted from ${numericLength} to ${clampedLength} (valid range: 0 - 2000)`
    );
  }

  // Add performance warnings
  if (clampedLength > 0 && clampedLength < 50) {
    warnings.push("Very short sentence limit may create fragmented speech");
  } else if (clampedLength > 1000) {
    warnings.push("Very long sentence limit may cause processing delays");
  }

  return {
    isValid: true,
    value: clampedLength,
    errors,
    warnings,
  };
};

/**
 * Validate Node.js executable path
 */
export const validateNodePath = (path: unknown): ValidationResult<string> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!path || typeof path !== "string") {
    errors.push("Node.js path must be a string");
    return {
      isValid: false,
      value: "node", // Default to system PATH
      errors,
      warnings,
    };
  }

  const cleanPath = path.trim();

  if (cleanPath.length === 0) {
    errors.push("Node.js path cannot be empty");
    return {
      isValid: false,
      value: "node",
      errors,
      warnings,
    };
  }

  // Basic path validation
  if (cleanPath.includes("..") || cleanPath.includes("~")) {
    warnings.push("Node.js path contains potentially unsafe characters");
  }

  // Check if path looks like a valid Node.js executable
  const nodePatterns = [/node$/, /node\.exe$/, /nodejs$/, /nodejs\.exe$/];

  const isValidNodePath = nodePatterns.some((pattern) => pattern.test(cleanPath));

  if (!isValidNodePath) {
    warnings.push("Path may not be a valid Node.js executable");
  }

  return {
    isValid: true,
    value: cleanPath,
    errors,
    warnings,
  };
};

/**
 * Validate performance profile
 */
export const validatePerformanceProfile = (profile: unknown): ValidationResult<string> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!profile || typeof profile !== "string") {
    errors.push("Performance profile must be a string");
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.performanceProfile,
      errors,
      warnings,
    };
  }

  const validProfiles = ["conservative", "balanced", "aggressive", "network-optimized"];

  if (!validProfiles.includes(profile)) {
    errors.push(`Invalid performance profile: ${profile}. Using default profile.`);
    return {
      isValid: false,
      value: DEFAULT_TTS_CONFIG.performanceProfile,
      errors,
      warnings,
    };
  }

  return {
    isValid: true,
    value: profile,
    errors,
    warnings,
  };
};

/**
 * Validate auto-select profile setting
 */
export const validateAutoSelectProfile = (autoSelect: unknown): ValidationResult<boolean> => {
  return validateBoolean(autoSelect, DEFAULT_TTS_CONFIG.autoSelectProfile, "Auto-select profile");
};

/**
 * Validate show performance metrics setting
 */
export const validateShowPerformanceMetrics = (showMetrics: unknown): ValidationResult<boolean> => {
  return validateBoolean(
    showMetrics,
    DEFAULT_TTS_CONFIG.showPerformanceMetrics,
    "Show performance metrics"
  );
};

/**
 * Validate complete TTS configuration
 */
export const validateTTSConfig = (
  config: Partial<TTSProcessorConfig>
): ValidationResult<TTSProcessorConfig> => {
  const errors: string[] = [];
  const warnings: string[] = [];

  // Validate each field
  const voiceResult = validateVoice(config.voice);
  const speedResult = validateSpeed(config.speed);
  const serverUrlResult = validateServerUrl(config.serverUrl);
  const daemonUrlResult = validateDaemonUrl(config.daemonUrl);
  const streamingResult = validateBoolean(
    config.useStreaming,
    DEFAULT_TTS_CONFIG.useStreaming,
    "useStreaming"
  );
  const pausesResult = validateBoolean(
    config.sentencePauses,
    DEFAULT_TTS_CONFIG.sentencePauses,
    "sentencePauses"
  );
  const maxLengthResult = validateMaxSentenceLength(config.maxSentenceLength);
  const performanceProfileResult = validatePerformanceProfile(config.performanceProfile);
  const autoSelectProfileResult = validateAutoSelectProfile(config.autoSelectProfile);
  const showPerformanceMetricsResult = validateShowPerformanceMetrics(
    config.showPerformanceMetrics
  );

  // Collect all errors and warnings
  errors.push(
    ...voiceResult.errors,
    ...speedResult.errors,
    ...serverUrlResult.errors,
    ...daemonUrlResult.errors,
    ...streamingResult.errors,
    ...pausesResult.errors,
    ...maxLengthResult.errors,
    ...performanceProfileResult.errors,
    ...autoSelectProfileResult.errors,
    ...showPerformanceMetricsResult.errors
  );
  warnings.push(
    ...voiceResult.warnings,
    ...speedResult.warnings,
    ...serverUrlResult.warnings,
    ...daemonUrlResult.warnings,
    ...streamingResult.warnings,
    ...pausesResult.warnings,
    ...maxLengthResult.warnings,
    ...performanceProfileResult.warnings,
    ...autoSelectProfileResult.warnings,
    ...showPerformanceMetricsResult.warnings
  );

  const validatedConfig: TTSProcessorConfig = {
    voice: voiceResult.value,
    speed: speedResult.value,
    serverUrl: serverUrlResult.value,
    daemonUrl: daemonUrlResult.value,
    useStreaming: streamingResult.value,
    sentencePauses: pausesResult.value,
    maxSentenceLength: maxLengthResult.value,
    format: config.format ?? DEFAULT_TTS_CONFIG.format,
    developmentMode: config.developmentMode ?? DEFAULT_TTS_CONFIG.developmentMode,
    performanceProfile: performanceProfileResult.value,
    autoSelectProfile: autoSelectProfileResult.value,
    showPerformanceMetrics: showPerformanceMetricsResult.value,
    onStatusUpdate: config.onStatusUpdate ?? DEFAULT_TTS_CONFIG.onStatusUpdate,
  };

  return {
    isValid: errors.length === 0,
    value: validatedConfig,
    errors,
    warnings,
  };
};

/**
 * Show validation results to user
 */
export const showValidationResults = async (result: ValidationResult<unknown>, context: string) => {
  if (result.errors.length > 0) {
    await showToast({
      style: Toast.Style.Failure,
      title: `Validation Error: ${context}`,
      message: result.errors.join(", "),
    });
  } else if (result.warnings.length > 0) {
    await showToast({
      style: Toast.Style.Animated,
      title: `Validation Warning: ${context}`,
      message: result.warnings.join(", "),
    });
  }
};

/**
 * Enhanced preference validation with user feedback
 */
export const validatePreferencesWithFeedback = async (
  config: Partial<TTSProcessorConfig>,
  showFeedback = true
): Promise<TTSProcessorConfig> => {
  const result = validateTTSConfig(config);

  if (showFeedback) {
    await showValidationResults(result, "Preferences");
  }

  return result.value;
};
