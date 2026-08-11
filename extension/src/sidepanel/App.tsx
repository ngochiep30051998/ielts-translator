import { useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { AuthUser, TranslateResult } from '../shared/types';
import { LoginScreen } from './LoginScreen';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import { ReviewTab } from './ReviewTab';
import { QuizTab } from './QuizTab';
import { StatsTab } from './StatsTab';

type Tab = 'translate' | 'vocab' | 'review' | 'quiz' | 'stats';

const TABS: { id: Tab; label: string }[] = [
  { id: 'translate', label: 'Dịch' },
  { id: 'vocab', label: 'Sổ từ' },
  { id: 'review', label: 'Ôn tập' },
  { id: 'quiz', label: 'Quiz' },
  { id: 'stats', label: 'Thống kê' },
];

/**
 * `undefined` = ĐANG ĐỌC trạng thái, `null` = chưa đăng nhập.
 *
 * Ba trạng thái chứ không hai: nhảy thẳng vào màn đăng nhập rồi mới biết là đã đăng nhập
 * sẽ nháy một cái ở MỖI lần mở panel.
 */
type AuthState = AuthUser | null | undefined;

export function App() {
  const [auth, setAuth] = useState<AuthState>(undefined);
  const [tab, setTab] = useState<Tab>('translate');
  const [draft, setDraft] = useState('');
  const [result, setResult] = useState<TranslateResult | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Ở App chứ không ở TranslateTab: đổi tab làm TranslateTab unmount, nên effect đặt
  // trong đó sẽ chạy lại mỗi lần quay lại tab Dịch và ghi đè state người dùng đang gõ dở.
  // Ở đây nó chạy đúng một lần cho mỗi lần mở side panel.
  useEffect(() => {
    void (async () => {
      const response = await sendToBackground({ type: 'GET_AUTH_STATE' });
      // Lỗi khi hỏi trạng thái cũng coi như chưa đăng nhập: màn đăng nhập là chỗ duy nhất
      // người dùng làm được gì đó, và nó tự hiện lỗi khi bấm.
      setAuth(response.ok ? response.data : null);
    })();
  }, []);

  useEffect(() => {
    if (!auth) return;
    void (async () => {
      const response = await sendToBackground({ type: 'GET_LAST_RESULT' });
      if (response.ok) setResult(response.data);
      // Tự điền để sửa lại đoạn bôi đen hụt rồi dịch lại, không phải gõ từ đầu.
      // Chỉ chạy một lần mỗi lần mở panel — hết lần này là nháp thuộc về người dùng.
      if (response.ok && response.data) setDraft(response.data.sourceText);
      setLoaded(true);
    })();
  }, [auth]);

  async function signOut() {
    await sendToBackground({ type: 'SIGN_OUT' });
    // Xoá sạch state phiên trước: giữ lại kết quả dịch của người vừa đăng xuất trên một
    // máy dùng chung là rò dữ liệu ngay trên màn hình.
    setResult(null);
    setDraft('');
    setLoaded(false);
    setAuth(null);
  }

  // Đang đọc storage — chưa biết gì thì chưa vẽ gì.
  if (auth === undefined) {
    return <div className="app" />;
  }

  if (auth === null) {
    return (
      <div className="app">
        <LoginScreen onSignedIn={setAuth} />
      </div>
    );
  }

  return (
    <div className="app">
      <header className="account">
        <span className="account-email">{auth.email}</span>
        <button type="button" className="account-signout" onClick={() => void signOut()}>
          Đăng xuất
        </button>
      </header>

      <nav className="tabs" role="tablist" aria-label="Khu vực">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            id={`tab-${t.id}`}
            className={tab === t.id ? 'active' : ''}
            aria-selected={tab === t.id}
            aria-controls="tab-panel"
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </nav>

      <main className="content" id="tab-panel" role="tabpanel" aria-labelledby={`tab-${tab}`}>
        {tab === 'translate' && (
          <TranslateTab
            draft={draft} onDraftChange={setDraft}
            result={result} onResult={setResult} loaded={loaded}
          />
        )}
        {tab === 'vocab' && <VocabTab />}
        {tab === 'review' && <ReviewTab />}
        {tab === 'quiz' && <QuizTab />}
        {tab === 'stats' && <StatsTab />}
      </main>
    </div>
  );
}
