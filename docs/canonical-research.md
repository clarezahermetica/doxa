# Canonical offline research acceptance

This is a constructed software-engineering fixture, not a study of model intelligence.
No live model, Moss, search service, GPU, or paid account is needed. The fixed corpus is
in `examples/canonical-research`; read its `PROTOCOL.md` before generating results.
An evidence link does not establish that the evidence supports the associated claim.

## Researcher procedure in the terminal

1. Run `doxa`. Open Getting Started with F1 if needed. Choose an existing workspace,
   or explicitly create a new, empty test workspace. Confirm its full path in Settings.
   Do not select your historical workspace for this exercise.
2. Use Ctrl+P, **Add agent template**. Create a Researcher, Skeptic and Archivist with
   instructions to use only the supplied corpus and to distinguish correctness from
   unmeasured performance. A model assignment is optional for this offline exercise.
   To inspect model configuration separately, **Choose model and connection** accepts
   an arbitrary model ID. Save it disabled and unverified; do not test a live connection.
3. **Create experiment**. Enter the question from the protocol. Select **synthetic**
   execution, adversarial Council, three rounds, and members such as
   `Reader:2; Critic:2; Archivist:1` using your actual template names.
   Enable structured actions and staged research. In the advanced limits, use context
   32768, per-agent tokens 131072, aggregate tokens 1048576, and timeout 300 seconds.
   These are context limits, not observed provider usage or a spending authorization.
4. **Import evidence** four times, selecting the four Markdown files in the corpus's
   `sources` directory. Sources belong to the selected experiment; create it first.
5. **Inspect launch preflight**. Confirm synthetic execution and offline tools. Then
   **Start selected run**. Watch persisted activity. Synthetic messages are fixture
   responses, not claims that any configured model was contacted.
6. Inspect Claims, Activity, Sources, Contexts and Evaluations. Use **Review branch
   and revise claims** to submit a human claim that every policy passes the contract,
   link S2, and submit a Skeptic challenge citing S2's failure cells. Respond as the
   original author and qualify the claim to the bounded conclusion in the protocol.
   Adjudicate the responded challenge. These inputs remain human annotations.
7. In the same review action, evaluate, create a checkpoint and fork from it. Choose
   the new branch, propose a revised claim, and use **Compare trajectories** to inspect
   the change. Text branches support human analysis; they do not replay inference.
8. **Export experiment history** to a new `.zip` file outside the installation directory.
   Reopen the workspace and inspect the same history. Quit the viewer normally; viewer
   closure is distinct from cancelling an experiment.

F1 provides searchable instructions; Ctrl+P exposes these existing actions. If a control
is unavailable, read the state explanation rather than changing stored records. A
completed run cannot be started again. Create another experiment for another run.

The default synthetic responses demonstrate controller operations; they do not
substitute for the domain-specific, preregistered scripts in the controlled comparison.

## Controlled A/B/C developer acceptance

From a source checkout with the existing development environment:

```powershell
.\.venv\Scripts\python.exe scripts\canonical_research.py `
  --workspace C:\DOXA-tests\canonical-new `
  --output C:\DOXA-tests\canonical-exports-new
```

Both paths must be new/empty. The harness writes preregistration before execution,
imports the fixed corpus and uses the same public controller commands as the clients.
It runs A (one researcher), B (researcher/critic), C (two researchers/two critics/
Archivist), then the existing finite cache companion that exercises all six systems.
It deliberately blocks HTTP/socket creation and disables Moss for the process.

This harness is an integration fixture, not a hidden prerequisite for terminal use.
Its fixed responses and changing Council composition cannot establish a causal effect
of criticism or additional models on research quality. No model quality is measured.

## Independent archive inspection

Copy `scripts/inspect_research_archive.py` and an exported ZIP to another location:

```powershell
python -I -S inspect_research_archive.py condition-C.zip
```

This uses only Python's standard library, without DOXA imports, network calls or access
to the original workspace. It checks hashes, event/author identities, claim versions,
contexts, source spans and branch/checkpoint relationships. It never executes archive
contents. This reproduces historical inspection, not generation by a model. A valid
span is not an entailment or truth judgment.

For a complete workspace copy, use `doxa backup-workspace <new-backup-directory>
--data-dir <workspace>` and `doxa restore-workspace <backup-directory>
<new-workspace-directory>` with a
new restore directory. Experiment ZIP exports are inspectable research artifacts;
workspace backups restore the database. They are different formats. Keep backups
private: research records and documents can themselves be sensitive.
