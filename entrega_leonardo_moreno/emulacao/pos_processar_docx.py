#!/usr/bin/env python3
"""Pos-processa o .docx gerado pelo pandoc a partir do relatorio HTML.

- tabelas na largura util da pagina, com colunas proporcionais ao conteudo;
- tipos de conteudo das imagens (o pandoc grava "image/png;base64" para data URIs);
- ordem dos filhos de pPr/rPr/tblPr conforme o esquema OOXML e texto solto removido;
- filhos de w:style e de settings.xml na ordem do esquema; w:nsid com 8 digitos hexadecimais.

Uso: pos_processar_docx.py entrada.docx saida.docx [largura_dxa]
"""
import re
import sys
import zipfile

from lxml import etree

SRC, DST = sys.argv[1], sys.argv[2]
TOTAL = int(sys.argv[3]) if len(sys.argv) > 3 else 9864  # A4 com margens de 18 mm
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

ORDER = {
    "pPr": ["pStyle", "keepNext", "keepLines", "pageBreakBefore", "framePr", "widowControl",
            "numPr", "suppressLineNumbers", "pBdr", "shd", "tabs", "suppressAutoHyphens",
            "kinsoku", "wordWrap", "overflowPunct", "topLinePunct", "autoSpaceDE", "autoSpaceDN",
            "bidi", "adjustRightInd", "snapToGrid", "spacing", "ind", "contextualSpacing",
            "mirrorIndents", "suppressOverlap", "jc", "textDirection", "textAlignment",
            "textboxTightWrap", "outlineLvl", "divId", "cnfStyle", "rPr", "sectPr", "pPrChange"],
    "rPr": ["rStyle", "rFonts", "b", "bCs", "i", "iCs", "caps", "smallCaps", "strike", "dstrike",
            "outline", "shadow", "emboss", "imprint", "noProof", "snapToGrid", "vanish",
            "webHidden", "color", "spacing", "w", "kern", "position", "sz", "szCs", "highlight",
            "u", "effect", "bdr", "shd", "fitText", "vertAlign", "rtl", "cs", "em", "lang",
            "eastAsianLayout", "specVanish", "oMath"],
    "tblPr": ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
              "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders",
              "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"],
    "style": ["name", "aliases", "basedOn", "next", "link", "autoRedefine", "hidden", "uiPriority",
              "semiHidden", "unhideWhenUsed", "qFormat", "locked", "personal", "personalCompose",
              "personalReply", "rsid", "pPr", "rPr", "tblPr", "trPr", "tcPr", "tblStylePr"],
}
SETTINGS = ("writeProtection view zoom removePersonalInformation removeDateAndTime "
            "doNotDisplayPageBoundaries displayBackgroundShape printPostScriptOverText "
            "printFractionalCharacterWidth printFormsData embedTrueTypeFonts embedSystemFonts "
            "saveSubsetFonts saveFormsData mirrorMargins alignBordersAndEdges "
            "bordersDoNotSurroundHeader bordersDoNotSurroundFooter gutterAtTop hideSpellingErrors "
            "hideGrammaticalErrors activeWritingStyle proofState formsDesign attachedTemplate "
            "linkStyles stylePaneFormatFilter stylePaneSortMethod documentType mailMerge "
            "revisionView trackRevisions doNotTrackMoves doNotTrackFormatting documentProtection "
            "autoFormatOverride styleLockTheme styleLockQFSet defaultTabStop autoHyphenation "
            "consecutiveHyphenLimit hyphenationZone doNotHyphenateCaps showEnvelope summaryLength "
            "clickAndTypeStyle defaultTableStyle evenAndOddHeaders bookFoldRevPrinting "
            "bookFoldPrinting bookFoldPrintingSheets drawingGridHorizontalSpacing "
            "drawingGridVerticalSpacing displayHorizontalDrawingGridEvery "
            "displayVerticalDrawingGridEvery doNotUseMarginsForDrawingGridOrigin "
            "drawingGridHorizontalOrigin drawingGridVerticalOrigin doNotShadeFormData "
            "noPunctuationKerning characterSpacingControl printTwoOnOne strictFirstAndLastChars "
            "noLineBreaksAfter noLineBreaksBefore savePreviewPicture doNotValidateAgainstSchema "
            "saveInvalidXml ignoreMixedContent alwaysShowPlaceholderText doNotDemarcateInvalidXml "
            "saveXmlDataOnly useXSLTWhenSaving saveThroughXslt showXMLTags "
            "alwaysMergeEmptyNamespace updateFields hdrShapeDefaults footnotePr endnotePr compat "
            "docVars rsids mathPr attachedSchema themeFontLang clrSchemeMapping "
            "doNotIncludeSubdocsInStats doNotAutoCompressPictures forceUpgrade captions "
            "readModeInkLockDown smartTagType schemaLibrary shapeDefaults doNotEmbedSmartTags "
            "decimalSymbol listSeparator").split()


