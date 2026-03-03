import json
from datetime import datetime
from typing import Any, Dict, List

import ollama
import streamlit as st

# ReportLab imports
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    HRFlowable,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import KeepTogether

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OLLAMA_HOST = "http://localhost:11434"
OLLAMA_MODEL = "llama3"
OUTPUT_PDF_PATH = "Audit_Report.pdf"

PAGE_W, PAGE_H = A4
MARGIN = 18 * mm

DARK_BG = colors.HexColor("#0D1117")
ACCENT = colors.HexColor("#00C8FF")
PANEL_BG = colors.HexColor("#161B22")
HEADER_BG = colors.HexColor("#1C2333")
BORDER = colors.HexColor("#30363D")
TEXT_PRIMARY = colors.HexColor("#E6EDF3")
TEXT_MUTED = colors.HexColor("#8B949E")

SEV_COLOURS = {
    "critical": colors.HexColor("#FF4444"),
    "high": colors.HexColor("#FF8C00"),
    "medium": colors.HexColor("#FFD700"),
    "low": colors.HexColor("#28A745"),
    "info": colors.HexColor("#1E90FF"),
    "unknown": colors.HexColor("#6E7681"),
}


def sev_color(severity: str) -> colors.Color:
    return SEV_COLOURS.get(severity.lower(), SEV_COLOURS["unknown"])


# ---------------------------------------------------------------------------
# Page callbacks
# ---------------------------------------------------------------------------
def _draw_cover(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H - 6, PAGE_W, 6, fill=1, stroke=0)
    canvas.setFillColor(PANEL_BG)
    canvas.rect(0, 0, PAGE_W, 22 * mm, fill=1, stroke=0)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN, 8 * mm, "CONFIDENTIAL -- For Authorised Personnel Only")
    canvas.drawRightString(
        PAGE_W - MARGIN,
        8 * mm,
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}",
    )
    canvas.restoreState()


