import { useState } from 'react';
import { TranslateTab } from './TranslateTab';
import { VocabTab } from './VocabTab';

type Tab = 'translate' | 'vocab';

export function App() {
  const [tab, setTab] = useState<Tab>('translate');

  return (
    <div className="app">
      <nav className="tabs">
        <button type="button" className={tab === 'translate' ? 'active' : ''}
                onClick={() => setTab('translate')}>Dịch</button>
        <button type="button" className={tab === 'vocab' ? 'active' : ''}
                onClick={() => setTab('vocab')}>Sổ từ</button>
      </nav>
      <main className="content">
        {tab === 'translate' ? <TranslateTab /> : <VocabTab />}
      </main>
    </div>
  );
}
