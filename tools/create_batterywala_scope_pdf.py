from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "pdf" / "BatteryWala_Project_Scope_Deliverables_and_Commercial_Terms.pdf"
LOGO = ROOT / "app" / "static" / "images" / "batterywala-logo-original.png"

BLUE = colors.HexColor("#081565")
ORANGE = colors.HexColor("#F36A21")
INK = colors.HexColor("#17213A")
MUTED = colors.HexColor("#667085")
LINE = colors.HexColor("#D9DFEA")
PALE_BLUE = colors.HexColor("#F3F6FD")
PALE_ORANGE = colors.HexColor("#FFF4EC")
GREEN = colors.HexColor("#14804A")


styles = getSampleStyleSheet()
styles.add(ParagraphStyle(
    name="DocTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=22, leading=27, textColor=BLUE, alignment=TA_CENTER,
    spaceAfter=18,
))
styles.add(ParagraphStyle(
    name="Section", parent=styles["Heading1"], fontName="Helvetica-Bold",
    fontSize=16, leading=20, textColor=BLUE, spaceBefore=4, spaceAfter=10,
    keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="Sub", parent=styles["Heading2"], fontName="Helvetica-Bold",
    fontSize=10.5, leading=14, textColor=INK, spaceBefore=7, spaceAfter=2,
    keepWithNext=True,
))
styles.add(ParagraphStyle(
    name="BodySmall", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=9.2, leading=13.2, textColor=INK, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="BulletSmall", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=9.2, leading=13.2, leftIndent=11, firstLineIndent=-7,
    textColor=INK, spaceAfter=3,
))
styles.add(ParagraphStyle(
    name="Meta", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=10.2, leading=15, textColor=INK, spaceAfter=2,
))
styles.add(ParagraphStyle(
    name="Note", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.4, leading=12, textColor=MUTED, spaceAfter=4,
))
styles.add(ParagraphStyle(
    name="CommercialTitle", parent=styles["Title"], fontName="Helvetica-Bold",
    fontSize=27, leading=31, textColor=BLUE, alignment=TA_LEFT, spaceAfter=6,
))
styles.add(ParagraphStyle(
    name="RightSmall", parent=styles["BodyText"], fontName="Helvetica",
    fontSize=8.5, leading=11.5, textColor=MUTED, alignment=TA_RIGHT,
))
styles.add(ParagraphStyle(
    name="TableHeader", parent=styles["BodyText"], fontName="Helvetica-Bold",
    fontSize=9.2, leading=12, textColor=colors.white,
))


def P(text, style="BodySmall"):
    return Paragraph(text, styles[style])


def bullet(text):
    return P(f"- {text}", "BulletSmall")


def rule():
    return Table([[""]], colWidths=[174 * mm], rowHeights=[1], style=TableStyle([
        ("LINEBELOW", (0, 0), (-1, -1), 0.7, LINE),
    ]))


def section(number, title):
    return [Spacer(1, 4), P(f"{number}. {title.upper()}", "Section")]


def item(title, description):
    return [P(title, "Sub"), P(description)]


