# Hint-card verification

Date: 2026-11-05. Baseline: `fb5418ed20979c159029d107a74e4761d0c33a5d`.
Implementation: `19e0dc66fdcf05428103b686205396059e0a0619`.

## Scope and review

Three-stage guides are stored separately from ordinary note content. A new linked
SQLite table avoids rebuilding the existing cards table. Progress updates compare the
expected guide and reveal count in a transaction; deleted or changed cards cannot be
advanced by a stale reading view. Metadata-only edits keep progress, while changed
stages reset it. Rollback and reopening tests cover these contracts.

The reading widget inserts only revealed text into its Qt document. The final solution
and existing-guide authoring view require explicit confirmation with Cancel as default.
Pins and previews share persisted progress, and clipboard actions reread that progress.
Search uses public metadata, including when all stages have already been revealed.
The authoring editor keeps multiline source and the existing quick-note draft intact.

Shared packs containing hints require format 2; their Markdown index and import preview
hide all stages, and recipients start at zero. Workspace backups containing hints
require format 3 and retain progress. Duplicate imports/restores keep destination
progress. Earlier ordinary pack and workspace formats remain supported. The database
and archives contain the full guide without encryption, as explained in the user guide.

No dependency or application-version change was required. New UI state lives in focused
hint modules, with integration through the existing Dashboard, pin and preview callbacks.
No additional worker, event loop, network service or global shortcut was introduced.
Database reads retain batched loading rather than issuing one query per card.

Native visual review also identified an existing pin background written in RGBA order.
Qt's eight-digit color syntax is [ARGB](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QColor.html).
Correcting the channel order restores the intended dark surface. Removing padding from
the fixed-size collapse button makes its glyph visible under the application theme.
A rendered-pixel regression checks the pin's reading background.

## Completed local checks

| Check | Result | Environment or scope |
| --- | --- | --- |
| Full test suite | 551 passed in 67.49 seconds; exit 0 | Python 3.12.10, PySide6 6.12.0, native Windows Qt platform |
| Full test suite | 551 passed in 43.55 seconds; exit 0 | Python 3.11.9, PySide6 6.12.0, native Windows Qt platform |
| Ruff | Passed | Entire repository |
| Release metadata | Passed | All four version sources remain 0.1.0 |
| PyInstaller | Passed | Fresh clean build, PyInstaller 6.22.3 |
| Inno Setup and SHA-256 generation | Passed | Fresh local installer, process exit 0 |
| Source visual smoke check | Passed | Native Windows; isolated settings/database; performed 2026-11-04 against the same runtime implementation |

The source smoke check exercised hidden and first-stage views, pin/preview synchronization,
the authoring dialog, and access to the creation button in the scrolled 430x640 panel.
Screenshots were visually inspected. Tests cover save errors/retry, stale confirmations,
changed/deleted cards, shutdown, click-through, duplicate progress, schema upgrade,
malformed formats, and cascade deletion. Related cases remain with their implementation
commits; splitting the pack and backup tests did not remove or skip any cases.

The local installer SHA-256 is
`53250644372e879982cd41db511ab3f325a8812ccd2ec99ed64a70d1cdebfd8f`.
This identifies the local build only; a separately built Actions artifact has its own
checksum and acceptance record.

An additional run with `QT_QPA_PLATFORM=offscreen` had 549 passing tests and two existing
layout assertion failures: compact Quick Panel button width and walkthrough description
height. Both test modules passed unchanged with the native Windows platform. The full
native suites above also passed. No assertion was weakened and no test was skipped;
offscreen layout execution is not certified by these results.

## Remote checks and acceptance limits

[CI on the implementation commit](https://github.com/amkumirab/gaming-buddy/actions/runs/41983521636)
passed on both Python versions: 551 tests and Ruff in each job, with successful process
exit. The [fresh Windows build](https://github.com/amkumirab/gaming-buddy/actions/runs/41983520992)
passed version validation, tests, Ruff, PyInstaller, Inno Setup, checksum generation and
the separate hosted-runner installer lifecycle job. Publication was correctly skipped
because this was a manual main-branch build, not a version tag.

The [development candidate record](../release-candidates/2026-11-05.md) identifies the
downloaded installer, matching checksum and exact automated acceptance scope. These
checks do not authorize an official release. No version tag or public Release is part
of this delivery.

Interactive installed-app hint reading/editing, screenshot capture, global shortcuts,
normal installed-app shutdown, clean Windows without Python, representative games,
and real older-official-version upgrade remain untested. Hosted-runner lifecycle fixtures
do not establish those outcomes. See the Windows acceptance and game compatibility
procedures for the remaining manual evidence.
