import { useState } from 'react';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';
import { ReviewTab } from './ReviewTab';

type Tab = 'translate' | 'vocab' | 'review';

const TABS: { id: Tab; label: string }[] = [
  { id: 'translate', label: 'Dịch' },
  { id: 'vocab', label: 'Sổ từ' },
  { id: 'review', label: 'Ôn tập' },
];

export function App() {
  const [tab, setTab] = useState<Tab>('translate');

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
        {tab === 'translate' && <TranslateTab />}
        {tab === 'vocab' && <VocabTab />}
        {tab === 'review' && <ReviewTab />}
      </main>
    </div>
  );
}
