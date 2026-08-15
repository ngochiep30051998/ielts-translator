import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { setSurfaceCapabilities } from '../surface';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import { transportSend } from '../../vitest.setup';

/**
 * Chỉ dẫn phải khớp với thứ surface đó LÀM ĐƯỢC.
 *
 * Lỗi này chỉ lộ ra khi chạy web thật: 5 tab dùng chung nên câu "Bôi đen text trên trang" —
 * đúng cho side panel của extension — cũng hiện luôn trên web, nơi không có trang nào của
 * người khác để bôi đen và không có bubble nào để lưu từ. Chỉ dẫn sai còn tệ hơn không có:
 * nó bảo người dùng làm một việc bất khả thi rồi để họ tự nghi ngờ mình.
 *
 * Không test nào bắt được nó, vì cả hai câu đều là chuỗi hợp lệ và cả hai surface đều render
 * ra được. Đây là test bù cho khoảng trống đó.
 */
describe('chỉ dẫn đổi theo khả năng của surface', () => {
  it('extension: mời bôi đen text trên trang', () => {
    setSurfaceCapabilities({ selectionCapture: true });

    render(<TranslateTab draft="" onDraftChange={() => {}} result={null} onResult={() => {}} loaded />);

    expect(screen.getByText(/Bôi đen text trên trang/)).toBeInTheDocument();
  });

  it('web: KHÔNG nhắc bôi đen — ở đó không có trang nào để bôi', () => {
    setSurfaceCapabilities({ selectionCapture: false });

    render(<TranslateTab draft="" onDraftChange={() => {}} result={null} onResult={() => {}} loaded />);

    expect(screen.queryByText(/Bôi đen/)).not.toBeInTheDocument();
    expect(screen.getByText(/Nhập hoặc dán text vào ô trên/)).toBeInTheDocument();
  });

  it('sổ từ rỗng: extension chỉ tới bubble, web chỉ tới tab Dịch', async () => {
    transportSend.mockImplementation(async (request: { type: string }) => {
      if (request.type === 'GET_VOCAB_TAGS') {
        return { ok: true, data: { total: 0, untagged: 0, tags: [] } };
      }
      return { ok: true, data: { content: [], totalElements: 0, totalPages: 0, number: 0 } };
    });

    setSurfaceCapabilities({ selectionCapture: true });
    const { unmount } = render(<VocabTab />);
    expect(await screen.findByText(/từ đầu tiên từ bubble dịch/)).toBeInTheDocument();
    unmount();

    setSurfaceCapabilities({ selectionCapture: false });
    render(<VocabTab />);
    expect(await screen.findByText(/Dịch một từ ở tab Dịch/)).toBeInTheDocument();
  });
});
