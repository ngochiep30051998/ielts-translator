import { useEffect, useState } from 'react';
import { sendToBackground } from '../shared/messages';
import type { TranslateResult } from '../shared/types';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import { ReviewTab } from './ReviewTab';
import { QuizTab } from './QuizTab';

type Tab = 'translate' | 'vocab' | 'review' | 'quiz';

const TABS: { id: Tab; label: string }[] = [
  { id: 'translate', label: 'Dịch' },
  { id: 'vocab', label: 'Sổ từ' },
  { id: 'review', label: 'Ôn tập' },
  { id: 'quiz', label: 'Quiz' },
];

export function App() {
  const [tab, setTab] = useState<Tab>('translate');
  const [result, setResult] = useState<TranslateResult | null>(null);
  const [loaded, setLoaded] = useState(false);

  // Ở App chứ không ở TranslateTab: đổi tab làm TranslateTab unmount, nên effect đặt
  // trong đó sẽ chạy lại mỗi lần quay lại tab Dịch và ghi đè state người dùng đang gõ dở.
  // Ở đây nó chạy đúng một lần cho mỗi lần mở side panel.
  useEffect(() => {
    void (async () => {
      const response = await sendToBackground({ type: 'GET_LAST_RESULT' });
      if (response.ok) setResult(response.data);
      setLoaded(true);
    })();
  }, []);

  return (
    <div className="app">
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
        {tab === 'translate' && <TranslateTab result={result} loaded={loaded} />}
        {tab === 'vocab' && <VocabTab />}
        {tab === 'review' && <ReviewTab />}
        {tab === 'quiz' && <QuizTab />}
      </main>
    </div>
  );
}
