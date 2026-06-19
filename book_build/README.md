# book_build — Graduation Book processing pipeline

Reproducible scripts used to audit, correct, humanize, and format the graduation book.
They operate on `Swarm_Robot_System_Graduation_Book_CORRECTED.docx` in the repo root and
require `python-docx`, `PyMuPDF` (fitz), `Pillow`, and (for PDF export) Microsoft Word via
`pywin32` COM. **Run from the repository root** (paths are relative to CWD).

> These are provided for transparency/reproducibility. The book itself is the deliverable;
> you normally edit the `.docx` directly and only re-run a script to repeat a bulk pass.

## Order of passes
1. **Corrections** — `edits_ch1.py … edits_ch6.py` define the verified per-chapter edits;
   `apply_book_edits.py` applies them. `apply_round2.py`, `apply_round3.py`,
   `restructure_ch5.py` apply the follow-up factual fixes and the Chapter-5 table rebuild.
2. **Images** — `manage_book_images.py` extracts/organizes figures and inserts placeholders.
3. **Humanization reassembly** — `reassemble.py` writes the humanized `docs/humanize_chunks/
   part_NN_done.txt` back into the doc by paragraph position (specs protected).
4. **Formatting** — `polish_format.py` (fonts, justification, tables, margins, page breaks).
5. **TOC / lists** — `polish_toc.py` (rebuild entries, dot leaders, split sub-subsections,
   recolor black, hyphenation) then `fill_toc_numbers.py` (recompute page numbers from the
   exported PDF and fill them in).

## PDF export
Done via Word COM inside `fill_toc_numbers.py` / ad-hoc; requires Word installed.

## Safety
- Each pass writes a timestamped/role backup (`.prev*`, `.prefmt`, `.pretoc`) — these are
  git-ignored. After any bulk change, re-run the protected-spec diff and re-export the PDF.
- Never run these against a `.docx` that is open in Word (file lock).
