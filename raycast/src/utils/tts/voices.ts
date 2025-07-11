import type { VoiceOption } from "../validation/tts-types";

/**
 * Voice configuration with traits and metadata
 */
export interface VoiceConfig {
  name: VoiceOption;
  traits: string;
  targetQuality: string;
  trainingDuration: string;
  overallGrade: string;
  sha256: string;
}

/**
 * Complete voice catalog with all available Kokoro voices and their characteristics
 * Note: British voices (bf_*, bm_*) are not included in this catalog
 */
export const VOICES: Record<VoiceOption, VoiceConfig> = {
  af_heart: {
    name: "af_heart",
    traits: "🚺❤️",
    targetQuality: "A",
    trainingDuration: "",
    overallGrade: "",
    sha256: "0ab5709b",
  },
  af_alloy: {
    name: "af_alloy",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "6d877149",
  },
  af_aoede: {
    name: "af_aoede",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "c03bd1a4",
  },
  af_bella: {
    name: "af_bella",
    traits: "🚺🔥",
    targetQuality: "A",
    trainingDuration: "HH hours",
    overallGrade: "A-",
    sha256: "8cb64e02",
  },
  af_jessica: {
    name: "af_jessica",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "cdfdccb8",
  },
  af_kore: {
    name: "af_kore",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "8bfbc512",
  },
  af_nicole: {
    name: "af_nicole",
    traits: "🚺🎧",
    targetQuality: "B",
    trainingDuration: "HH hours",
    overallGrade: "B-",
    sha256: "c5561808",
  },
  af_nova: {
    name: "af_nova",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "e0233676",
  },
  af_river: {
    name: "af_river",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "e149459b",
  },
  af_sarah: {
    name: "af_sarah",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "49bd364e",
  },
  af_sky: {
    name: "af_sky",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "M minutes 🤏",
    overallGrade: "C-",
    sha256: "c799548a",
  },
  am_adam: {
    name: "am_adam",
    traits: "🚹",
    targetQuality: "D",
    trainingDuration: "H hours",
    overallGrade: "F+",
    sha256: "ced7e284",
  },
  am_echo: {
    name: "am_echo",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "8bcfdc85",
  },
  am_eric: {
    name: "am_eric",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "ada66f0e",
  },
  am_fenrir: {
    name: "am_fenrir",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "98e507ec",
  },
  am_liam: {
    name: "am_liam",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "c8255075",
  },
  am_michael: {
    name: "am_michael",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "9a443b79",
  },
  am_onyx: {
    name: "am_onyx",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "e8452be1",
  },
  am_puck: {
    name: "am_puck",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "dd1d8973",
  },
  am_santa: {
    name: "am_santa",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "M minutes 🤏",
    overallGrade: "D-",
    sha256: "7f2f7582",
  },
  // British English
  bf_alice: {
    name: "bf_alice",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "d292651b",
  },
  bf_emma: {
    name: "bf_emma",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "HH hours",
    overallGrade: "B-",
    sha256: "d0a423de",
  },
  bf_isabella: {
    name: "bf_isabella",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "cdd4c370",
  },
  bf_lily: {
    name: "bf_lily",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "6e09c2e4",
  },
  bm_daniel: {
    name: "bm_daniel",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "fc3fce4e",
  },
  bm_fable: {
    name: "bm_fable",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "d44935f3",
  },
  bm_george: {
    name: "bm_george",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "f1bc8122",
  },
  bm_lewis: {
    name: "bm_lewis",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "H hours",
    overallGrade: "D+",
    sha256: "b5204750",
  },
  // Japanese
  jf_alpha: {
    name: "jf_alpha",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "H hours",
    overallGrade: "C+",
    sha256: "1bf4c9dc",
  },
  jf_gongitsune: {
    name: "jf_gongitsune",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "1b171917",
  },
  jf_nezumi: {
    name: "jf_nezumi",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "M minutes 🤏",
    overallGrade: "C-",
    sha256: "d83f007a",
  },
  jf_tebukuro: {
    name: "jf_tebukuro",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "0d691790",
  },
  jm_kumo: {
    name: "jm_kumo",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "M minutes 🤏",
    overallGrade: "C-",
    sha256: "98340afd",
  },
  // Mandarin Chinese
  zf_xiaobei: {
    name: "zf_xiaobei",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "9b76be63",
  },
  zf_xiaoni: {
    name: "zf_xiaoni",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "95b49f16",
  },
  zf_xiaoxiao: {
    name: "zf_xiaoxiao",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "cfaf6f2d",
  },
  zf_xiaoyi: {
    name: "zf_xiaoyi",
    traits: "🚺",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "b5235dba",
  },
  zm_yunjian: {
    name: "zm_yunjian",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "76cbf8ba",
  },
  zm_yunxi: {
    name: "zm_yunxi",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "dbe6e1ce",
  },
  zm_yunxia: {
    name: "zm_yunxia",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "bb2b03b0",
  },
  zm_yunyang: {
    name: "zm_yunyang",
    traits: "🚹",
    targetQuality: "C",
    trainingDuration: "MM minutes",
    overallGrade: "D",
    sha256: "5238ac22",
  },
  // Spanish
  ef_dora: {
    name: "ef_dora",
    traits: "🚺",
    targetQuality: "",
    trainingDuration: "",
    overallGrade: "",
    sha256: "d9d69b0f",
  },
  em_alex: {
    name: "em_alex",
    traits: "🚹",
    targetQuality: "",
    trainingDuration: "",
    overallGrade: "",
    sha256: "5eac53f7",
  },
  em_santa: {
    name: "em_santa",
    traits: "🚹",
    targetQuality: "",
    trainingDuration: "",
    overallGrade: "",
    sha256: "aa8620cb",
  },
  // French
  ff_siwis: {
    name: "ff_siwis",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "<11 hours",
    overallGrade: "B-",
    sha256: "8073bf2d",
  },
  // Hindi
  hf_alpha: {
    name: "hf_alpha",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "06906fe0",
  },
  hf_beta: {
    name: "hf_beta",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "63c0a1a6",
  },
  hm_omega: {
    name: "hm_omega",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "b55f02a8",
  },
  hm_psi: {
    name: "hm_psi",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "2f0f055c",
  },
  // Italian
  if_sara: {
    name: "if_sara",
    traits: "🚺",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "6c0b253b",
  },
  im_nicola: {
    name: "im_nicola",
    traits: "🚹",
    targetQuality: "B",
    trainingDuration: "MM minutes",
    overallGrade: "C",
    sha256: "234ed066",
  },
  // Brazilian Portuguese
  pf_dora: {
    name: "pf_dora",
    traits: "🚺",
    targetQuality: "",
    trainingDuration: "",
    overallGrade: "",
    sha256: "07e4ff98",
  },
  pm_alex: {
    name: "pm_alex",
    traits: "🚹",
    targetQuality: "",
    trainingDuration: "",
    overallGrade: "",
    sha256: "cf0ba8c5",
  },
  pm_santa: {
    name: "pm_santa",
    traits: "🚹",
    targetQuality: "",
    trainingDuration: "",
    overallGrade: "",
    sha256: "d4210316",
  },
};

