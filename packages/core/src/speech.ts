/**
 * Phát âm qua Web Speech API. Dùng chung cho bubble (content script) và tab Ôn tập,
 * để hai chỗ không trôi khỏi nhau khi đổi cách chọn giọng.
 *
 * Không tìm được giọng nào khớp thì để nguyên giọng mặc định của hệ thống —
 * im lặng không đọc gì còn khó hiểu hơn là đọc bằng giọng khác.
 */
export function speak(text: string, voiceName: string | null): void {
  const utterance = new SpeechSynthesisUtterance(text);
  const voice = speechSynthesis.getVoices()
    .find((v) => (voiceName ? v.name === voiceName : v.lang.startsWith('en')));
  if (voice) utterance.voice = voice;
  speechSynthesis.speak(utterance);
}
