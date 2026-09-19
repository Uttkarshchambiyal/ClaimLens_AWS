"""Build the project guide from Markdown and render every page for visual QA."""
from datetime import datetime
from pathlib import Path
import html
import json
import re
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, Preformatted
from pypdf import PdfReader
import pymupdf

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'output/pdf/claimlens-architecture-and-readiness.pdf'
QA = ROOT / 'tmp/pdfs/claimlens-guide'
WIDTH = A4[0] - 96
INK = colors.HexColor('#202027')
GOLD = colors.HexColor('#92703b')
MUTED = colors.HexColor('#5e626b')
report = json.loads((ROOT / 'docs/verification-results.json').read_text())
stamp = datetime.fromisoformat(report['checkedAt']).astimezone(ZoneInfo('Asia/Kolkata')).strftime('%d %B %Y, %H:%M IST')
styles = {
    'title': ParagraphStyle('title', fontName='Helvetica', fontSize=24, leading=30, textColor=INK, spaceAfter=18),
    'sub': ParagraphStyle('sub', fontName='Helvetica-Bold', fontSize=11, leading=15, textColor=GOLD, spaceBefore=12, spaceAfter=6, keepWithNext=True),
    'body': ParagraphStyle('body', fontName='Helvetica', fontSize=9.5, leading=14, textColor=INK, spaceAfter=7.5),
    'cell': ParagraphStyle('cell', fontName='Helvetica', fontSize=8.5, leading=12.2, textColor=INK),
    'head': ParagraphStyle('head', fontName='Helvetica-Bold', fontSize=8.5, leading=12.2, textColor=colors.white),
    'cell_compact': ParagraphStyle('cell_compact', fontName='Helvetica', fontSize=7.1, leading=8.8, textColor=INK),
    'head_compact': ParagraphStyle('head_compact', fontName='Helvetica-Bold', fontSize=7.1, leading=8.8, textColor=colors.white),
    'code': ParagraphStyle('code', fontName='Courier', fontSize=8, leading=12, textColor=INK, backColor=colors.HexColor('#f4f4f6'), borderPadding=10, spaceBefore=6, spaceAfter=12),
}


def p(text, style='body'):
    return Paragraph(html.escape(text), styles[style])


def table(rows, compact=False):
    head_style = 'head_compact' if compact else 'head'
    cell_style = 'cell_compact' if compact else 'cell'
    body = [[p(cell.strip(), head_style if i == 0 else cell_style) for cell in row] for i, row in enumerate(rows)]
    obj = Table(body, colWidths=[WIDTH * .29, WIDTH * .71], hAlign='LEFT', repeatRows=1)
    obj.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), INK),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f6f6f8'), colors.white]),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 9), ('RIGHTPADDING', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5 if compact else 7), ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5 if compact else 7),
        ('LINEBELOW', (0, 0), (-1, 0), 1, GOLD),
        ('LINEBELOW', (0, 1), (-1, -1), .3, colors.HexColor('#e1e1e6')),
    ]))
    return obj


