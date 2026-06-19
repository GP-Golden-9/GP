# Output format I need back (to review + rewrite the .docx)

For each part, save the humanized result as:
    docs/humanize_chunks/part_NN_done.txt   (NN = 01..25, same number as the source)

## The format (KEEP THE MARKERS)
Each source part looks like this:

    @@P0123@@
    <original paragraph 123 text>

    @@P0125@@
    <original paragraph 125 text>

Your *_done.txt must keep the SAME @@P####@@ lines, in the SAME order, with the
humanized prose under each one:

    @@P0123@@
    <humanized version of paragraph 123>

    @@P0125@@
    <humanized version of paragraph 125>

## Hard rules (so reassembly is exact)
1. Do NOT change, reorder, merge, split, add, or delete any @@P####@@ marker.
2. Exactly ONE humanized paragraph under each marker (no extra blank lines inside it).
3. Keep the blank line BETWEEN marker-blocks.
4. Humanize prose only - never edit numbers, model names, units, or anything that
   looks like a spec (the chunks already exclude tables/specs, so just don't add any).
5. Same paragraph count in = same count out.

## If QuillBot strips the @@P####@@ markers
That can happen. Fallback that still works: just return the part as plain
paragraphs separated by blank lines, in the SAME order and SAME count as the
source. I stored each part's paragraph-ID order, so I can map by position.
(The markers are the safer option - keep them if you can.)

## What I do with it
- Parse each part_NN_done.txt, map every @@P####@@ -> its docx paragraph, and
  overwrite ONLY that paragraph's text. Tables, numbers, captions, figures,
  headings, and references are never touched.
- Run a protected-strings diff (specs/numbers/model names must be unchanged).
- Flag any part where the marker set or paragraph count doesn't match.
- Regenerate the PDF and re-validate.

## Quickest way to hand it back
Either drop the 25 part_NN_done.txt files in docs/humanize_chunks/, OR paste the
humanized text of each part into chat labelled "PART NN:" and I'll save them.
