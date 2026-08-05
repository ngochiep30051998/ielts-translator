import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Options } from './Options';
import { DEFAULT_SETTINGS, loadSettings } from '../shared/settings';

describe('Options', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    await chrome.storage.local.clear();
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, data: { status: 'UP', dbConnected: true, geminiConfigured: true },
    });
  });

  it('hiện giá trị mặc định khi chưa lưu gì', async () => {
    render(<Options />);

    expect(await screen.findByLabelText(/Địa chỉ backend/i))
      .toHaveValue(DEFAULT_SETTINGS.backendUrl);
  });

  it('lưu backend URL mới vào storage', async () => {
    render(<Options />);
    const input = await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.clear(input);
    await userEvent.type(input, 'http://127.0.0.1:9090');
    await userEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(async () =>
      expect((await loadSettings()).backendUrl).toBe('http://127.0.0.1:9090'));
  });

  it('đổi được chế độ kích hoạt sang phím tắt', async () => {
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByLabelText(/Chỉ khi bấm Alt\+T/i));
    await userEvent.click(screen.getByRole('button', { name: /Lưu/i }));

    await waitFor(async () => expect((await loadSettings()).triggerMode).toBe('hotkey'));
  });

  it('nút kiểm tra kết nối báo thành công', async () => {
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByRole('button', { name: /Kiểm tra kết nối/i }));

    expect(await screen.findByText(/Backend đang chạy/i)).toBeInTheDocument();
  });

  it('nút kiểm tra kết nối báo lỗi khi backend chết', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: false, error: { code: 'BACKEND_DOWN', message: 'Backend chưa chạy', retryable: true },
    });
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByRole('button', { name: /Kiểm tra kết nối/i }));

    expect(await screen.findByText('Backend chưa chạy')).toBeInTheDocument();
  });

  it('cảnh báo khi backend chạy nhưng chưa cấu hình Gemini API key', async () => {
    (chrome.runtime.sendMessage as ReturnType<typeof vi.fn>).mockResolvedValue({
      ok: true, data: { status: 'UP', dbConnected: true, geminiConfigured: false },
    });
    render(<Options />);
    await screen.findByLabelText(/Địa chỉ backend/i);

    await userEvent.click(screen.getByRole('button', { name: /Kiểm tra kết nối/i }));

    expect(await screen.findByText(/chưa cấu hình GEMINI_API_KEY/i)).toBeInTheDocument();
  });
});
