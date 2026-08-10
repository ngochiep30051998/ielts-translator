import { useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { ApiError, AuthUser } from '../shared/types';

/**
 * Màn đăng nhập. Không tự mở luồng OAuth khi vừa render — `launchWebAuthFlow` bật một cửa
 * sổ, và cửa sổ tự bật khi người dùng chưa bấm gì là hành vi đáng ngờ.
 */
export function LoginScreen({ onSignedIn }: { onSignedIn: (user: AuthUser) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function signIn() {
    if (busy) return;
    setBusy(true);
    setError(null);
    const response = await sendToBackground({ type: 'SIGN_IN' });
    setBusy(false);
    if (response.ok) {
      onSignedIn(response.data);
    } else {
      setError(response.error);
    }
  }

  return (
    <div className="login">
      <h2>IELTS Translator</h2>
      <p className="login-lead">
        Đăng nhập để đồng bộ sổ từ vựng và lịch ôn giữa các thiết bị.
      </p>

      <button type="button" className="login-button" disabled={busy} onClick={() => void signIn()}>
        {busy ? 'Đang mở Google…' : 'Đăng nhập với Google'}
      </button>

      {error && (
        <p className="status bad" role="alert">
          {error.message}{' '}
          {/*
            FORBIDDEN là trạng thái VĨNH VIỄN — email chưa được cấp quyền thì bấm mười lần
            vẫn thế. Mời thử lại ở đây là chỉ sai đường hồi phục.
          */}
          {error.code === 'FORBIDDEN'
            ? 'Nhờ người quản trị thêm email của bạn vào danh sách cho phép.'
            : 'Bấm "Đăng nhập với Google" để thử lại.'}
        </p>
      )}
    </div>
  );
}
