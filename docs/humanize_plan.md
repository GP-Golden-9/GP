# Humanization Plan - Graduation Book (QuillBot Premium)

**Document:** Swarm_Robot_System_Graduation_Book_CORRECTED.docx (90 pp.)
**Tool:** QuillBot Premium - Humanizer mode
**Goal:** Make the narrative read naturally / human-written WITHOUT altering any
verified technical fact, number, table, figure, or citation.

---

## 1. Objective & success criteria
- Every prose paragraph reads naturally and passes as human-written.
- ZERO regressions to technical content: specs, model names, ports, numbers,
  tables, captions, and references are byte-identical to the corrected master.
- Final deliverables: humanized .docx + regenerated .pdf, both verified.

## 2. Scope
**IN (humanize):** narrative prose of Chapters 1-6 - overview, background,
motivation, analysis, design rationale, implementation narrative, results
discussion, conclusion. (24 prepared parts, ~160k chars total.)

**OUT (never paste into the Humanizer):**
- All tables (3.1-3.3, 4.1, 5.1-5.5) - specs and numbers.
- Numeric/spec sentences and identifiers: XL4015, JGB37-520, 25GA370, yolov8s.pt,
  fire.pt, MQ-5, GY-87, ports 5556-5560, 0.025 m, 5200/2200 mAh, 0.6/0.8/1.0 s, etc.
- Table of Contents, List of Figures/Tables, figure/table captions.
- References / citations.
- Cover page, team names, acknowledgements.

## 3. Tooling notes (confirm on your account)
- Humanizer per-pass limit ~10,000 characters on Premium. Chunks were sized to
  ~7,000 chars for a safe margin; re-chunk if your limit differs.
- Use ONE consistent Humanizer setting/strength for the whole book (consistency).
- Premium = unlimited monthly words, so the only constraint is per-pass size.

## 4. Workflow (per part, 24 parts)
1. Open docs/humanize_chunks/part_NN.txt; copy the text BELOW the header rule.
2. Paste into QuillBot Humanizer -> Humanize.
3. Proofread the output: fix any broken meaning; restore any technical term the
   tool altered; keep blank lines between paragraphs (same count & order).
4. Save result to docs/humanize_chunks/part_NN_done.txt.
5. Mark the part DONE in TRACKER.md.
Batch in sessions of ~6 parts to keep quality/attention high.

## 5. Reassembly & verification (done by Claude)
1. Claude writes each *_done.txt back into the .docx paragraph-by-paragraph
   (tables/numbers/captions untouched). Mismatched paragraph counts are flagged.
2. Automated diff check: confirm all protected strings (Section 2 OUT-list) are
   still present and unchanged across the document.
3. Regenerate the PDF via Word export and re-validate (page count, images, specs).

## 6. Quality control / integrity
- Humanize prose only; never numbers or tables.
- Re-read every humanized part before saving - humanizers can invert meaning or
  drop qualifiers ("not", "only", "approximately").
- Keep the corrected master as the source of truth; back up before reassembly
  (auto .prev backups are created each pass).
- Confirm the workflow complies with your institution's AI-assistance policy.

## 7. Effort estimate
- ~24 parts x ~5-8 min (humanize + proofread) ~= 2.5-3.5 hours of focused work.
- Reassembly + PDF + verification: ~15 min (Claude).

## 8. Risk register
| Risk | Mitigation |
|------|------------|
| Tool alters a number/spec | Specs excluded from chunks; post-diff check |
| Meaning inverted by rewrite | Mandatory per-part proofread step |
| Paragraph count changes | Keep blank lines; reassembler flags mismatches |
| Inconsistent tone | One Humanizer setting for all parts |
| Lost work | Versioned backups + tracker |

## 9. Acceptance checklist (before submission)
- [ ] All 24 parts humanized, proofread, saved as *_done.txt
- [ ] Reassembled .docx opens; tables/figures intact
- [ ] Protected-strings diff = 0 changes
- [ ] PDF regenerated and spot-checked
- [ ] Final read-through of Chapters 1-6
