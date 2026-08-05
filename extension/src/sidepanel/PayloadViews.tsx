import type { ReactNode } from 'react';
import type {
  EnViSentencePayload, EnViWordPayload, TranslateResult,
  ViEnSentencePayload, ViEnWordPayload,
} from '../shared/types';

const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

function Band({ value }: { value: string }) {
  return <span className="band" title={BAND_HINT}>{value}</span>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="section">
      <h3>{title}</h3>
      {children}
    </section>
  );
}

export function EnViWordView({ p }: { p: EnViWordPayload }) {
  return (
    <>
      <header className="entry-head">
        <h2>{p.term}</h2>
        <div className="meta">
          <span className="ipa">{p.ipa}</span>
          <span>{p.pos}</span>
          <span>{p.cefr}</span>
          <Band value={p.band_level} />
          <span>{p.register}</span>
        </div>
        <p className="meaning">{p.meaning_vi}</p>
        <p className="definition">{p.definition_en}</p>
      </header>

      <Section title="Collocations">
        <ul>{p.collocations.map((c) => <li key={c}>{c}</li>)}</ul>
      </Section>

      <Section title="Ví dụ">
        <ul>
          {p.examples.map((e) => (
            <li key={e.en}><span className="en">{e.en}</span><span className="vi">{e.vi}</span></li>
          ))}
        </ul>
      </Section>

      <Section title="Từ đồng nghĩa">
        <ul>
          {p.synonyms.map((s) => (
            <li key={s.term}>{s.term} <Band value={s.band} /></li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function EnViSentenceView({ p }: { p: EnViSentencePayload }) {
  return (
    <>
      <header className="entry-head">
        <p className="meaning">{p.translation_vi}</p>
      </header>

      <Section title="Từ đáng học">
        <ul>
          {p.key_vocab.map((v) => (
            <li key={v.term}>
              <strong>{v.term}</strong> — {v.meaning_vi} <Band value={v.band_level} />
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Ghi chú cấu trúc">
        <p>{p.structure_note}</p>
      </Section>
    </>
  );
}

export function ViEnWordView({ p }: { p: ViEnWordPayload }) {
  return (
    <>
      <header className="entry-head">
        <h2>{p.best_en}</h2>
      </header>

      <Section title="Lựa chọn khác">
        <ul>
          {p.alternatives.map((a) => (
            <li key={a.term}>
              <strong>{a.term}</strong> <Band value={a.band} /> <span>{a.register}</span>
              <span className="vi">{a.when_to_use}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Collocations">
        <ul>{p.collocations.map((c) => <li key={c}>{c}</li>)}</ul>
      </Section>

      <Section title="Ví dụ">
        <ul>{p.examples.map((e) => <li key={e}>{e}</li>)}</ul>
      </Section>
    </>
  );
}

export function ViEnSentenceView({ p }: { p: ViEnSentencePayload }) {
  return (
    <>
      <header className="entry-head">
        <p className="meaning">{p.band65_version}</p>
      </header>

      <Section title="Vì sao viết như vậy">
        <ul>{p.why_notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </Section>

      <Section title="Cụm đáng học">
        <ul>{p.key_phrases.map((k) => <li key={k}>{k}</li>)}</ul>
      </Section>

      <Section title="Nên tránh">
        <ul>
          {p.avoid.map((a) => (
            <li key={a.phrase}>
              <strong>{a.phrase}</strong><span className="vi">{a.reason}</span>
            </li>
          ))}
        </ul>
      </Section>
    </>
  );
}

export function PayloadView({ result }: { result: TranslateResult }) {
  if (result.direction === 'EN_VI') {
    return result.mode === 'WORD'
      ? <EnViWordView p={result.payload as EnViWordPayload} />
      : <EnViSentenceView p={result.payload as EnViSentencePayload} />;
  }
  return result.mode === 'WORD'
    ? <ViEnWordView p={result.payload as ViEnWordPayload} />
    : <ViEnSentenceView p={result.payload as ViEnSentencePayload} />;
}
