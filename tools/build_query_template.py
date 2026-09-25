"""בונה את reference/query-template.docx מתוך שאילתה אמיתית (ש1, 25.9.2026).

**התבנית היא שאילתה אמיתית של הכנסת, לא שחזור שלה.** הסגנונות (caption,
heading 1-3), המספור (numId 3, "%1."), הגופנים (David לעברית), סמל
המדינה וגודל העמוד - כולם מגיעים כמות שהם מ-25_pq_5753896.docx.
query_doc.py מחליף רק את הגוף, מ"הכנסת" והלאה.

מה מוסר: customXml (מטא-נתונים של SharePoint), [trash], docProps/custom.xml,
ושמות העורכים והארגון ב-docProps.

**ראיה לכותרת:** ב-app.xml של הדוגמה, שם הסימנייה QUR_Type הוא
"<סוג שאילתה (אם לא רגילה)>" - כלומר "שאילתה" לבדה לרגילה,
ו"שאילתה דחופה"/"שאילתה ישירה" לאחרות.

הרצה: python3 tools/build_query_template.py
"""
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reference" / "sheiltot" / "25_pq_5753896.docx"
OUT = ROOT / "reference" / "query-template.docx"

CORE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        '<dc:title>שאילתה</dc:title><dc:creator></dc:creator><cp:lastModifiedBy></cp:lastModifiedBy>'
        '<cp:revision>1</cp:revision></cp:coreProperties>')


def _dropped(name: str) -> bool:
    return (name.startswith("customXml/") or name.startswith("[trash]/")
            or name == "docProps/custom.xml")


def main() -> None:
    src = zipfile.ZipFile(SOURCE)
    with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            if _dropped(item.filename):
                continue
            data = src.read(item.filename)
            if item.filename == "[Content_Types].xml":
                text = data.decode()
                text = re.sub(r'<Override PartName="/customXml/[^"]+"[^>]*/>', "", text)
                text = re.sub(r'<Override PartName="/docProps/custom.xml"[^>]*/>', "", text)
                data = text.encode()
            elif item.filename == "_rels/.rels":
                data = re.sub(r'<Relationship [^>]*Target="docProps/custom.xml"/>', "",
                              data.decode()).encode()
            elif item.filename == "word/_rels/document.xml.rels":
                data = re.sub(r'<Relationship [^>]*Target="\.\./customXml/[^"]+"/>', "",
                              data.decode()).encode()
            elif item.filename == "docProps/core.xml":
                data = CORE.encode()
            elif item.filename == "docProps/app.xml":
                data = re.sub(r"<Company>[^<]*</Company>", "<Company></Company>",
                              data.decode()).encode()
            out.writestr(item.filename, data)
    print(f"נכתב {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
