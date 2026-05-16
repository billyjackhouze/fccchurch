"""
PDF Reports — Member Directory & Year-End Giving Statements
  GET /api/reports/directory-pdf?status=Active&fmt=grid    (admin)
  GET /api/reports/giving-statement/{member_id}?year=2025  (admin)
  GET /api/reports/giving-statements-all?year=2025         (admin, zip of all members)
"""
import io
import os
import zipfile
import traceback
from decimal import Decimal
from datetime import date as dt_date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import extract
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.routers.auth import require_admin

router = APIRouter(prefix="/api/reports", tags=["Reports"])

NAVY   = "#1E3A5F"
GOLD   = "#B8860B"
GRAY   = "#6B7280"
LIGHT  = "#F9FAFB"
BORDER = "#E5E7EB"


def _photo_path(filename):
    if not filename:
        return None
    p = os.path.join(os.path.dirname(__file__), "..", "..", "static", "photos", filename)
    p = os.path.normpath(p)
    return p if os.path.exists(p) else None


def _hr_table(color, thickness=1.5, space=10):
    """Thin horizontal rule as a Table (avoids HRFlowable version issues)."""
    from reportlab.platypus import Table, TableStyle
    from reportlab.lib.units import inch
    t = Table([['']], colWidths=[6.5 * inch])
    t.setStyle(TableStyle([
        ('LINEBELOW',      (0, 0), (-1, -1), thickness, color),
        ('TOPPADDING',     (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING',  (0, 0), (-1, -1), space),
    ]))
    return t


# ══════════════════════════════════════════════════════════════════════════════
# 1.  MEMBER DIRECTORY PDF
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/directory-pdf")
def member_directory_pdf(
    status: Optional[str] = Query(None),
    fmt:    str            = Query("grid"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.platypus import (
            SimpleDocTemplate, Table, TableStyle,
            Paragraph, Spacer, Image,
        )

        q = db.query(models.Member)
        if status and status.lower() != "all":
            q = q.filter(models.Member.status == status)
        members = q.order_by(models.Member.last, models.Member.first).all()

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=letter,
            leftMargin=0.5*inch, rightMargin=0.5*inch,
            topMargin=0.65*inch, bottomMargin=0.65*inch,
        )

        C      = colors
        navy   = C.HexColor(NAVY)
        gold   = C.HexColor(GOLD)
        gray   = C.HexColor(GRAY)
        light  = C.HexColor(LIGHT)
        border = C.HexColor(BORDER)

        title_s = ParagraphStyle("title", fontSize=20, fontName="Helvetica-Bold",
                                  textColor=navy, alignment=TA_CENTER, spaceAfter=2)
        sub_s   = ParagraphStyle("sub",   fontSize=10, fontName="Helvetica",
                                  textColor=gold, alignment=TA_CENTER, spaceAfter=12)
        name_s  = ParagraphStyle("name",  fontSize=9,  fontName="Helvetica-Bold",
                                  textColor=navy, alignment=TA_CENTER, spaceBefore=4, leading=11)
        info_s  = ParagraphStyle("info",  fontSize=7.5, fontName="Helvetica",
                                  textColor=gray, alignment=TA_CENTER, leading=10)
        init_s  = ParagraphStyle("init",  fontSize=24, fontName="Helvetica-Bold",
                                  textColor=navy, alignment=TA_CENTER, spaceBefore=6, spaceAfter=6)

        story = []
        story.append(Paragraph("FFC Church", title_s))
        status_label = f" - {status}" if status and status.lower() != "all" else ""
        story.append(Paragraph(
            f"Member Directory{status_label}  -  {dt_date.today().strftime('%B %d, %Y')}",
            sub_s,
        ))
        story.append(_hr_table(navy, thickness=2, space=14))

        if not members:
            story.append(Paragraph("No members found.", ParagraphStyle("e", fontSize=11)))
            doc.build(story)
            buf.seek(0)
            return Response(buf.read(), media_type="application/pdf",
                            headers={"Content-Disposition": 'attachment; filename="member_directory.pdf"'})

        # ── GRID layout (3 cols) ──────────────────────────────────────────────
        if fmt == "grid":
            COLS   = 3
            CELL_W = 2.15 * inch
            PW     = 0.95 * inch

            cells = []
            for m in members:
                cell = []
                pp = _photo_path(m.photo)
                if pp:
                    img = Image(pp, width=PW, height=PW)
                    img.hAlign = "CENTER"
                    cell.append(img)
                else:
                    initials = ((m.first or " ")[0] + (m.last or " ")[0]).upper()
                    cell.append(Paragraph(initials, init_s))

                cell.append(Paragraph(f"{m.first} {m.last}", name_s))
                lines = []
                if m.phone: lines.append(m.phone)
                if m.email: lines.append(m.email)
                if lines:
                    cell.append(Paragraph("<br/>".join(lines), info_s))
                cells.append(cell)

            while len(cells) % COLS:
                cells.append([""])

            rows  = [cells[i:i+COLS] for i in range(0, len(cells), COLS)]
            row_h = [1.85 * inch] * len(rows)

            tbl = Table(rows, colWidths=[CELL_W]*COLS, rowHeights=row_h)
            tbl.setStyle(TableStyle([
                ("VALIGN",         (0,0), (-1,-1), "TOP"),
                ("ALIGN",          (0,0), (-1,-1), "CENTER"),
                ("GRID",           (0,0), (-1,-1), 0.5, border),
                ("TOPPADDING",     (0,0), (-1,-1), 8),
                ("BOTTOMPADDING",  (0,0), (-1,-1), 6),
                ("ROWBACKGROUNDS", (0,0), (-1,-1), [C.white, light]),
            ]))
            story.append(tbl)

        # ── LIST layout ───────────────────────────────────────────────────────
        else:
            rn_s = ParagraphStyle("rn", fontSize=10, fontName="Helvetica-Bold",
                                   textColor=navy, leading=13)
            ri_s = ParagraphStyle("ri", fontSize=8.5, fontName="Helvetica",
                                   textColor=gray, leading=11)
            hh   = ParagraphStyle("hh", fontSize=9, fontName="Helvetica-Bold",
                                   textColor=C.white)
            hc   = ParagraphStyle("hc", fontSize=9, fontName="Helvetica-Bold",
                                   textColor=C.white, alignment=TA_CENTER)

            header = [
                Paragraph("Photo",  hc),
                Paragraph("Name",   hh),
                Paragraph("Phone",  hh),
                Paragraph("Email",  hh),
                Paragraph("Status", hh),
            ]
            rows = [header]
            PH = 0.55 * inch
            for m in members:
                pp = _photo_path(m.photo)
                if pp:
                    img = Image(pp, width=PH, height=PH)
                    img.hAlign = "CENTER"
                    photo_cell = img
                else:
                    initials = ((m.first or " ")[0] + (m.last or " ")[0]).upper()
                    photo_cell = Paragraph(
                        initials,
                        ParagraphStyle("pi", fontSize=14, fontName="Helvetica-Bold",
                                       textColor=navy, alignment=TA_CENTER),
                    )
                rows.append([
                    photo_cell,
                    Paragraph(f"{m.first} {m.last}", rn_s),
                    Paragraph(m.phone or "-", ri_s),
                    Paragraph(m.email or "-", ri_s),
                    Paragraph(m.status or "-", ri_s),
                ])

            col_w = [0.7*inch, 2.0*inch, 1.3*inch, 2.4*inch, 0.9*inch]
            tbl = Table(rows, colWidths=col_w)
            tbl.setStyle(TableStyle([
                ("BACKGROUND",    (0,0), (-1,0), navy),
                ("VALIGN",        (0,0), (-1,-1), "MIDDLE"),
                ("ALIGN",         (0,0), (0,-1), "CENTER"),
                ("GRID",          (0,0), (-1,-1), 0.5, border),
                ("ROWBACKGROUNDS",(0,1), (-1,-1), [C.white, light]),
                ("TOPPADDING",    (0,0), (-1,-1), 5),
                ("BOTTOMPADDING", (0,0), (-1,-1), 5),
                ("LEFTPADDING",   (0,0), (-1,-1), 6),
                ("RIGHTPADDING",  (0,0), (-1,-1), 6),
            ]))
            story.append(tbl)

        story.append(Spacer(1, 10))
        story.append(Paragraph(
            f"Total: {len(members)} member{'s' if len(members) != 1 else ''}",
            ParagraphStyle("foot", fontSize=8, fontName="Helvetica",
                           textColor=gray, alignment=TA_CENTER),
        ))

        doc.build(story)
        buf.seek(0)
        fname = f"member_directory_{dt_date.today()}.pdf"
        return Response(buf.read(), media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Directory PDF failed: {type(exc).__name__}: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# 2.  YEAR-END GIVING STATEMENT  (shared builder)
# ══════════════════════════════════════════════════════════════════════════════

def _build_statement_pdf(member: models.Member, records: list, year: int) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle,
        Paragraph, Spacer,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=inch, rightMargin=inch,
        topMargin=0.85*inch, bottomMargin=0.85*inch,
    )

    C      = colors
    navy   = C.HexColor(NAVY)
    gold   = C.HexColor(GOLD)
    gray   = C.HexColor(GRAY)
    light  = C.HexColor(LIGHT)
    border = C.HexColor(BORDER)
    dark   = C.HexColor("#374151")

    def S(name, **kw):
        kw.setdefault("fontName", "Helvetica")
        kw.setdefault("fontSize", 10)
        kw.setdefault("leading",  14)
        kw.setdefault("textColor", C.black)
        return ParagraphStyle(name, **kw)

    story = []

    # ── header ──
    story.append(Paragraph(
        "FFC Church",
        S("ch", fontSize=22, fontName="Helvetica-Bold", textColor=navy,
          alignment=TA_CENTER, spaceAfter=2),
    ))
    story.append(Paragraph(
        "Contribution Statement",
        S("cs", fontSize=12, textColor=gold, alignment=TA_CENTER, spaceAfter=6),
    ))
    story.append(_hr_table(navy, thickness=2, space=16))

    # ── member info ──
    info_rows = [
        [Paragraph("<b>Tax Year</b>", S("l", textColor=gray, fontSize=9)),
         Paragraph(str(year),         S("v", fontName="Helvetica-Bold", fontSize=13, textColor=navy))],
        [Paragraph("<b>Member</b>",   S("l", textColor=gray, fontSize=9)),
         Paragraph(f"{member.first} {member.last}",
                   S("v", fontName="Helvetica-Bold", fontSize=11, textColor=navy))],
    ]
    if member.email:
        info_rows.append([
            Paragraph("<b>Email</b>", S("l", textColor=gray, fontSize=9)),
            Paragraph(member.email,   S("v", fontSize=10, textColor=dark)),
        ])
    if member.address:
        info_rows.append([
            Paragraph("<b>Address</b>", S("l", textColor=gray, fontSize=9)),
            Paragraph(member.address,   S("v", fontSize=10, textColor=dark)),
        ])

    info_tbl = Table(info_rows, colWidths=[1.1*inch, 5.0*inch])
    info_tbl.setStyle(TableStyle([
        ("VALIGN",        (0,0), (-1,-1), "TOP"),
        ("TOPPADDING",    (0,0), (-1,-1), 3),
        ("BOTTOMPADDING", (0,0), (-1,-1), 3),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 14))

    if not records:
        story.append(Paragraph(
            f"No giving records found for {member.first} {member.last} in {year}.",
            S("no", textColor=gray),
        ))
    else:
        # ── itemised table ──
        story.append(Paragraph(
            "Donation Detail",
            S("sh", fontSize=11, fontName="Helvetica-Bold", textColor=navy, spaceAfter=6),
        ))
        hw = S("hw", fontName="Helvetica-Bold", textColor=C.white, fontSize=9)
        hwr = S("hwr", fontName="Helvetica-Bold", textColor=C.white, fontSize=9,
                alignment=TA_RIGHT)
        dv  = S("dv", fontSize=9, textColor=dark)
        dvr = S("dvr", fontSize=9, textColor=dark, alignment=TA_RIGHT)

        hdr = [
            Paragraph("Date",   hw),
            Paragraph("Type",   hw),
            Paragraph("Fund",   hw),
            Paragraph("Amount", hwr),
        ]
        rows = [hdr]
        for r in records:
            rows.append([
                Paragraph(str(r.date),              dv),
                Paragraph(r.type or "-",            dv),
                Paragraph(r.fund or "General Fund", dv),
                Paragraph(f"${r.amount:,.2f}",      dvr),
            ])

        item_tbl = Table(rows, colWidths=[1.1*inch, 1.5*inch, 2.6*inch, 1.0*inch])
        item_tbl.setStyle(TableStyle([
            ("BACKGROUND",    (0,0), (-1,0), navy),
            ("ROWBACKGROUNDS",(0,1), (-1,-1), [C.white, light]),
            ("GRID",          (0,0), (-1,-1), 0.4, border),
            ("TOPPADDING",    (0,0), (-1,-1), 5),
            ("BOTTOMPADDING", (0,0), (-1,-1), 5),
            ("LEFTPADDING",   (0,0), (-1,-1), 7),
            ("RIGHTPADDING",  (0,0), (-1,-1), 7),
            ("ALIGN",         (3,0), (3,-1), "RIGHT"),
        ]))
        story.append(item_tbl)
        story.append(Spacer(1, 16))

        # ── fund summary ──
        story.append(Paragraph(
            "Summary by Fund",
            S("sh2", fontSize=11, fontName="Helvetica-Bold", textColor=navy, spaceAfter=6),
        ))
        fund_totals: dict = {}
        for r in records:
            k = r.fund or "General Fund"
            fund_totals[k] = fund_totals.get(k, Decimal("0")) + r.amount
        grand = sum(fund_totals.values())

        fr  = S("fr",  fontSize=10)
        fa  = S("fa",  fontSize=10, alignment=TA_RIGHT)
        fbt = S("fbt", fontSize=11, fontName="Helvetica-Bold", textColor=navy)
        fba = S("fba", fontSize=11, fontName="Helvetica-Bold", textColor=navy, alignment=TA_RIGHT)

        sum_rows = []
        for fund in sorted(fund_totals):
            sum_rows.append([
                Paragraph(fund, fr),
                Paragraph(f"${fund_totals[fund]:,.2f}", fa),
            ])
        sum_rows.append([
            Paragraph("<b>Total Contributions</b>", fbt),
            Paragraph(f"<b>${grand:,.2f}</b>",       fba),
        ])

        sum_tbl = Table(sum_rows, colWidths=[4.5*inch, 1.7*inch])
        sum_tbl.setStyle(TableStyle([
            ("LINEABOVE",     (0,-1), (-1,-1), 1.5, navy),
            ("LINEBELOW",     (0,-2), (-1,-2), 0.4, border),
            ("TOPPADDING",    (0,0), (-1,-1), 4),
            ("BOTTOMPADDING", (0,0), (-1,-1), 4),
            ("ALIGN",         (1,0), (1,-1), "RIGHT"),
        ]))
        story.append(sum_tbl)

    # ── disclaimer ──
    story.append(Spacer(1, 24))
    story.append(_hr_table(border, thickness=0.5, space=8))
    story.append(Paragraph(
        "No goods or services were provided in exchange for these contributions. "
        f"Please retain this statement for your {year} tax records. "
        "FFC Church is a 501(c)(3) nonprofit organization.",
        S("disc", fontSize=8, fontName="Helvetica-Oblique", textColor=gray,
          alignment=TA_CENTER, leading=12),
    ))
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        f"Statement generated {dt_date.today().strftime('%B %d, %Y')}",
        S("gen", fontSize=7.5, textColor=C.HexColor("#9CA3AF"), alignment=TA_CENTER),
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()


@router.get("/giving-statement/{member_id}")
def giving_statement(
    member_id: str,
    year: int = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    try:
        if not year:
            year = datetime.utcnow().year
        member = db.query(models.Member).filter(models.Member.id == member_id).first()
        if not member:
            raise HTTPException(status_code=404, detail="Member not found")

        records = (
            db.query(models.GivingRecord)
            .filter(models.GivingRecord.member_id == member_id)
            .filter(extract("year", models.GivingRecord.date) == year)
            .order_by(models.GivingRecord.date)
            .all()
        )

        pdf_bytes = _build_statement_pdf(member, records, year)
        fname = f"giving_statement_{member.last}_{year}.pdf"
        return Response(pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Statement PDF failed: {type(exc).__name__}: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# 3.  BULK GIVING STATEMENTS  (all members as a ZIP)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/giving-statements-all")
def giving_statements_all(
    year: int = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_admin),
):
    try:
        if not year:
            year = datetime.utcnow().year

        member_ids = (
            db.query(models.GivingRecord.member_id)
            .filter(extract("year", models.GivingRecord.date) == year)
            .filter(models.GivingRecord.member_id.isnot(None))
            .distinct()
            .all()
        )
        member_ids = [r[0] for r in member_ids]

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for mid in member_ids:
                member = db.query(models.Member).filter(models.Member.id == mid).first()
                if not member:
                    continue
                records = (
                    db.query(models.GivingRecord)
                    .filter(models.GivingRecord.member_id == mid)
                    .filter(extract("year", models.GivingRecord.date) == year)
                    .order_by(models.GivingRecord.date)
                    .all()
                )
                pdf_bytes = _build_statement_pdf(member, records, year)
                zf.writestr(
                    f"giving_statement_{member.last}_{member.first}_{year}.pdf",
                    pdf_bytes,
                )

        zip_buf.seek(0)
        fname = f"giving_statements_{year}.zip"
        return Response(zip_buf.read(), media_type="application/zip",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500,
                            detail=f"Bulk statements failed: {type(exc).__name__}: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# 4.  NAME TAG / BADGE PRINTING  (Avery 5395 or 5160)
# ══════════════════════════════════════════════════════════════════════════════

# --- Label sheet specs (all in points, 1 inch = 72 pts) ----------------------
_LABEL_SPECS = {
    "5395": dict(
        cols=2, rows=4,
        badge_w=3.25 * 72, badge_h=2.25 * 72,
        margin_left=0.625 * 72, margin_top=0.5 * 72,
        h_gap=0.5 * 72, v_gap=0.125 * 72,
        desc="Avery 5395 — 8 per sheet (2⅓ × 3⅜\")",
    ),
    "5160": dict(
        cols=3, rows=10,
        badge_w=2.625 * 72, badge_h=1.0 * 72,
        margin_left=0.1875 * 72, margin_top=0.5 * 72,
        h_gap=0.125 * 72, v_gap=0.0,
        desc="Avery 5160 — 30 per sheet (1 × 2⅝\")",
    ),
}


def _draw_badge_5395(c, x, y, w, h, member, badge_date: str):
    """Draw a large name-badge (5395 style) at canvas position (x,y)."""
    from reportlab.pdfgen import canvas as _c
    from reportlab.lib.colors import HexColor, white, Color

    PAD = 6
    navy = HexColor(NAVY)
    gold = HexColor(GOLD)

    # ── Clip/border ──────────────────────────────────────────────────────────
    c.saveState()
    p = c.beginPath()
    p.roundRect(x, y, w, h, 6)
    c.clipPath(p, stroke=0, fill=0)

    # Background
    c.setFillColor(white)
    c.roundRect(x, y, w, h, 6, stroke=0, fill=1)

    # Navy header bar (top 22% of badge)
    hdr_h = h * 0.22
    c.setFillColor(navy)
    c.rect(x, y + h - hdr_h, w, hdr_h, stroke=0, fill=1)

    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(x + w / 2, y + h - hdr_h + hdr_h * 0.35, "FFC CHURCH")

    # Gold accent line below header
    c.setStrokeColor(gold)
    c.setLineWidth(2)
    c.line(x, y + h - hdr_h, x + w, y + h - hdr_h)

    # ── Photo / avatar ────────────────────────────────────────────────────────
    body_top   = y + h - hdr_h - PAD        # top of body area
    body_bot   = y + PAD
    body_h     = body_top - body_bot

    avatar_r   = min(w * 0.18, body_h * 0.32)
    avatar_cx  = x + avatar_r + PAD * 2
    avatar_cy  = body_top - avatar_r - PAD * 1.5

    photo_path = _photo_path(member.photo) if member.photo else None
    if photo_path:
        try:
            from reportlab.platypus import Image as RLImg
            img_x = avatar_cx - avatar_r
            img_y = avatar_cy - avatar_r
            img_d = avatar_r * 2
            # Clip to circle then draw image
            cp = c.beginPath()
            cp.circle(avatar_cx, avatar_cy, avatar_r)
            c.clipPath(cp, stroke=0, fill=0)
            c.drawImage(photo_path, img_x, img_y, img_d, img_d,
                        preserveAspectRatio=True, mask="auto")
            c.restoreState(); c.saveState()
            p2 = c.beginPath(); p2.roundRect(x, y, w, h, 6)
            c.clipPath(p2, stroke=0, fill=0)
        except Exception:
            photo_path = None

    if not photo_path:
        initials = f"{member.first[0]}{member.last[0]}".upper() if member.first and member.last else "?"
        c.setFillColor(HexColor("#EBF0F8"))
        c.circle(avatar_cx, avatar_cy, avatar_r, stroke=0, fill=1)
        c.setFillColor(navy)
        c.setFont("Helvetica-Bold", avatar_r * 0.9)
        c.drawCentredString(avatar_cx, avatar_cy - avatar_r * 0.3, initials)

    # ── Name & details ────────────────────────────────────────────────────────
    text_x = avatar_cx + avatar_r + PAD * 2
    text_w = (x + w - PAD) - text_x

    full_name = f"{member.first} {member.last}"
    # Scale font to fit width
    name_size = 14
    c.setFont("Helvetica-Bold", name_size)
    while c.stringWidth(full_name, "Helvetica-Bold", name_size) > text_w and name_size > 8:
        name_size -= 1

    name_y = body_top - name_size - PAD * 1.5
    c.setFillColor(HexColor("#111827"))
    c.setFont("Helvetica-Bold", name_size)
    c.drawString(text_x, name_y, full_name)

    # Ministry
    if member.ministry:
        c.setFont("Helvetica", 8)
        c.setFillColor(HexColor(GRAY))
        c.drawString(text_x, name_y - 13, member.ministry[:38])

    # Date
    c.setFont("Helvetica", 7)
    c.setFillColor(HexColor(GRAY))
    c.drawString(text_x, body_bot + 4, badge_date)

    # Border outline
    c.setStrokeColor(HexColor("#D1D5DB"))
    c.setLineWidth(0.5)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=0)

    c.restoreState()


def _draw_badge_5160(c, x, y, w, h, member, badge_date: str):
    """Draw a small address-label badge (5160 style) at canvas position (x,y)."""
    from reportlab.lib.colors import HexColor, white

    PAD = 3
    navy = HexColor(NAVY)

    c.saveState()

    # Thin top border accent
    c.setFillColor(navy)
    c.rect(x, y + h - 3, w, 3, stroke=0, fill=1)

    full_name = f"{member.first} {member.last}"
    name_size = 8
    c.setFont("Helvetica-Bold", name_size)
    while c.stringWidth(full_name, "Helvetica-Bold", name_size) > w - PAD * 2 - 20 and name_size > 6:
        name_size -= 0.5

    c.setFillColor(HexColor("#111827"))
    c.setFont("Helvetica-Bold", name_size)
    c.drawString(x + PAD, y + h - 3 - name_size - PAD, full_name)

    if member.ministry:
        c.setFont("Helvetica", 6.5)
        c.setFillColor(HexColor(GRAY))
        c.drawString(x + PAD, y + PAD + 1, member.ministry[:32])

    # "FFC" top right
    c.setFont("Helvetica-Bold", 5.5)
    c.setFillColor(white)
    c.drawRightString(x + w - PAD, y + h - 3 - 6, "FFC")

    c.restoreState()


def _build_name_tags_pdf(members, label_format: str, badge_date: str) -> bytes:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as rl_canvas

    spec   = _LABEL_SPECS.get(label_format, _LABEL_SPECS["5395"])
    cols   = spec["cols"]
    rows   = spec["rows"]
    bw     = spec["badge_w"]
    bh     = spec["badge_h"]
    ml     = spec["margin_left"]
    mt     = spec["margin_top"]
    hgap   = spec["h_gap"]
    vgap   = spec["v_gap"]

    page_w, page_h = letter
    buf = io.BytesIO()
    c   = rl_canvas.Canvas(buf, pagesize=letter)

    per_page = cols * rows
    for page_idx in range(0, len(members), per_page):
        page_members = members[page_idx:page_idx + per_page]
        if page_idx > 0:
            c.showPage()

        for i, m in enumerate(page_members):
            col = i % cols
            row = i // cols
            x = ml + col * (bw + hgap)
            # PDF y=0 is at bottom; top margin is from top of page
            y = page_h - mt - (row + 1) * bh - row * vgap

            if label_format == "5160":
                _draw_badge_5160(c, x, y, bw, bh, m, badge_date)
            else:
                _draw_badge_5395(c, x, y, bw, bh, m, badge_date)

    c.save()
    buf.seek(0)
    return buf.read()


@router.get("/name-tags")
def name_tags_pdf(
    label_format: str  = Query("5395", description="5395 or 5160"),
    date:         Optional[str] = Query(None, description="YYYY-MM-DD attendance date"),
    member_ids:   Optional[str] = Query(None, description="Comma-separated member IDs"),
    db:           Session = Depends(get_db),
    _user:        models.User = Depends(require_admin),
):
    try:
        # ── Resolve members ───────────────────────────────────────────────────
        if member_ids:
            id_list = [i.strip() for i in member_ids.split(",") if i.strip()]
            members = db.query(models.Member).filter(models.Member.id.in_(id_list)).all()
            # preserve order
            id_order = {v: k for k, v in enumerate(id_list)}
            members  = sorted(members, key=lambda m: id_order.get(m.id, 999))
        elif date:
            from datetime import date as _date
            d = _date.fromisoformat(date)
            checkins   = db.query(models.MemberCheckin).filter(
                models.MemberCheckin.date == d).all()
            seen = set(); mid_list = []
            for ck in checkins:
                if ck.member_id not in seen:
                    seen.add(ck.member_id); mid_list.append(ck.member_id)
            members = db.query(models.Member).filter(models.Member.id.in_(mid_list)).all()
            id_order = {v: k for k, v in enumerate(mid_list)}
            members  = sorted(members, key=lambda m: id_order.get(m.id, 999))
        else:
            raise HTTPException(400, "Provide date or member_ids")

        if not members:
            raise HTTPException(404, "No members found for the given criteria")

        badge_date = date or dt_date.today().strftime("%B %d, %Y")
        if date:
            try:
                from datetime import date as _date2
                badge_date = _date2.fromisoformat(date).strftime("%B %d, %Y")
            except Exception:
                pass

        if label_format not in _LABEL_SPECS:
            label_format = "5395"

        pdf_bytes = _build_name_tags_pdf(members, label_format, badge_date)
        fname = f"name_tags_{date or 'custom'}_{label_format}.pdf"
        return Response(pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{fname}"'})

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, detail=f"Name tags failed: {type(exc).__name__}: {exc}")
