# -*- coding: utf-8 -*-
"""Stage 2: export PDF, compute the real page number for every TOC/LoF/LoT entry
(read from each target page's own footer), and fill the placeholders."""
import re, os, docx
import win32com.client as win32

F = os.path.abspath("Swarm_Robot_System_Graduation_Book_CORRECTED.docx")
PDF = os.path.abspath("Swarm_Robot_System_Graduation_Book_CORRECTED.pdf")
PH = "§"

def export():
    w = win32.DispatchEx("Word.Application"); w.Visible = False; w.DisplayAlerts = 0
    try:
        doc = w.Documents.Open(F, ReadOnly=True)
        doc.ExportAsFixedFormat(OutputFileName=PDF, ExportFormat=17, OpenAfterExport=False,
                                OptimizeFor=0, CreateBookmarks=1)
        doc.Close(False)
    finally:
        w.Quit()

export()
import fitz
pdf = fitz.open(PDF)
ptext = [pdf[i].get_text() for i in range(pdf.page_count)]
plow = [t.lower() for t in ptext]

def footer_num(i):
    ms = re.findall(r"(\d+)\s*\|\s*P", ptext[i])
    return int(ms[-1]) if ms else i + 1

def pages_with(key):
    k = key.lower()
    return [i for i in range(len(plow)) if k in plow[i]]

def page_of(key, mode="max"):
    hits = pages_with(key)
    if not hits: return None
    return footer_num(max(hits) if mode == "max" else min(hits))

FM = {
    "acknowledgement": ("acknowledgement", "min"),
    "abstract": ("abstract", "min"),
    "table of contents": ("table of contents", "min"),
    "list of figures": ("figure 2.1", "min"),     # page of first LoF item = the LoF page
    "list of tables": ("table 1.1", "min"),        # page of first LoT item = the LoT page
    "list of abbreviations and acronyms": ("list of abbreviation", "min"),
}

def target_page(label):
    lab = label.strip()
    low = lab.lower()
    if low in FM:
        key, mode = FM[low]; return page_of(key, mode)
    if re.match(r"^(Chapter|CHAPTER)\s+\d", lab):
        return page_of(lab, "max")
    m = re.match(r"^(Figure\s+\d+\.\d+)", lab)
    if m: return page_of(m.group(1), "max")
    m = re.match(r"^(Table\s+\d+\.\d+)", lab)
    if m: return page_of(m.group(1), "max")
    if re.match(r"^\d+(\.\d+)*\s", lab):           # section / sub-section
        return page_of(lab, "max")
    return page_of(lab, "max")

# ---- fill placeholders ----
d = docx.Document(F)
filled, missing = 0, []
for p in d.paragraphs:
    if PH not in p.text:
        continue
    label = p.text.split("\t")[0].strip()
    pg = target_page(label)
    for r in p.runs:
        if PH in r.text:
            r.text = r.text.replace(PH, str(pg) if pg else "")
    if pg:
        filled += 1
    else:
        missing.append(label[:45])

d.save(F)
print("filled:", filled, "| unresolved:", len(missing))
for m in missing: print("   no page found:", m)
export()
print("PDF re-exported:", os.path.getsize(PDF))