class Architecture(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 226

    def draw(self):
        c = self.canv
        boxes = [(0, 177, WIDTH, 'REVIEWER / REACT + TYPESCRIPT', 'Sign in, upload, inspect sources, record dispositions'),
                 (0, 119, WIDTH, 'COGNITO > API GATEWAY > API LAMBDA', 'Token validation, tenant authorization, signed URLs and analysis requests'),
                 (0, 61, WIDTH * .48, 'S3 + DYNAMODB', 'Files, extraction and tenant records'),
                 (WIDTH * .52, 61, WIDTH * .48, 'STEP FUNCTIONS STANDARD', 'Asynchronous start / wait / poll'),
                 (0, 3, WIDTH, 'TEXTRACT > PYTHON RULES + BOUNDED BEDROCK', 'Source-linked extraction, deterministic checks, validated semantic comparison')]
        for x, y, w, title, detail in boxes:
            c.setFillColor(colors.HexColor('#f4f4f6'))
            c.setStrokeColor(colors.HexColor('#d9d9df'))
            c.roundRect(x, y, w, 44, 6, stroke=1, fill=1)
            c.setFillColor(INK); c.setFont('Helvetica-Bold', 8.5); c.drawCentredString(x+w/2, y+27, title)
            c.setFillColor(MUTED); c.setFont('Helvetica', 7.8); c.drawCentredString(x+w/2, y+12, detail)
        c.setStrokeColor(GOLD)
        for y in [177, 119, 61]:
            c.line(WIDTH/2, y, WIDTH/2, y-12)
        c.setFont('Helvetica', 7); c.setFillColor(GOLD)


def footer(canvas, doc):
    canvas.setTitle('ClaimLens | Architecture and Hackathon Readiness')
    canvas.setAuthor('ClaimLens project documentation')
    canvas.setStrokeColor(GOLD); canvas.line(48, A4[1]-37, A4[0]-48, A4[1]-37)
    canvas.setFont('Helvetica-Bold', 8); canvas.setFillColor(INK)
    canvas.drawString(48, A4[1]-28, 'CLAIMLENS / PROJECT GUIDE')
    canvas.setFont('Helvetica', 7); canvas.setFillColor(MUTED)
    canvas.drawString(48, 28, 'Assessment: ' + stamp + ' | Synthetic data only')
    canvas.drawRightString(A4[0]-48, 28, f'{doc.page:02}')


def main():
    source = (ROOT / 'docs/claimlens-guide.md').read_text().splitlines()
    story = []
    index = 0
    sections = 0
    while index < len(source):
        line = source[index].strip()
        index += 1
        if not line or line.startswith('# ') or sections == 0 and not line.startswith('## '): continue
        if line.startswith('## '):
            if sections: story.append(PageBreak())
            sections += 1
            story.append(p(line[3:], 'title'))
        elif line.startswith('### '): story.append(p(line[4:], 'sub'))
        elif line == ':::architecture': story.extend([Architecture(), Spacer(1, 8)])
        elif line == ':::verification':
            rows = [['Verification', 'Recorded result']]
            labels = {'dependency_check': 'Python dependency consistency', 'backend_compile': 'Python bytecode compilation', 'backend_tests': 'Python regression tests', 'quality_benchmark': 'Labeled rule quality benchmark', 'large_packet_benchmark': 'Maximum-shape packet benchmark', 'evaluation_artifact': 'Eight-page OCR artifact validation', 'frontend_tests': 'React interaction tests', 'production_build': 'TypeScript + Vite build', 'sam_lint': 'CloudFormation / SAM lint', 'formatting': 'Frontend formatting', 'verifier_syntax': 'AWS verifier shell syntax', 'browser_smoke': 'Desktop/mobile browser workflow'}
            for result in report['checks']:
                count = re.search(r'(\d+) passed', result['output'])
                summary = result['status']
                if count and result['check'] in {'backend_tests', 'frontend_tests'}:
                    if result['check'] == 'frontend_tests':
                        count = re.search(r'Tests\s+(\d+) passed', result['output'])
                    if count: summary += ' - ' + count.group(1) + ' tests'
                rows.append([labels.get(result['check'], result['check']), summary])
            story.extend([table(rows, compact=True), Spacer(1, 8)])
            browser = 'PASS' if report.get('browserSmokeVerified') else 'UNVERIFIED'
            visual = 'PASS' if report.get('browserVisualVerified') else 'UNVERIFIED'
            story.append(p(f'Local browser workflow: {browser}. Manual screenshot review: {visual}. Live AWS services and signed-source behavior remain UNVERIFIED.'))
        elif line.startswith('|'):
            rows = [[value.strip() for value in line.strip('|').split('|')]]
            while index < len(source) and source[index].strip().startswith('|'):
                rows.append([value.strip() for value in source[index].strip().strip('|').split('|')]); index += 1
            story.extend([table(rows), Spacer(1, 8)])
        elif line.startswith('```'):
            code = []
            while index < len(source) and not source[index].startswith('```'):
                code.append(source[index]); index += 1
            index += 1
            story.append(Preformatted('\n'.join(code), styles['code']))
        else: story.append(p(line))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    QA.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(str(OUT), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=56, bottomMargin=49)
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    reader = PdfReader(OUT)
    text = '\n'.join(page.extract_text() for page in reader.pages)
    assert all(f'{i:02} |' in text for i in range(1, 15)), 'Missing guide section'
    assert len(reader.pages) == 14, f'Layout spilled to {len(reader.pages)} pages; inspect and rebalance'
    pdf = pymupdf.open(OUT)
    for i, page in enumerate(pdf):
        page.get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4)).save(QA / f'page-{i+1:02}.png')
    (QA / 'extracted-text.txt').write_text(text)
    print(json.dumps({'pdf': str(OUT), 'pages': len(reader.pages), 'words': len(text.split()), 'renderedPages': len(pdf)}))


if __name__ == '__main__': main()
