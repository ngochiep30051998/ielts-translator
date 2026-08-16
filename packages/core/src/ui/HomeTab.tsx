import { useCallback, useEffect, useState } from 'react';
import type { CSSProperties } from 'react';
import { sendToBackground } from '../messages';
import { loadSettings } from '../settings';
import { surfaceCapabilities } from '../surface';
import {
  dailyGoal, estimateMinutes, formatVietnameseDate, recallPercent, sparkline, STREAK_DAYS,
  streakLevel, weakestTopics,
} from '../today';
import type { ApiError, AuthUser, SrsStats, StatsDto, VocabTagsResponse } from '../types';
import { Spinner } from './Spinner';

/** Dưới mức này thì thanh chủ đề chuyển sang màu cảnh báo. */
const WEAK_PERCENT = 50;

/** Tab mà màn Hôm nay đưa người dùng sang được. */
export type HomeTarget = 'translate' | 'vocab' | 'review';

/**
 * Màn chủ của thiết kế 1b.
 *
 * Nó KHÔNG thay thế `StatsTab`: chỗ này chỉ tóm tắt, còn heatmap 91 ngày, biểu đồ cột và
 * phân rã tỉ lệ nhớ vẫn nằm nguyên ở màn kia — `onOpenStats` là đường sang đó.
 */
export function HomeTab({
  user, active, onSignOut, onNavigate, onOpenStats,
}: {
  user: AuthUser;
  /** Màn này đang hiện ra trước mắt người dùng hay không. Nó được giữ mounted kể cả khi
   *  ẩn (xem `App.tsx`), nên đây là tín hiệu DUY NHẤT để biết lúc nào phải nạp lại số. */
  active: boolean;
  onSignOut(): void;
  onNavigate(tab: HomeTarget): void;
  onOpenStats(): void;
}) {
  const [srs, setSrs] = useState<SrsStats | null>(null);
  const [stats, setStats] = useState<StatsDto | null>(null);
  /** `null` = GET_VOCAB_TAGS hỏng. Khác hẳn `{ total: 0 }` là "sổ rỗng". */
  const [tagInfo, setTagInfo] = useState<VocabTagsResponse | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const newLimit = (await loadSettings()).newWordsPerDay;
    // Ba lượt gọi SONG SONG: chúng độc lập nhau, xếp hàng tuần tự chỉ làm màn chủ — thứ mở
    // ra đầu tiên mỗi lần bật panel — chờ lâu gấp ba mà không đổi lấy gì.
    const [srsRes, statsRes, tagsRes] = await Promise.all([
      sendToBackground({ type: 'GET_SRS_STATS', newLimit }),
      sendToBackground({ type: 'GET_STATS' }),
      sendToBackground({ type: 'GET_VOCAB_TAGS' }),
    ]);

    // Hàng chip chủ đề hỏng thì im lặng bỏ card "Chủ đề đang yếu" đi — nó là gợi ý, không
    // phải nội dung chính của màn. Hai lượt kia hỏng là màn này không còn gì để nói.
    setTagInfo(tagsRes.ok ? tagsRes.data : null);
    if (!srsRes.ok || !statsRes.ok) {
      setError(srsRes.ok ? (statsRes.ok ? null : statsRes.error) : srsRes.error);
      setLoading(false);
      return;
    }
    setSrs(srsRes.data);
    setStats(statsRes.data);
    setError(null);
    setLoading(false);
  }, []);

  /**
   * Nạp lại MỖI LẦN màn này được mở ra, không phải một lần duy nhất mỗi phiên.
   *
   * Đây là bảng điểm: người dùng sang tab Ôn tập, ôn hết thẻ, rồi quay về đây chính là để
   * xem con số vừa đổi. Nạp một lần lúc mount thì vòng tròn vẫn ghi "còn 11 thẻ" sau khi
   * họ vừa ôn xong sạch — sai ngay ở chỗ người ta nhìn vào để biết mình đã làm được gì.
   *
   * Đổi tab ĐI thì `active` thành false và effect không chạy, nên không có request thừa
   * nào cho những lần render khác. Một lần mở = một lượt nạp.
   */
  useEffect(() => {
    if (active) void load();
  }, [active, load]);

  return (
    <div className="home-tab">
      <div className="home-head">
        <span className="home-title">Hôm nay</span>
        <span className="home-date">{formatVietnameseDate(new Date())}</span>
      </div>

      {/* Dải tài khoản: 1b bỏ nó khỏi header, nhưng mất đường đăng xuất là hỏng thật —
          trên một máy dùng chung đó đúng là thứ người dùng cần nhất. Nó nằm NGOÀI mọi
          nhánh loading/lỗi bên dưới để backend chết cũng không nuốt mất nó. */}
      <div className="home-account">
        <span className="home-email">{user.email}</span>
        <button type="button" className="account-signout" onClick={onSignOut}>
          Đăng xuất
        </button>
      </div>

      <HomeBody
        loading={loading}
        error={error}
        srs={srs}
        stats={stats}
        tagInfo={tagInfo}
        onReload={() => void load()}
        onNavigate={onNavigate}
      />

      {/* Đường sang màn thống kê đầy đủ, và là đường DUY NHẤT — 1b không vẽ tab "Tiến độ"
          nữa. Nó nằm NGOÀI `HomeBody` vì thân màn return sớm ở hai trạng thái có thật (sổ
          rỗng, GET_STATS/GET_SRS_STATS hỏng); để nút bên trong là mất heatmap 91 ngày và
          biểu đồ cột đúng ở những lúc đó, tức xoá tính năng theo trạng thái. */}
      <button type="button" className="home-detail" onClick={onOpenStats}>
        Xem chi tiết tiến độ
      </button>
    </div>
  );
}

