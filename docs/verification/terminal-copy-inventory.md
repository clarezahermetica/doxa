# Terminal copy discovery inventory — November 1, 2026

This is the complete **212-line initial keyword-search inventory** across `src/doxa/cli/`,
including non-displayed code hits. These are discovery candidates, not 212 user-facing defects.
Search terms: placeholder, TODO, FIXME, TBD, coming soon, dummy, sample, example, test, mock,
temporary, not implemented, NULL, Textual, Typer and FastAPI (case-insensitive).
A separate review of all terminal labels/actions covered wording not caught by keywords.
No genuine unfinished TODO/TBD/coming-soon/dummy text or robot/NULL graphic was found in the terminal.
Line numbers refer to the **pre-edit source**, retained here so rewrites do not erase audit evidence.
Input placeholders are intentional entry hints. Imports, API identifiers and docstrings are not
ordinary user help, except docstrings actually exposed by CLI help.

| Classification | Hits |
| --- | ---: |
| Internal API/code; not displayed | 90 |
| Source documentation; inspect CLI docstrings if exposed | 4 |
| Intentional input hint; retained | 21 |
| Invocation example or parameter guidance; retained | 8 |
| Accounting disclosure; retained in advanced recovery details | 1 |
| Output statement; displayed text reviewed separately | 75 |
| Connection verification limitation; retained | 3 |
| Legitimate technical or scientific terminology; retained | 5 |
| Framework wording; rewritten in ordinary Help | 5 |

