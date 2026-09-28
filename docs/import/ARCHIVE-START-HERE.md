# AI Day Trading Bot — expanded project handoff

Prepared from the project locations supplied by the owner on September 25, 2026. This archive replaces the earlier BOT2/BOT21 shareable ZIPs, which omitted the main repository's data and Brain vault and flattened project paths.

## What is included

- `project-main/`: the main Hyperliquid trading project, including `exchange/`, Python and PowerShell code, configuration, data, logs, backtests, research, generated results, and working files.
- `project-phase5c-v3/`: the separately maintained BOT2/BOT21 Phase 5C worktree, including its uncommitted work.
- `other-project-worktrees/`: the four other registered working copies belonging to this same Git repository, preserving additional working files.
- `obsidian-Brain/`: the actual Obsidian vault, including notes, trade journals, strategy specifications, recovered historical transcript material, templates, plugin files, and all available saved continuity checkpoints. The Desktop shortcut was only an application launcher; the vault contains the content.
- `Claude/local-sessions/`: the three local Claude sessions previously recovered for TradingView connection checks and the Obsidian connector setup, with credentials removed. Additional Claude-related content saved in the vault is included in its original location. This is not a complete export of the owner's Claude cloud account.
- `supporting-integrations/`: the Obsidian Python bridge and local TradingView MCP connector source used in the recovered setup workflow, with dependency caches and machine-specific policy settings omitted.
- `Git-history/`: a portable Git bundle with the available branches and their committed history, plus a commit log and working-copy inventory. It does not connect to GitHub or publish anything.
- `Project-notes/`: the database inspection, Docker review, and exact coverage/exclusion report.
- `MANIFEST.csv`: original source locations, packaged paths, file sizes, SHA-256 checksums, and whether a copied file was redacted or exported as a SQLite snapshot.

## Database and recorded data

The main project's `database/` contains two SQLite test databases: `trade_ledger_test.db` and `execution_integration_test.db`. Each contains one BTC trade dated August 21, 2026. Both were read without changing the originals and exported using SQLite's backup mechanism. These are test records, not proof of real-money executions.

Most recorded project data is stored in CSV and JSON/JSONL files under `project-main/data/` and `project-main/outputs/`. This includes BTC backtest/recorder data, ES/NQ observations and bars, paper-session records, news snapshots, operational evidence, and analytics. No `database/trading_bot.db` was found in the supplied working copies. See the Docker review for its separate result.

## How to open it

1. Extract the entire ZIP into a new, short local folder. It contains over 200,000 files, so extraction can take time and some paths are long.
2. Browse `project-main/data/` and `project-main/outputs/` for recorded data.
3. In Obsidian, use **Open folder as vault** and select the extracted `obsidian-Brain/` folder. Original plugin files are preserved; review any plugins before enabling them.
4. For development, use the chosen working copy's requirements and documentation. Python environments are not included and must be recreated. Windows PowerShell scripts are included as source files.
5. To inspect committed history in a separate folder, run `git clone Git-history/all-project-branches.bundle restored-history`. The working-copy folders also include uncommitted/untracked changes that are not represented by a Git commit.

The package was created for review and transfer. The packaging process did not start the bot, execute project scripts, or place trades. Read project documentation before running anything; historical documents describe different versions and some stored results are synthetic or paper-trading results.

## Scope and exclusions

Folder structure is preserved. Original source files were not edited. Known credential values and common secret formats were screened in copied text, configuration, and nested ZIP contents. Environment values were replaced with `[REDACTED]` in the share copies. Redacted files and modified nested archives are listed in the coverage report; their old internal hashes or signatures may no longer match. Git history and saved Git bundles were checked for known credentials and recognized token patterns; synthetic test literals were retained.

Git working metadata, virtual environments, dependency installation folders, and Python/tool caches are omitted because they are machine-specific or regenerable. Git history is supplied separately. The recorder's in-use `.single-writer.lock` file is omitted; it coordinates a running process and is not recorded trading data. The complete Docker virtual disk and base images are not included; they are runtime machinery rather than the project source or recorded trading data. See the Docker review for what was actually present on the stopped disk.

The archive covers the accessible supplied folders and their directly associated working copies, not a verified eight-month export of every cloud conversation, broker account, or other device. The earliest available local Git commit date is August 24, 2026. Preserved files and vault notes may have other dates. No cloud account data was fetched or uploaded.

Files were captured over the build interval, rather than freezing all applications at a single instant. A changing-files list records any file observed changing during its read. The manifest defines the exact captured version. Archive entries were checked against their recorded checksums after packaging.

One pre-existing unfinished checkpoint, `.staging-8f659ebe75604ebfb93498cd5bdd4847/runtime-evidence.zip` in the Brain continuity folder, is a zero-byte file. It is preserved as found and is not a usable backup; the coverage report lists it as an opaque archive. The other available checkpoint material is included.