def _draw_body_page(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(DARK_BG)
    canvas.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    canvas.setFillColor(ACCENT)
    canvas.rect(0, PAGE_H - 3, PAGE_W, 3, fill=1, stroke=0)
    canvas.setFillColor(PANEL_BG)
    canvas.rect(0, 0, 8 * mm, PAGE_H, fill=1, stroke=0)
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(ACCENT)
    canvas.drawString(MARGIN + 8 * mm, PAGE_H - 11 * mm, "SYNTHETIC AUDITOR")
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 11 * mm, f"Page {doc.page}")
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(MARGIN + 8 * mm, 20 * mm, PAGE_W - MARGIN, 20 * mm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(TEXT_MUTED)
    canvas.drawString(MARGIN + 8 * mm, 13 * mm, "CONFIDENTIAL -- For Authorised Personnel Only")
    canvas.drawRightString(PAGE_W - MARGIN, 13 * mm, f"Generated: {datetime.now().strftime('%Y-%m-%d')}")
    canvas.restoreState()


# ---------------------------------------------------------------------------
# Document template
# ---------------------------------------------------------------------------
def build_doc(output_path: str) -> BaseDocTemplate:
    doc = BaseDocTemplate(output_path, pagesize=A4)

    cover_frame = Frame(
        MARGIN,
        22 * mm,
        PAGE_W - 2 * MARGIN,
        PAGE_H - 22 * mm - 10 * mm,
        id="cover",
        showBoundary=0,
    )
    body_frame = Frame(
        MARGIN + 8 * mm,
        24 * mm,
        PAGE_W - MARGIN * 2 - 8 * mm,
        PAGE_H - 16 * mm - 24 * mm,
        id="body",
        showBoundary=0,
    )

    doc.addPageTemplates(
        [
            PageTemplate(id="Cover", frames=[cover_frame], onPage=_draw_cover),
            PageTemplate(id="Body", frames=[body_frame], onPage=_draw_body_page),
        ]
    )
    return doc


# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
def build_styles() -> dict:
    def s(name, **kw):
        return ParagraphStyle(name, **kw)

    return {
        "cover_title": s(
            "CoverTitle",
            fontName="Helvetica-Bold",
            fontSize=32,
            textColor=TEXT_PRIMARY,
            spaceAfter=6,
            alignment=TA_CENTER,
        ),
        "cover_sub": s(
            "CoverSub",
            fontName="Helvetica",
            fontSize=14,
            textColor=ACCENT,
            spaceAfter=4,
            alignment=TA_CENTER,
        ),
        "section_h1": s(
            "SectionH1",
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=ACCENT,
            spaceBefore=12,
            spaceAfter=5,
        ),
        "body": s(
            "Body",
            fontName="Helvetica",
            fontSize=10,
            textColor=TEXT_PRIMARY,
            leading=15,
            spaceAfter=5,
        ),
        "muted": s(
            "Muted",
            fontName="Helvetica-Oblique",
            fontSize=9,
            textColor=TEXT_MUTED,
            leading=13,
            spaceAfter=4,
        ),
        "th": s("TH", fontName="Helvetica-Bold", fontSize=9, textColor=ACCENT),
    }


# ---------------------------------------------------------------------------
# Content builders
# ---------------------------------------------------------------------------
def _safe_p(text: str, style: ParagraphStyle) -> Paragraph:
    safe = str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return Paragraph(safe, style)


def cover_page(context_note: str, findings: List[Dict[str, str]], styles: dict) -> List:
    """
    Cover page. NextPageTemplate('Body') is placed BEFORE the PageBreak so the
    very next page (executive summary) correctly uses the Body template.
    """
    story = []
    story.append(Spacer(1, 55 * mm))

    story.append(Paragraph("Synthetic Auditor", styles["cover_title"]))
    story.append(Paragraph("Cybersecurity Audit Report", styles["cover_sub"]))
    story.append(Spacer(1, 8 * mm))
    story.append(HRFlowable(width="80%", thickness=1, color=ACCENT, hAlign="CENTER", spaceAfter=8 * mm))

    date_str = datetime.now().strftime("%B %d, %Y")
    crit = sum(1 for f in findings if f.get("severity", "").lower() == "critical")
    high = sum(1 for f in findings if f.get("severity", "").lower() == "high")
    med = sum(1 for f in findings if f.get("severity", "").lower() == "medium")

    ml = ParagraphStyle("ml", fontName="Helvetica", fontSize=9, textColor=TEXT_MUTED, alignment=TA_CENTER)
    mv = ParagraphStyle("mv", fontName="Helvetica-Bold", fontSize=18, textColor=TEXT_PRIMARY, alignment=TA_CENTER)
    mvc = ParagraphStyle("mvc", fontName="Helvetica-Bold", fontSize=18, textColor=SEV_COLOURS["critical"], alignment=TA_CENTER)
    mvh = ParagraphStyle("mvh", fontName="Helvetica-Bold", fontSize=18, textColor=SEV_COLOURS["high"], alignment=TA_CENTER)
    mvm = ParagraphStyle("mvm", fontName="Helvetica-Bold", fontSize=18, textColor=SEV_COLOURS["medium"], alignment=TA_CENTER)

    stats = Table(
        [
            [Paragraph(str(len(findings)), mv), Paragraph(str(crit), mvc), Paragraph(str(high), mvh), Paragraph(str(med), mvm)],
            [Paragraph("Total Findings", ml), Paragraph("Critical", ml), Paragraph("High", ml), Paragraph("Medium", ml)],
        ],
        colWidths=[38 * mm] * 4,
    )
    stats.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
                ("GRID", (0, 0), (-1, -1), 0.5, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LINEABOVE", (0, 0), (0, 0), 3, SEV_COLOURS["info"]),
                ("LINEABOVE", (1, 0), (1, 0), 3, SEV_COLOURS["critical"]),
                ("LINEABOVE", (2, 0), (2, 0), 3, SEV_COLOURS["high"]),
                ("LINEABOVE", (3, 0), (3, 0), 3, SEV_COLOURS["medium"]),
            ]
        )
    )
    story.append(stats)
    story.append(Spacer(1, 8 * mm))

    dp = ParagraphStyle("dp", fontName="Helvetica", fontSize=10, textColor=TEXT_MUTED, alignment=TA_CENTER)
    story.append(Paragraph(f"Report Date: {date_str}", dp))

    if context_note and context_note.strip():
        story.append(Spacer(1, 6 * mm))
        cp = ParagraphStyle("cp", fontName="Helvetica", fontSize=9, textColor=TEXT_MUTED, alignment=TA_CENTER, leading=14)
        truncated = context_note.strip()[:400]
        story.append(Paragraph(f"Scope: {truncated}", cp))

    # CRITICAL FIX: switch template BEFORE the PageBreak
    story.append(NextPageTemplate("Body"))
    story.append(PageBreak())
    return story