| Original location | Original matching line | Disposition |
| --- | --- | --- |
| `src/doxa/cli/activity.py:9` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/activity.py:10` | `from textual.containers import Horizontal, Vertical` | Internal API/code; not displayed |
| `src/doxa/cli/activity.py:11` | `from textual.screen import ModalScreen` | Internal API/code; not displayed |
| `src/doxa/cli/activity.py:12` | `from textual.widgets import Button, Label, TextArea` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:1` | `"""Textual viewer: closing it never cancels a run owned by another client."""` | Source documentation; inspect CLI docstrings if exposed |
| `src/doxa/cli/console.py:9` | `from textual.app import App, ComposeResult, SystemCommand` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:10` | `from textual.binding import Binding` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:11` | `from textual.containers import Horizontal` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:12` | `from textual.events import Resize` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:13` | `from textual.screen import Screen` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:14` | `from textual.widgets import (` | Internal API/code; not displayed |
| `src/doxa/cli/console.py:157` | `yield Input(placeholder="Search complete branch historyâ€¦", id="activity-search")` | Intentional input hint; retained |
| `src/doxa/cli/console.py:185` | `yield Input(placeholder="Filter recordsâ€¦", id="filter")` | Intentional input hint; retained |
| `src/doxa/cli/console.py:862` | `System shell examples (do not paste into the palette):` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/console.py:867` | `Exact accounting (unknown is null):` | Accounting disclosure; retained in advanced recovery details |
| `src/doxa/cli/inspectors.py:5` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/inspectors.py:6` | `from textual.containers import VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/inspectors.py:7` | `from textual.widgets import Button, Input, Label, TextArea` | Internal API/code; not displayed |
| `src/doxa/cli/inspectors.py:177` | `yield Input(placeholder="Destination path", id="export-path")` | Intentional input hint; retained |
| `src/doxa/cli/main.py:8` | `import typer` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:24` | `app = typer.Typer(` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:37` | `raise typer.BadParameter(` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:44` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:51` | `typer.echo(report.model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:53` | `typer.echo("DOXA local installation Â· no external probe performed")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:54` | `typer.echo(f"Configuration: {'valid' if report.configuration.valid else 'needs attention'}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:55` | `typer.echo(f"Model profiles: {len(report.configuration.profiles)}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:57` | `typer.echo(f"  {profile.profile_id}: {profile.status}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:58` | `typer.echo("Generated-code execution: disabled")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:59` | `typer.echo("Use --json for the full diagnostic record.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:69` | `typer.echo(report.model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:71` | `raise typer.Exit(1)` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:78` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:93` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:98` | `typer.echo(json.dumps([a.model_dump(mode="json") for a in records], indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:101` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:106` | `typer.echo("No agent templates. Use agent-add or the Council form in Studio.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:111` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:116` | `typer.echo(json.dumps([p.model_dump(mode="json") for p in records], indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:119` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:124` | `typer.echo("No model profiles. Add a disabled profile in Studio or the terminal.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:130` | `typer.echo(controller(data_dir).recover_run(run_id).model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:135` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:144` | `typer.echo(json.dumps(result, indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:146` | `typer.echo("Synthetic cache-policy research demonstration completed.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:147` | `typer.echo(f"Created {len(result['children'])} child trajectories; no live inference.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:148` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:153` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:157` | `typer.echo(f"Run: {result['run_id']}. Use --json for full records.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:168` | `typer.echo(result.model_dump_json())` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:184` | `raise typer.BadParameter("Research command file is invalid or secret-bearing") from None` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:185` | `typer.echo(controller(data_dir).research_command(run_id, branch_id, command).model_dump_json())` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:201` | `json_output: bool = typer.Option(False, "--json"),` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:208` | `typer.echo(result.model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:210` | `typer.echo(result.caveat)` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:211` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:219` | `typer.echo(label + ": " + ", ".join(f"{k}={v}" for k, v in metrics.items()))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:232` | `raise typer.BadParameter("Set RUNPOD_MODEL_ID to the exact served model ID")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:244` | `typer.echo("Pinned RunPod model/endpoint metadata. No inference was requested.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:254` | `typer.echo(report.model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:255` | `raise typer.Exit(1)` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:257` | `typer.echo("Saved immutable agent/model configuration versions (no credential values).")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:263` | `typer.echo(controller(data_dir).configuration().model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:270` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:278` | `typer.echo(controller(data_dir).cancel(run_id).model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:285` | `typer.echo(controller(data_dir).propose_memory(run_id, command).model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:291` | `typer.echo(controller(data_dir).validate_memory(run_id, memory_id).model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:300` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:310` | `typer.echo(json.dumps([r.model_dump(mode="json") for r in results], indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:316` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:325` | `typer.echo("Operator-reported charge recorded; no external balance was inferred.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:331` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:335` | `raise typer.Exit(2)` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:339` | `raise typer.BadParameter(str(exc)) from None` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:347` | `typer.echo("Initialized local canonical ledger. No experiment executed.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:354` | `typer.echo(controller(data_dir).configure_run(command).model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:359` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:365` | `typer.echo(json.dumps([r.model_dump(mode="json") for r in records]))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:369` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:374` | `typer.echo("No runs. Create an experiment in Studio or run doxa demo.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:381` | `json_output: bool = typer.Option(False, "--json"),` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:387` | `typer.echo(bundle.model_dump_json(indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:390` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:394` | `typer.echo(f"{len(bundle.events)} committed events. Run: {bundle.run.id}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:395` | `typer.echo("Use --json to inspect exact records, or open the branch review in Studio.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:403` | `typer.echo(str(export_run(controller(data_dir), run_id, output)))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:417` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:431` | `typer.echo(version_string())` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:432` | `raise typer.Exit()` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:437` | `ctx: typer.Context,` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:438` | `version: bool = typer.Option(` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:454` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:465` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:480` | `raise typer.BadParameter(str(exc)) from None` | Internal API/code; not displayed |
| `src/doxa/cli/main.py:481` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:491` | `typer.echo(json.dumps(verify_workspace(data_dir), indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:499` | `typer.echo(json.dumps(backup_workspace(data_dir, destination), indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:507` | `typer.echo(json.dumps(restore_workspace(backup, destination), indent=2))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:520` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/main.py:521` | `"Local stop attestation recorded. This does not replay a call or claim a model result."` | Connection verification limitation; retained |
| `src/doxa/cli/navigation.py:5` | `from textual.screen import ModalScreen` | Internal API/code; not displayed |
| `src/doxa/cli/operations.py:9` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/operations.py:10` | `from textual.containers import VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/operations.py:11` | `from textual.widgets import Button, Checkbox, Input, Label, Select` | Internal API/code; not displayed |
| `src/doxa/cli/operations.py:73` | `stdin=subprocess.DEVNULL,` | Internal API/code; not displayed |
| `src/doxa/cli/operations.py:94` | `yield Input(placeholder="Local TXT / Markdown / JSON / PDF / DOCX path", id="file")` | Intentional input hint; retained |
| `src/doxa/cli/operations.py:145` | `yield Input(placeholder="Complete remote per-attempt cost bound USD", id="start-bound")` | Intentional input hint; retained |
| `src/doxa/cli/operations.py:219` | `("Condition: counterexamples", "counterexamples"),` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/model_setup.py:1` | `"""Model-first terminal setup. No discovery, connection test or inference is performed."""` | Source documentation; inspect CLI docstrings if exposed |
| `src/doxa/cli/model_setup.py:11` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/model_setup.py:12` | `from textual.containers import Horizontal, Vertical, VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/model_setup.py:13` | `from textual.widgets import Button, Checkbox, Collapsible, DataTable, Input, Label, Select` | Internal API/code; not displayed |
| `src/doxa/cli/model_setup.py:103` | `placeholder="Developer / family / model / exact ID", id="catalog-search"` | Intentional input hint; retained |
| `src/doxa/cli/model_setup.py:138` | `value=self.initial_connection or Select.NULL,` | Internal API/code; not displayed |
| `src/doxa/cli/model_setup.py:268` | `placeholder="Leave blank to preserve current settings",` | Intentional input hint; retained |
| `src/doxa/cli/model_setup.py:301` | `"Text request capability â€” manual declaration, never a connection test"` | Connection verification limitation; retained |
| `src/doxa/cli/model_setup.py:480` | `elif not implemented:` | Internal API/code; not displayed |
| `src/doxa/cli/model_setup.py:562` | `if not implemented:` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:1` | `"""One action registry feeds the palette, contextual menu and searchable F1 reference."""` | Source documentation; inspect CLI docstrings if exposed |
| `src/doxa/cli/reference.py:7` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:8` | `from textual.binding import Binding` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:9` | `from textual.containers import Horizontal, Vertical` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:10` | `from textual.screen import ModalScreen` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:11` | `from textual.widgets import Button, DataTable, Input, Label, Select, TextArea` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:12` | `from typer import _click as click` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:13` | `from typer.core import TyperGroup, TyperOption` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:198` | `from typer.main import get_command` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:205` | `(p.opts[0] + " " if isinstance(p, TyperOption) else "") + (p.name or "VALUE").upper()` | Legitimate technical or scientific terminology; retained |
| `src/doxa/cli/reference.py:208` | `example = (path + " " + args).strip()` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/reference.py:215` | `f"Required: {args or 'none'}\nExample: {example}\n"` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/reference.py:216` | `"Arguments above are placeholders. Use --data-dir PATH where supported.\n"` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/reference.py:223` | `if isinstance(p, TyperOption)` | Legitimate technical or scientific terminology; retained |
| `src/doxa/cli/reference.py:232` | `if isinstance(command, TyperGroup):` | Legitimate technical or scientific terminology; retained |
| `src/doxa/cli/reference.py:248` | `f"Textual action.\nAvailability: {reason or 'available'}\nRequired: "` | Framework wording; rewritten in ordinary Help |
| `src/doxa/cli/reference.py:251` | `f"\nExample: Ctrl+P â†’ {spec.title}\n\n{spec.description}\n"` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/reference.py:263` | `"Textual shortcuts",` | Framework wording; rewritten in ordinary Help |
| `src/doxa/cli/reference.py:266` | `f"Textual shortcut: {key}\nAction: {binding.action}\nExample: press {key}.\n"` | Framework wording; rewritten in ordinary Help |
| `src/doxa/cli/reference.py:273` | `from textual.containers import VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:274` | `from textual.widgets import Checkbox, Collapsible, Select, SelectionList, TabbedContent` | Internal API/code; not displayed |
| `src/doxa/cli/reference.py:317` | `f"Example: focus with Tab, then press {key}.\n"` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/reference.py:332` | `f"Textual built-in command.\nExample: Ctrl+P â†’ {command.title}\n"` | Framework wording; rewritten in ordinary Help |
| `src/doxa/cli/reference.py:334` | `"Availability is supplied by Textual."` | Framework wording; rewritten in ordinary Help |
| `src/doxa/cli/reference.py:398` | `placeholder="Search names, arguments, shortcuts, limitationsâ€¦",` | Intentional input hint; retained |
| `src/doxa/cli/onboarding.py:9` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/onboarding.py:10` | `from textual.containers import Horizontal, Vertical, VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/onboarding.py:11` | `from textual.screen import ModalScreen` | Internal API/code; not displayed |
| `src/doxa/cli/onboarding.py:12` | `from textual.widgets import Button, Checkbox, DataTable, Label, Select, TextArea` | Internal API/code; not displayed |
| `src/doxa/cli/onboarding.py:76` | `"cost money. Saving a connection is configuration, not a successful model test. Offline "` | Connection verification limitation; retained |
| `src/doxa/cli/research_tools.py:4` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/research_tools.py:5` | `from textual.containers import VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/research_tools.py:6` | `from textual.widgets import Button, Checkbox, Input, Label, Select, TextArea` | Internal API/code; not displayed |
| `src/doxa/cli/research_tools.py:46` | `yield Input(placeholder="Memory query", id="tool-query")` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:7` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/screens.py:8` | `from textual.containers import Horizontal, Vertical, VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/screens.py:9` | `from textual.widgets import (` | Internal API/code; not displayed |
| `src/doxa/cli/screens.py:71` | `placeholder="Name",` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:79` | `value=self.execution_kind if self.execution_kind else Select.NULL,` | Internal API/code; not displayed |
| `src/doxa/cli/screens.py:90` | `yield Input(placeholder="Researcher:1; Skeptic:3", id="setup-members")` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:108` | `yield Input(value="2", placeholder="Rounds", id="setup-rounds")` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:110` | `value="1", placeholder="Concurrent calls", id="setup-concurrency"` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:112` | `yield Input(value="20", placeholder="Maximum model calls", id="setup-calls")` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:115` | `placeholder="Per-agent token cap",` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:120` | `placeholder="Aggregate token cap",` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:124` | `value="120", placeholder="Run timeout seconds", id="setup-timeout"` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:127` | `value="8192", placeholder="Context token cap", id="setup-context"` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:129` | `yield Input(value="1024", placeholder="Output token cap", id="setup-output")` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:131` | `value="1", placeholder="Run spending ceiling USD", id="setup-run-cap"` | Intentional input hint; retained |
| `src/doxa/cli/screens.py:406` | `yield Input(value="local-operator", placeholder="Reviewer name", id="review-name")` | Intentional input hint; retained |
| `src/doxa/cli/workbench.py:10` | `import typer` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:28` | `experiment_app = typer.Typer()` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:29` | `run_app = typer.Typer()` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:35` | `json_output: bool = typer.Option(False, "--json"),` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:42` | `typer.echo(report.model_dump_json(indent=2) if json_output else format_preflight(report))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:52` | `if criticism_strategy not in {None, "evidence_gaps", "counterexamples", "source_conflicts"}:` | Invocation example or parameter guidance; retained |
| `src/doxa/cli/workbench.py:53` | `raise typer.BadParameter("Choose evidence_gaps, counterexamples or source_conflicts")` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:60` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:67` | `raise typer.BadParameter(` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:74` | `raise typer.BadParameter(str(exc)) from None` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:80` | `name: str = typer.Option(..., prompt=True),` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:81` | `question: str = typer.Option(..., prompt=True),` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:82` | `member: Annotated[list[str]  /  None, typer.Option()] = None,` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:96` | `raise typer.BadParameter("Use --member 'Unique agent name:count'")` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:114` | `typer.echo(f"Created {name} ({run.execution_kind}). Run: {run.id}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:138` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:152` | `typer.echo(f"{event.timestamp:%H:%M:%S}  {event.type}  {event.provenance}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:163` | `typer.echo("Cancellation recorded. Remote billing may remain unknown.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:166` | `def install(app: typer.Typer) -> None:` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:167` | `app.add_typer(experiment_app, name="experiment")` | Legitimate technical or scientific terminology; retained |
| `src/doxa/cli/workbench.py:168` | `app.add_typer(run_app, name="run")` | Legitimate technical or scientific terminology; retained |
| `src/doxa/cli/workbench.py:172` | `name: str = typer.Option(..., prompt=True),` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:174` | `instructions: str = typer.Option(..., prompt=True),` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:182` | `raise typer.BadParameter("Verifier and orchestrator are outside the LLM Council")` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:196` | `typer.echo(f"Saved {result.display_name} v{result.version} ({role.value})")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:202` | `json_output: bool = typer.Option(False, "--json"),` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:224` | `typer.echo(json.dumps([p.model_dump(mode="json") for p in records]))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:227` | `typer.echo(f"{index}. {record.proposition} ({record.status}; {record.provenance})")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:229` | `typer.echo("No claims recorded on this branch.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:233` | `json_output: bool = typer.Option(False, "--json"), data_dir: Path = DEFAULT_DATA_DIR` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:238` | `typer.echo(json.dumps([p.model_dump(mode="json") for p in config.profiles]))` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:241` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:245` | `typer.echo("No model profiles. Add one in Studio; credentials stay in .env.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:255` | `raise typer.BadParameter("Choose a document up to 10 MB")` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:265` | `typer.echo(f"Imported {doc.title} Â· SHA-256 {doc.content.sha256}")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:274` | `typer.echo("The graphical client is a separate archived desktop build.")` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workbench.py:275` | `raise typer.Exit(2)` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:289` | `"""Open the existing Textual application against one workspace."""` | Source documentation; inspect CLI docstrings if exposed |
| `src/doxa/cli/workbench.py:296` | `data_dir: Path = DEFAULT_DATA_DIR, json_output: bool = typer.Option(False, "--json")` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:303` | `raise typer.BadParameter("A new demo workspace must be an empty directory")` | Internal API/code; not displayed |
| `src/doxa/cli/workbench.py:308` | `typer.echo(` | Output statement; displayed text reviewed separately |
| `src/doxa/cli/workspace_screen.py:3` | `from textual.app import ComposeResult` | Internal API/code; not displayed |
| `src/doxa/cli/workspace_screen.py:4` | `from textual.containers import VerticalScroll` | Internal API/code; not displayed |
| `src/doxa/cli/workspace_screen.py:5` | `from textual.widgets import Button, Checkbox, Input, Label, Select` | Internal API/code; not displayed |

## Additional findings outside the keyword search

| Area | Finding and disposition |
| --- | --- |
| Getting Started | Workflow order and prerequisites retained. “Synthetic fixtures” became “simulated” in the novice guide; no verified-model claim added. |
| Workspace/home | Canonical path, creation opt-in, separate histories and OneDrive warnings are actionable and retained. |
| Help/palette | Framework wording removed, friendly control names added, application callbacks retained, reference-only entries labeled. Single-result list now shrinks. |
| Models/providers | Capability unknown/unverified, unsupported transport and credential-reference notices remain accurate; no new compatibility claims. |
| Agent/experiment setup | Role/model distinction, template prerequisites, pinned composition, explicit mode and bounded budgets retained. |
| Execution/activity | Launch authorization wording corrected; independent worker, uncertain remote cancellation and synthetic/live distinctions retained. |
| Sources/claims/revisions | Local document types/size, shared evidence, immutable revisions, criticism response and verification limitations retained. |
| Evaluations/comparison | Model opinion and deterministic evidence remain distinct. Comparison action now says what it compares. |
| Memory/retrieval | Query button and heading name eligible memory and existing permissions/spending controls; optional remote retrieval is not described as universally offline. |
| Recovery/status | Unknown costs/reservations, stopped-process attestation, no automatic replay/release and shell recovery examples retained. |
| Export/backup | New destination/no overwrite, JSON vs ZIP, artifact hashes, isolated restore and no credential export guidance retained; backups remain shell commands. |
| Settings/preferences | Theme help explains the chooser and automatic saving; persistence mechanism unchanged. |
| Errors/empty/disabled | Removed obsolete Studio directions from CLI empty/inspection states; Help explains unavailable vs reference-only actions. |

The inventory is a copy audit; preserved historical records, provider outputs and fixtures were not rewritten.
