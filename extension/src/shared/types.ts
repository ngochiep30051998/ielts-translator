export type Direction = 'EN_VI' | 'VI_EN';
export type Mode = 'WORD' | 'SENTENCE';

export interface EnViWordPayload {
  term: string;
  lemma: string;
  pos: string;
  ipa: string;
  meaning_vi: string;
  definition_en: string;
  cefr: string;
  band_level: string;
  register: string;
  collocations: string[];
  examples: { en: string; vi: string }[];
  synonyms: { term: string; band: string }[];
}

export interface EnViSentencePayload {
  translation_vi: string;
  key_vocab: { term: string; meaning_vi: string; band_level: string }[];
  structure_note: string;
}

export interface ViEnWordPayload {
  best_en: string;
  alternatives: { term: string; band: string; register: string; when_to_use: string }[];
  collocations: string[];
  examples: string[];
}

export interface ViEnSentencePayload {
  band65_version: string;
  why_notes: string[];
  key_phrases: string[];
  avoid: { phrase: string; reason: string }[];
}

export type TranslatePayload =
  | EnViWordPayload
  | EnViSentencePayload
  | ViEnWordPayload
  | ViEnSentencePayload;

export interface TranslateResult {
  direction: Direction;
  mode: Mode;
  cached: boolean;
  payload: TranslatePayload;
  /** Text người dùng đã bôi đen — backend không trả, client tự gắn vào. */
  sourceText: string;
  sourceUrl?: string;
  sourceSentence?: string;
}

export interface ApiError {
  code: string;
  message: string;
  retryable: boolean;
}

export interface VocabEntryDto {
  id: number;
  term: string;
  lemma: string | null;
  lang: string;
  pos: string;
  ipa: string | null;
  meaningVi: string;
  definitionEn: string | null;
  cefr: string | null;
  bandLevel: string | null;
  tags: string[];
  sourceUrl: string | null;
  sourceSentence: string | null;
  collocations: unknown;
  examples: unknown;
  createdAt: string;
}

export interface PageResponse<T> {
  content: T[];
  totalElements: number;
  totalPages: number;
  number: number;
}

export interface SaveVocabResponse {
  id: number;
  alreadyExists: boolean;
}