def executive_summary_section(summary_text: str, styles: dict) -> List:
    story = []
    story.append(Paragraph("Executive Summary", styles["section_h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=5))
    for para in summary_text.strip().split("\n\n") or [summary_text]:
        if para.strip():
            story.append(_safe_p(para.strip(), styles["body"]))
            story.append(Spacer(1, 2 * mm))
    return story


def scoring_table_section(findings: List[Dict[str, str]], styles: dict) -> List:
    story = []
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("Findings Overview", styles["section_h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=5))

    avail = PAGE_W - MARGIN * 2 - 8 * mm
    col_w = [32 * mm, 26 * mm, avail - 32 * mm - 26 * mm]

    rows = [[Paragraph("ID", styles["th"]), Paragraph("Severity", styles["th"]), Paragraph("Vulnerability Name", styles["th"])]]

    for f in findings:
        sev = f.get("severity", "Unknown")
        colour = sev_color(sev)
        sev_style = ParagraphStyle(f"sev_{sev.lower()}", fontName="Helvetica-Bold", fontSize=9, textColor=colour)
        rows.append([
            _safe_p(f.get("vulnerability_id", "N/A")[:20], styles["muted"]),
            Paragraph(sev.upper(), sev_style),
            _safe_p(f.get("name", "Unnamed Finding"), styles["body"]),
        ])

    t = Table(rows, colWidths=col_w, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEADER_BG),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [PANEL_BG, DARK_BG]),
                ("GRID", (0, 0), (-1, -1), 0.4, BORDER),
                ("LINEBELOW", (0, 0), (-1, 0), 1.5, ACCENT),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(t)
    return story


def finding_cards(findings: List[Dict[str, str]], styles: dict) -> List:
    story = []
    story.append(PageBreak())
    story.append(Paragraph("Detailed Findings", styles["section_h1"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BORDER, spaceAfter=6))

    avail = PAGE_W - MARGIN * 2 - 8 * mm

    for idx, f in enumerate(findings, start=1):
        sev = f.get("severity", "Unknown")
        colour = sev_color(sev)
        name = f.get("name", "Unnamed Finding")
        vid = f.get("vulnerability_id", "N/A")
        ai_text = f.get("ai_analysis", "No analysis available.")
        evidence = f.get("evidence", "No evidence provided.")

        # Card header
        hdr_t = Table(
            [
                [
                    _safe_p(
                        f"Finding {idx} of {len(findings)}: {name}",
                        ParagraphStyle(
                            f"hl{idx}",
                            fontName="Helvetica-Bold",
                            fontSize=11,
                            textColor=TEXT_PRIMARY,
                            leading=15,
                        ),
                    ),
                    _safe_p(
                        f"ID: {vid}",
                        ParagraphStyle(
                            f"hr{idx}",
                            fontName="Helvetica",
                            fontSize=8,
                            textColor=TEXT_MUTED,
                            alignment=TA_RIGHT,
                        ),
                    ),
                ]
            ],
            colWidths=[avail * 0.72, avail * 0.28],
        )
        hdr_t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), HEADER_BG),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ("LEFTPADDING", (0, 0), (0, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("LINEBELOW", (0, 0), (-1, -1), 2.5, colour),
                ]
            )
        )

        # Severity row
        badge_t = Table(
            [
                [
                    Paragraph(
                        "SEVERITY",
                        ParagraphStyle(
                            f"sl{idx}",
                            fontName="Helvetica-Bold",
                            fontSize=8,
                            textColor=ACCENT,
                        ),
                    ),
                    Paragraph(
                        sev.upper(),
                        ParagraphStyle(
                            f"sv{idx}",
                            fontName="Helvetica-Bold",
                            fontSize=10,
                            textColor=colour,
                        ),
                    ),
                ]
            ],
            colWidths=[26 * mm, avail - 26 * mm],
        )
        badge_t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 10),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, colour),
                ]
            )
        )

        # AI Analysis block
        safe_ai = ai_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ai_t = Table(
            [
                [
                    Paragraph(
                        "AI ANALYSIS",
                        ParagraphStyle(
                            f"ail{idx}",
                            fontName="Helvetica-Bold",
                            fontSize=8,
                            textColor=ACCENT,
                            spaceAfter=3,
                        ),
                    )
                ],
                [
                    Paragraph(
                        safe_ai.replace("\n", "<br/>"),
                        ParagraphStyle(
                            f"aib{idx}",
                            fontName="Helvetica",
                            fontSize=9,
                            textColor=TEXT_PRIMARY,
                            leading=14,
                        ),
                    )
                ],
            ],
            colWidths=[avail],
        )
        ai_t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), PANEL_BG),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (0, 0), 6),
                    ("TOPPADDING", (0, 1), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
                ]
            )
        )

        # Evidence block
        safe_ev = evidence.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ev_t = Table(
            [
                [
                    Paragraph(
                        "EVIDENCE",
                        ParagraphStyle(
                            f"evl{idx}",
                            fontName="Helvetica-Bold",
                            fontSize=8,
                            textColor=TEXT_MUTED,
                            spaceAfter=3,
                        ),
                    )
                ],
                [
                    Paragraph(
                        safe_ev.replace("\n", "<br/>"),
                        ParagraphStyle(
                            f"evb{idx}",
                            fontName="Helvetica-Oblique",
                            fontSize=8,
                            textColor=TEXT_MUTED,
                            leading=13,
                        ),
                    )
                ],
            ],
            colWidths=[avail],
        )
        ev_t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), DARK_BG),
                    ("LEFTPADDING", (0, 0), (-1, -1), 12),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                    ("TOPPADDING", (0, 0), (0, 0), 6),
                    ("TOPPADDING", (0, 1), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, -1), (-1, -1), 8),
                    ("LINEBEFORE", (0, 0), (0, -1), 3, BORDER),
                ]
            )
        )

        card = KeepTogether([hdr_t, badge_t, ai_t, ev_t, Spacer(1, 5 * mm)])
        story.append(card)

    return story


