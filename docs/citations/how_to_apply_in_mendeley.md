# How to apply this in Mendeley (and make citations clickable)

Your document's citations are managed by **Mendeley Cite** (the in-text numbers and the
bibliography are auto-generated). Do everything through Mendeley so the numbering and
bibliography stay consistent — don't type reference numbers by hand.

## A. Add the new references to your Mendeley library
1. Open **Mendeley Reference Manager** (desktop/web).
2. **Add new → Add entry manually** (or the "+" / "by identifier") and paste the **DOI**
   from `references_to_add.md` — Mendeley fetches the full record automatically. For the
   two books use the **ISBN**; for software/datasheets add them manually (type = Web page
   / Computer program).
3. Confirm each record's author/title/year looks right.

## B. Insert the in-text citations
1. In Word, open the **References → Mendeley Cite** pane (or Mendeley Cite add-in).
2. Go to each location in `citation_placement_map.md`, click right **after the sentence/term**,
   then in Mendeley Cite search the source and **Insert citation**.
3. To cite several sources at one point, select them together before inserting.
4. Mendeley assigns/renumbers `[n]` automatically and rebuilds the bibliography — you never
   edit numbers manually.

## C. Make the citations clickable (jump to the reference)
Mendeley Cite (IEEE style) can hyperlink in-text numbers to the bibliography:
1. In the **Mendeley Cite** pane → **Settings / More** → enable **"Include links to
   bibliography entries"** (wording varies by version: "Citation links" / "Link in-text
   citations to references").
2. Re-insert or **refresh** the document (Mendeley Cite → the refresh/update icon) so the
   links are generated.
3. Test: Ctrl-click an in-text `[n]` — it should jump to that reference at the end.

If your Mendeley version lacks that toggle:
- Use **References → Bibliography style** with an IEEE style that emits hyperlinks, **or**
- After you've **finished** all citing, as a *final* step you can "freeze" the document
  (Mendeley Cite → **Export → Without Mendeley fields**) to get a static copy, and I can
  then add clickable cross-references to that static copy safely (it no longer depends on
  the add-in). Do this only when citations are final.

## D. Refresh & finish
1. Mendeley Cite → **Refresh** to regenerate all numbers + the bibliography.
2. Re-check the **List of Tables/Figures and TOC page numbers** afterward (adding citations
   can shift pagination by a little). Tell me and I'll re-run the page-number pass.
3. Click each new DOI once to confirm it resolves.

## Order of operations (recommended)
1. Add all refs to Mendeley (A).
2. Insert citations per the map (B).
3. Turn on citation links + refresh (C).
4. Re-run my TOC/list page-number update (D) and regenerate the PDF.
