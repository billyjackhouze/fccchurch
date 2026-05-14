"""
Sermon archive endpoints.
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app import models, schemas
from app.routers.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/sermons", tags=["Sermons"])


def enrich_sermon(s: models.Sermon) -> schemas.SermonOut:
    return schemas.SermonOut(
        id=s.id,
        title=s.title,
        date=s.date,
        series_name=s.series_name,
        scripture=s.scripture,
        preacher_id=s.preacher_id,
        plan_id=s.plan_id,
        sermon_notes=s.sermon_notes,
        tags=s.tags,
        outline_json=s.outline_json,
        preacher_name=f"{s.preacher.first} {s.preacher.last}" if s.preacher else None,
        plan_title=s.plan.title if s.plan else None,
        created_at=s.created_at,
    )


def q_sermons(db):
    return db.query(models.Sermon).options(
        joinedload(models.Sermon.preacher),
        joinedload(models.Sermon.plan),
    )


@router.get("", response_model=List[schemas.SermonOut])
def list_sermons(
    search: Optional[str] = Query(None),
    series: Optional[str] = Query(None),
    preacher_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: models.User = Depends(get_current_user),
):
    q = q_sermons(db)
    if search:
        like = f"%{search}%"
        q = q.filter(
            (models.Sermon.title.ilike(like)) |
            (models.Sermon.scripture.ilike(like)) |
            (models.Sermon.series_name.ilike(like)) |
            (models.Sermon.tags.ilike(like))
        )
    if series:
        q = q.filter(models.Sermon.series_name == series)
    if preacher_id:
        q = q.filter(models.Sermon.preacher_id == preacher_id)
    sermons = q.order_by(models.Sermon.date.desc()).all()
    return [enrich_sermon(s) for s in sermons]


@router.get("/{sermon_id}", response_model=schemas.SermonOut)
def get_sermon(sermon_id: str, db: Session = Depends(get_db),
               _: models.User = Depends(get_current_user)):
    s = q_sermons(db).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    return enrich_sermon(s)


@router.post("", response_model=schemas.SermonOut, status_code=201)
def create_sermon(data: schemas.SermonCreate, db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    s = models.Sermon(**data.dict())
    db.add(s)
    db.commit()
    db.refresh(s)
    return enrich_sermon(q_sermons(db).filter(models.Sermon.id == s.id).first())


@router.put("/{sermon_id}", response_model=schemas.SermonOut)
def update_sermon(sermon_id: str, data: schemas.SermonUpdate,
                  db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    s = db.query(models.Sermon).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    for k, v in data.dict(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    return enrich_sermon(q_sermons(db).filter(models.Sermon.id == sermon_id).first())


@router.delete("/{sermon_id}", status_code=204)
def delete_sermon(sermon_id: str, db: Session = Depends(get_db),
                  _: models.User = Depends(require_admin)):
    s = db.query(models.Sermon).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    db.delete(s)
    db.commit()


# ── Outline save (admin) ──────────────────────────────────────────────────────

@router.patch("/{sermon_id}/outline", response_model=schemas.SermonOut)
def save_outline(sermon_id: str, body: dict, db: Session = Depends(get_db),
                 _: models.User = Depends(require_admin)):
    import json
    s = db.query(models.Sermon).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")
    s.outline_json = json.dumps(body.get("outline", {}))
    db.commit()
    return enrich_sermon(q_sermons(db).filter(models.Sermon.id == sermon_id).first())


# ── PDF export ────────────────────────────────────────────────────────────────

@router.get("/{sermon_id}/export-pdf")
def export_pdf(sermon_id: str, db: Session = Depends(get_db),
               _: models.User = Depends(get_current_user)):
    import json
    from io import BytesIO
    from fastapi.responses import StreamingResponse
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
    except ImportError:
        raise HTTPException(status_code=500, detail="reportlab not installed")

    s = q_sermons(db).filter(models.Sermon.id == sermon_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="Sermon not found")

    outline = {}
    if s.outline_json:
        try:
            outline = json.loads(s.outline_json)
        except Exception:
            outline = {}

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter,
                            rightMargin=inch, leftMargin=inch,
                            topMargin=inch, bottomMargin=inch)

    styles = getSampleStyleSheet()
    PURPLE = colors.HexColor("#6366f1")
    GRAY   = colors.HexColor("#6b7280")
    LIGHT  = colors.HexColor("#f9fafb")

    title_style = ParagraphStyle('STitle', parent=styles['Title'],
                                 fontSize=22, textColor=PURPLE, spaceAfter=4)
    meta_style  = ParagraphStyle('SMeta',  parent=styles['Normal'],
                                 fontSize=10, textColor=GRAY, spaceAfter=16)
    h2_style    = ParagraphStyle('SH2',    parent=styles['Heading2'],
                                 fontSize=13, textColor=PURPLE, spaceBefore=16, spaceAfter=6)
    h3_style    = ParagraphStyle('SH3',    parent=styles['Heading3'],
                                 fontSize=11, textColor=colors.HexColor("#374151"),
                                 spaceBefore=10, spaceAfter=4)
    body_style  = ParagraphStyle('SBody',  parent=styles['Normal'],
                                 fontSize=10, leading=15, spaceAfter=6)
    label_style = ParagraphStyle('SLabel', parent=styles['Normal'],
                                 fontSize=9, textColor=GRAY, spaceAfter=2)

    def safe(text):
        return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def section_block(heading, content):
        items = []
        if heading:
            items.append(Paragraph(safe(heading), h3_style))
        if content:
            for line in content.split("\n"):
                items.append(Paragraph(safe(line) or "&nbsp;", body_style))
        return items

    story = []

    # Header
    story.append(Paragraph(safe(s.title), title_style))
    meta_parts = [s.date.strftime("%B %d, %Y") if s.date else ""]
    if s.preacher and s.preacher.first:
        meta_parts.append(f"{s.preacher.first} {s.preacher.last}")
    if s.series_name:
        meta_parts.append(f"Series: {s.series_name}")
    if s.scripture:
        meta_parts.append(f"Scripture: {s.scripture}")
    story.append(Paragraph("  ·  ".join(p for p in meta_parts if p), meta_style))
    story.append(HRFlowable(width="100%", thickness=2, color=PURPLE, spaceAfter=16))

    # Introduction
    intro = outline.get("introduction", "")
    if intro:
        story.append(Paragraph("Introduction", h2_style))
        for line in intro.split("\n"):
            story.append(Paragraph(safe(line) or "&nbsp;", body_style))

    # Main Points
    main_points = outline.get("main_points", [])
    roman = ["I", "II", "III", "IV", "V"]
    for idx, pt in enumerate(main_points):
        label = roman[idx] if idx < len(roman) else str(idx + 1)
        heading = pt.get("heading", "")
        story.append(Paragraph(f"Point {label}{': ' + safe(heading) if heading else ''}", h2_style))

        if pt.get("scripture"):
            story.append(Paragraph("Scripture", label_style))
            story.append(Paragraph(safe(pt["scripture"]), body_style))

        if pt.get("illustration"):
            story.append(Paragraph("Illustration / Story", label_style))
            for line in pt["illustration"].split("\n"):
                story.append(Paragraph(safe(line) or "&nbsp;", body_style))

        if pt.get("application"):
            story.append(Paragraph("Application", label_style))
            for line in pt["application"].split("\n"):
                story.append(Paragraph(safe(line) or "&nbsp;", body_style))

    # Conclusion
    conclusion = outline.get("conclusion", "")
    if conclusion:
        story.append(Paragraph("Conclusion", h2_style))
        for line in conclusion.split("\n"):
            story.append(Paragraph(safe(line) or "&nbsp;", body_style))

    cta = outline.get("call_to_action", "")
    if cta:
        story.append(Paragraph("Call to Action", h2_style))
        for line in cta.split("\n"):
            story.append(Paragraph(safe(line) or "&nbsp;", body_style))

    # Footer note
    story.append(Spacer(1, 24))
    story.append(HRFlowable(width="100%", thickness=1, color=GRAY))
    story.append(Paragraph("Generated by FFC Church Management System", meta_style))

    doc.build(story)
    buf.seek(0)
    filename = f"sermon_{s.date}_{s.title[:30].replace(' ','_')}.pdf"
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ── AI Sermon Assistant ───────────────────────────────────────────────────────

class AISermonRequest(BaseModel):
    topic:      str
    scripture:  Optional[str] = None
    style:      Optional[str] = "expository"   # expository | topical | narrative
    num_points: Optional[int] = 3

@router.post("/ai-assist")
def ai_sermon_assist(req: AISermonRequest, db: Session = Depends(get_db),
                     _: models.User = Depends(require_admin)):
    from app.routers.settings import get_raw
    api_key = get_raw("api_anthropic_key", db)
    if not api_key:
        raise HTTPException(status_code=400,
            detail="Anthropic API key not configured. Add it in Admin → Settings → API Keys.")

    try:
        import anthropic
    except ImportError:
        raise HTTPException(status_code=500, detail="anthropic library not installed on server.")

    style_desc = {
        "expository": "expository (verse-by-verse scripture analysis)",
        "topical":    "topical (theme-based with supporting scriptures)",
        "narrative":  "narrative (story-driven with personal illustration)",
    }.get(req.style, "expository")

    scripture_hint = f" The primary scripture is: {req.scripture}." if req.scripture else ""
    prompt = f"""You are a helpful sermon preparation assistant for a Christian pastor.

Generate a complete sermon outline for a {style_desc} sermon on this topic: "{req.topic}".{scripture_hint}

The outline should have {req.num_points} main points. Format your response as valid JSON only, with this exact structure:
{{
  "sermon_title": "A compelling sermon title",
  "scripture": "Primary scripture reference",
  "introduction": "2-3 sentences for the introduction / opening hook",
  "main_points": [
    {{
      "heading": "Point heading",
      "scripture": "Supporting scripture reference",
      "illustration": "A brief illustration or story idea",
      "application": "Practical application for the congregation"
    }}
  ],
  "conclusion": "2-3 sentences wrapping up the message",
  "call_to_action": "What you want the congregation to do or feel"
}}

Return ONLY the JSON, no explanation, no markdown code fences."""

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    # Strip markdown fences if model wrapped it anyway
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])

    import json as _json
    try:
        outline = _json.loads(raw)
    except Exception:
        raise HTTPException(status_code=500, detail="AI returned malformed JSON. Try again.")

    return {"outline": outline}
