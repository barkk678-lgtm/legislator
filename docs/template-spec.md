# מפרט תבנית החקיקה — תוצר משימה 0

הונדס לאחור משני קובצי `.docx` אמיתיים שהוגשו לכנסת ה-25, שנוצרו בתבנית
`HakikaV16`. כל הערכים כאן הם מדידות מהקבצים, לא השערות.

---

## 1. מבנה החבילה

```
[Content_Types].xml
_rels/.rels
customXml/item1-4.xml + itemProps + _rels   ← מטא-דאטה של סנהדרין. לשמר כפי שהוא.
docProps/{app,core,custom}.xml
word/document.xml
word/styles.xml          ← 69 סגנונות. זה הנכס. להעתיק as-is.
word/footnotes.xml       ← מראי מקום ברשומות
word/footer1.xml         ← מספר עמוד ממורכז
word/footer2.xml
word/settings.xml, numbering.xml, fontTable.xml, theme/theme1.xml, webSettings.xml
```

**החלטה:** לא לבנות docx מאפס עם `python-docx`. לקחת את החבילה הקיימת כשלד,
להחליף רק את `word/document.xml` ו-`word/footnotes.xml`, ולשמר את כל השאר בייטים.
כך `styles.xml` המקורי נשמר בדיוק ואין סיכון של סטייה מהתבנית.

---

## 2. הגדרות מסמך

### docDefaults
```xml
<w:rFonts w:ascii="Times New Roman" w:eastAsia="MS Mincho"
          w:hAnsi="Times New Roman" w:cs="Times New Roman"/>
<w:lang w:val="en-US" w:eastAsia="en-US" w:bidi="he-IL"/>
```

### sectPr
```xml
<w:pgSz w:w="11907" w:h="16840" w:code="9"/>            <!-- A4 -->
<w:pgMar w:top="1701" w:right="1134" w:bottom="1417" w:left="1134"
         w:header="680" w:footer="680" w:gutter="0"/>
<w:cols w:space="720"/>
<w:noEndnote/>
<w:titlePg/>
<w:bidi/>          <!-- RTL ברמת המקטע -->
<w:rtlGutter/>
<w:docGrid w:linePitch="326"/>
```

**כיווניות:** אין `<w:bidi/>` ברמת הפסקה באף מקום. ה-RTL מגיע משלושה מקומות:
`<w:bidi/>` ב-sectPr, `<w:bidiVisual/>` ב-tblPr, ו-`<w:rtl/>` בכל `rPr` של כל run.
**כל run עברי חייב `<w:rFonts w:hint="cs"/><w:rtl/>`.** run שמכיל רק en-dash (`–`)
מקבל `<w:rtl/>` בלי `hint="cs"`.

---

## 3. טבלת החקיקה — המבנה הקריטי

```xml
<w:tblPr>
  <w:bidiVisual/>
  <w:tblW w:w="9638" w:type="dxa"/>
  <w:tblLayout w:type="fixed"/>
  <w:tblCellMar>
    <w:top w:w="57"/><w:left w:w="0"/><w:bottom w:w="57"/><w:right w:w="0"/>
  </w:tblCellMar>
  <w:tblLook w:val="01E0" .../>
</w:tblPr>
<w:tblGrid>
  <w:gridCol w:w="1871"/>   <!-- עמודה 0: כותרת שוליים -->
  <w:gridCol w:w="624"/>    <!-- עמודה 1: מספר הסעיף -->
  <w:gridCol w:w="624"/>    <!-- עמודות 2-6: חמש רמות הזחה -->
  <w:gridCol w:w="624"/>
  <w:gridCol w:w="624"/>
  <w:gridCol w:w="624"/>
  <w:gridCol w:w="624"/>
  <w:gridCol w:w="4023"/>   <!-- עמודה 7: תוכן ברמה העמוקה ביותר -->
</w:tblGrid>
```

סכום: 1871 + 6×624 + 4023 = 9638. אין גבולות. `<w:cantSplit/>` בכל שורה.

### נוסחת ההזחה — זה הלב של הרנדרר

