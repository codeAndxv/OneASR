/**
 * Model Localization & Multi-language Specifications Catalog
 *
 * Centralized i18n descriptions, localized default language tags,
 * and standard language option resolvers for ASR models.
 */

export const MODEL_I18N = {
  'sensevoice-small': {
    descEn: 'Ultra-fast end-to-end ASR foundation model (<150ms TTFT) with native support for Chinese, English, Japanese, Korean, Cantonese, and audio event detection.',
    langsEn: 'ZH / EN / JA / KO / YUE'
  },
  'paraformer-zh': {
    descEn: 'Alibaba DAMO industrial-grade Mandarin ASR foundation model with dedicated Silero VAD and punctuation restoration.',
    langsEn: 'Mandarin / English'
  },
  'fun-asr-nano': {
    descEn: 'Alibaba next-gen lightweight Audio-LLM blending SenseVoice acoustic features with Qwen semantics for superior noise resistance.',
    langsEn: 'ZH / EN / JA / KO / YUE'
  },
  'whisper-large-v3-turbo': {
    descEn: 'OpenAI official distilled flagship model optimized with CTranslate2. Extremely high accuracy, 8x faster than vanilla Whisper, ideal for podcasts and long meetings.',
    langsEn: '99+ Global Languages'
  },
  'whisper-small': {
    descEn: 'Lightweight multilingual transcription model. Low VRAM footprint, optimal balance between speed and precision for consumer GPUs.',
    langsEn: '99+ Global Languages'
  },
  'whisper-base': {
    descEn: 'Minimal resource multilingual model. Extremely rapid execution suitable for strictly constrained CPU environments.',
    langsEn: '99+ Global Languages'
  },
  'whisper-tiny': {
    descEn: 'Ultra-fast entry-level multilingual model (~75MB). Sub-second responses on low-power edge devices.',
    langsEn: '99+ Global Languages'
  },
  'whisper-medium': {
    descEn: 'High-accuracy multilingual benchmark model (~1.4GB). Exceptional accuracy for audiovisual podcasts and bilingual subtitles.',
    langsEn: '99+ Global Languages'
  },
  'whisper-large-v1': {
    descEn: 'Whisper flagship 1st gen full-scale global multilingual foundation model.',
    langsEn: '99+ Global Languages'
  },
  'whisper-large-v2': {
    descEn: 'Whisper flagship 2nd gen full-scale global multilingual model with enhanced noise generalization.',
    langsEn: '99+ Global Languages'
  },
  'whisper-large-v3': {
    descEn: 'Whisper flagship 3rd gen highest-accuracy model with 128 Mel bands. Industry gold standard for global multilingual transcription.',
    langsEn: '99+ Global Languages'
  },
  'whisper-tiny-en': {
    descEn: 'Ultra-fast English-specialized micro model (~75MB). Low-latency lightweight transcription.',
    langsEn: 'English (EN)'
  },
  'whisper-base-en': {
    descEn: 'Lightweight English-specialized model (~145MB). Low resource usage and high throughput.',
    langsEn: 'English (EN)'
  },
  'whisper-small-en': {
    descEn: 'High-accuracy English-specialized model (~480MB). Ideal for daily meetings and video subtitling.',
    langsEn: 'English (EN)'
  },
  'whisper-medium-en': {
    descEn: 'Professional production-grade English-specialized model (~1.4GB) for complex long-form audio.',
    langsEn: 'English (EN)'
  },
  'distil-whisper-small-en': {
    descEn: 'Distilled English-specialized model (~330MB). 6x faster inference with minimal accuracy tradeoff.',
    langsEn: 'English (EN)'
  },
  'distil-whisper-medium-en': {
    descEn: 'Distilled advanced English model (~790MB). High throughput with production subtitle quality.',
    langsEn: 'English (EN)'
  },
  'distil-whisper-large-v2': {
    descEn: 'Distilled multilingual foundation model based on Large V2 (~1.5GB). Top choice for high-concurrency throughput.',
    langsEn: '99+ Global Languages'
  },
  'distil-whisper-large-v3': {
    descEn: 'Latest distilled multilingual flagship model based on Large V3 (~1.5GB). Extreme speed and state-of-the-art accuracy.',
    langsEn: '99+ Global Languages'
  },
  'sherpa-onnx-zh-en': {
    descEn: 'High-precision Chinese-English bilingual end-to-end ASR model optimized for Sherpa-ONNX with low memory footprint.',
    langsEn: 'Chinese & English'
  },
  'firered-asr-aed': {
    descEn: 'Xiaohongshu industrial-grade AED speech model specially reinforced for background noise, singing lyrics, and heavy accents.',
    langsEn: 'Bilingual / Noisy Environments'
  },
  'firered-asr-llm': {
    descEn: 'Xiaohongshu flagship 8.3B Encoder-LLM speech model deeply covering 20+ Chinese regional dialects and code-switching.',
    langsEn: 'ZH / EN / 20+ Dialects'
  },
  'qwen-audio-0.6b': {
    descEn: 'Alibaba Qwen compact 0.6B audio foundation model. Minimal footprint and agile response.',
    langsEn: 'General Multilingual'
  },
  'qwen-audio-chat': {
    descEn: 'Alibaba Qwen multimodal audio foundation model capable of rich audio understanding, Q&A, and forced alignment.',
    langsEn: 'ZH / EN / Audio-LLM'
  },
  'xasr': {
    descEn: 'Sherpa-ONNX streaming bilingual ASR engine with zero dependencies and ultra-low CPU overhead. Optimal for real-time conference transcription.',
    langsEn: 'Streaming ZH / EN'
  },
  'xasr-zh-en-160ms': {
    descEn: 'Ultra-low latency 160ms streaming speech dictation for Chinese and English with fast responsive feedback.',
    langsEn: 'Streaming ZH / EN'
  },
  'xasr-zh-en-480ms': {
    descEn: 'Balanced 480ms latency with improved recognition accuracy for Chinese and English.',
    langsEn: 'Streaming ZH / EN'
  },
  'xasr-zh-en-960ms': {
    descEn: 'Extended 960ms context window for higher noise resilience and multi-speaker transcription.',
    langsEn: 'Streaming ZH / EN'
  },
  'xasr-zh-en-1920ms': {
    descEn: 'High-accuracy 1920ms streaming speech recognition approaching offline quality with ~1.9s first token latency.',
    langsEn: 'Streaming ZH / EN'
  },
  'sherpa-onnx-streaming-zipformer-ar_en_id_ja_ru_th_vi_zh-2025-02-10': {
    descEn: 'Multilingual 8-in-1 streaming Zipformer supporting Japanese, Russian, Vietnamese, Arabic, Thai, Indonesian, English, and Chinese.',
    langsEn: 'JA / RU / VI / AR / TH / ID / EN / ZH'
  },
  'sherpa-onnx-streaming-paraformer-trilingual-zh-cantonese-en': {
    descEn: 'Trilingual streaming speech recognition supporting Cantonese (Yue), Mandarin, and English.',
    langsEn: 'Cantonese / ZH / EN'
  },
  'sherpa-onnx-streaming-zipformer-es-kroko-2025-08-06': {
    descEn: 'Low-latency streaming speech recognition dedicated for Spanish.',
    langsEn: 'Spanish (es)'
  },
  'sherpa-onnx-streaming-zipformer-fr-kroko-2025-08-06': {
    descEn: 'Low-latency streaming speech recognition dedicated for French.',
    langsEn: 'French (fr)'
  },
  'sherpa-onnx-streaming-zipformer-de-kroko-2025-08-06': {
    descEn: 'Low-latency streaming speech recognition dedicated for German.',
    langsEn: 'German (de)'
  },
  'sherpa-onnx-streaming-zipformer-small-ru-vosk-int8-2025-08-16': {
    descEn: 'Ultra-lightweight 27MB streaming speech recognition dedicated for Russian.',
    langsEn: 'Russian (ru)'
  },
  'firered-asr': {
    descEn: 'Sherpa-ONNX optimized high-precision bilingual ASR foundation model with low VRAM footprint.',
    langsEn: 'Chinese / English'
  },
  'firered2-aed': {
    descEn: 'Xiaohongshu industrial-grade AED speech model specially reinforced for noisy environments and strong accents.',
    langsEn: 'Chinese / English'
  },
  'firered2-llm': {
    descEn: 'Xiaohongshu flagship 8.3B Encoder-LLM speech model deeply covering 20+ Chinese regional dialects and code-switching.',
    langsEn: 'Chinese / English'
  },
  'qwen3-asr-0.6b': {
    descEn: 'Alibaba Qwen compact 0.6B audio foundation model with minimal resource footprint and agile response.',
    langsEn: 'Chinese / English'
  },
  'qwen-asr': {
    descEn: 'Alibaba Qwen multimodal audio foundation model capable of rich audio understanding, Q&A, and alignment.',
    langsEn: 'Chinese / English'
  }
};

