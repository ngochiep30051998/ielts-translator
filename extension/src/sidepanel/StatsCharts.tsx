import { buildHeatmap, parseDay } from '../shared/heatmap';
import type {
  DailyPoint, QuizTypeStats, RecallBreakdown, StatsTotals, StreakInfo,
} from '../shared/types';

/** Số ngày trên biểu đồ cột. `daily` dài 91 nên đây là phép cắt, không phải request riêng. */
const BAR_DAYS = 30;

const WEEKDAYS = ['T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'CN'];

/** Nhãn khớp với QuizTab để cùng một loại không mang hai tên trong cùng một extension. */
const QUIZ_LABELS: Record<QuizTypeStats['type'], string> = {
  FILL_BLANK: 'Điền từ',
  COLLOCATION_CHOICE: 'Chọn cụm từ',
  FREE_WRITE: 'Tự viết câu',
};

/** "2026-08-11" → "11/08". Dùng `parseDay` chứ không `new Date(iso)` — xem `heatmap.ts`. */
function formatDayMonth(iso: string): string {
  const d = parseDay(iso);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}`;
}

/**
 * Tỉ lệ phần trăm, hoặc `—` khi mẫu số bằng 0.
 *
 * `—` chứ không `0%`: "chưa làm" và "làm sai hết" là hai chuyện khác nhau, và hiện 0% cho
 * loại chưa đụng tới là nói dối người học rằng họ đã thử và trượt.
 */
function percent(numerator: number, denominator: number): string {
  return denominator <= 0 ? '—' : `${Math.round((numerator / denominator) * 100)}%`;
}

export function StatRow({ streak, totals }: { streak: StreakInfo; totals: StatsTotals }) {
  const items: { label: string; value: number }[] = [
    { label: 'ngày liên tiếp', value: streak.current },
    { label: 'kỷ lục', value: streak.longest },
    { label: 'lượt ôn', value: totals.reviews },
    { label: 'từ đã học', value: totals.learnedWords },
  ];
  return (
    <div className="stat-row">
      {items.map((item) => (
        <div className="stat-cell" key={item.label}>
          <strong>{item.value}</strong>
          <span>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export function DailyBars({ daily }: { daily: DailyPoint[] }) {
  const recentDays = daily.slice(-BAR_DAYS);
  const max = Math.max(0, ...recentDays.map((d) => d.reviews));
  const total = recentDays.reduce((a, d) => a + d.reviews, 0);

  return (
    <section className="chart">
      <h3>30 ngày gần nhất</h3>
      <div
        className="bars"
        role="img"
        aria-label={`Số lượt ôn 30 ngày gần nhất: tổng ${total} lượt, cao nhất ${max} lượt trong một ngày`}
      >
        {recentDays.map((d) => (
          <div
            key={d.date}
            className="bar"
            data-testid="bar"
            // max = 0 khi 30 ngày qua không ôn lượt nào. Chia ở đây cho ra NaN, và
            // `height: NaN%` là cột biến mất — cột lùn và cột không có là hai thông tin
            // khác nhau, nên sàn 2% được áp cho mọi trường hợp.
            style={{ height: `${max > 0 ? Math.max(2, (d.reviews / max) * 100) : 2}%` }}
            title={`${formatDayMonth(d.date)}: ${d.reviews} lượt ôn`}
          />
        ))}
      </div>
    </section>
  );
}

export function Heatmap({ daily }: { daily: DailyPoint[] }) {
  const columns = buildHeatmap(daily);
  const activeDays = daily.filter((d) => d.reviews > 0).length;
  const busiest = daily.reduce(
    (a, d) => (d.reviews > a.reviews ? d : a),
    { date: '', reviews: 0 },
  );

  // Nhãn nói "91 ngày" chứ không "13 tuần": lưới ra 13 hay 14 cột tuỳ ngày đầu rơi vào thứ
  // mấy, nên "13 tuần" là con số sai vào phần lớn các ngày trong tuần.
  const summary = busiest.reviews > 0
    ? `Lịch ôn 91 ngày gần nhất: ${activeDays} ngày có ôn, cao nhất ${busiest.reviews} lượt ngày ${formatDayMonth(busiest.date)}`
    : 'Lịch ôn 91 ngày gần nhất: chưa có ngày nào ôn';

  return (
    <section className="chart">
      <h3>91 ngày gần nhất</h3>
      <div className="heatmap">
        <div className="heatmap-days" aria-hidden="true">
          {WEEKDAYS.map((t) => <span key={t}>{t}</span>)}
        </div>
        {/* Từng ô chỉ có `title`, không `aria-label`: gắn nhãn cho cả 91 ô là bắt trình đọc
            màn hình đọc 91 câu để nói một điều mà hàng số liệu phía trên đã nói rồi. */}
        <div className="heatmap-grid" role="img" aria-label={summary}>
          {columns.map((week, i) => (
            <div className="heatmap-col" key={i}>
              {week.map((cell, j) =>
                cell === null
                  ? <div className="cell pad" key={j} />
                  : (
                    <div
                      className={`cell lv${cell.level}`}
                      key={j}
                      data-testid="cell"
                      title={`${formatDayMonth(cell.date)}: ${cell.reviews} lượt ôn`}
                    />
                  ),
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Accuracy({
  recall, quiz,
}: { recall: RecallBreakdown; quiz: QuizTypeStats[] }) {
  const totalRatings = recall.again + recall.hard + recall.good + recall.easy;
  const remembered = totalRatings - recall.again;

  return (
    <section className="chart">
      <h3>Độ chính xác</h3>

      <div className="acc-line">
        <span>Tỉ lệ nhớ khi ôn</span>
        <strong data-testid="recall-rate">{percent(remembered, totalRatings)}</strong>
      </div>
      <div
        className="acc-bar"
        role="img"
        aria-label={`Phân bố mức tự chấm: ${recall.again} quên, ${recall.hard} khó, ${recall.good} nhớ, ${recall.easy} dễ`}
      >
        {(['again', 'hard', 'good', 'easy'] as const).map((ratingKey) => (
          <div
            key={ratingKey}
            className={`seg seg-${ratingKey}`}
            style={{ width: `${totalRatings > 0 ? (recall[ratingKey] / totalRatings) * 100 : 0}%` }}
          />
        ))}
      </div>

      {quiz.map((row) => (
        <div className="acc-line" key={row.type}>
          <span>{QUIZ_LABELS[row.type]}</span>
          <span className="acc-detail">
            {row.attempts > 0 && `${row.correct}/${row.attempts}`}
            {row.avgScore !== null && ` · ${row.avgScore}/100`}
          </span>
          <strong data-testid="quiz-rate">{percent(row.correct, row.attempts)}</strong>
        </div>
      ))}
    </section>
  );
}
