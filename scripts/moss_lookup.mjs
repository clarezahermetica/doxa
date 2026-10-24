// One-shot SDK smoke test requested by Dana. Not a second application backend.
// Credentials are supplied only to this process by the Python accounting wrapper.
import { MossClient } from '@moss-js/moss';

const client = new MossClient(
  process.env.MOSS_PROJECT_ID,
  process.env.MOSS_PROJECT_KEY,
);

async function main() {
  try {
    await client.loadIndex('agent-memory-context');
    const results = await client.query(
      'agent-memory-context',
      'how to sleep',
      { topK: 3 },
    );
    console.log(JSON.stringify({ docs: results.docs }, null, 2));
  } finally {
    await client.close();
  }
}

main().catch(error => {
  console.error(JSON.stringify({ code: error.code ?? 'UNCLASSIFIED', message: error.message }));
  process.exitCode = 1;
});
