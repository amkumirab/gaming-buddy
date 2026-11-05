# Hint cards

Hint cards are guides you write yourself or import from another player. They use three
stages: **Subtle hint**, **More guidance**, and **Full solution**. They work offline.

## Create and read a guide

1. In the Capture tab, choose **New hint card…** beside **Checklist**. Your quick-note
   draft stays intact.
2. Enter a title, game, optional comma-separated tags, and all three stages. Keep the
   title and tags free of spoilers: they are visible in the library and search results.
   Each stage supports plain text or Markdown, up to 30,000 characters.
3. Save, then find the card in the Library. It is labeled **Hint** and included in the
   **Notes** filter. Use its preview or pin it above the game.
4. Choose **Reveal first hint**, then **Reveal more guidance** when needed. Revealing
   the full solution requires a separate confirmation; Cancel is the default.
5. **Start over** hides all stages again. It does not delete the guide.

Reveal progress is saved per card and stays synchronized between its pin and preview.
It survives closing and reopening the app. If a save fails or the card has changed,
the requested stage stays hidden. Reopen the card and retry after checking storage access.
Click-through and focus mode prevent interaction with pins; return to interactive mode
before revealing a stage there. Locking a pin only locks its position and size.

**Copy revealed hints** copies only the stages currently revealed in the saved card.
With no revealed stages, nothing is copied and the previous clipboard is kept. Hiding
a stage cannot retract text you previously copied elsewhere.

## Edit and organize

**Edit** warns before opening the authoring view, because all three stages are available
there. Cancel the warning to keep them hidden. Changing any stage resets progress to
zero; changing only the title, game, or tags keeps existing progress. Multiline text and
Markdown source are preserved.

Hints support game profiles, tags, favorites, trash/restore, and workspace layouts like
ordinary notes. Search uses their title, game, and tags, never their stage text, including
after a stage is revealed. Delete permanently removes the structured guide as well.

## Share and back up

- **Export selected…** includes the full guide in a card pack. A hint pack uses format
  version 2, and older importers refuse it. Its Markdown index and import preview omit
  all stages. The recipient starts with zero stages revealed. Importing an exact duplicate
  skips it and keeps the existing card's progress.
- A workspace backup containing hints uses format version 3 and preserves progress.
  Restoring an existing duplicate keeps its destination progress. Backups without hints
  continue to use version 2. Existing version 1/2 workspace backups remain supported.
- Titles, games, and tags are always visible. The database and ZIP/JSON files contain
  every stage in unencrypted form. This feature prevents accidental spoilers while
  reading in the app; it does not keep answers secret from someone opening those files.
  Only share guides whose complete contents you intend the recipient to receive.
