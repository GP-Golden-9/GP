# -*- coding: utf-8 -*-
"""Write the 24 humanized parts back into the .docx by paragraph position.
Tables, numbers, captions, figures, headings, references are untouched.
Light cleanup: re-space '25cm'->'25 cm', British 'metre'->'meter', fix 'MQ-5sensor'.
"""
import json, re, shutil, docx

F = "Swarm_Robot_System_Graduation_Book_CORRECTED.docx"
shutil.copyfile(F, "Swarm_Robot_System_Graduation_Book_CORRECTED.prev4.docx")
pmap = json.load(open("docs/humanize_chunks/_pmap.json"))
d = docx.Document(F)


def clean(t):
    t = re.sub(r"\s*\n\s*", " ", t.strip())        # flatten any internal newline
    t = re.sub(r"(\d)\s*cm\b", r"\1 cm", t)         # 25cm -> 25 cm
    t = re.sub(r"\bmetres\b", "meters", t)
    t = re.sub(r"\bmetre\b", "meter", t)
    t = t.replace("MQ-5sensor", "MQ-5 sensor")
    return t


def set_par(idx, text):
    p = d.paragraphs[idx]
    if p.runs:
        r0 = p.runs[0]
        r0.text = text
        r0.bold = False        # humanized body prose -> plain (avoid inheriting a bold run-in label)
        r0.italic = False
        for r in p.runs[1:]:
            r.text = ""
    else:
        p.add_run(text)


written, mism = 0, []
for nn in sorted(pmap):
    ids = pmap[nn]
    raw = open("docs/humanize_chunks/part_%s_done.txt" % nn, encoding="utf-8").read()
    blocks = [b for b in raw.replace("\r\n", "\n").split("\n\n") if b.strip()]
    if len(blocks) != len(ids):
        mism.append((nn, len(blocks), len(ids)))
        continue
    for j, b in enumerate(blocks):
        set_par(ids[j], clean(b))
        written += 1

if mism:
    print("COUNT MISMATCH (NOT written):", mism)
else:
    d.save(F)
    print("Reassembled %d humanized paragraphs into %s" % (written, F))