הזחה מיוצגת על ידי **מספר תאים ריקים**, לא על ידי `w:ind`.
לעומק `d` (0 = גוף סעיף ראשי, 5 = העמוק ביותר):

| רכיב | ערך |
|---|---|
| תא 0 | `w=1871`, סגנון `TableSideHeading` |
| תא 1 | `w=624`, סגנון `TableText` (מספר הסעיף, או ריק) |
| תאי הזחה | `d` תאים של `w=624` סגנון `TableText`, ריקים |
| תא התוכן | `gridSpan = 6 - d`, `w = 4023 + 624 × (5 - d)` |

בדיקה: `d=0` → span=6, w=7143. `d=5` → span=1, w=4023. תואם לקבצים.

### דפוס "סעיף פנימי" (סעיף חדש בתוך מרכאות עם כותרת שוליים משלו)

כשמוסיפים סעיף שלם (`אחרי סעיף 4 לחוק העיקרי יבוא:`) השורה הבאה שונה:

| תא | רוחב | span | סגנון | תוכן |
|---|---|---|---|---|
| 0 | 1871 | 1 | `TableSideHeading` | ריק |
| 1 | 624 | 1 | `TableText` | ריק |
| 2 | 1872 | **3** | `TableInnerSideHeading` | כותרת השוליים של הסעיף החדש |
| 3 | 624 | 1 | `TableText` | `4א.` |
| 4 | 4647 | **2** | `TableBlock` | גוף הסעיף |

זהו — הטבלה מכילה "טבלה בתוך טבלה" לוגית, בלי `tbl` מקונן.

### סגנונות פסקה בתוך התאים

| סגנון | תפקיד |
|---|---|
| `TableSideHeading` | כותרת שוליים של סעיף בהצעה ("תיקון סעיף 1") |
| `TableText` | מספר סעיף + כל תא הזחה ריק |
| `TableBlock` | גוף טקסט, `jc=both` |
| `TableBlockOutdent` | טקסט מצוטט עם תלייה: `ind left=624 hanging=624` |
| `TableHead` | כותרת פרק/סימן, ממורכזת, מודגשת |
| `TableInnerSideHeading` | כותרת שוליים של סעיף מצוטט |
| `TableText2`, `TableHead2`, `TableSideHeading2` | וריאנטים ללא `outlineLvl` |

`TableBlockOutdent` הוא הסגנון לכל שורה שמתחילה במרכאות ומצטטת נוסח חדש —
הוא נותן את התלייה שמיישרת את השורה השנייה מתחת לראשונה.

### מספור פסקאות `(1)`, `(א)`

**אינו numbering אוטומטי.** זה טקסט מילולי בתוך הפסקה, ואחריו `<w:tab/>`,
עם `tabs` מוגדרים ב-`pPr` ב-624 וב-1247:

```xml
<w:pPr><w:pStyle w:val="TableBlock"/>
  <w:tabs><w:tab w:val="left" w:pos="624"/><w:tab w:val="left" w:pos="1247"/></w:tabs>
</w:pPr>
<w:r><w:rPr><w:rFonts w:hint="cs"/><w:rtl/></w:rPr><w:t>(1)</w:t></w:r>
<w:r><w:rPr><w:rFonts w:hint="cs"/><w:rtl/></w:rPr><w:tab/><w:t>פעילותו...</w:t></w:r>
```

זה אומר שהרנדרר שולט במספור בעצמו — טוב, כי המספור המשפטי (`3א`, `34כד`)
ממילא לא ניתן לביטוי ב-`numbering.xml`.

---

## 4. מבנה המסמך מסביב לטבלה

לפי סדר, מתוך שני הקבצים:

