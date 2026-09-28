# 07_Analytics — README

This folder contains derived statistics and analysis computed exclusively from 06_Trades.

Rules governing this folder (per the Master Script and Data Contract v1):

- 06_Trades is the sole source of raw trade and decision data. Nothing in this folder is a primary data source.
- No statistic may be manually entered or fabricated. If underlying data is insufficient, the correct output is the literal phrase "Insufficient data."
- Count-based statistics (no-trade decisions, missed opportunities, rule violations) must be computed across the full set of record_kind values in 06_Trades, not only executed trades.
- Outcome-based statistics (win rate, expectancy, profit factor, average win/loss) are correctly scoped to record_kind: executed only.
- No numeric sample-size threshold is asserted. Sample size is described in words (e.g., "based on 3 observations"), not treated as statistically reliable below any fixed cutoff.
- Dataview queries are used where the environment supports them. No plugins are installed and no Obsidian configuration is modified as part of populating this folder.
- Claude may create and refresh queries. Claude does not assert interpretive conclusions (e.g., "this setup has an edge") — only the query and its raw output are presented; interpretation remains with the user.

See also:
- 00_System/Daily Trading Brain - MASTER SCRIPT.md, Section 19 (Statistics & Feedback Engine)
- 00_System/DATA CONTRACT v1.md, Section 7 (Analytics Inputs/Outputs)
