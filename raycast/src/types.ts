import { Toast as _Toast } from "@raycast/api";
import type {
  TTSRequestParams,
  VoiceOption,
  TTSProcessorConfig,
  StatusUpdate,
} from "./utils/validation/tts-types";

export type { TTSRequestParams, VoiceOption, TTSProcessorConfig, StatusUpdate };

/**
 * Word tracking for highlighting during playback, currently not implemented.
 */
export interface WordTracker {
  word: string;
  startTime: number;
  endTime: number;
  isActive: boolean;
}
