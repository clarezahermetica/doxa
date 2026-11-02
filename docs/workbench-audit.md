# Workbench audit and implementation - October 24, 2026

Baseline: `0639d27`, clean working tree, 129 passing tests before this change.
README remains intentionally empty. This audit uses the checked-out source and
existing docs; quoted assessments of older commits were not treated as current facts.

| Area | Baseline evidence | Change / boundary |
| --- | --- | --- |
| Storage/controller | Append-only events, versioned configuration, atomic accounting and recovery already present | Reused unchanged authority; additive JSON record kinds and optional fields, no second database |
| Council | `Runtime.agent()` selected first matching role | Legacy cache runtime now rejects ambiguous role assignments; new text-workbench runtime instantiates every selected participant |
| Tasks | Cache fixture only | Typed research-debate task and source manifests; code-repair remains rejected |
| Providers | Runpod and generic compatible wire adapters | Native OpenAI text Chat Completions and Claude text Messages; mocked checks only |
| Retrieval | Local word overlap; one authorized Moss session per retrieval | Scoped FTS5 BM25 snapshot ranking; exact-snapshot session reuse within an instance only |
| Context | Inline task prompts | Content-addressed exact message manifests for every new workbench turn |
| Internet | Permission strings without executor | Explicit bounded HTTPS fetch gateway and synthetic search/fetch fixtures; no configured live search provider |
| Interfaces | JSON CLI and Studio inspector | Readable workbench CLI, Textual viewer, Studio workspaces/forms, reconnectable ledger SSE |
| Desktop | Absent | pywebview/WebView2 launcher, production assets, user workspace and PyInstaller one-folder build |

No six-system algorithm was replaced. Cache experiments keep their existing controller
commands and independent oracle. Research debate is a separate text-only execution path,
with no generated-code execution and no claim of objective correctness.
