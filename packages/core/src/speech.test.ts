import { beforeEach, describe, expect, it, vi } from 'vitest';
import { speak } from './speech';

const enVoice = { name: 'Samantha', lang: 'en-US' };
const viVoice = { name: 'Linh', lang: 'vi-VN' };

/** Utterance vừa gửi cho speechSynthesis.speak — nơi duy nhất thấy được giọng đã chọn. */
function lastUtterance(): { text: string; voice: unknown } {
  return vi.mocked(speechSynthesis.speak).mock.calls[0][0] as unknown as {
    text: string;
    voice: unknown;
  };
}

describe('speak', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'SpeechSynthesisUtterance',
      class {
        voice: unknown = null;
        constructor(public text: string) {}
      },
    );
    vi.stubGlobal('speechSynthesis', {
      getVoices: () => [viVoice, enVoice],
      speak: vi.fn(),
    });
  });

  it('không chỉ định giọng thì chọn giọng tiếng Anh đầu tiên', () => {
    speak('mitigate', null);

    expect(lastUtterance().voice).toBe(enVoice);
  });

  it('chỉ định giọng theo tên thì dùng đúng giọng đó', () => {
    speak('mitigate', 'Linh');

    expect(lastUtterance().voice).toBe(viVoice);
  });

  it('đọc đúng text được truyền vào', () => {
    speak('resilient', null);

    expect(lastUtterance().text).toBe('resilient');
  });

  it('không có giọng nào khớp thì vẫn đọc bằng giọng mặc định của hệ thống', () => {
    speak('mitigate', 'Không tồn tại');

    expect(lastUtterance().voice).toBeNull();
    expect(speechSynthesis.speak).toHaveBeenCalledTimes(1);
  });
});