def sort_children(el, order):
    key = {n: i for i, n in enumerate(order)}
    kids = [k for k in el if isinstance(k.tag, str)]
    for k in list(el):
        el.remove(k)
    el.text = None
    kids.sort(key=lambda k: key.get(etree.QName(k).localname, len(order)))
    for k in kids:
        k.tail = None
        el.append(k)


def reorder(root):
    for tag, order in ORDER.items():
        for el in root.iter(W + tag):
            sort_children(el, order)


def cell_text(tc):
    return "".join(t.text or "" for t in tc.iter(W + "t"))


def fix_tables(root):
    for tbl in root.iter(W + "tbl"):
        rows = tbl.findall(W + "tr")
        cells = [r.findall(W + "tc") for r in rows]
        ncol = max(len(c) for c in cells)
        weight = [6.0] * ncol
        for row in cells:
            for j, tc in enumerate(row):
                text = cell_text(tc)
                longest = max((len(x) for x in text.split()), default=0)
                weight[j] = max(weight[j], min(len(text), 70) * 0.6 + longest * 0.8)
        widths = [int(TOTAL * w / sum(weight)) for w in weight]
        widths[-1] += TOTAL - sum(widths)
        grid = tbl.find(W + "tblGrid")
        for g in list(grid):
            grid.remove(g)
        for w in widths:
            etree.SubElement(grid, W + "gridCol", {W + "w": str(w)})
        tblw = tbl.find(W + "tblPr/" + W + "tblW")
        tblw.set(W + "type", "dxa")
        tblw.set(W + "w", str(TOTAL))
        for row in cells:
            for j, tc in enumerate(row):
                tcpr = tc.find(W + "tcPr")
                if tcpr is None:
                    tcpr = etree.Element(W + "tcPr")
                    tc.insert(0, tcpr)
                for old in tcpr.findall(W + "tcW"):
                    tcpr.remove(old)
                tcpr.insert(0, etree.Element(W + "tcW", {W + "w": str(widths[j]), W + "type": "dxa"}))


def xml_bytes(root):
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


zin = zipfile.ZipFile(SRC)
zout = zipfile.ZipFile(DST, "w", zipfile.ZIP_DEFLATED)
for item in zin.infolist():
    data = zin.read(item.filename)
    name = item.filename
    if name == "[Content_Types].xml":
        txt = data.decode("utf-8").replace('ContentType="image/png;base64"', 'ContentType="image/png"')
        if 'Extension="png"' not in txt:
            txt = txt.replace("<Default Extension=\"xml\"",
                              '<Default Extension="png" ContentType="image/png" /><Default Extension="xml"', 1)
        data = txt.encode("utf-8")
    elif name in ("word/document.xml", "word/styles.xml"):
        root = etree.fromstring(data)
        if name == "word/document.xml":
            fix_tables(root)
        reorder(root)
        data = xml_bytes(root)
    elif name == "word/settings.xml":
        root = etree.fromstring(data)
        sort_children(root, SETTINGS)
        data = xml_bytes(root)
    elif name == "word/numbering.xml":
        txt = data.decode("utf-8")
        txt = re.sub(r'(<w:nsid w:val=")([0-9A-Fa-f]+)(")',
                     lambda m: m.group(1) + m.group(2).upper().rjust(8, "0")[-8:] + m.group(3), txt)
        data = txt.encode("utf-8")
    zout.writestr(item, data)
zout.close()
print("ok", DST)