/**
 * Standard bilingual display names for ISO 639-1 / 639-3 language codes
 */
export const LANGUAGE_DICTIONARY = {
  zh: { zh: '中文普通话', en: 'Mandarin Chinese' },
  en: { zh: '英语', en: 'English' },
  yue: { zh: '粤语', en: 'Cantonese' },
  ja: { zh: '日语', en: 'Japanese' },
  ko: { zh: '韩语', en: 'Korean' },
  es: { zh: '西班牙语', en: 'Spanish' },
  fr: { zh: '法语', en: 'French' },
  de: { zh: '德语', en: 'German' },
  ru: { zh: '俄语', en: 'Russian' },
  pt: { zh: '葡萄牙语', en: 'Portuguese' },
  it: { zh: '意大利语', en: 'Italian' },
  ar: { zh: '阿拉伯语', en: 'Arabic' },
  id: { zh: '印度尼西亚语', en: 'Indonesian' },
  th: { zh: '泰语', en: 'Thai' },
  vi: { zh: '越南语', en: 'Vietnamese' },
  nl: { zh: '荷兰语', en: 'Dutch' },
  pl: { zh: '波兰语', en: 'Polish' },
  tr: { zh: '土耳其语', en: 'Turkish' },
  sv: { zh: '瑞典语', en: 'Swedish' },
  hi: { zh: '印地语', en: 'Hindi' },
  uk: { zh: '乌克兰语', en: 'Ukrainian' },
  el: { zh: '希腊语', en: 'Greek' },
  cs: { zh: '捷克语', en: 'Czech' },
  da: { zh: '丹麦语', en: 'Danish' },
  fi: { zh: '芬兰语', en: 'Finnish' },
  he: { zh: '希伯来语', en: 'Hebrew' },
  hu: { zh: '匈牙利语', en: 'Hungarian' },
  no: { zh: '挪威语', en: 'Norwegian' },
  ro: { zh: '罗马尼亚语', en: 'Romanian' },
  ms: { zh: '马来语', en: 'Malay' }
};

