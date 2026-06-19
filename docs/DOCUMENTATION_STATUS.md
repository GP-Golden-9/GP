# Graduation Book — Documentation Status & Task Board

This file is the single source of truth for the state of the graduation book
(`Swarm_Robot_System_Graduation_Book_CORRECTED.docx` / `.pdf`). It records what has been
done, where every artifact lives, and what the team still needs to do. Pending items are
also opened as **GitHub Issues** (see the Task Board) so anyone can pick them up.

> Deliverables: **`Swarm_Robot_System_Graduation_Book_CORRECTED.docx`** (editable master)
> and **`…CORRECTED.pdf`** (export, 109 pp). The original supplied file is
> **`…_FORMATTED.docx`/`.pdf`** (kept as a baseline).

---

## 1. What has been done ✅

### Technical accuracy pass
- Full chapter‑by‑chapter audit of the book against the real codebase; **125 factual
  corrections** applied (fabricated hardware removed, specs/numbers/model names fixed,
  per‑robot batteries, XL4015 regulators, servo removed, camera = Logitech C270, Alpha
  Mega + JGB37‑520 encoders clarified, etc.).
- Per‑chapter rationale + evidence: **`docs/book_corrections/chapter{1..6}_corrections.md`**.

### Chapter 5 results — honest restructuring
- Results tables rebuilt to contain **only backed data** (configured / simulation‑soak /
  calibration); no fabricated accuracy/mAP/latency. "Not measured" gaps removed by
  redesigning the tables.

### Humanization (AI‑text reduction)
- Narrative prose (645 paragraphs, 24 parts) humanized via QuillBot; reassembled back into
  the doc by position with technical specs protected. AI detection ~5%.
- Workflow + chunks: **`docs/humanize_chunks/`** (source `part_NN.txt`, results
  `part_NN_done.txt`, `TRACKER.md`, `OUTPUT_FORMAT.md`); plan: **`docs/humanize_plan.md`**.

### Professional formatting
- Cambria body (justified, hyphenation on), headings restyled, **all text black except
  table headers**; elegant tables (navy header that repeats, zebra rows, no mid‑row or
  bottom‑of‑page splits); comfortable margins.
- **TOC / List of Figures / List of Tables** rebuilt: dot‑leader tab stops, sub‑subsections
  split one‑per‑line (consistent across chapters), and **all page numbers recomputed** to
  match the current 109‑page layout.

### Images
- All embedded figures extracted, de‑duplicated, and organized by chapter with descriptive
  names; placeholders generated for the two missing figures. See
  **`docs/book_images/`** + `docs/book_images/IMAGE_AUDIT.md`.

### Reproducible build pipeline
- All scripts used for the above live in **`book_build/`** (see `book_build/README.md`).

---

## 2. Reference & citation work (prepared, ready to apply)
The book uses the **Mendeley Cite** add‑in (99 in‑text citations + auto IEEE bibliography).
To avoid breaking it, additions are prepared for the team to apply in Mendeley:
- **`docs/citations/references_to_add.md`** — 14 verified primary references for the actual
  toolchain (ROS 2, slam_toolbox, rf2o, YOLO/YOLOv8, ZeroMQ, A*, complementary filter,
  occupancy grids, SLAM survey, multi‑robot SAR, …) with DOIs.
- **`docs/citations/citation_placement_map.md`** — exactly where to cite each one.
- **`docs/citations/how_to_apply_in_mendeley.md`** — steps + how to make citations clickable.

## 3. Visuals plan (ready to generate)
- **`docs/visuals/visual_plan.md`** — ~25 diagrams/charts/infographics with a shared design
  system and paste‑ready generation prompts (architecture, pipelines, flowcharts, the
  problem→solution infographic, result charts, etc.). Charts list the only allowed real
  values (no fabrication).

---

## 4. Task Board (pending — see GitHub Issues)
| # | Task | Owner area | Artifact / reference |
|---|------|-----------|----------------------|
| 1 | Insert the 14 references into Mendeley + cite per map | Writing | `docs/citations/` |
| 2 | Enable clickable citation hyperlinks + Mendeley refresh | Writing | `docs/citations/how_to_apply_in_mendeley.md` |
| 3 | Generate the visuals (Claude Design), batch 1 first | Design | `docs/visuals/visual_plan.md` |
| 4 | Provide real **Figure 5.1** (SLAM grid vs arena) photo | Testing | `docs/book_images/chapter5/` |
| 5 | Provide real **Figure 5.2** (dashboard gas view) photo | Testing | `docs/book_images/chapter5/` |
| 6 | After figures/citations: re‑run TOC + List page‑number pass, re‑export PDF | Maintainer | `book_build/` (polish_toc / fill_toc_numbers) |
| 7 | (Optional) Standardize British→American spelling | Writing | — |
| 8 | Hardware: Beta **GY‑87 IMU rewire 3.3 V→5 V + resolder** (top demo ticket) | Electronics | `CLAUDE.md` |

> When figures or citations are added, pagination shifts — always finish with task #6.

---

## 5. Notes
- Redundant intermediate `.docx` safety backups (`.prev*`, `.prefmt`, `.pretoc`) and
  regenerable text dumps are **git‑ignored** on purpose (they are auto‑generated, ~9 MB each).
  The build scripts in `book_build/` regenerate everything from the master.
- No secrets are committed (see repository `.gitignore`).
