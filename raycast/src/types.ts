import { Toast } from "@raycast/api";
import type {
  TTSRequest,
  VoiceOption,
  TTSConfig,
  StatusUpdate,
} from "./utils/validation/tts-types";

export type { TTSRequest, VoiceOption, TTSConfig, StatusUpdate };

/**
 * Word tracking for highlighting during playback, currently not implemented.
 */
export interface WordTracker {
  word: string;
  startTime: number;
  endTime: number;
  isActive: boolean;
}