/**
 * Get voice configuration by name
 * @param voice - Voice option name
 * @returns Voice configuration or undefined if not found
 */
export const getVoiceConfig = (voice: VoiceOption): VoiceConfig | undefined => {
  return VOICES[voice as VoiceOption];
};

/**
 * Get all female voices (af_* prefix)
 * @returns Array of female voice configurations
 */
export const getFemaleVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("af_"));
};

/**
 * Get all male voices (am_* prefix)
 * @returns Array of male voice configurations
 */
export const getMaleVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("am_"));
};

/**
 * Get voices by target quality grade
 * @param grade - Target quality grade (A, B, C, D)
 * @returns Array of voice configurations matching the grade
 */
export const getVoicesByQuality = (grade: string): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.targetQuality === grade);
};

/**
 * Get voices by overall grade
 * @param grade - Overall grade (A-, B-, C+, C, C-, D, F+, etc.)
 * @returns Array of voice configurations matching the grade
 */
export const getVoicesByOverallGrade = (grade: string): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.overallGrade === grade);
};

/**
 * Get voices by language prefix
 * @param prefix - Language prefix (af, am, bf, bm, jf, jm, zf, zm, ef, em, ff, hf, hm, if, im, pf, pm)
 * @returns Array of voice configurations matching the language prefix
 */
export const getVoicesByLanguage = (prefix: string): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith(prefix));
};

/**
 * Get American English voices
 * @returns Array of American English voice configurations
 */
export const getAmericanEnglishVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("a"));
};

/**
 * Get British English voices
 * @returns Array of British English voice configurations
 */
export const getBritishEnglishVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("b"));
};

/**
 * Get Japanese voices
 * @returns Array of Japanese voice configurations
 */
export const getJapaneseVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("j"));
};

/**
 * Get Mandarin Chinese voices
 * @returns Array of Mandarin Chinese voice configurations
 */
export const getMandarinChineseVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("z"));
};

/**
 * Get Spanish voices
 * @returns Array of Spanish voice configurations
 */
export const getSpanishVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("e"));
};

/**
 * Get French voices
 * @returns Array of French voice configurations
 */
export const getFrenchVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("f"));
};

/**
 * Get Hindi voices
 * @returns Array of Hindi voice configurations
 */
export const getHindiVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("h"));
};

/**
 * Get Italian voices
 * @returns Array of Italian voice configurations
 */
export const getItalianVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("i"));
};

/**
 * Get Brazilian Portuguese voices
 * @returns Array of Brazilian Portuguese voice configurations
 */
export const getBrazilianPortugueseVoices = (): VoiceConfig[] => {
  return Object.values(VOICES).filter((voice) => voice.name.startsWith("p"));
};
