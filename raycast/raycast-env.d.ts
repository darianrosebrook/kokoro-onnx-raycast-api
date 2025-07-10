/// <reference types="@raycast/api">

/*   
 * This file is auto-generated from the extension's manifest.
 * Do not modify manually. Instead, update the `package.json` file.
 *    */

/* eslint-disable @typescript-eslint/ban-types */

type ExtensionPreferences = {
  /** Voice - Select the voice for text-to-speech */
  "voice": "bm_fable" | "af_bella" | "af_heart" | "af_nicole" | "am_michael" | "am_fenrir" | "am_puck" | "af_aoede" | "af_kore" | "af_sarah",
  /** Speech Speed - Adjust the speech speed (0.5 - 2.0) */
  "speed": string,
  /** Server URL - Kokoro TTS server URL */
  "serverUrl": string,
  /** Use Streaming - Enable streaming mode for real-time audio processing */
  "useStreaming": boolean,
  /** Sentence Pauses - Add natural pauses between sentences for better speech flow */
  "sentencePauses": boolean,
  /** Max Sentence Length - Maximum characters per sentence (0 = no limit) */
  "maxSentenceLength": string
}

/** Preferences accessible in all the extension's commands */
declare type Preferences = ExtensionPreferences

declare namespace Preferences {
  /** Preferences accessible in the `speak-text` command */
  export type SpeakText = ExtensionPreferences & {}
  /** Preferences accessible in the `speak-selection` command */
  export type SpeakSelection = ExtensionPreferences & {}
}

declare namespace Arguments {
  /** Arguments passed to the `speak-text` command */
  export type SpeakText = {}
  /** Arguments passed to the `speak-selection` command */
  export type SpeakSelection = {}
}

