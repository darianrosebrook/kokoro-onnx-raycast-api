import { Toast } from "@raycast/api";

/**
 * TTS request payload for the Kokoro API
 * Matches the FastAPI server's TTSRequest model exactly
 */
export interface TTSRequest {
  text: string; // Required field for the text to synthesize
  voice?: string; // Voice to use (defaults to server default)
  speed?: number; // Speed multiplier (0.25-4.0, defaults to 1.0)
  lang?: string; // Language code (defaults to "en-us")
  stream?: boolean; // Whether to stream the response (defaults to false)
  format?: string; // Audio format: "pcm" or "wav" (defaults to "pcm")
}

/**
 * Available voice options for Kokoro TTS, organized by language.
 */
export type VoiceOption =
  // American English
  | "af_heart"
  | "af_alloy"
  | "af_aoede"
  | "af_bella"
  | "af_jessica"
  | "af_kore"
  | "af_nicole"
  | "af_nova"
  | "af_river"
  | "af_sarah"
  | "af_sky"
  | "am_adam"
  | "am_echo"
  | "am_eric"
  | "am_fenrir"
  | "am_liam"
  | "am_michael"
  | "am_onyx"
  | "am_puck"
  | "am_santa"
  // British English
  | "bf_alice"
  | "bf_emma"
  | "bf_isabella"
  | "bf_lily"
  | "bm_daniel"
  | "bm_fable"
  | "bm_george"
  | "bm_lewis"
  // Japanese
  | "jf_alpha"
  | "jf_gongitsune"
  | "jf_nezumi"
  | "jf_tebukuro"
  | "jm_kumo"
  // Mandarin Chinese
  | "zf_xiaobei"
  | "zf_xiaoni"
  | "zf_xiaoxiao"
  | "zf_xiaoyi"
  | "zm_yunjian"
  | "zm_yunxi"
  | "zm_yunxia"
  | "zm_yunyang"
  // Spanish
  | "ef_dora"
  | "em_alex"
  | "em_santa"
  // French
  | "ff_siwis"
  // Hindi
  | "hf_alpha"
  | "hf_beta"
  | "hm_omega"
  | "hm_psi"
  // Italian
  | "if_sara"
  | "im_nicola"
  // Brazilian Portuguese
  | "pf_dora"
  | "pm_alex"
  | "pm_santa";

/**
 * TTS configuration settings
 */
export interface TTSConfig {
  voice: VoiceOption;
  speed: number;
  serverUrl: string;
  useStreaming: boolean;
  sentencePauses?: boolean;
  maxSentenceLength?: number;
}

/**
 * Word tracking for highlighting during playback, currently not implemented.
 */
export interface WordTracker {
  word: string;
  startTime: number;
  endTime: number;
  isActive: boolean;
}

/**
 * Defines the shape of the status update object passed to the onStatusUpdate callback.
 */
export type StatusUpdate = {
  message: string;
  style?: Toast.Style;
  isPlaying: boolean;
  isPaused: boolean;
  primaryAction?: Toast.ActionOptions;
  secondaryAction?: Toast.ActionOptions;
};