def info_box(title, text, color=PALE_BLUE):
    table = Table([[P(title, "Sub")], [P(text)]], colWidths=[174 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    return table


def header_footer(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(LINE)
    canvas.setLineWidth(0.5)
    canvas.line(18 * mm, 15 * mm, width - 18 * mm, 15 * mm)
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 9 * mm, "BatteryWala | Draft for review | 30 August 2026")
    canvas.drawRightString(width - 18 * mm, 9 * mm, str(doc.page))
    canvas.restoreState()


def add_brand_header(story, compact=False):
    if LOGO.exists():
        logo = Image(str(LOGO))
        max_w = 46 * mm if compact else 58 * mm
        max_h = 19 * mm if compact else 24 * mm
        ratio = min(max_w / logo.imageWidth, max_h / logo.imageHeight)
        logo.drawWidth = logo.imageWidth * ratio
        logo.drawHeight = logo.imageHeight * ratio
        logo.hAlign = "CENTER"
        story.extend([logo, Spacer(1, 7)])


def build_story():
    story = []

    # Page 1 - Overview
    add_brand_header(story)
    story.append(P("Project Scope, Deliverables & Commercial Terms", "DocTitle"))
    metadata = [
        [P("<b>Client</b>"), P("BatteryWala")],
        [P("<b>Project</b>"), P("Responsive Website, Battery Recommendation & Quotation Platform")],
        [P("<b>Proposed Timeline</b>"), P("6 weeks from confirmed kickoff")],
        [P("<b>Document Status</b>"), P("First draft for review")],
    ]
    meta_table = Table(metadata, colWidths=[39 * mm, 132 * mm])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([meta_table, Spacer(1, 14), rule()])
    story.extend(section(1, "Project objective"))
    story.append(P(
        "The objective is to deliver a professional, fast and reliable digital platform for BatteryWala that helps customers identify a suitable battery, request restoration support, receive a private quotation and connect with the business through clear conversion paths."
    ))
    story.append(P(
        "The platform will also provide an authenticated administration workspace for pricing catalogues, customer leads, quotation records, delivery attempts and operational recipients. This document defines the proposed deliverables, timeline, revision limits, commercial structure, responsibilities and project boundaries."
    ))
    story.extend([Spacer(1, 5), rule()])
    story.extend(section(2, "Solution scope at a glance"))
    for line in [
        "Responsive public website aligned with the approved BatteryWala identity.",
        "Application-specific battery recommendation and restoration enquiry forms.",
        "Server-generated customer quotations with private delivery links.",
        "Admin-only catalogue, pricing, lead and recipient management workspace.",
        "Email and SMS delivery integrations when provider credentials are supplied.",
        "Testing, deployment support, documentation and source-code handover.",
    ]:
        story.append(bullet(line))
    story.append(Spacer(1, 6))
    story.append(info_box(
        "Commercial note",
        "The final fee, tax treatment, legal billing name, address and tax registration details are intentionally left for confirmation on the commercial summary page. No amount has been assumed in this draft.",
        PALE_ORANGE,
    ))

    # Page 2 - Public website
    story.append(PageBreak())
    add_brand_header(story, compact=True)
    story.extend(section(3, "Public website experience"))
    for title, desc in [
        ("Information Architecture & Navigation", "Clear section flow for the homepage, applications, battery finder, services, reasons to choose BatteryWala, customer reviews, FAQs and contact actions."),
        ("Responsive UI Implementation", "Production-ready layouts for desktop, tablet and mobile using the approved BatteryWala blue, orange and supporting visual system."),
        ("Application Showcase", "Guided presentation of automotive, inverter and UPS, industrial, e-mobility, commercial, generator and speciality battery requirements."),
        ("Dynamic Battery Request Forms", "Forms adapt to the selected solution type and application, collecting only the details required for a useful fitment or restoration assessment."),
        ("Battery Recommendation Flow", "Server-side recommendation support based on submitted fitment details, configured catalogues and approved external search providers where applicable."),
        ("Battery Backup Restoration Service", "Dedicated enquiry experience for eligible inverter, industrial and traction battery restoration assessments, with clear next-step messaging."),
        ("Conversion & Contact Paths", "Telephone, WhatsApp, callback, quotation and enquiry actions placed throughout the experience to reduce customer effort."),
        ("Accessible Interaction States", "Keyboard-friendly controls, clear labels, validation messages, focus states, reduced-motion considerations and responsive component behaviour."),
        ("Performance & Content Polish", "Optimised assets, clear hierarchy, reusable components and sensible fallbacks for a dependable experience across common browsers and devices."),
    ]:
        story.extend(item(title, desc))
    story.append(info_box(
        "Public-facing safety note",
        "Recommendations remain fitment aids. Final battery dimensions, terminal layout, original equipment compatibility, warranty and current price should be confirmed before sale or installation.",
    ))

    # Page 3 - Platform and administration
    story.append(PageBreak())
    add_brand_header(story, compact=True)
    story.extend(section(4, "Full-stack platform & administration"))
    for title, desc in [
        ("Secure Admin Login", "Authenticated access to the operational workspace, with password protection, CSRF safeguards and controlled administrative actions."),
        ("Pricing Catalogue Workspace", "Upload and manage retail, MRP, dealer-price, scrap and buyback source documents without deleting unrelated catalogue data."),
        ("PDF & Image Data Extraction", "Text extraction with OCR fallback for supported PDF and image uploads, followed by structured preview, record validation and publication."),
        ("Catalogue Update Rules", "Matching brand and battery-model records are updated while new models are added to the appropriate catalogue. Existing unrelated records remain intact."),
        ("Automated Quotation Generation", "Customer-specific PDF quotations with immutable price snapshots, exchange handling, GST-aware customer pricing and clear manual-confirmation states."),
        ("Private Quotation Delivery", "Email attachment and SMS-link delivery options using time-independent private access tokens. Delivery begins only after the customer chooses a channel."),
        ("Lead & Delivery Records", "Storage of customer enquiries, quotation references, delivery attempts, provider outcomes and timestamps for operational follow-up."),
        ("Notification Recipient Management", "Admin controls for operational email and mobile recipients used for lead and workflow notifications."),
        ("Database & Configuration", "SQLite support by default with configurable database, public base URL, email, SMS and approved recommendation-provider settings."),
        ("Privacy-Aware Search", "Personal customer information is excluded from recommendation search requests; only allowlisted fitment fields and sources may influence results."),
    ]:
        story.extend(item(title, desc))

    # Page 4 - Timeline and revisions
    story.append(PageBreak())
    add_brand_header(story, compact=True)
    story.extend(section(5, "Proposed project timeline"))
    timeline = [
        ("Week 1 | Discovery & specification", "Business goals, content inputs, catalogue sources, user journeys, technical constraints and acceptance criteria."),
        ("Week 2 | UI system & responsive experience", "Page hierarchy, interface refinement, responsive states, forms, conversion paths and client design review."),
        ("Week 3 | Public website build", "Frontend implementation, dynamic application forms, validation, accessibility and WhatsApp/contact flows."),
        ("Week 4 | Backend & quotation platform", "Recommendation logic, catalogue matching, quotation PDFs, private tokens, lead records and delivery workflows."),
        ("Week 5 | Admin, imports & integrations", "Admin workspace, upload extraction, catalogue publishing, recipient management, email/SMS configuration and security checks."),
        ("Week 6 | QA, deployment & handover", "Functional tests, responsive verification, bug fixes, deployment configuration, documentation and final handover."),
    ]
    for title, desc in timeline:
        story.extend(item(title, desc))
    story.append(P(
        "The timeline begins after receipt of the advance, confirmed scope, required content, catalogue files, access credentials and other necessary inputs. Delayed feedback, approvals, credentials or content may extend delivery dates."
    ))
    story.extend([Spacer(1, 4), rule()])
    story.extend(section(6, "Revision policy"))
    story.append(P("The proposed scope includes:"))
    story.append(bullet("UI and responsive presentation: up to 2 consolidated revision rounds."))
    story.append(bullet("Functional workflow feedback: up to 2 consolidated revision rounds."))
    story.append(bullet("Final content corrections before launch: 1 consolidated round."))
    story.append(P(
        "A revision round means one consolidated, prioritised set of feedback submitted by the client. Minor corrections within the approved direction are included. A new design direction, substantial workflow change, revised data model or redesign after approval may be treated as additional work."
    ))

    # Page 5 - Scope and responsibilities
    story.append(PageBreak())
    add_brand_header(story, compact=True)
    story.extend(section(7, "Scope & additional work"))
    story.append(P(
        "Only the deliverables specifically stated in this document form the proposed scope. Examples of work that may require a separate quotation include additional portals or mobile apps, payment gateways, live inventory or ERP integration, multilingual content, advanced analytics, bespoke illustrations or videos, large-scale manual data entry, new delivery providers, custom AI training, ongoing advertising, and functionality requested after approval."
    ))
    story.append(P(
        "Additional work will begin only after the requirement, schedule and associated charges have been discussed and approved in writing. Material changes to a completed or approved phase may also be treated as additional work."
    ))
    story.extend([Spacer(1, 5), rule()])
    story.extend(section(8, "Client responsibilities"))
    story.append(P("The client is responsible for providing accurate and final project inputs, including:"))
    for line in [
        "Business, service, warranty, pricing, exchange and contact information.",
        "Approved logo, brand preferences, written content, images and videos.",
        "Current battery catalogues, vehicle mappings and restoration criteria.",
        "Domain, hosting, DNS and third-party provider access where required.",
        "SMTP, SMS, search or AI-provider credentials and approved usage limits.",
        "Legally required policies, tax information, consent wording and disclaimers.",
        "A single authorised feedback contact and timely consolidated approvals.",
        "Final pre-launch review of prices, content, links and business claims.",
    ]:
        story.append(bullet(line))
    story.append(P(
        "The service provider is not responsible for delays or incorrect output caused by missing, late, inaccurate or outdated client-supplied information, or by dependencies outside the provider's control."
    ))
    story.append(info_box(
        "Catalogue responsibility",
        "BatteryWala remains responsible for confirming that published customer prices, GST treatment, exchange values, warranties and fitment mappings are commercially and technically correct.",
        PALE_ORANGE,
    ))

    # Page 6 - Payment, ownership and support
    story.append(PageBreak())
    add_brand_header(story, compact=True)
    story.extend(section(9, "Payment structure"))
    for title, desc in [
        ("30% Advance", "Payable before project commencement and scheduling."),
        ("40% Build Milestone", "Payable after approval of the responsive UI and completion of the core public, quotation and administration workflows."),
        ("30% Final Payment", "Payable before production launch, final source-code handover and transfer of approved project assets."),
    ]:
        story.extend(item(title, desc))
    story.append(P(
        "The milestone percentages are proposed norms and may be revised in the final commercial quotation. Third-party fees and taxes, if applicable, will be stated separately."
    ))
    story.extend([Spacer(1, 4), rule()])
    story.extend(section(10, "Ownership & handover"))
    story.append(P(
        "Upon receipt of full payment, the client receives the approved project source code, project-specific design assets, configuration guidance and documentation included in this scope. Until full payment is received, working files, source code and project materials remain the property of the service provider."
    ))
    story.append(P(
        "Pre-existing tools, reusable utilities, open-source packages, third-party services, fonts, stock assets and licensed components remain subject to their original ownership and licence terms. Rejected concepts, exploratory work and internal working material are not included unless separately agreed."
    ))
    story.extend([Spacer(1, 4), rule()])
    story.extend(section(11, "Launch support & maintenance"))
    story.append(P(
        "The proposed handover includes 30 calendar days of post-launch defect support for reproducible issues within the approved scope. This period does not include new features, content updates, catalogue maintenance, provider-policy changes, hosting incidents, data correction, redesign or ongoing operational support."
    ))
    story.append(P(
        "Any recurring maintenance, monitoring, backups, content administration, security updates, catalogue operations or support-level commitment should be covered by a separate maintenance agreement."
    ))

    # Page 7 - Conditions and acceptance
    story.append(PageBreak())
    add_brand_header(story, compact=True)
    story.extend(section(12, "Important project conditions"))
    for line in [
        "Approvals should be provided in writing; approval of a phase allows work to proceed.",
        "Substantial changes after approval may affect both the timeline and commercial amount.",
        "Domain, hosting, email, SMS, search, AI, stock media, paid fonts and other external costs are excluded unless expressly listed.",
        "Third-party availability, pricing, quotas, policies and delivery outcomes cannot be guaranteed by the service provider.",
        "Automated recommendations and extracted catalogue records require human commercial and technical verification before live use.",
        "The client must provide legally compliant privacy, consent, warranty, refund and business terms applicable to its operations.",
        "Production deployment is subject to compatible hosting, required environment configuration and access being available.",
        "No performance, revenue, ranking, lead-volume or delivery-provider outcome is guaranteed.",
        "Any additional work requires written approval before commencement.",
    ]:
        story.append(bullet(line))
    story.extend([Spacer(1, 5), rule()])
    story.extend(section(13, "Final deliverable"))
    story.append(P(
        "At completion, BatteryWala will receive the approved responsive website, dynamic customer forms, recommendation and quotation workflows, catalogue and pricing administration workspace, lead and delivery records, configured integrations within scope, test coverage, deployment files, documentation and source-code handover described in this document."
    ))
    story.append(P(
        "This scope should be read together with the final commercial quotation, which will identify the contracting parties, tax treatment, approved fee, payment dates and any project-specific exclusions."
    ))
    story.append(Spacer(1, 18))
    sign = Table([
        [P("<b>Prepared by</b><br/>Name: To be confirmed<br/>Role / Company: To be confirmed<br/>Signature: ____________________<br/>Date: ____________________"),
         P("<b>Accepted for BatteryWala</b><br/>Name: To be confirmed<br/>Role: To be confirmed<br/>Signature: ____________________<br/>Date: ____________________")],
    ], colWidths=[84 * mm, 84 * mm])
    sign.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, LINE),
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sign)

    # Page 8 - Commercial summary
    story.append(PageBreak())
    top = Table([
        [P("PROFORMA COMMERCIAL SUMMARY", "CommercialTitle"),
         P("<b>Prepared by</b><br/>Name / Company: To be confirmed<br/>Address: To be confirmed<br/>Phone: To be confirmed<br/>Email: To be confirmed<br/>Tax ID / GSTIN: If applicable", "RightSmall")],
    ], colWidths=[104 * mm, 66 * mm])
    top.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.extend([top, Spacer(1, 10)])
    summary_meta = Table([
        [P("<b>Reference</b>"), P("BW-WEB-DRAFT-01"), P("<b>Date</b>"), P("30/08/2026")],
        [P("<b>Status</b>"), P("Draft - not a tax invoice"), P("<b>Validity</b>"), P("To be confirmed")],
        [P("<b>Prepared for</b>"), P("BatteryWala"), P("<b>Currency</b>"), P("INR")],
    ], colWidths=[29 * mm, 59 * mm, 27 * mm, 55 * mm])
    summary_meta.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), PALE_BLUE),
        ("BOX", (0, 0), (-1, -1), 0.7, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([summary_meta, Spacer(1, 16)])

    rows = [
        [P("#", "TableHeader"), P("Item & description", "TableHeader"), P("Qty", "TableHeader"), P("Amount", "TableHeader")],
        [P("1"), P("<b>Responsive Website UX/UI & Frontend</b><br/>Public information architecture, responsive interface, application showcase, dynamic request forms, accessibility and conversion paths."), P("1"), P("To be confirmed")],
        [P("2"), P("<b>Full-stack Recommendation & Quotation Platform</b><br/>Server workflows, catalogue matching, quotation PDFs, private access tokens, lead storage and customer delivery controls."), P("1"), P("To be confirmed")],
        [P("3"), P("<b>Admin, Catalogue Imports & Integrations</b><br/>Secure admin workspace, PDF/image extraction, catalogue publishing, recipients, SMTP/SMS configuration and operational records."), P("1"), P("To be confirmed")],
        [P("4"), P("<b>QA, Deployment & Handover</b><br/>Responsive and functional verification, production configuration support, documentation, source code and 30-day defect support."), P("1"), P("To be confirmed")],
    ]
    table = Table(rows, colWidths=[10 * mm, 112 * mm, 14 * mm, 34 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 1), (2, -1), "CENTER"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([table, Spacer(1, 12)])
    totals = Table([
        [P("Subtotal"), P("To be confirmed")],
        [P("Taxes, if applicable"), P("To be confirmed")],
        [P("<b>PROJECT TOTAL</b>"), P("<b>To be confirmed</b>")],
    ], colWidths=[58 * mm, 42 * mm], hAlign="RIGHT")
    totals.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.35, LINE),
        ("BACKGROUND", (0, 2), (-1, 2), PALE_ORANGE),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story.extend([totals, Spacer(1, 15)])
    story.append(info_box(
        "Proposed payment milestones",
        "30% advance | 40% build milestone | 30% before production launch and final handover",
    ))
    story.append(Spacer(1, 12))
    story.append(P(
        "<b>Notes</b><br/>This page is a draft commercial summary and is not a tax invoice or request for payment. Final contracting identity, address, tax information, fee, taxes, due dates and payment details must be inserted and approved before issue. Third-party charges are excluded unless expressly added to the final quotation.",
        "Note",
    ))
    story.append(Spacer(1, 22))
    story.append(P("Authorised signature: ______________________________", "BodySmall"))

    return story


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUTPUT), pagesize=A4,
        rightMargin=18 * mm, leftMargin=18 * mm,
        topMargin=16 * mm, bottomMargin=21 * mm,
        title="BatteryWala Project Scope, Deliverables and Commercial Terms",
        author="Draft prepared for BatteryWala",
        subject="Website design, development, quotation platform and commercial terms",
    )
    doc.build(build_story(), onFirstPage=header_footer, onLaterPages=header_footer)
    print(OUTPUT)


if __name__ == "__main__":
    main()
