# Spoiler-safe hint cards

## User behavior

- Create a hint card with a public title/game/tags and three authored stages: subtle
  hint, more guidance, full solution. Existing drafts and ordinary notes stay intact.
- A new card starts at zero. Reveal one stage at a time; full solution requires an
  explicit confirmation with Cancel as default. Cancelling or failing a save cannot
  advance the view. Progress survives closing/reopening and is shared between pin and
  library preview. Start over hides all stages without deleting them.
- Unrevealed text must never enter UI previews, tooltips, accessibility text, clipboard,
  list summaries or search matches. Search hint cards by their public metadata only.
  Editing an existing hint explicitly warns that authoring reveals every stage.
- Hint cards work with ordinary game profiles, favorites, tags, trash and pin layouts.
  No new dependency, service, account, automatic hint authoring or game integration.

## Persistence and formats

- Keep the existing note/image table contract; a hint is a note with empty ordinary
  content and separate structured hint data linked by card ID. Add one table safely;
  do not rebuild the existing cards table or discard records.
- Validate bounded plain strings and progress 0..3. Atomic writes and guarded progress
  updates must reject deleted or stale cards without overwriting newer content.
- Card sharing includes the full authored guide but resets recipient progress to zero.
  A pack containing hints requires format version 2, so old readers refuse it. Export
  Markdown indexes and import previews contain public metadata, not the solution.
- Backups containing hints require version 3 and preserve private reveal progress.
  Existing note/image packs (v1) and backups (v1/v2) remain supported.
- This protects the app's reading experience, not secrets: ZIP/JSON/SQLite files are
  unencrypted and contain every stage. Titles/tags written by authors are public.

## Implementation and verification

1. Validated hint model and database storage/search/transaction regressions.
2. Reusable reading view and author editor with keyboard, confirmation and failure tests.
3. Integrate pin/preview/create/edit/copy, export/import and backup boundaries with
   anti-spoiler tests and existing note/image regression checks.
4. Native source visual/lifecycle smoke checks and English usage documentation.
5. Full test suites on Python 3.11 and 3.12 with successful process exit, Ruff,
   synchronized version metadata and a fresh Windows bundle/installer build.
   Record installed-app and real-game acceptance separately from source smoke checks.