def generate_pdf(
    context_note: str,
    findings: List[Dict[str, str]],
    executive_summary: str,
    output_path: str,
) -> None:
    styles = build_styles()
    doc = build_doc(output_path)
    story = []

    # Cover page (NextPageTemplate('Body') is embedded inside cover_page before PageBreak)
    story += cover_page(context_note, findings, styles)
    story += executive_summary_section(executive_summary, styles)
    story += scoring_table_section(findings, styles)
    story += finding_cards(findings, styles)

    doc.build(story)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------
def normalize_finding(item: Dict[str, Any]) -> Dict[str, str]:
    return {
        "vulnerability_id": str(item.get("vulnerability_id") or item.get("id") or "N/A"),
        "name": str(item.get("name") or item.get("title") or "Unnamed Finding"),
        "severity": str(item.get("severity") or item.get("risk") or item.get("RiskLevel") or "Unknown"),
        "description": str(item.get("description") or "No description provided."),
        "evidence": str(item.get("evidence") or "No evidence provided."),
    }


def load_preprocessed_findings(uploaded_file) -> List[Dict[str, str]]:
    payload = json.loads(uploaded_file.getvalue().decode("utf-8", errors="ignore"))
    findings_raw: List[Dict[str, Any]] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("critical_findings"), list):
            findings_raw = payload["critical_findings"]
        elif isinstance(payload.get("findings"), list):
            findings_raw = payload["findings"]
    elif isinstance(payload, list):
        findings_raw = payload
    return [normalize_finding(i) for i in findings_raw if isinstance(i, dict)]


def resolve_ollama_model(client: ollama.Client, preferred_model: str) -> str:
    available: List[str] = []
    listed = client.list()
    raw_models = getattr(listed, "models", None)
    if raw_models is None and hasattr(listed, "get"):
        raw_models = listed.get("models", [])
    if raw_models is None and hasattr(listed, "model_dump"):
        raw_models = listed.model_dump().get("models", [])
    raw_models = raw_models or []
    for model in raw_models:
        if isinstance(model, dict):
            name = model.get("name") or model.get("model")
        else:
            name = getattr(model, "name", None) or getattr(model, "model", None)
        if isinstance(name, str) and name.strip():
            available.append(name.strip())
    if preferred_model in available:
        return preferred_model
    for fallback in ("llama3:latest", "llama3.1:latest", "llama3.2:latest"):
        if fallback in available:
            return fallback
    if available:
        return available[0]
    raise RuntimeError("No Ollama models installed. Run: ollama pull llama3.1")


def run_ollama_analysis(
    client: ollama.Client,
    context_note: str,
    findings: List[Dict[str, str]],
    model_name: str,
) -> List[Dict[str, str]]:
    analyzed: List[Dict[str, str]] = []
    for finding in findings:
        prompt = (
            "You are a strict cybersecurity auditor.\n"
            f"CLIENT CONTEXT: {context_note}\n"
            f"VULNERABILITY FOUND: {finding.get('name', '')}\n"
            f"DESCRIPTION: {finding.get('description', '')}\n\n"
            "TASK: Write a professional 1-paragraph explanation of why this specific vulnerability "
            "is a major business risk to this specific client. Then provide a 1-sentence "
            "recommendation to fix it. Do not hallucinate or invent vulnerabilities not listed here."
        )
        response = client.chat(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0},
        )
        ai_text = response.get("message", {}).get("content", "")
        updated = dict(finding)
        updated["ai_analysis"] = ai_text.strip() if ai_text else "No AI analysis returned."
        analyzed.append(updated)
    return analyzed