/**
 * Curated list of major global languages supported by Whisper
 */
export const WHISPER_MAJOR_LANGS = [
  'zh', 'en', 'yue', 'ja', 'ko', 'es', 'fr', 'de', 'ru', 'pt',
  'it', 'ar', 'nl', 'pl', 'tr', 'sv', 'id', 'vi', 'th', 'hi',
  'uk', 'el', 'cs', 'da', 'fi', 'he', 'hu', 'no', 'ro', 'ms'
];

/**
 * Resolves a model's localized description
 */
export function getModelDesc(model, locale = 'zh-CN') {
  if (locale === 'en-US' && MODEL_I18N[model.id]?.descEn) {
    return MODEL_I18N[model.id].descEn;
  }
  return model.desc;
}

/**
 * Resolves a model's primary display language badge/summary dynamically
 * using slash-separated language names.
 */
/**
 * Gets a clean, localized display name for a given language code.
 * Leverages native Web Intl.DisplayNames for international scalability (zh, en, ja, ko, de, fr, es, ru, etc.).
 */
export function getLocalizedLangName(code, locale = 'zh-CN') {
  const c = String(code).toLowerCase();
  const isZh = String(locale).startsWith('zh');

  if (isZh) {
    if (c === 'zh') return '中文';
    if (c === 'yue') return '粤语';
    if (c === 'en') return '英语';
    if (c === 'id') return '印尼语';
  }

  try {
    const dn = new Intl.DisplayNames([locale], { type: 'language' });
    const name = dn.of(c);
    if (name) {
      if (isZh) {
        return name.replace('普通话', '').trim();
      }
      return name;
    }
  } catch (e) {}

  const meta = LANGUAGE_DICTIONARY[c];
  if (meta) {
    return locale === 'en-US' ? meta.en : meta.zh.replace('普通话', '').trim();
  }
  return c.toUpperCase();
}

/**
 * Formats a language code into a standard localized item: e.g. "中文 (zh)" or "Chinese (zh)"
 */
export function formatLangCode(code, locale = 'zh-CN') {
  const c = String(code).toLowerCase();
  const name = getLocalizedLangName(c, locale);
  return `${name} (${c})`;
}

/**
 * Resolves a model's primary display language badge/summary dynamically
 * using unified slash-separated format:
 * - 1 language: localized name + (code), e.g. "俄语 (ru)"
 * - 1 ~ 4 languages: fully displayed with slash-separation, e.g. "中文 / 英语", "粤语 / 中文 / 英语"
 * - > 4 languages: first 3 languages with concise count suffix, e.g. "日语 / 俄语 / 越南语... (+5)"
 */