function HomeBody({
  loading, error, srs, stats, tagInfo, onReload, onNavigate,
}: {
  loading: boolean;
  error: ApiError | null;
  srs: SrsStats | null;
  stats: StatsDto | null;
  tagInfo: VocabTagsResponse | null;
  onReload(): void;
  onNavigate(tab: HomeTarget): void;
}) {
  if (loading) return <p className="status" aria-live="polite"><Spinner /> Đang tải…</p>;

  if (error) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && <button type="button" onClick={onReload}>Thử lại</button>}
      </div>
    );
  }

  if (!srs || !stats) return null;

  // Sổ rỗng: vẽ lưới bốn số 0 và một vòng tròn trống là nói với người vừa cài rằng họ đang
  // học rất tệ, trong khi họ chưa lưu từ nào. `tagInfo === null` (lượt gọi hỏng) KHÔNG rơi
  // vào đây — không biết thì đừng đoán là rỗng.
  if (tagInfo !== null && tagInfo.total === 0) {
    return (
      <p className="empty">
        {surfaceCapabilities().selectionCapture
          ? 'Sổ từ đang trống. Bôi đen một từ trên trang bất kỳ rồi lưu vào sổ để bắt đầu.'
          : 'Sổ từ đang trống. Dịch một từ ở tab Dịch rồi bấm Lưu để bắt đầu.'}
      </p>
    );
  }

  // `daily` LUÔN kết thúc ở hôm nay (theo múi giờ server), nên phần tử cuối là số lượt ôn
  // theo lịch của hôm nay. Đó là nửa còn lại của mẫu số vòng tròn.
  const reviewsToday = stats.daily.at(-1)?.reviews ?? 0;
  const goal = dailyGoal(reviewsToday, srs.dueCount);
  const minutes = estimateMinutes(srs.dueCount);
  const recall = recallPercent(stats.recall);
  const week = sparkline(stats.daily);
  // `slice(-STREAK_DAYS)` chứ không `slice(0, 7)`: `daily` dài 91 phần tử và LUÔN kết thúc ở
  // hôm nay, nên lấy đầu mảng là vẽ tuần của ba tháng trước mà không có gì đỏ.
  const weekDays = stats.daily.slice(-STREAK_DAYS);
  const weak = weakestTopics(tagInfo?.tags ?? []);

  return (
    <>
      <section className="home-hero">
        {/* Vòng tròn vẽ bằng conic-gradient trên một div, không thư viện và không SVG
            (ràng buộc #12) — đúng cách StatsCharts vẽ biểu đồ cột bằng div. */}
        <div
          className="home-ring"
          style={{ '--goal-turn': `${goal.ratio}turn` } as CSSProperties}
        >
          <div className="home-ring-core">
            <strong>{goal.done}</strong>
            <span>/{goal.total} thẻ</span>
          </div>
        </div>
        <div className="home-hero-body">
          <p className="home-hero-title">
            {goal.total === 0
              ? 'Chưa có thẻ nào đến hạn'
              : goal.remaining === 0
                ? 'Đã xong mục tiêu hôm nay'
                : `Còn ${goal.remaining} thẻ đến hạn`}
          </p>
          <p className="home-hero-note">
            {goal.remaining === 0
              ? 'Mở tab Ôn tập nếu muốn luyện thêm.'
              // "Khoảng" chứ không nói chắc: đây là ước lượng thô theo hằng số giây/thẻ,
              // không đo thời gian thật của người dùng.
              : `Khoảng ${minutes} phút nữa là xong mục tiêu hôm nay.`}
          </p>
          {goal.remaining > 0 && (
            <button type="button" className="home-cta" onClick={() => onNavigate('review')}>
              Ôn tiếp
            </button>
          )}
        </div>
      </section>

      <div className="home-grid">
        <div className="home-cell" data-tone="amber">
          <div className="home-cell-value"><strong>{stats.streak.current}</strong></div>
          <span className="home-cell-label">ngày liên tiếp</span>
          {/* Dải ô chỉ minh hoạ cho con số ngay trên nó, không mang thêm thông tin nào —
              nên aria-hidden thay vì bắt trình đọc màn hình đọc bảy ô. */}
          <span className="home-streak" aria-hidden="true">
            {weekDays.map((point) => (
              <i key={point.date} data-testid="streak-cell" data-level={streakLevel(point)} />
            ))}
          </span>
        </div>

        <div className="home-cell" data-tone="blue">
          {/* `masteredWords` chứ KHÔNG phải `learnedWords`: "thuộc" ở 1b chỉ có MỘT nghĩa —
              `repetitions >= MASTERED_REPETITIONS`, đúng ngưỡng mà thanh 5 vạch ở Sổ từ và
              % của chip chủ đề dùng. `learnedWords` (`repetitions >= 1`) ở đây làm màn này
              ghi "96 từ đã thuộc" trong khi card "Chủ đề đang yếu" ngay dưới vẽ 0%. */}
          <div className="home-cell-value"><strong>{stats.totals.masteredWords}</strong></div>
          <span className="home-cell-label">từ đã thuộc</span>
          {/* "từ MỚI" chứ không "+N tuần này": `introducedLast7` đếm từ lần đầu được đưa vào
              ôn, không phải phần tăng thêm của con số ngay trên nó. */}
          <span className="home-cell-note">+{stats.totals.introducedLast7} từ mới tuần này</span>
        </div>

        <div className="home-cell" data-tone="green">
          <div className="home-cell-value">
            {/* null = chưa tự chấm lượt nào. "0%" ở đây đọc là "quên sạch". */}
            <strong>{recall === null ? '—' : recall}</strong>
            {recall !== null && <span className="home-cell-unit">%</span>}
          </div>
          <span className="home-cell-label">tỉ lệ nhớ</span>
          <span className="home-spark" aria-hidden="true">
            {week.map((bar) => (
              <i
                key={bar.date}
                style={{ height: `${bar.height}%` }}
                data-peak={bar.peak ? '' : undefined}
              />
            ))}
          </span>
        </div>

        <div className="home-cell" data-tone="purple">
          <div className="home-cell-value">
            {/* null = chưa từ nào có band. Khác hẳn 0.0 — xem ghi chú ở StatsTotals. */}
            <strong>{stats.totals.avgBand === null ? '—' : stats.totals.avgBand.toFixed(1)}</strong>
          </div>
          <span className="home-cell-label">band trung bình</span>
          {tagInfo && <span className="home-cell-note">{tagInfo.total} từ trong sổ</span>}
        </div>
      </div>

      {weak.length > 0 && (
        <section className="home-topics">
          <div className="home-topics-head">
            <span>Chủ đề đang yếu</span>
            <button type="button" className="home-link" onClick={() => onNavigate('vocab')}>
              Xem cả sổ
            </button>
          </div>
          {weak.map((topic) => (
            <div key={topic.tag} className="home-topic">
              <span className="home-topic-name">{topic.tag}</span>
              <div className="home-topic-track" aria-hidden="true">
                <div
                  className="home-topic-fill"
                  data-weak={topic.percent < WEAK_PERCENT ? '' : undefined}
                  style={{ width: `${topic.percent}%` }}
                />
              </div>
              <span className="home-topic-percent">{topic.percent}%</span>
            </div>
          ))}
        </section>
      )}
    </>
  );
}
