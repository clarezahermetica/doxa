import { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import type { components } from './api.generated';
import './style.css';

type Run = components['schemas']['Run'];
type RunBundle = components['schemas']['RunBundle'];
type CouncilConfig = components['schemas']['CouncilConfig-Output'];
type InstallationReadiness = components['schemas']['InstallationReadiness'];

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
  const [configuration, setConfiguration] = useState<CouncilConfig | null>(null);
  const [readiness, setReadiness] = useState<InstallationReadiness | null>(null);
  const [configurationError, setConfigurationError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    setConfiguration(null);
    setReadiness(null);
    setConfigurationError('');
    Promise.all([
      read<CouncilConfig>('/api/configuration', controller.signal),
      read<InstallationReadiness>('/api/readiness', controller.signal),
    ]).then(([config, status]) => { setConfiguration(config); setReadiness(status); })
      .catch((error: Error) => {
        if (!controller.signal.aborted) setConfigurationError(error.message);
      });
    return () => controller.abort();
  }, [revision]);

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
    <section aria-labelledby="configuration-heading">
      <h2 id="configuration-heading">Agents and provider readiness</h2>
      <p>Local configuration checks only. Remote availability and credit balances are unverified.</p>
      {configurationError && <p role="alert">{configurationError}</p>}
      {readiness && <>
        {readiness.configuration.profiles.length === 0 && <p>No model profiles configured. Offline inspection is available.</p>}
        <ul>{readiness.configuration.profiles.map(profile => <li key={`${profile.profile_id}:${profile.version}`}>
          <strong>{profile.profile_id} v{profile.version}</strong> · {profile.provider} · {profile.model_id} · {profile.status}
          <p>Credential reference: {profile.credential_env}; {profile.credential_present ? 'present locally' : 'missing'}.</p>
          {profile.issues.length > 0 && <ul>{profile.issues.map(issue => <li key={issue}>{issue}</li>)}</ul>}
          {profile.warnings.map(warning => <p key={warning}>{warning}</p>)}
        </li>)}</ul>
        <p>Generated-code execution: {readiness.sandbox.execution_enabled ? 'enabled' : 'disabled'}. {readiness.sandbox.prerequisite}</p>
      </>}
      {configuration && <details><summary>Stored agents, permissions and model assignments ({configuration.agents.length} agents)</summary>
        <pre>{JSON.stringify(configuration, null, 2)}</pre>
      </details>}
    </section>
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
        <details><summary>Recorded provider usage and reservations</summary>
          <p>Reservations are spending holds. An unreported bill remains null.</p>
          <pre>{JSON.stringify(bundle.accounting, null, 2)}</pre>
        </details>
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