export function getModelLangs(model, locale = 'zh-CN') {
  const isEn = locale === 'en-US';
  let langs = (Array.isArray(model.rawLanguages) && model.rawLanguages.length > 0)
    ? model.rawLanguages
    : (Array.isArray(model.languages) && model.languages.length > 0 ? model.languages : []);

  if (langs.length === 0) {
    const mid = (model.id || '').toLowerCase();
    if (mid.includes('xasr-zh-en') || mid.includes('firered') || mid.includes('paraformer') || mid.includes('qwen')) {
      langs = ['zh', 'en'];
    } else if (mid.includes('zipformer-ar_en_id_ja_ru_th_vi_zh')) {
      langs = ['ja', 'ru', 'vi', 'ar', 'th', 'id', 'en', 'zh'];
    } else if (mid.includes('cantonese') || mid.includes('trilingual')) {
      langs = ['yue', 'zh', 'en'];
    } else if (mid.includes('sensevoice') || mid.includes('fun-asr-nano')) {
      langs = ['zh', 'en', 'yue', 'ja', 'ko'];
    } else if (mid.includes('whisper')) {
      langs = WHISPER_MAJOR_LANGS;
    }
  }

  if (langs.length === 0) {
    if (model.langs && !model.langs.includes('流式') && !model.langs.includes('多语言') && !model.langs.includes('专用')) {
      return model.langs;
    }
    return isEn ? 'Multilingual' : '多语言';
  }

  // 1 language
  if (langs.length === 1) {
    return formatLangCode(langs[0], locale);
  }

  // 1 ~ 4 languages: displayed in full with " / "
  if (langs.length <= 4) {
    return langs.map(c => getLocalizedLangName(c, locale)).join(' / ');
  }

  // > 4 languages: first 3 languages + (+remaining)
  const first3 = langs.slice(0, 3).map(c => getLocalizedLangName(c, locale)).join(' / ');
  const remaining = langs.length - 3;
  return `${first3}... (+${remaining})`;
}

/**
 * Returns a comprehensive tooltip string listing all supported languages.
 */
export function getModelLangsFullTooltip(model, locale = 'zh-CN') {
  const isEn = locale === 'en-US';
  let langs = (Array.isArray(model.rawLanguages) && model.rawLanguages.length > 0)
    ? model.rawLanguages
    : (Array.isArray(model.languages) && model.languages.length > 0 ? model.languages : []);

  if (langs.length === 0) {
    const mid = (model.id || '').toLowerCase();
    if (mid.includes('xasr-zh-en') || mid.includes('firered') || mid.includes('paraformer') || mid.includes('qwen')) {
      langs = ['zh', 'en'];
    } else if (mid.includes('zipformer-ar_en_id_ja_ru_th_vi_zh')) {
      langs = ['ja', 'ru', 'vi', 'ar', 'th', 'id', 'en', 'zh'];
    } else if (mid.includes('cantonese') || mid.includes('trilingual')) {
      langs = ['yue', 'zh', 'en'];
    } else if (mid.includes('sensevoice') || mid.includes('fun-asr-nano')) {
      langs = ['zh', 'en', 'yue', 'ja', 'ko'];
    } else if (mid.includes('whisper')) {
      langs = WHISPER_MAJOR_LANGS;
    }
  }

  if (langs.length === 0) {
    return isEn ? 'Multilingual' : '多语言';
  }

  const fullNames = langs.map(c => formatLangCode(c, locale));
  const suffix = isEn ? ` (Total ${langs.length} languages)` : ` (共 ${langs.length} 种支持语言)`;
  return fullNames.join(', ') + suffix;
}

/**
 * Returns the complete array of localized language options for a given model
 */
export function getModelLanguageOptions(model, locale = 'zh-CN') {
  const isEn = locale === 'en-US';
  let langs = (Array.isArray(model.rawLanguages) && model.rawLanguages.length > 0)
    ? model.rawLanguages
    : (Array.isArray(model.languages) && model.languages.length > 0 ? model.languages : []);

  if (langs.length === 0) {
    const mid = (model.id || '').toLowerCase();
    if (mid.includes('xasr-zh-en') || mid.includes('firered') || mid.includes('paraformer') || mid.includes('qwen')) {
      langs = ['zh', 'en'];
    } else if (mid.includes('zipformer-ar_en_id_ja_ru_th_vi_zh')) {
      langs = ['ja', 'ru', 'vi', 'ar', 'th', 'id', 'en', 'zh'];
    } else if (mid.includes('cantonese') || mid.includes('trilingual')) {
      langs = ['yue', 'zh', 'en'];
    } else if (mid.includes('sensevoice') || mid.includes('fun-asr-nano')) {
      langs = ['zh', 'en', 'yue', 'ja', 'ko'];
    } else if (mid.includes('whisper')) {
      const options = WHISPER_MAJOR_LANGS.map(code => formatLangCode(code, locale));
      options.push(isEn ? '90+ More Global Official Languages...' : '90+ 更多全球官方主流语言...');
      return options;
    }
  }

  if (langs.length > 0) {
    if (langs.length > 30) {
      const major = langs.slice(0, 30).map(code => formatLangCode(code, locale));
      const remaining = langs.length - 30;
      if (remaining > 0) {
        major.push(isEn ? `${remaining}+ More Global Official Languages...` : `${remaining}+ 更多全球官方主流语言...`);
      }
      return major;
    }
    return langs.map(code => formatLangCode(code, locale));
  }

  return [];
}
