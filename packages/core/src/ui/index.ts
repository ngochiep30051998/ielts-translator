/**
 * Màn hình dùng chung. Side panel của extension và web app render CÙNG những component này.
 *
 * Chúng không biết mình đang chạy ở đâu: mọi lượt gọi backend đi qua `sendToBackground`,
 * và surface quyết định `sendToBackground` nối vào đâu bằng `setTransport`.
 */

export { App } from './App';
export { LoginScreen } from './LoginScreen';
export { TranslateTab } from './TranslateTab';
export { VocabTab } from './VocabTab';
export { ReviewTab } from './ReviewTab';
export { QuizTab } from './QuizTab';
export { StatsTab } from './StatsTab';
export { StatRow, DailyBars, Heatmap, Accuracy } from './StatsCharts';
