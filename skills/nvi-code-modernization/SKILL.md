---
name: nvi-code-modernization
description: Assess a legacy codebase, map its behavior, plan an uplift or rewrite, migrate it in stages, and verify the result with executable evidence. Use when the user asks to modernize, migrate, uplift, rewrite, or verify an old codebase.
---

# Code modernization

This skill is the entry point for Codex and Copilot. The installed plugin root is the parent of `skills/`; the workspace is the current project directory. Read `references/host-compatibility.md` before opening a stage document.

## Run a stage

1. Determine the system name and stage from the request. With no stage, start at `modernize`. If no system name was supplied, inspect `analysis/` and `legacy/`; when neither identifies a system, run `prepare_project.py --workspace <workspace>` to discover a unique top-level legacy folder. If several candidates exist, ask which folder is legacy. Use `status` when the user asks where work stands. Available stages: `modernize`, `preflight`, `assess`, `map`, `extract-rules`, `review`, `brief`, `uplift`, `transform`, `reimagine`, `verify`, `harden`, `status`.
2. Read `<plugin-root>/commands/nvi-modernize[-<stage>].md` for the detailed procedure. For the `modernize` stage, read `commands/nvi-modernize.md`. Apply the substitutions and precedence rules in `references/host-compatibility.md` throughout. These documents are the procedural specification; their Claude-specific syntax is adapted by the compatibility reference.
3. Work in the migration workspace. If `legacy/<system>` is missing and the workspace contains a physical top-level `<system>/` directory, run `prepare_project.py <system> --workspace <workspace>` to create the local alias. Keep the original source at `legacy/<system>` read-only. Place analysis under `analysis/<system>/` and generated code under `modernized/`. Keep the same artifact names and schemas regardless of host. At the start of preflight, before any build, run `source_guard.py snapshot <system> --workspace <workspace>`. After any stage that may run legacy code, run `source_guard.py verify <system> --workspace <workspace>` and address a changed or unknown result before continuing.
4. When a script is needed, run the installed file from `<plugin-root>/scripts/` with an explicit `--workspace` where supported. Find a working Python 3 interpreter through the environment. Do not rely on the current directory being the plugin directory.
5. Preserve each human decision gate. An unavailable question tool means ask the user in conversation and wait for their answer. A headless run records the unresolved decision and stops dependent work. An absent parallel-agent facility means execute bounded batches sequentially, saving the same result artifacts and gaps.
6. After a stage, refresh the report with `build_report.py <system> --workspace <workspace> --host <host>` and give the next host-specific invocation. Mark a stage complete only when its required artifacts and checks exist.

The proof verdict comes from `scripts/proof_pack.py` and its current evidence. Never infer PROVEN from a model's own summary.