| # | סגנון | תוכן |
|---|---|---|
| 1 | `Normal` | `מספר פנימי: 2233987` — מזהה סנהדרין |
| 2 | `HeadHatzaotHok` | `הכנסת העשרים וחמש` |
| 3 | `Normal` | ריק |
| 4 | `David` | `יוזם:` \t `חבר הכנסת` \t `{שם}` |
| 5 | `David` | קו: 46 תווי `_` |
| 6 | `David` | `פ/6158/25` |
| 7 | `David` | ריק |
| 8 | `HeadHatzaotHok` | **שם הצעת החוק** |
| 9 | — | **טבלת החקיקה** |
| 10 | `HeadDivreiHesber` | `דברי הסבר` |
| 11+ | `Hesber` | פסקאות דברי ההסבר |
| | `Normal` | `--------------------------------` |
| | `Normal` | `הוגשה ליו"ר הכנסת והסגנים` |
| | `Normal` | `והונחה על שולחן הכנסת ביום` |
| | `Normal` | `כ"ז בתמוז התשפ"ה (23.07.2025)` |

סגנונות דברי הסבר נוספים שקיימים ויש להשתמש בהם בהצעות מורכבות:
`HesberHeading` (פסקה שמתחילה במספר סעיף, מודגשת), `Hesber1st` (פסקה ראשונה,
`firstLine=0`), `HesberWriters` (שמות היוזמים).

`Hesber` = `ind left=0 firstLine=340`, Arial, `sz=20 / szCs=26`.

---

## 5. הערות שוליים

כל אזכור ראשון של חוק אחר → הערת שוליים. המבנה ב-`footnotes.xml`:

```xml
<w:footnote w:id="2">
  <w:p><w:pPr><w:pStyle w:val="a4"/><w:rPr><w:rtl/></w:rPr></w:pPr>
    <w:r><w:rPr><w:rStyle w:val="a5"/></w:rPr><w:footnoteRef/></w:r>
    <w:r><w:rPr><w:rtl/></w:rPr><w:t xml:space="preserve"> </w:t></w:r>
    <w:r><w:rPr><w:rFonts w:hint="cs"/><w:rtl/></w:rPr>
        <w:t xml:space="preserve">ס"ח התשע"ו, עמ' 898. </w:t></w:r>
  </w:p>
</w:footnote>
```

`a4` = footnote text, `a5` = footnote reference. מזהים 0 ו-1 שמורים
(separator / continuationSeparator) — הערות אמיתיות מתחילות מ-2.

**הפורמט:** `ס"ח התשע"ו, עמ' 898.` — עם נקודה ורווח בסוף.

---

## 6. תווים — רשימת בדיקה

| נכון | לא נכון | הערה |
|---|---|---|
| `התשל"ז–1977` | `התשל"ז-1977` | en-dash U+2013, בתוך run נפרד ללא `hint="cs"` |
| `(להלן – החוק העיקרי)` | `(להלן - ...)` | en-dash מוקף רווחים |
| `"` (U+0022) | `״` (U+05F4) | הקבצים משתמשים במרכאה כפולה רגילה |
| `עמ'` (U+0027) | `עמ׳` | גרש רגיל |

`xml:space="preserve"` חובה בכל `<w:t>` שמתחיל או מסתיים ברווח. זו התקלה
הכי שכיחה ברנדרר שנכתב ידנית.

---

## 7. מה שעדיין לא ידוע

- **`footer2.xml`** — קיים ומקושר, לא נבדק תוכנו.
- **`customXml/item1-4.xml`** — ככל הנראה מטא-דאטה של סנהדרין. יש לבדוק אם
  סנהדרין דורשת שדות מסוימים בהעלאה, או שהיא מתעלמת מהם.
- **התבנית המקורית מ-`tavnit.justice.gov.il`** — עדיין שווה להשיג, כי היא
  עשויה להכיל סגנונות שלא בשימוש בשני הקבצים האלה (למשל לתזכירים).
- **פורמט הצעת חוק ממשלתית** — שונה. הסגנונות `Cover1-Reshumot`,
  `Cover2-HatzaotHok`, `Cover3-Haknesset`, `Cover4-Date`, `TOC`, `TOCpg`,
  `HeadMitparsemetBaze` קיימים ב-`styles.xml` ומיועדים לפרסום ברשומות.
  זה אומר שאותו `styles.xml` משרת גם את הצעות הממשלה — בשורה טובה לשלב ב'.
