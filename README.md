# Artemis Day Trading Program

Python research, backtesting, market-data collection, paper trading, risk controls, and exchange integrations, including the BOT 2.0 and BOT 2.1 work.

## Current Artemis paper pilot

The `mes-paper-pilot-v1` branch contains the three-account MES paper pilot, the October 2 context/readiness repair, and the read-only **Artemis dashboard**. Start with the [current handoff](HANDOFF.md), [three-portfolio settings](docs/MES_THREE_PAPER_PORTFOLIOS.md), and [dashboard instructions](dashboard/PAPER_DASHBOARD_README.md).

Conservative, moderate, and aggressive accounts each start with a synthetic $100,000 and compare sizing policies on the same strategy. Live order routing remains disabled. The 70–75% win rate is a target, not a demonstrated result. The repaired engine still needs its first open-market forward paper session; diagnostic replays and synthetic fills are separate evidence.

The dashboard opens locally on your computer. GitHub stores its source; it does not host the dashboard or run the scheduled bot. Credentials, recorded market data, account ledgers, and machine-specific schedules remain local. A fresh clone therefore needs its own environment, data, calendar, and scheduling setup before running the pilot.

## Original project archive

This repository contains the source and documentation imported from the owner's September 25, 2026 project archive. The full archive is also available as one downloadable file.

**[Download the complete project ZIP](https://github.com/thatman0830-code/Artemis-Day-trading-program/releases/download/project-archive-2026-09-25/AI-Day-Trading-Project-Expanded-2026-09-25.zip)** · **[Release and checksum](https://github.com/thatman0830-code/Artemis-Day-trading-program/releases/tag/project-archive-2026-09-25)**

## Browse the project

| Location | Contents |
| --- | --- |
| [Project overview](docs/PROJECT_OVERVIEW.md) | Architecture and research/paper-trading scope |
| [bot2](bot2/) | BOT 2.0 data, features, models, and research |
| [exchange](exchange/), [execution](execution/), [risk](risk/) | Exchange adapters, execution components, and risk controls |
| [backtesting](backtesting/), [strategy](strategy/), [futures_data](futures_data/) | Backtesting, strategy work, and market-data tools |
| [scripts](scripts/), [deploy](deploy/), [monitoring](monitoring/) | Python/PowerShell tools, deployment definitions, and monitoring |
| [versions/phase5c-v3](versions/phase5c-v3/) | Separate BOT 2.0 / BOT 2.1 Phase 5C working version |
| [Other working versions](versions/) | Hermes, protective lifecycle audit, clean slate, and adversarial review snapshots |
| [Obsidian Brain notes](knowledge/obsidian-Brain/) | Browseable strategy notes, journals, and documentation |
| [Local Claude records](knowledge/Claude/) | The recovered, redacted local sessions present in the archive |
| [Supporting integrations](supporting-integrations/) | TradingView connector and Obsidian bridge source |
| [Import guide](docs/import/IMPORT.md) | Exact scope, folder mapping, and data restoration |

## Getting started

Start with the [project overview](docs/PROJECT_OVERVIEW.md) and the documentation for the working version you want to inspect. Work from the repository root for the main project, or from a folder under `versions/` for that snapshot; the versions preserve independent work and have not been merged into one implementation.

Use that version's `requirements.txt` and `.env.example` when creating your own Python environment. Some components have separate dependencies and setup instructions. The top-level `main.py` is a preserved empty placeholder, not a launcher for the complete system.

Recorded datasets, database snapshots, generated outputs, full Obsidian continuity backups, and the historical Git bundle are in the complete ZIP. See the [restoration instructions](docs/import/IMPORT.md#restore-data-and-history) when a tool needs those files.

This import preserves source for review and development. It does not establish live-trading readiness or validate the historical research results. No trading program, broker connection, model training, or deployment was started as part of the import.
