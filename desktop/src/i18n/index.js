// OneASR Localization Dictionary (Strict i18n standard)
import { ref } from 'vue';

const currentLocale = ref(localStorage.getItem('oneasr_locale') || 'zh-CN');

export const translations = {
  'zh-CN': {
    // App & Navigation
    appName: 'OneASR',
    appSubtitle: '私有高精度语音转录引擎',
    navDictate: '实时听写',
    navFiles: '文件转录',
    navModels: '模型管理',
    navSettings: '设置',
    historyTitle: '转录历史',
    historyClear: '清空全部',
    historyEmpty: '暂无历史记录',
    historyCopied: '已复制到剪贴板',
    statusOnline: '引擎在线',
    statusOffline: '引擎未就绪',
    statusStarting: '正在连接...',
    
    // Dictate Tab
    dictateTitle: '麦克风实时听写',
    dictateSubtitle: '点击开始说话，毫秒级流式文本与延迟检测',
    selectModel: '推理模型',
    selectMicrophone: '收音设备',
    micDefault: '系统默认麦克风',
    micSearching: '正在检测麦克风...',
    micPermissionDenied: '麦克风权限被拒绝，请在系统设置中允许 OneASR 访问麦克风',
    btnStartRecord: '点击开始录音',
    btnStopRecord: '点击停止录音',
    recordingStatus: '正在收音中...',
    idleStatus: '准备就绪，点击麦克风开始',
    copyText: '复制文本',
    clearText: '清空内容',
    latencyMetric: '首字延迟',
    rtfMetric: '实时因数 (RTF)',
    durationMetric: '录音时长',
    previewPlaceholder: '按住或点击下方麦克风开始说话，识别结果将在此实时呈现...',
    
    // Files Tab
    filesTitle: '音视频文件转录',
    filesSubtitle: '拖入长音频或视频文件，快速生成带时间戳字幕与分段文本',
    dropzoneTitle: '拖入音视频文件，或点击选择',
    dropzoneHint: '支持 MP3, WAV, M4A, MP4, MKV, FLAC, OGG, WEBM 等格式',
    fileSelected: '已选文件',
    fileSize: '文件大小',
    btnStartTranscribe: '开始转写',
    btnCancelTranscribe: '取消任务',
    transcribingStatus: '正在转录中...',
    exportSrt: '导出 SRT',
    exportVtt: '导出 VTT',
    exportTxt: '导出 TXT',
    subtitleEmpty: '暂无转写字幕，拖入音频文件即可开始',
    stageAudioDecode: '音频流解码与重采样...',
    stageInference: '神经网络分块推理中...',
    stageTimestamps: '对齐标点与精确时间戳...',
    
    // Models Tab
    modelsTitle: '语音模型管理',
    modelsSubtitle: '查看并管理本地已下载与可用的 ASR 神经网络模型',
    modelActiveBadge: '当前激活',
    modelDownloadedBadge: '已就绪',
    modelRemoteBadge: '可一键下载',
    modelParams: '参数量',
    modelVram: '建议显存',
    modelLangs: '支持语言',
    btnLoadModel: '载入模型',
    btnUnloadModel: '释放显存',
    btnDownloadModel: '一键下载',
    downloadingProgress: '正在下载...',
    modelDownloadSuccess: '模型下载成功',
    modelLoadSuccess: '模型已成功载入内存',
    modelUnloadSuccess: '模型已释放',
    
    // Settings Tab
    settingsTitle: '系统设置',
    settingsSubtitle: '配置界面外观、多语言、模型路径与服务策略',
    sectionGeneral: '通用设置',
    generalTheme: '外观主题',
    generalThemeDesc: '深色、浅色或随系统自动切换',
    themeDark: '深色模式',
    themeLight: '浅色模式',
    themeAuto: '跟随系统',
    generalLanguage: '显示语言',
    generalLanguageDesc: '系统多语言本地化支持',
    langZh: '简体中文',
    langEn: 'English',
    btnConfirm: '完成',
    btnClose: '关闭',
    sectionStorage: '存储与路径',
    modelDirLabel: '模型存放目录',
    btnOpenDir: '打开文件夹',
    btnChangeDir: '更改目录',
    sectionNetwork: '网络与接口',
    lanAccessLabel: '局域网访问 (LAN)',
    lanLocalOnly: '仅允许本机 (127.0.0.1)',
    lanExposed: '允许局域网设备访问 (0.0.0.0)',
    portLabel: '服务端口',
    sectionStrategy: '运行策略',
    keepAliveLabel: '闲置自动卸载超时 (Keep-Alive)',
    keepAlive1Min: '1 分钟',
    keepAlive5Min: '5 分钟 (推荐)',
    keepAlive15Min: '15 分钟',
    keepAlive30Min: '30 分钟',
    keepAliveNever: '从不自动卸载',
    sectionDiagnostics: '硬件与诊断',
    hardwareChip: '计算加速平台',
    memoryUsage: '进程内存占用',
    swaggerDocs: 'Swagger API 文档',
    btnViewLogs: '查看运行日志',
    sectionLanguage: '界面多语言',
    languageLabel: '显示语言',
    
    // General
    success: '操作成功',
    error: '发生错误',
    close: '关闭'
  },
  'en-US': {
    // App & Navigation
    appName: 'OneASR',
    appSubtitle: 'Private High-Precision ASR Engine',
    navDictate: 'Dictate',
    navFiles: 'Files',
    navModels: 'Models',
    navSettings: 'Settings',
    historyTitle: 'Transcription History',
    historyClear: 'Clear All',
    historyEmpty: 'No history records yet',
    historyCopied: 'Copied to clipboard',
    statusOnline: 'Engine Online',
    statusOffline: 'Engine Offline',
    statusStarting: 'Connecting...',
    
    // Dictate Tab
    dictateTitle: 'Real-time Microphone Dictation',
    dictateSubtitle: 'Click to speak with low-latency streaming text and RTF telemetry',
    selectModel: 'Model',
    selectMicrophone: 'Microphone',
    micDefault: 'System Default Microphone',
    micSearching: 'Detecting audio devices...',
    micPermissionDenied: 'Microphone permission denied. Please allow OneASR in System Settings.',
    btnStartRecord: 'Start Recording',
    btnStopRecord: 'Stop Recording',
    recordingStatus: 'Recording in progress...',
    idleStatus: 'Ready. Click microphone to start',
    copyText: 'Copy Text',
    clearText: 'Clear',
    latencyMetric: 'First Token Latency',
    rtfMetric: 'Real-Time Factor (RTF)',
    durationMetric: 'Duration',
    previewPlaceholder: 'Click the microphone below to start speaking. Results will appear here in real time...',
    
    // Files Tab
    filesTitle: 'Audio & Video Transcription',
    filesSubtitle: 'Drag and drop audio or video files to generate timestamped subtitles and segments',
    dropzoneTitle: 'Drop audio/video file here, or click to browse',
    dropzoneHint: 'Supports MP3, WAV, M4A, MP4, MKV, FLAC, OGG, WEBM formats',
    fileSelected: 'Selected File',
    fileSize: 'File Size',
    btnStartTranscribe: 'Start Transcribing',
    btnCancelTranscribe: 'Cancel Task',
    transcribingStatus: 'Transcribing in progress...',
    exportSrt: 'Export SRT',
    exportVtt: 'Export VTT',
    exportTxt: 'Export TXT',
    subtitleEmpty: 'No subtitles yet. Drop an audio file to begin.',
    stageAudioDecode: 'Decoding and resampling audio...',
    stageInference: 'Neural network chunk inference...',
    stageTimestamps: 'Aligning punctuation and timestamps...',
    
    // Models Tab
    modelsTitle: 'ASR Model Manager',
    modelsSubtitle: 'Inspect and manage local downloaded and available neural network models',
    modelActiveBadge: 'Active',
    modelDownloadedBadge: 'Ready',
    modelRemoteBadge: 'Available',
    modelParams: 'Parameters',
    modelVram: 'Recommended VRAM',
    modelLangs: 'Languages',
    btnLoadModel: 'Load Model',
    btnUnloadModel: 'Unload Model',
    btnDownloadModel: 'Download',
    downloadingProgress: 'Downloading...',
    modelDownloadSuccess: 'Model downloaded successfully',
    modelLoadSuccess: 'Model loaded into memory',
    modelUnloadSuccess: 'Model unloaded',
    
    // Settings Tab
    settingsTitle: 'Settings',
    settingsSubtitle: 'Configure appearance, language, models directory, and service strategy',
    sectionGeneral: 'General Settings',
    generalTheme: 'Appearance Theme',
    generalThemeDesc: 'Light, dark, or follow system theme',
    themeDark: 'Dark Mode',
    themeLight: 'Light Mode',
    themeAuto: 'System Default',
    generalLanguage: 'Display Language',
    generalLanguageDesc: 'Multi-language display support',
    langZh: '简体中文 (Simplified Chinese)',
    langEn: 'English',
    btnConfirm: 'Done',
    btnClose: 'Close',
    sectionStorage: 'Storage & Paths',
    modelDirLabel: 'Models Directory',
    btnOpenDir: 'Open Directory',
    btnChangeDir: 'Change Directory',
    sectionNetwork: 'Network & API',
    lanAccessLabel: 'Local Network Access (LAN)',
    lanLocalOnly: 'Localhost Only (127.0.0.1)',
    lanExposed: 'Exposed to LAN (0.0.0.0)',
    portLabel: 'Port',
    sectionStrategy: 'Lifecycle Strategy',
    keepAliveLabel: 'Idle Auto-Unload Timeout (Keep-Alive)',
    keepAlive1Min: '1 Minute',
    keepAlive5Min: '5 Minutes (Recommended)',
    keepAlive15Min: '15 Minutes',
    keepAlive30Min: '30 Minutes',
    keepAliveNever: 'Never auto-unload',
    sectionDiagnostics: 'Hardware & Diagnosis',
    hardwareChip: 'Compute Acceleration',
    memoryUsage: 'Process Memory',
    swaggerDocs: 'Swagger API Docs',
    btnViewLogs: 'View Service Logs',
    sectionLanguage: 'Language',
    languageLabel: 'Display Language',
    
    // General
    success: 'Success',
    error: 'Error',
    close: 'Close'
  }
};

export function useI18n() {
  function t(key) {
    const localeDict = translations[currentLocale.value] || translations['zh-CN'];
    return localeDict[key] || translations['en-US'][key] || key;
  }

  function setLocale(newLocale) {
    if (translations[newLocale]) {
      currentLocale.value = newLocale;
      localStorage.setItem('oneasr_locale', newLocale);
    }
  }

  return {
    locale: currentLocale,
    t,
    setLocale
  };
}
