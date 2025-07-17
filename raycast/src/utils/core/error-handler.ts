/**
 * Error handling system for user-facing errors in the TTS system
 * @author @darianrosebrook
 */

import { logger } from "./logger";

/**
 * Error types that can be presented to users
 */
export enum UserErrorType {
  NODE_JS_MISSING = "NODE_JS_MISSING",
  DAEMON_STARTUP_FAILED = "DAEMON_STARTUP_FAILED",
  AUDIO_DEVICE_ERROR = "AUDIO_DEVICE_ERROR",
  NETWORK_ERROR = "NETWORK_ERROR",
  PERMISSION_ERROR = "PERMISSION_ERROR",
  CONFIGURATION_ERROR = "CONFIGURATION_ERROR",
  UNKNOWN_ERROR = "UNKNOWN_ERROR",
}

/**
 * User-friendly error information
 */
export interface UserError {
  type: UserErrorType;
  title: string;
  message: string;
  suggestion: string;
  technicalDetails?: string;
  recoverySteps?: string[];
}

/**
 * Error handler for TTS system
 */
export class TTSErrorHandler {
  private static readonly ERROR_MESSAGES: Record<UserErrorType, UserError> = {
    [UserErrorType.NODE_JS_MISSING]: {
      type: UserErrorType.NODE_JS_MISSING,
      title: "Node.js Not Found",
      message: "Node.js is required but not found on your system.",
      suggestion: "Please install Node.js from https://nodejs.org/",
      recoverySteps: [
        "Download and install Node.js from https://nodejs.org/",
        "Restart Raycast after installation",
        "Verify installation by running 'node --version' in Terminal",
      ],
    },
    [UserErrorType.DAEMON_STARTUP_FAILED]: {
      type: UserErrorType.DAEMON_STARTUP_FAILED,
      title: "Audio Service Failed to Start",
      message: "The audio playback service could not be started.",
      suggestion: "Try restarting Raycast or check system permissions.",
      recoverySteps: [
        "Restart Raycast completely",
        "Check if another application is using the audio port",
        "Verify microphone permissions in System Preferences",
      ],
    },
    [UserErrorType.AUDIO_DEVICE_ERROR]: {
      type: UserErrorType.AUDIO_DEVICE_ERROR,
      title: "Audio Device Error",
      message: "There was a problem with your audio output device.",
      suggestion: "Check your audio settings and try again.",
      recoverySteps: [
        "Check if your speakers/headphones are connected",
        "Verify audio output settings in System Preferences",
        "Try selecting a different audio output device",
      ],
    },
    [UserErrorType.NETWORK_ERROR]: {
      type: UserErrorType.NETWORK_ERROR,
      title: "Network Connection Error",
      message: "Unable to connect to the text-to-speech service.",
      suggestion: "Check your internet connection and try again.",
      recoverySteps: [
        "Verify your internet connection",
        "Check if the TTS service is available",
        "Try again in a few moments",
      ],
    },
    [UserErrorType.PERMISSION_ERROR]: {
      type: UserErrorType.PERMISSION_ERROR,
      title: "Permission Required",
      message: "This extension needs permission to access audio features.",
      suggestion: "Grant the required permissions in System Preferences.",
      recoverySteps: [
        "Open System Preferences > Security & Privacy > Privacy",
        "Select 'Microphone' from the left sidebar",
        "Add Raycast to the list of allowed applications",
      ],
    },
    [UserErrorType.CONFIGURATION_ERROR]: {
      type: UserErrorType.CONFIGURATION_ERROR,
      title: "Configuration Error",
      message: "There's a problem with your TTS settings.",
      suggestion: "Reset your preferences or check the configuration.",
      recoverySteps: [
        "Open Raycast preferences",
        "Reset TTS settings to defaults",
        "Reconfigure your preferred voice settings",
      ],
    },
    [UserErrorType.UNKNOWN_ERROR]: {
      type: UserErrorType.UNKNOWN_ERROR,
      title: "Unexpected Error",
      message: "An unexpected error occurred while processing your request.",
      suggestion: "Try again or restart Raycast if the problem persists.",
      recoverySteps: [
        "Try the operation again",
        "Restart Raycast completely",
        "Check the logs for more details",
      ],
    },
  };

  /**
   * Convert a technical error to a user-friendly error
   */
  static createUserError(
    error: Error,
    context?: { component?: string; method?: string; [key: string]: unknown }
  ): UserError {
    logger.error("Creating user error from technical error", {
      component: "TTSErrorHandler",
      method: "createUserError",
      error: error.message,
      errorStack: error.stack,
      context,
    });

    // Determine error type based on error message and context
    const errorType = this.determineErrorType(error, context);
    const userError = this.ERROR_MESSAGES[errorType];

    // Add technical details for debugging
    return {
      ...userError,
      technicalDetails: error.message,
    };
  }

  /**
   * Determine the appropriate error type based on the technical error
   */
  private static determineErrorType(
    error: Error,
    context?: { component?: string; method?: string; [key: string]: unknown }
  ): UserErrorType {
    const message = error.message.toLowerCase();
    const component = context?.component?.toLowerCase() ?? "";

    // Node.js related errors
    if (
      message.includes("node") ||
      message.includes("executable") ||
      message.includes("not found") ||
      component.includes("daemon")
    ) {
      return UserErrorType.NODE_JS_MISSING;
    }

    // Daemon startup errors
    if (
      message.includes("daemon") ||
      message.includes("spawn") ||
      message.includes("startup") ||
      message.includes("timeout")
    ) {
      return UserErrorType.DAEMON_STARTUP_FAILED;
    }

    // Audio device errors
    if (
      message.includes("audio") ||
      message.includes("device") ||
      message.includes("sox") ||
      message.includes("playback")
    ) {
      return UserErrorType.AUDIO_DEVICE_ERROR;
    }

    // Network errors
    if (
      message.includes("network") ||
      message.includes("connection") ||
      message.includes("timeout") ||
      message.includes("unreachable")
    ) {
      return UserErrorType.NETWORK_ERROR;
    }

    // Permission errors
    if (
      message.includes("permission") ||
      message.includes("access") ||
      message.includes("denied") ||
      message.includes("unauthorized")
    ) {
      return UserErrorType.PERMISSION_ERROR;
    }

    // Configuration errors
    if (
      message.includes("config") ||
      message.includes("setting") ||
      message.includes("preference") ||
      message.includes("invalid")
    ) {
      return UserErrorType.CONFIGURATION_ERROR;
    }

    return UserErrorType.UNKNOWN_ERROR;
  }

  /**
   * Log error for debugging purposes
   */
  static logError(
    error: Error,
    context?: { component?: string; method?: string; [key: string]: unknown }
  ): void {
    logger.error("TTS Error occurred", {
      component: context?.component ?? "Unknown",
      method: context?.method ?? "Unknown",
      error: error.message,
      errorStack: error.stack,
      context,
    });
  }

  /**
   * Get recovery suggestions for a specific error type
   */
  static getRecoverySteps(errorType: UserErrorType): string[] {
    return this.ERROR_MESSAGES[errorType].recoverySteps ?? [];
  }

  /**
   * Format error for display in UI
   */
  static formatErrorForDisplay(userError: UserError): {
    title: string;
    message: string;
    suggestion: string;
    details?: string;
  } {
    return {
      title: userError.title,
      message: userError.message,
      suggestion: userError.suggestion,
      details: userError.technicalDetails,
    };
  }
}
