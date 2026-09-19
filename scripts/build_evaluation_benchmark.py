#!/usr/bin/env python3
"""Build a synthetic, multi-layout PDF for live ClaimLens OCR evaluation."""
from __future__ import annotations

from pathlib import Path
from html import escape

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "claimlens-evaluation-benchmark.pdf"
TMP = ROOT / "tmp" / "pdfs" / "claimlens-evaluation"
WIDTH, HEIGHT = A4
INK = HexColor("#17202a")
GOLD = HexColor("#b68a3a")


def heading(pdf, title, subtitle):
    pdf.setFillColor(INK)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(44, HEIGHT - 48, title)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(HexColor("#566573"))
    pdf.drawString(44, HEIGHT - 65, subtitle)
    pdf.setStrokeColor(GOLD)
    pdf.setLineWidth(1.5)
    pdf.line(44, HEIGHT - 75, WIDTH - 44, HEIGHT - 75)


def footer(pdf, page, category):
    pdf.setFillColor(HexColor("#707b7c"))
    pdf.setFont("Helvetica", 8)
    pdf.drawString(44, 25, f"ClaimLens synthetic OCR benchmark - {category}")
    pdf.drawRightString(WIDTH - 44, 25, f"Page {page}")


def key_values(pdf, pairs, top=HEIGHT - 105):
    y = top
    for label, value in pairs:
        pdf.setStrokeColor(HexColor("#d5d8dc"))
        pdf.setFillColor(HexColor("#f8f9f9"))
        pdf.roundRect(44, y - 18, WIDTH - 88, 27, 4, fill=1, stroke=1)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(55, y - 8, label)
        pdf.setFont("Helvetica", 10)
        pdf.drawString(205, y - 8, value)
        y -= 35
    return y


def table(pdf, rows, top):
    x0, x1, x2 = 44, 390, WIDTH - 44
    row_height = 29
    y = top
    for index, (description, amount) in enumerate(rows):
        fill = HexColor("#f2f4f4") if index == 0 else white
        pdf.setFillColor(fill)
        pdf.setStrokeColor(HexColor("#bdc3c7"))
        pdf.rect(x0, y - row_height, x2 - x0, row_height, fill=1, stroke=1)
        pdf.line(x1, y, x1, y - row_height)
        pdf.setFillColor(INK)
        pdf.setFont("Helvetica-Bold" if index == 0 else "Helvetica", 9)
        pdf.drawString(x0 + 9, y - 19, description)
        pdf.drawRightString(x2 - 9, y - 19, amount)
        y -= row_height
    return y


def bitmap_page(lines, path, *, angle=0, blur=0, contrast=1, font_path=None):
    image = Image.new("RGB", (1600, 2200), "white")
    draw = ImageDraw.Draw(image)
    default_font = font_path or "/System/Library/Fonts/Supplemental/Arial.ttf"
    try:
        title_font = ImageFont.truetype(default_font, 48)
        body_font = ImageFont.truetype(default_font, 38)
    except OSError:
        title_font = ImageFont.load_default()
        body_font = ImageFont.load_default()
    draw.rectangle((80, 80, 1520, 2120), outline=(120, 120, 120), width=3)
    draw.text((120, 125), lines[0], fill=(30, 30, 30), font=title_font)
    y = 260
    for line in lines[1:]:
        draw.line((120, y + 62, 1480, y + 62), fill=(210, 210, 210), width=2)
        draw.text((130, y), line, fill=(55, 55, 55), font=body_font)
        y += 115
    if contrast != 1:
        image = ImageEnhance.Contrast(image).enhance(contrast)
    if blur:
        image = image.filter(ImageFilter.GaussianBlur(blur))
    if angle:
        image = image.rotate(angle, resample=Image.Resampling.BICUBIC, expand=False, fillcolor="white")
    image.save(path, quality=86)


def browser_unicode_page(lines, path):
    """Use Chromium shaping for scripts that Pillow cannot render correctly here."""
    from playwright.sync_api import sync_playwright

    rows = "".join(f"<div>{escape(line)}</div>" for line in lines[1:])
    html = f"""<!doctype html><html lang="hi"><meta charset="utf-8"><style>
      * {{ box-sizing: border-box; }}
      body {{ margin: 0; width: 1600px; height: 2200px; padding: 80px; background: white;
              color: #20252b; font-family: 'Noto Sans Devanagari', 'Devanagari Sangam MN', Arial, sans-serif; }}
      main {{ height: 2040px; border: 3px solid #777; padding: 44px; }}
      h1 {{ margin: 0 0 50px; font-size: 48px; font-weight: 700; }}
      div {{ padding: 22px 10px; border-bottom: 2px solid #ddd; font-size: 38px; }}
    </style><main><h1>{escape(lines[0])}</h1>{rows}</main></html>"""
    with sync_playwright() as driver:
        browser = driver.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 2200}, device_scale_factor=1)
        page.set_content(html)
        page.screenshot(path=str(path), full_page=True)
        browser.close()


