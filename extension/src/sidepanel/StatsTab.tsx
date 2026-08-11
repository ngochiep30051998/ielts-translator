import { useCallback, useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { ApiError, StatsDto } from '../shared/types';
import { Accuracy, DailyBars, Heatmap, StatRow } from './StatsCharts';

export function StatsTab() {
  const [data, setData] = useState<StatsDto | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    const response = await sendToBackground({ type: 'GET_STATS' });
    if (response.ok) {
      setData(response.data);
      setError(null);
    } else {
      setError(response.error);
    }
    setLoading(false);
  }, []);

  useEffect(() => { void load(); }, [load]);

  if (loading) return <p className="status">Đang tải…</p>;

  if (error) {
    return (
      <div className="empty">
        <p>{error.message}</p>
        {error.retryable && (
          <button type="button" onClick={() => void load()}>Thử lại</button>
        )}
      </div>
    );
  }

  if (data === null) return null;

  // Chưa ôn lượt nào thì bốn khối chỉ là tường số 0 và một lưới trắng trơn — không nói được
  // gì cho người vừa cài, và tệ hơn là làm màn này trông như đang hỏng.
  if (data.totals.reviews === 0) {
    return (
      <div className="empty">
        <p>Chưa có lượt ôn nào. Ôn vài thẻ ở tab Ôn tập rồi quay lại đây.</p>
      </div>
    );
  }

  return (
    <div className="stats">
      <StatRow streak={data.streak} totals={data.totals} />
      <DailyBars daily={data.daily} />
      <Heatmap daily={data.daily} />
      <Accuracy recall={data.recall} quiz={data.quiz} />
    </div>
  );
}
