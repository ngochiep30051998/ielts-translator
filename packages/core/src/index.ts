/**
 * Bề mặt công khai của `@ielts/core`.
 *
 * Mọi thứ ở đây phải chạy được ở CẢ HAI surface. Thứ gì chỉ đúng cho một bên thì thuộc về
 * `apps/*`, không thuộc về đây — và nếu nó cần một mảnh môi trường, mảnh đó là một port
 * trong `ports.ts`.
 */

export * from './types';
export * from './ports';
export * from './messages';
export * from './operations';
export * from './api-client';
export { setTransport, currentTransport } from './transport';
export {
  resetSurfaceCapabilities, setSurfaceCapabilities, surfaceCapabilities,
  type SurfaceCapabilities,
} from './surface';
export {
  FALLBACK_SETTINGS, loadSettings, normaliseSettings, resetSettingsProvider,
  setSettingsProvider, type Settings, type TriggerMode,
} from './settings';

export * from './mcq';
export * from './heatmap';
export * from './vocab-progress';
export * from './pagination';
export * from './summary';
export * from './today';
export * from './text';
export * from './speech';
export * from './theme';
