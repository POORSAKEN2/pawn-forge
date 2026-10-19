# Changelog

## 0.1.0

First release.

- MCP server (Python stdlib only) with 11 tools: `project_info`, `compile`, `install_compiler`, `lint`,
  `lint_rules`, `analyze_log`, `lookup`, `api_lookup`, `migrate_openmp`, `convert_textdraws`, `run_server`.
- Compiler bridge for pawncc 3.10.x and sampctl, structured diagnostics with fix hints, stack estimates, and
  automatic backslash-include normalisation so YSI compiles on Linux/macOS.
- 31 lint rules across buffers, security, databases, lifecycle, performance, modernisation and ID validation.
- CrashDetect / server log analyser with incident grouping and source context.
- Reference data generated from upstream: 212 vehicles, 53 weapons, 311 skins, 129 interiors, 1,812 animations,
  1,339 native and 109 callback signatures, 89 open.mp deprecations.
- Skills: pawn-standards (auto-loaded for .pwn/.inc), build, audit, migrate-openmp, debug-crash, textdraw,
  modernize-storage, test. Agents: pawn-auditor, pawn-build-fixer. Hooks: lint-on-edit, Pawn project detection.