def image_sheet(pdf, image_path, title, subtitle, page, category):
    heading(pdf, title, subtitle)
    pdf.drawImage(str(image_path), 54, 55, width=WIDTH - 108, height=HEIGHT - 150, preserveAspectRatio=True, anchor="c")
    footer(pdf, page, category)
    pdf.showPage()


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    TMP.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUTPUT), pagesize=A4, pageCompression=1)
    pdf.setTitle("ClaimLens Synthetic Evaluation Benchmark")
    pdf.setAuthor("ClaimLens")

    heading(pdf, "Synthetic Itemized Bill", "Clear digital layout - baseline extraction")
    y = key_values(pdf, [
        ("Invoice Number", "INV-BENCH-1001"), ("Hospital ID", "HOSP-42"),
        ("Patient ID", "MEM-2048"), ("Admission Date", "2026-09-10"),
        ("Discharge Date", "2026-09-12"),
    ])
    table(pdf, [("Description", "Amount"), ("Room charges", "600.00"), ("Pharmacy", "400.00")], y - 5)
    footer(pdf, 1, "clear-layout")
    pdf.showPage()

    heading(pdf, "Itemized Bill - Continuation", "Repeated table header on a second page")
    table(pdf, [("Description", "Amount"), ("Laboratory services", "500.00"), ("Sub total", "1500.00")], HEIGHT - 115)
    footer(pdf, 2, "multi-page-table")
    pdf.showPage()

    heading(pdf, "Tax and Adjustment Summary", "Explicit GST, discount and signed round-off")
    y = table(pdf, [
        ("Description", "Amount"), ("Base services", "1000.00"), ("GST", "180.00"),
        ("Discount", "50.00"), ("Round off", "-0.50"), ("Grand total", "1129.50"),
    ], HEIGHT - 115)
    key_values(pdf, [("Invoice Total", "1129.50")], y - 20)
    footer(pdf, 3, "adjustments")
    pdf.showPage()

    hindi = TMP / "hindi-form.png"
    browser_unicode_page([
        "काल्पनिक अस्पताल बिल / Synthetic Hospital Bill", "बिल संख्या: INV-HI-42", "अस्पताल आईडी: HOSP-HI",
        "रोगी आईडी: MEM-HI-42", "भर्ती तिथि: 18/09/2026", "डिस्चार्ज तिथि: 19/09/2026", "कुल राशि: 1129.50",
    ], hindi)
    image_sheet(pdf, hindi, "Bilingual Hindi-English Form", "Printed multilingual labels and Latin identifiers", 4, "multilingual")

    heading(pdf, "Procedure Terminology Variants", "Abbreviations and related clinical terminology")
    table(pdf, [
        ("Description", "Amount"), ("TKR surgery package", "88000.00"),
        ("MRI knee", "12000.00"), ("Orthopaedic prosthesis", "72000.00"),
    ], HEIGHT - 115)
    footer(pdf, 5, "terminology")
    pdf.showPage()

    rotated = TMP / "rotated-scan.jpg"
    bitmap_page(["Scanned Claim Page", "Invoice Number: INV-ROT-7", "Patient ID: MEM-ROT", "Invoice Total: 1500.00"], rotated, angle=4)
    image_sheet(pdf, rotated, "Rotated Scan", "Four-degree rotation with preserved readable content", 6, "rotated")

    blurry = TMP / "blurry-scan.jpg"
    bitmap_page(["Low Contrast Scan", "Invoice Number: INV-BLUR-8", "Patient ID: MEM-BLUR", "Invoice Total: 1750.00"], blurry, blur=1.8, contrast=.42)
    image_sheet(pdf, blurry, "Blurred and Low-Contrast Scan", "Designed to exercise the low-confidence review gate", 7, "low-confidence")

    handwriting = TMP / "handwritten-note.jpg"
    script_font = "/System/Library/Fonts/Supplemental/Apple Chancery.ttf"
    bitmap_page(["Handwritten-style intake note", "Invoice Number: INV-NOTE-9", "Patient ID: MEM-NOTE", "Invoice Total: 900.00"], handwriting, angle=-2, blur=.35, font_path=script_font)
    image_sheet(pdf, handwriting, "Handwritten-Style Note", "Synthetic cursive bitmap - accuracy must be measured, never assumed", 8, "handwritten-style")

    pdf.save()
    print(OUTPUT)


if __name__ == "__main__":
    main()
