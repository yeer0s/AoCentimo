"""Document discovery scan — read-only inventory of the household's document folder.

Usage:
    python scripts/scan.py <documents-folder>                     # print inventory report
    python scripts/scan.py <documents-folder> --out <dossier-dir> # also write document-inventory.md/.json there

STRICTLY READ-ONLY on the scanned folder: never moves, renames, modifies, or deletes a
user file. "Sorting" is a categorized REPORT (the assistant and user decide any moves).
Writes only the two inventory files, and only into the --out folder the user designates
(normally the handoff dossier folder). Plain Python stdlib; no network, no subprocess,
no environment access. The inventory lists real filenames (the user's own data, destined
for their own dossier); the skill's no-PII rule governs MEMORY.md, not this deliverable.
"""
import argparse, datetime, hashlib, json, os, sys

EXT_CLASS = {
    ".pdf": "pdf", ".jpg": "image", ".jpeg": "image", ".png": "image", ".heic": "image",
    ".csv": "csv", ".xlsx": "spreadsheet", ".xls": "spreadsheet",
    ".txt": "text", ".md": "text", ".eml": "email", ".msg": "email",
}

# filename heuristics -> suggested dossier category (PT document-naming reality)
CATEGORY_PATTERNS = [
    (("vencimento", "recibo_venc", "salario", "payslip", "folha"), "payslip (Anexo A support)"),
    (("recibo-verde", "recibos_verdes", "rv-", "ato-isolado"), "recibos verdes (Anexo B support)"),
    (("e-fatura", "efatura", "consulta_faturas"), "e-Fatura export"),
    (("renda", "arrendamento", "recibo_renda", "landlord"), "rent (78-E support)"),
    (("farmacia", "clinica", "hospital", "medic", "saude", "receita"), "health (78-C support)"),
    (("propina", "escola", "universidade", "colegio", "creche", "explica"), "education (78-D support)"),
    (("ppr",), "PPR statement"),
    (("donativo", "mecenato", "donation"), "donation receipt"),
    (("juros", "irs_bancario", "declaracao_fiscal", "extrato_anual", "annual_statement"), "bank/broker annual statement"),
    (("extrato", "statement", "movimentos"), "bank statement / movements"),
    (("modelo3", "modelo_3", "irs_20"), "prior Modelo 3 / IRS document"),
    (("lar", "apoio_domiciliario"), "nursing home (art. 84 support)"),
    (("pensao", "alimentos"), "alimony (83-A support)"),
    (("seguro", "apolice", "premio"), "insurance (annual-bill / possible deduction)"),
]

def classify(name):
    low = name.lower().replace(" ", "_")
    for keys, cat in CATEGORY_PATTERNS:
        for k in keys:
            if k in low:
                return cat
    return "unclassified (assistant to review)"

def scan(folder):
    rows, errors = [], []
    for root, dirs, files in os.walk(folder):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, folder)
            try:
                size = os.path.getsize(p)
                h = hashlib.sha256()
                with open(p, "rb") as fh:
                    for chunk in iter(lambda: fh.read(1 << 20), b""):
                        h.update(chunk)
                rows.append({
                    "file": rel.replace(os.sep, "/"),
                    "sha256_16": h.hexdigest()[:16],
                    "size": size,
                    "modified": datetime.date.fromtimestamp(os.path.getmtime(p)).isoformat(),
                    "type": EXT_CLASS.get(os.path.splitext(f)[1].lower(), "other"),
                    "suggested_category": classify(f),
                    "flags": (["zero-byte"] if size == 0 else []),
                })
            except OSError as e:
                errors.append(rel + ": unreadable (" + type(e).__name__ + ")")
    # duplicate detection by content hash
    by_hash = {}
    for r in rows:
        by_hash.setdefault(r["sha256_16"], []).append(r)
    for h, group in by_hash.items():
        if len(group) > 1 and group[0]["size"] > 0:
            for r in group:
                r["flags"].append("duplicate-content x" + str(len(group)))
    return rows, errors

def report_md(folder, rows, errors):
    lines = ["# Document inventory — " + folder,
             "", "_Scanned " + datetime.date.today().isoformat() +
             " (read-only; no files were moved or modified). Categories are SUGGESTIONS "
             "for the assistant and user to confirm — not decisions._", ""]
    by_cat = {}
    for r in rows:
        by_cat.setdefault(r["suggested_category"], []).append(r)
    lines.append("| Suggested category | File | Type | Modified | Size | Flags |")
    lines.append("|---|---|---|---|---|---|")
    for cat in sorted(by_cat):
        for r in sorted(by_cat[cat], key=lambda x: x["file"]):
            lines.append("| " + cat + " | " + r["file"] + " | " + r["type"] + " | " +
                         r["modified"] + " | " + str(r["size"]) + " | " +
                         (", ".join(r["flags"]) or "—") + " |")
    dupes = sum(1 for r in rows if any(f.startswith("duplicate") for f in r["flags"]))
    unclass = sum(1 for r in rows if r["suggested_category"].startswith("unclassified"))
    lines += ["", "**Totals:** " + str(len(rows)) + " files · " + str(dupes) +
              " in duplicate groups · " + str(unclass) + " unclassified · " +
              str(len(errors)) + " unreadable"]
    if errors:
        lines += ["", "## Unreadable"] + ["- " + e for e in errors]
    lines += ["", "_Scanned-image and PDF contents are NOT extracted by this script. Text "
              "extraction happens in the assistant session (or via a user-installed OCR "
              "tool such as ocrmypdf/tesseract for scans) — this inventory is the map, "
              "not the reading._"]
    return "\n".join(lines) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", metavar="DOSSIER_DIR")
    a = ap.parse_args()
    if not os.path.isdir(a.folder):
        print("FAIL  not a folder: " + a.folder); sys.exit(2)
    rows, errors = scan(a.folder)
    md = report_md(a.folder, rows, errors)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        with open(os.path.join(a.out, "document-inventory.json"), "w", encoding="utf-8") as f:
            json.dump({"scanned": datetime.date.today().isoformat(), "root": a.folder,
                       "files": rows, "unreadable": errors}, f, ensure_ascii=False, indent=1)
        with open(os.path.join(a.out, "document-inventory.md"), "w", encoding="utf-8") as f:
            f.write(md)
        print("OK    inventory written to " + a.out + " (" + str(len(rows)) + " files, read-only scan)")
    else:
        print(md)
    sys.exit(0)

main()
