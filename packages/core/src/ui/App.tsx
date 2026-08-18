import { useEffect, useState } from 'react';
import { sendToBackground } from '../messages';
import type { ApiError, AuthUser, TranslateResult } from '../types';
import { LoginScreen } from './LoginScreen';
import { HomeTab } from './HomeTab';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import { ReviewTab } from './ReviewTab';
import { QuizTab } from './QuizTab';
import { StatsTab } from './StatsTab';
import { TabIcon } from './TabIcons';

type Tab = 'home' | 'translate' | 'vocab' | 'review' | 'quiz';

/** Id của tiêu đề màn con — vùng nội dung mượn nó làm nhãn khi màn đó đang mở. */
const SUBSCREEN_TITLE_ID = 'subscreen-title';

/**
 * Bottom nav — ĐÚNG năm mục, "Hôm nay" đứng đầu.
 *
 * Thứ tự nav và tab mở sẵn là HAI quyết định tách rời, đừng suy cái này ra cái kia:
 * "Hôm nay" đứng đầu vì nó là màn tổng quan, còn `TAB_MO_SAN` bên dưới là "Dịch" vì đó là
 * việc người dùng mở app ra để làm.
 *
 * "Tiến độ" không còn ở đây, nhưng `StatsTab` vẫn nguyên vẹn: nó thành màn con của Hôm nay,
 * mở bằng nút "Xem chi tiết tiến độ". Bỏ hẳn tab đi mà không làm gì là xoá heatmap 91 ngày,
 * biểu đồ cột và phân rã tỉ lệ nhớ — xoá tính năng, không phải đổi giao diện.
 */
const TABS: { id: Tab; label: string }[] = [
  { id: 'home', label: 'Hôm nay' },
  { id: 'translate', label: 'Dịch' },
  { id: 'vocab', label: 'Sổ từ' },
  { id: 'review', label: 'Ôn tập' },
  { id: 'quiz', label: 'Quiz' },
];

/**
 * Tab mở ra đầu tiên mỗi lần mở app, và cũng là tab quay về sau khi đăng xuất.
 *
 * Một hằng số chứ không phải hai chữ `'translate'` rải hai chỗ: hai chỗ đó PHẢI bằng nhau —
 * đăng xuất rồi đăng nhập lại mà rơi vào một tab khác lúc mới mở là hai trạng thái khác
 * nhau cho cùng một hành động "bắt đầu dùng app".
 */
const TAB_MO_SAN: Tab = 'translate';

/**
 * `undefined` = ĐANG ĐỌC trạng thái, `null` = chưa đăng nhập.
 *
 * Ba trạng thái chứ không hai: nhảy thẳng vào màn đăng nhập rồi mới biết là đã đăng nhập
 * sẽ nháy một cái ở MỖI lần mở panel.
 */
type AuthState = AuthUser | null | undefined;

export function App({
  initialAuthError = null,
  initialDraft = '',
}: {
  initialAuthError?: ApiError | null;
  /**
   * Text điền sẵn vào ô Dịch. Chỉ web dùng — nó đến từ Web Share Target, tức người dùng
   * vừa chia sẻ một đoạn từ app khác sang và mong thấy nó ở đây ngay.
   */
  initialDraft?: string;
} = {}) {
  const [auth, setAuth] = useState<AuthState>(undefined);
  const [tab, setTab] = useState<Tab>(TAB_MO_SAN);
  /** Màn thống kê đầy đủ đang mở đè lên Hôm nay. */
  const [statsOpen, setStatsOpen] = useState(false);
  const [draft, setDraft] = useState(initialDraft);
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
      //
      // `initialDraft` THẮNG: nếu người dùng vừa chia sẻ một đoạn text sang, ghi đè nó bằng
      // kết quả dịch lần trước là vứt đi đúng thứ họ vừa cố ý gửi tới.
      if (!initialDraft && response.ok && response.data) setDraft(response.data.sourceText);
      setLoaded(true);
    })();
  }, [auth, initialDraft]);

  /** Đổi tab. Luôn đóng màn con của Hôm nay — nó là một lớp đè, không phải một tab. */
  function goTab(next: Tab) {
    setStatsOpen(false);
    setTab(next);
  }

  async function signOut() {
    await sendToBackground({ type: 'SIGN_OUT' });
    // Xoá sạch state phiên trước: giữ lại kết quả dịch của người vừa đăng xuất trên một
    // máy dùng chung là rò dữ liệu ngay trên màn hình.
    setResult(null);
    setDraft('');
    setLoaded(false);
    setStatsOpen(false);
    setTab(TAB_MO_SAN);
    setAuth(null);
  }

  // Đang đọc storage — chưa biết gì thì chưa vẽ gì.
  if (auth === undefined) {
    return <div className="app" />;
  }

  if (auth === null) {
    return (
      <div className="app">
        <LoginScreen onSignedIn={setAuth} initialError={initialAuthError} />
      </div>
    );
  }

  /** Màn con "Tiến độ" đang đè lên Hôm nay. */
  const subscreenOpen = tab === 'home' && statsOpen;

  return (
    <div className="app">
      <main
        className="content"
        id="tab-panel"
        role="tabpanel"
        // Màn con có tiêu đề riêng: để nhãn trỏ tab "Hôm nay" trong khi nội dung là màn
        // "Tiến độ" là đọc sai tên vùng người dùng vừa mở.
        aria-labelledby={subscreenOpen ? SUBSCREEN_TITLE_ID : `tab-${tab}`}
      >
        {/* Hôm nay được GIỮ MOUNTED và ẩn bằng `hidden` thay vì tháo ra khỏi cây, để giữ
            lại state đã nạp thay vì dựng màn trắng mỗi lần quay về. `hidden` bỏ nó khỏi cả
            phần nhìn lẫn cây a11y và thứ tự tab của bàn phím.

            Giữ mounted KHÔNG có nghĩa là dữ liệu đứng yên: `active` báo cho HomeTab biết
            lúc nào nó được mở ra để nạp lại số. Đó là bảng điểm — ôn xong quay về mà vẫn
            thấy con số cũ là sai ngay chỗ người ta nhìn vào. */}
        <div className="tab-pane" hidden={tab !== 'home' || statsOpen}>
          <HomeTab
            user={auth}
            active={tab === 'home' && !statsOpen}
            onSignOut={() => void signOut()}
            onNavigate={goTab}
            onOpenStats={() => setStatsOpen(true)}
          />
        </div>
        {subscreenOpen && (
          <div className="subscreen">
            <button
              type="button"
              className="subscreen-back"
              onClick={() => setStatsOpen(false)}
            >
              ← Hôm nay
            </button>
            <h2 className="subscreen-title" id={SUBSCREEN_TITLE_ID}>Tiến độ</h2>
            <StatsTab />
          </div>
        )}
        {tab === 'translate' && (
          <TranslateTab
            draft={draft} onDraftChange={setDraft}
            result={result} onResult={setResult} loaded={loaded}
          />
        )}
        {tab === 'vocab' && <VocabTab />}
        {tab === 'review' && <ReviewTab />}
        {tab === 'quiz' && <QuizTab />}
      </main>

      {/* Nav nằm SAU main trong DOM chứ không trước: nó dính đáy màn hình, và thứ tự đọc
          của bàn phím/trình đọc màn hình phải khớp thứ tự nhìn thấy. */}
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
            onClick={() => goTab(t.id)}
          >
            {/* Mỗi tab một hình riêng (xem `TabIcons.tsx`). Icon tự lấy màu của nút qua
                `currentColor`, nên trạng thái active không cần thêm quy tắc nào. */}
            <TabIcon name={t.id} />
            {t.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
