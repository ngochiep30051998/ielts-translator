import type { ReactNode } from 'react';
import type {
  EnViSentencePayload, EnViWordPayload, TranslateResult,
  ViEnSentencePayload, ViEnWordPayload,
} from '../types';

const BAND_HINT = 'Band do AI ước lượng, chỉ mang tính tham khảo';

/** Pill hiển thị band. `title` là hợp đồng với test — đừng gắn cho phần tử khác. */
function Band({ value }: { value: string }) {
  return <span className="band" title={BAND_HINT}>band {value}</span>;
}

function Chip({ children }: { children: ReactNode }) {
  return children ? <span className="chip">{children}</span> : null;
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
        <div className="term-row">
          <h2>{p.term}</h2>
          <span className="ipa">{p.ipa}</span>
        </div>
        <div className="chips">
          <Chip>{p.pos}</Chip>
          <Chip>{p.cefr}</Chip>
          <Chip>{p.register}</Chip>
          <Band value={p.band_level} />
        </div>
        <p className="meaning">{p.meaning_vi}</p>
        <p className="definition">{p.definition_en}</p>
      </header>

      <Section title="Collocations">
        <ul className="pills">{p.collocations.map((c) => <li key={c}>{c}</li>)}</ul>
      </Section>

      <Section title="Ví dụ">
        <ul className="rows">
          {p.examples.map((e) => (
            <li key={e.en} className="example">
              <span className="en">{e.en}</span>
              <span className="vi">{e.vi}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Từ đồng nghĩa">
        <ul className="rows">
          {p.synonyms.map((s) => (
            <li key={s.term} className="word-row">
              <strong>{s.term}</strong>
              <Band value={s.band} />
            </li>
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
        <div className="chips"><Chip>EN → VI</Chip></div>
        <p className="meaning">{p.translation_vi}</p>
      </header>

      <Section title="Từ đáng học">
        <ul className="rows">
          {p.key_vocab.map((v) => (
            <li key={v.term} className="word-row">
              <strong>{v.term}</strong>
              <Band value={v.band_level} />
              <span className="vi">{v.meaning_vi}</span>
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
        <div className="term-row">
          <h2>{p.best_en}</h2>
        </div>
      </header>

      <Section title="Lựa chọn khác">
        <ul className="rows">
          {p.alternatives.map((a) => (
            <li key={a.term} className="word-row">
              <strong>{a.term}</strong>
              <Band value={a.band} />
              <Chip>{a.register}</Chip>
              <span className="vi">{a.when_to_use}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Section title="Collocations">
        <ul className="pills">{p.collocations.map((c) => <li key={c}>{c}</li>)}</ul>
      </Section>

      <Section title="Ví dụ">
        <ul className="rows">
          {p.examples.map((e) => <li key={e} className="example">{e}</li>)}
        </ul>
      </Section>
    </>
  );
}

export function ViEnSentenceView({ p }: { p: ViEnSentencePayload }) {
  return (
    <>
      <header className="entry-head">
        <div className="chips"><Chip>VI → EN</Chip></div>
        <p className="meaning">{p.band65_version}</p>
      </header>

      <Section title="Vì sao viết như vậy">
        <ul className="notes">{p.why_notes.map((n) => <li key={n}>{n}</li>)}</ul>
      </Section>

      <Section title="Cụm đáng học">
        <ul className="pills">{p.key_phrases.map((k) => <li key={k}>{k}</li>)}</ul>
      </Section>

      <Section title="Nên tránh">
        <ul className="avoid">
          {p.avoid.map((a) => (
            <li key={a.phrase}>
              <strong>{a.phrase}</strong>
              <span className="vi">{a.reason}</span>
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
