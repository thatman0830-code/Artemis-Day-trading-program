# Source import from the expanded project archive

The Code tab now contains 6,795 files selected from the already-published September 25, 2026 archive, plus the repository README, import documentation, manifest, and Git file-handling rules. It is a source snapshot, not a merge of the separate working versions.

## Folder mapping

| Archive folder | Repository location |
| --- | --- |
| `project-main/` | Repository root |
| `project-phase5c-v3/` | `versions/phase5c-v3/` |
| `other-project-worktrees/<name>/` | `versions/<name>/` |
| `obsidian-Brain/` | `knowledge/obsidian-Brain/` for Markdown/canvas notes outside continuity snapshots |
| `Claude/` | `knowledge/Claude/` |
| `supporting-integrations/` | Same folder name |
| `Project-notes/` | `docs/import/Project-notes/` |
| `START-HERE.md` | `docs/import/ARCHIVE-START-HERE.md` |

The original main README and Git handling files are retained under `docs/import/original-main/`. The root README was added for navigation. Imported code is preserved as supplied, including empty placeholders and existing encodings. Historical documents may mention local paths, old branches, unavailable datasets, or different setup states.

The [source manifest](source-manifest.json) records each imported archive path, its repository path, byte count, and SHA-256 hash. It also records counts of files retained only in the release. This makes the import auditable without placing the archive's approximately 99 MB full inventory in Git.

## Restore data and history

1. Download **AI-Day-Trading-Project-Expanded-2026-09-25.zip** from the [project archive release](https://github.com/thatman0830-code/Artemis-Day-trading-program/releases/tag/project-archive-2026-09-25). The automatically generated “Source code” downloads contain this Git repository; choose the named expanded ZIP for the complete handoff.
2. Extract it to a separate local directory. The complete ZIP includes recorded data, generated outputs, SQLite test snapshots, the full Obsidian vault and continuity backups, Claude material, and historical Git data.
3. For the main source checkout, copy needed `project-main/data/`, `project-main/outputs/`, and database files from the extraction into matching local folders. For another version, use the matching archived version's data and output files. These local runtime paths are ignored by Git.
4. To open the complete Obsidian vault, select the extracted `obsidian-Brain/` folder in Obsidian. The notes in this repository omit plugin settings and continuity backup binaries.
5. To inspect the original committed history, clone the extracted `Git-history/all-project-branches.bundle` into a separate folder. The current repository's import commit does not replace the original branch histories; the bundle preserves those.

Archive SHA-256:

```text
FC36819538AD820E0F26FF55911681260C7923B0F7F1F80FAE5E2648056A4B5D
```

## Scope and validation

Environment files containing machine settings were left out; example environment files were retained. Database binaries, logs, generated/runtime directories, and backup archives remain in the release. Source code in the `database/` directory is included. The copied source was screened for recognized credential-token formats, and imported file hashes are checked against the published archive before committing.

The archive contains two SQLite **test** databases and recorded CSV/JSON data; it is not a verified export of a live trading database. The Claude material is the recovered local content available during packaging, not a complete export from the Claude cloud account. See [the original coverage guide](ARCHIVE-START-HERE.md) for the full collection scope.

No dependencies were installed and no project application was executed for this source import. Historical tests and operational claims in the preserved documentation were not revalidated.
