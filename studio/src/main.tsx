import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { components } from './api.generated';
import './style.css';

type Run = components['schemas']['Run'];
type RunBundle = components['schemas']['RunBundle'];

async function read<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) throw new Error(`Local API returned ${response.status}`);
  return response.json() as Promise<T>;
}

function Studio() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [selected, setSelected] = useState('');
  const [bundle, setBundle] = useState<RunBundle | null>(null);
  const [listError, setListError] = useState('');
  const [detailError, setDetailError] = useState('');
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setListError('');
    read<Run[]>('/api/runs', controller.signal)
      .then(setRuns)
      .catch((error: Error) => { if (!controller.signal.aborted) setListError(error.message); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [revision]);

  useEffect(() => {
    const controller = new AbortController();
    setBundle(null);
    setDetailError('');
    if (selected) {
      read<RunBundle>(`/api/runs/${encodeURIComponent(selected)}`, controller.signal)
        .then(setBundle)
        .catch((error: Error) => { if (!controller.signal.aborted) setDetailError(error.message); });
    }
    return () => controller.abort();
  }, [selected, revision]);

  return <main>
    <header><p className="eyebrow">LOCAL RESEARCH FRAMEWORK · BACKEND PROTOTYPE</p><h1>DOXA</h1>
      <p>Experiments, trajectories, and evidence from your local ledger.</p></header>
    <aside>Bounded cache-policy prototype. Synthetic runs use supplied answers. External services are optional; generated-code execution remains disabled.</aside>
    <section aria-labelledby="runs-heading">
      <div className="row"><h2 id="runs-heading">Configured runs</h2><button onClick={() => setRevision(r => r + 1)} disabled={loading}>Refresh ledger</button></div>
      {listError && <p role="alert">{listError}. Start the local API with <code>doxa serve</code>.</p>}
      {loading ? <p role="status">Reading local ledger…</p> : runs.length === 0 && !listError ?
        <p>No runs configured. Use <code>doxa configure examples/configure.json</code> after initializing the ledger.</p> :
        <ul>{runs.map(run => <li key={run.id}><button aria-pressed={selected === run.id} onClick={() => setSelected(run.id)}>
          {run.mode} · {run.status} · {run.execution_kind}<small>{run.id}</small>
        </button></li>)}</ul>}
    </section>
    <section aria-labelledby="trajectory-heading"><h2 id="trajectory-heading">Persisted trajectory</h2>
      {detailError && <p role="alert">{detailError}</p>}
      {!selected && <p>Select a configured run to inspect its records.</p>}
      {selected && !bundle && !detailError && <p role="status">Reading trajectory…</p>}
      {bundle && <><p>{bundle.events.length} recorded event(s). This run is {bundle.run.status}.</p>
        <a href={`/api/runs/${encodeURIComponent(selected)}/export`} download={`${selected}.json`}>Export ledger JSON</a>
        {bundle.events.map(event => <article key={event.id}>
          <h3>{event.sequence}. {event.type}</h3><p>{event.provenance} · <time>{event.timestamp}</time></p>
          <pre>{JSON.stringify(event, null, 2)}</pre>
        </article>)}
      </>}
    </section>
  </main>;
}

createRoot(document.getElementById('root')!).render(<Studio />);