def run_ollama_executive_summary(
    client: ollama.Client,
    context_note: str,
    findings: List[Dict[str, str]],
    model_name: str,
) -> str:
    names = [f"- {f.get('name', 'Unnamed Finding')}" for f in findings]
    summary_list = "\n".join(names) if names else "- No critical findings identified"
    prompt = (
        "You are a strict cybersecurity auditor.\n"
        f"CLIENT CONTEXT: {context_note}\n"
        "CRITICAL FINDINGS LIST:\n"
        f"{summary_list}\n\n"
        "TASK: Write exactly 2 concise professional paragraphs for an Executive Summary "
        "describing overall network risk and business impact based only on this context "
        "and these findings."
    )
    response = client.chat(
        model=model_name,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0},
    )
    text = response.get("message", {}).get("content", "")
    return text.strip() if text else "Executive summary could not be generated."


# ---------------------------------------------------------------------------
# Streamlit UI
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Synthetic Auditor", layout="wide", page_icon="🔒")
    st.title("🔒 Synthetic Auditor")
    st.caption("Secure Local AI Layer — Local LLM analysis · Professional PDF export")

    col1, col2 = st.columns([3, 2])
    with col1:
        context_note = st.text_area(
            "Context Note",
            height=180,
            placeholder="Describe the client environment: industry, infrastructure, compliance requirements...",
            help="Used by the AI to tailor risk explanations to this specific client.",
        )
    with col2:
        st.markdown("**Upload Findings JSON**")
        uploaded_file = st.file_uploader(
            "Preprocessed findings JSON",
            type=["json"],
            help="Accepts: list of findings, or object with critical_findings/findings keys.",
            label_visibility="collapsed",
        )
        if uploaded_file:
            try:
                preview = load_preprocessed_findings(uploaded_file)
                uploaded_file.seek(0)
                sev_counts: Dict[str, int] = {}
                for finding in preview:
                    key = finding["severity"].capitalize()
                    sev_counts[key] = sev_counts.get(key, 0) + 1
                st.success(f"✅ {len(preview)} findings loaded")
                for sev, count in sorted(sev_counts.items()):
                    st.write(f"  • {sev}: {count}")
            except Exception:
                pass

    if "pdf_bytes" not in st.session_state:
        st.session_state.pdf_bytes = None

    st.divider()
    col_btn, col_dl = st.columns([2, 3])

    with col_btn:
        generate = st.button("⚡ Generate Audit Report", type="primary", use_container_width=True)

    if generate:
        if uploaded_file is None:
            st.warning("Please upload a preprocessed JSON findings file.")
            return
        try:
            findings = load_preprocessed_findings(uploaded_file)
            if not findings:
                st.warning("No findings found in uploaded JSON.")
                return

            client = ollama.Client(host=OLLAMA_HOST)
            model_name = resolve_ollama_model(client, OLLAMA_MODEL)
            st.info(f"Using Ollama model: **{model_name}**")

            progress = st.progress(0, text="Starting analysis...")
            with st.spinner("Running local LLM analysis..."):
                analyzed_findings = run_ollama_analysis(client, context_note, findings, model_name)
                progress.progress(60, text="Generating executive summary...")
                executive_summary = run_ollama_executive_summary(client, context_note, analyzed_findings, model_name)
                progress.progress(80, text="Building PDF...")
                generate_pdf(context_note, analyzed_findings, executive_summary, OUTPUT_PDF_PATH)
                progress.progress(100, text="Done!")

            with open(OUTPUT_PDF_PATH, "rb") as fh:
                st.session_state.pdf_bytes = fh.read()

            st.success(f"✅ Report generated — {len(analyzed_findings)} findings processed.")

        except json.JSONDecodeError:
            st.error("Uploaded file is not valid JSON.")
        except ollama.ResponseError as error:
            st.warning(f"Ollama error. Confirm it's running at {OLLAMA_HOST}. Details: {error}")
        except Exception as error:
            err = str(error).lower()
            if any(t in err for t in ["connection", "refused", "ollama"]):
                st.warning(f"Cannot connect to Ollama at {OLLAMA_HOST}. Start Ollama and ensure a model is installed.")
            else:
                st.error(f"Unexpected error: {error}")

    with col_dl:
        if st.session_state.pdf_bytes:
            fname = f"Audit_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
            st.download_button(
                label="📄 Download Audit Report (PDF)",
                data=st.session_state.pdf_bytes,
                file_name=fname,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
            )


if __name__ == "__main__":
    main()
