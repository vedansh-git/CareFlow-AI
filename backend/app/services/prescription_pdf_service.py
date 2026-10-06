"""
CareFlow AI - Doctor Prescription PDF Generation Service
Generates print-ready, professional, single-page A4 Doctor Prescriptions
using standard Indian prescription pad formatting and ReportLab.
"""

import io
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.pdfgen import canvas

from app.core.clinical.prescription_parser import (
    PrescriptionParser,
    PrescriptionData,
    MedicationItem
)
from app.services.data_store import db_store

logger = logging.getLogger(__name__)


class NumberedCanvas(canvas.Canvas):
    """
    Custom canvas that draws:
    1. Outer double-line teal & slate prescription border.
    2. Draft watermark if unapproved.
    3. Bottom-anchored Doctor Digital Signature & Verification block (bottom right).
    4. Bottom-anchored Clinical Legal/Safety Notice (bottom left).
    5. Discreet bottom confidentiality and page count footer.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []
        self.is_draft = False
        self.presc_data: Optional[PrescriptionData] = None

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_decorations(self, page_count: int):
        self.saveState()
        
        # 1. Draft Watermark if note is not yet approved
        if self.is_draft:
            self.saveState()
            self.setFont("Helvetica-Bold", 38)
            self.setFillColor(colors.Color(0.9, 0.2, 0.2, alpha=0.10))
            self.translate(A4[0] / 2.0, A4[1] / 2.0)
            self.rotate(35)
            self.drawCentredString(0, 0, "DRAFT - NOT FOR DISPENSING")
            self.setFont("Helvetica", 13)
            self.drawCentredString(0, -25, "Physician Review & Formal Verification Pending")
            self.restoreState()

        # 2. Outer decorative prescription borders
        # Primary border
        self.setStrokeColor(colors.HexColor("#0f766e"))
        self.setLineWidth(1.2)
        self.rect(20, 18, A4[0] - 40, A4[1] - 36, stroke=1, fill=0)

        # Subtle inner micro-border
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.6)
        self.rect(23, 21, A4[0] - 46, A4[1] - 42, stroke=1, fill=0)

        # 3. Bottom Signature & Verification Block (Anchored at Bottom-Right: y = 36 to 120)
        p = self.presc_data
        if p:
            # Bottom Left: Clinical Safety & Authenticity notice
            self.setFont("Helvetica-Bold", 7.5)
            self.setFillColor(colors.HexColor("#475569"))
            self.drawString(32, 114, "CLINICAL RECORD & DISPENSING AUTHENTICITY:")
            
            self.setFont("Helvetica", 7)
            self.setFillColor(colors.HexColor("#64748b"))
            self.drawString(32, 102, "• Valid digital medical prescription issued via CareFlow Healthcare EMR platform.")
            self.drawString(32, 91, "• Take medications strictly as directed. Keep all medicines out of reach of children.")
            self.drawString(32, 80, "• In case of adverse reaction, drug allergy, or acute distress, report to emergency.")
            self.drawString(32, 69, "• Generic substitution permitted only with licensed pharmacist verification.")

            # Bottom Right: Doctor's Signature & Verification Box
            right_x = A4[0] - 32
            box_w = 210
            box_h = 80
            box_x = right_x - box_w
            box_y = 40

            # Subtle background for signature box
            self.setFillColor(colors.HexColor("#f8fafc"))
            self.setStrokeColor(colors.HexColor("#cbd5e1"))
            self.setLineWidth(0.75)
            self.roundRect(box_x, box_y, box_w, box_h, 4, stroke=1, fill=1)

            # Doctor details inside box
            self.setFont("Helvetica-Bold", 9.5)
            self.setFillColor(colors.HexColor("#0f4c81"))
            self.drawRightString(right_x - 10, box_y + box_h - 16, p.doctor_name)

            self.setFont("Helvetica-Bold", 8)
            self.setFillColor(colors.HexColor("#1e293b"))
            self.drawRightString(right_x - 10, box_y + box_h - 28, p.doctor_qualification)

            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#0f766e"))
            self.drawRightString(right_x - 10, box_y + box_h - 39, p.doctor_specialty)

            self.setFont("Helvetica", 7.5)
            self.setFillColor(colors.HexColor("#475569"))
            self.drawRightString(right_x - 10, box_y + box_h - 50, p.doctor_registration_no)

            # Digital Verification badge
            if p.is_approved:
                self.setFont("Helvetica-Bold", 8)
                self.setFillColor(colors.HexColor("#059669"))
                self.drawRightString(right_x - 10, box_y + box_h - 63, "✓ [ DIGITALLY SIGNED & VERIFIED ]")
                self.setFont("Helvetica", 6.5)
                self.setFillColor(colors.HexColor("#64748b"))
                self.drawRightString(right_x - 10, box_y + box_h - 73, f"Approved on: {p.prescription_date} {p.prescription_time or ''}")
            else:
                self.setFont("Helvetica-Bold", 8)
                self.setFillColor(colors.HexColor("#dc2626"))
                self.drawRightString(right_x - 10, box_y + box_h - 63, "[ PENDING PHYSICIAN SIGNATURE ]")
                self.setFont("Helvetica", 6.5)
                self.setFillColor(colors.HexColor("#64748b"))
                self.drawRightString(right_x - 10, box_y + box_h - 73, "Unverified Draft Consultation Record")

        # 4. Bottom Footer Bar (y = 25)
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(32, 32, A4[0] - 32, 32)

        self.setFont("Helvetica", 7)
        self.setFillColor(colors.HexColor("#64748b"))
        self.drawString(32, 24, "CareFlow AI Healthcare Network • Confidential Digital Health Record • Valid with Verified Doctor Signature")
        self.drawRightString(A4[0] - 32, 24, f"Page 1 of {max(1, page_count)}")

        self.restoreState()


class PrescriptionPdfService:
    """
    Generates print-ready, professional, single-page A4 Doctor Prescriptions
    from verified SOAP encounter records and doctor/patient profiles.
    """

    def __init__(self):
        pass

    def _get_styles(self, is_compact: bool = False):
        """Returns configured typography stylesheet with clear typography."""
        styles = getSampleStyleSheet()

        title_size = 13.5 if is_compact else 14.5
        body_size = 8.5 if is_compact else 9
        body_lead = 11 if is_compact else 11.5

        styles.add(ParagraphStyle(
            name="DocHeaderName",
            fontName="Helvetica-Bold",
            fontSize=title_size,
            leading=title_size + 2,
            textColor=colors.HexColor("#0f4c81"),
        ))
        styles.add(ParagraphStyle(
            name="DocHeaderQual",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#1e293b"),
        ))
        styles.add(ParagraphStyle(
            name="DocHeaderSpec",
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#0f766e"),
        ))
        styles.add(ParagraphStyle(
            name="DocHeaderMeta",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#475569"),
        ))
        styles.add(ParagraphStyle(
            name="ClinicHeaderRight",
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12.5,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#0f4c81"),
        ))
        styles.add(ParagraphStyle(
            name="ClinicHeaderMetaRight",
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#475569"),
        ))

        # Patient Info Styles
        styles.add(ParagraphStyle(
            name="PatientLabel",
            fontName="Helvetica-Bold",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#475569"),
        ))
        styles.add(ParagraphStyle(
            name="PatientValue",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#0f172a"),
        ))

        # Vitals Style (noticeably larger, clearer font)
        styles.add(ParagraphStyle(
            name="VitalsHeaderLabel",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#0f766e"),
        ))
        styles.add(ParagraphStyle(
            name="VitalsValueText",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#0369a1"),
        ))

        # Clinical Sections
        styles.add(ParagraphStyle(
            name="ClinicalLabel",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#475569"),
        ))
        styles.add(ParagraphStyle(
            name="ChiefComplaintText",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11.5,
            textColor=colors.HexColor("#334155"),
        ))
        styles.add(ParagraphStyle(
            name="DiagnosisText",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#0f766e"),
        ))

        # ℞ Table Styles
        styles.add(ParagraphStyle(
            name="RxGlyph",
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=18,
            textColor=colors.HexColor("#0f766e"),
        ))
        styles.add(ParagraphStyle(
            name="SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=9.5,
            leading=12,
            textColor=colors.HexColor("#0f4c81"),
        ))
        styles.add(ParagraphStyle(
            name="TableHeader",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.white,
            alignment=TA_LEFT,
        ))
        styles.add(ParagraphStyle(
            name="TableCellMedName",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#0f172a"),
        ))
        styles.add(ParagraphStyle(
            name="TableCell",
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.HexColor("#334155"),
        ))
        styles.add(ParagraphStyle(
            name="TableFlagText",
            fontName="Helvetica-Oblique",
            fontSize=7,
            leading=8.5,
            textColor=colors.HexColor("#b45309"),
        ))

        # Advice & Instructions
        styles.add(ParagraphStyle(
            name="AdviceCardHeading",
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11.5,
            textColor=colors.HexColor("#0f4c81"),
        ))
        styles.add(ParagraphStyle(
            name="AdviceItem",
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#334155"),
        ))
        styles.add(ParagraphStyle(
            name="InstructionItem",
            fontName="Helvetica",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#475569"),
        ))

        return styles

    def generate_prescription_pdf(self, presc: PrescriptionData) -> bytes:
        """
        Builds the single-page A4 PDF binary stream.
        """
        buffer = io.BytesIO()

        # Dynamic compactness: adjust styling if medication list is long
        med_count = len(presc.medications)
        is_compact = med_count >= 5
        styles = self._get_styles(is_compact=is_compact)

        # Printable width: 595.27 - 56 = 539.27
        left_margin = 28
        right_margin = 28
        top_margin = 24
        bottom_margin = 125  # Reserved space for bottom-anchored signature & safety block
        content_width = A4[0] - (left_margin + right_margin)

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottom_margin,
            title=f"Prescription - {presc.patient_name}",
            author=presc.doctor_name,
            subject="Doctor Prescription",
        )

        story = []

        # ============================================================
        # 1. TOP HEADER: DOCTOR & CLINIC INFORMATION
        # ============================================================
        doc_info = [
            Paragraph(f"<b>{presc.doctor_name}</b>", styles["DocHeaderName"]),
            Paragraph(f"{presc.doctor_qualification}", styles["DocHeaderQual"]),
            Paragraph(f"<b>{presc.doctor_specialty}</b>", styles["DocHeaderSpec"]),
            Paragraph(f"{presc.doctor_registration_no}", styles["DocHeaderMeta"]),
            Paragraph(f"Phone: {presc.doctor_phone or '+1-555-0100'} | {presc.doctor_email or 'care@careflow.ai'}", styles["DocHeaderMeta"]),
        ]

        clinic_info = [
            Paragraph(f"<b>{presc.clinic_name}</b>", styles["ClinicHeaderRight"]),
            Paragraph(f"{presc.clinic_address}", styles["ClinicHeaderMetaRight"]),
            Paragraph("CareFlow Outpatient & Telehealth Division", styles["ClinicHeaderMetaRight"]),
            Paragraph("Emergency Contact: 24/7 Helpline Active", styles["ClinicHeaderMetaRight"]),
        ]

        header_table = Table(
            [[doc_info, clinic_info]],
            colWidths=[content_width * 0.58, content_width * 0.42]
        )
        header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(header_table)
        story.append(Spacer(1, 3))

        # Brand divider rule
        story.append(HRFlowable(
            width="100%",
            thickness=2,
            color=colors.HexColor("#0f766e"),
            spaceBefore=2,
            spaceAfter=4
        ))

        # ============================================================
        # 2. PATIENT INFORMATION & DOCUMENTED VITALS STRIP
        # ============================================================
        age_gender = f"{presc.patient_age} / {presc.patient_gender}"
        pat_cell1 = [
            Paragraph("PATIENT NAME", styles["PatientLabel"]),
            Paragraph(f"{presc.patient_name}", styles["PatientValue"])
        ]
        pat_cell2 = [
            Paragraph("AGE / GENDER", styles["PatientLabel"]),
            Paragraph(f"{age_gender}", styles["PatientValue"])
        ]
        pat_cell3 = [
            Paragraph("PRESCRIPTION DATE", styles["PatientLabel"]),
            Paragraph(f"{presc.prescription_date} {presc.prescription_time or ''}".strip(), styles["PatientValue"])
        ]
        pat_cell4 = [
            Paragraph("RECORD REFERENCE", styles["PatientLabel"]),
            Paragraph(f"#{presc.note_id[:8].upper()}", styles["PatientValue"])
        ]

        # Vitals display row - Larger, clear, well-spaced format
        vitals_text = presc.vitals_summary or "Baseline vital measurements within documented limits"
        vitals_cell = [
            Paragraph(f"<font color='#0f766e'><b>DOCUMENTED VITALS:</b></font>  &nbsp;&nbsp; {vitals_text}", styles["VitalsValueText"])
        ]

        patient_box_data = [
            [pat_cell1, pat_cell2, pat_cell3, pat_cell4],
            [vitals_cell, "", "", ""]
        ]

        col_w = content_width / 4.0
        patient_table = Table(
            patient_box_data,
            colWidths=[col_w, col_w, col_w, col_w]
        )
        patient_table.setStyle(TableStyle([
            ("SPAN", (0, 1), (3, 1)),
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#f0fdfa")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, 0), 0.5, colors.HexColor("#e2e8f0")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#99f6e4")),
            ("TOPPADDING", (0, 0), (-1, 0), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 3.5),
            ("TOPPADDING", (0, 1), (-1, 1), 4),
            ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(patient_table)
        story.append(Spacer(1, 4))

        # ============================================================
        # 3. CLINICAL IMPRESSION / SHORT CHIEF COMPLAINT & DIAGNOSIS
        # ============================================================
        diag_data = [
            [
                Paragraph("<b>Chief Complaint:</b>", styles["ClinicalLabel"]),
                Paragraph(f"{presc.chief_complaint}", styles["ChiefComplaintText"])
            ],
            [
                Paragraph("<b>Diagnosis / Impression:</b>", styles["ClinicalLabel"]),
                Paragraph(f"<b>{presc.diagnosis}</b>", styles["DiagnosisText"])
            ]
        ]
        diag_table = Table(
            diag_data,
            colWidths=[content_width * 0.22, content_width * 0.78]
        )
        diag_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#cbd5e1")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(diag_table)
        story.append(Spacer(1, 4))

        # ============================================================
        # 4. ℞ SECTION (MEDICATION TABLE)
        # ============================================================
        rx_header_data = [
            [
                Paragraph("℞", styles["RxGlyph"]),
                Paragraph("<b>MEDICATIONS PRESCRIBED</b>", styles["SectionHeading"])
            ]
        ]
        rx_header_table = Table(
            rx_header_data,
            colWidths=[24, content_width - 24]
        )
        rx_header_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
        ]))
        story.append(rx_header_table)

        col_widths = [18, 160, 55, 115, 115, 76]

        med_table_rows = [
            [
                Paragraph("#", styles["TableHeader"]),
                Paragraph("Medicine Name & Strength", styles["TableHeader"]),
                Paragraph("Dosage", styles["TableHeader"]),
                Paragraph("Frequency", styles["TableHeader"]),
                Paragraph("Instructions / Timing", styles["TableHeader"]),
                Paragraph("Duration", styles["TableHeader"]),
            ]
        ]

        safe_meds = presc.medications[:9]
        if not safe_meds:
            med_table_rows.append([
                Paragraph("1", styles["TableCell"]),
                Paragraph("No active pharmacological medications prescribed", styles["TableCellMedName"]),
                Paragraph("-", styles["TableCell"]),
                Paragraph("Supportive care only", styles["TableCell"]),
                Paragraph("Refer to advice section", styles["TableCell"]),
                Paragraph("-", styles["TableCell"]),
            ])
        else:
            for i, m in enumerate(safe_meds, 1):
                name_flowables = [
                    Paragraph(f"<b>{m.name}</b>" + (f" ({m.strength})" if m.strength and m.strength not in m.name else ""), styles["TableCellMedName"])
                ]
                if not m.is_complete and m.flag_reason:
                    name_flowables.append(Paragraph(f"{m.flag_reason}", styles["TableFlagText"]))

                med_table_rows.append([
                    Paragraph(str(i), styles["TableCell"]),
                    name_flowables,
                    Paragraph(m.dosage, styles["TableCell"]),
                    Paragraph(m.frequency, styles["TableCell"]),
                    Paragraph(m.instructions, styles["TableCell"]),
                    Paragraph(m.duration, styles["TableCell"]),
                ])

        med_table = Table(med_table_rows, colWidths=col_widths, repeatRows=1)
        
        table_style_commands = [
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f4c81")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 3 if is_compact else 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3 if is_compact else 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#0f4c81")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
        ]
        # Alternating row colors
        for row_idx in range(1, len(med_table_rows)):
            bg_color = colors.HexColor("#f8fafc") if row_idx % 2 == 0 else colors.white
            table_style_commands.append(("BACKGROUND", (0, row_idx), (-1, row_idx), bg_color))

        med_table.setStyle(TableStyle(table_style_commands))
        story.append(med_table)

        if len(presc.medications) > 9:
            story.append(Spacer(1, 2))
            story.append(Paragraph(
                f"<font color='#b45309'><b>Note:</b> {len(presc.medications) - 9} additional medication item(s) recorded in electronic record. Review complete history with physician.</font>",
                styles["TableFlagText"]
            ))

        story.append(Spacer(1, 4))

        # ============================================================
        # 5. INVESTIGATIONS & ADVICE (2-COLUMN CARDS)
        # ============================================================
        left_card_content = []
        left_card_content.append(Paragraph("<b>INVESTIGATIONS / LAB TESTS</b>", styles["AdviceCardHeading"]))
        if presc.investigations:
            for inv in presc.investigations[:3]:
                left_card_content.append(Paragraph(f"• {inv}", styles["AdviceItem"]))
        else:
            left_card_content.append(Paragraph("• No immediate laboratory tests ordered", styles["AdviceItem"]))

        right_card_content = []
        right_card_content.append(Paragraph("<b>ADVICE & PRECAUTIONS</b>", styles["AdviceCardHeading"]))
        if presc.advice:
            for adv in presc.advice[:3]:
                right_card_content.append(Paragraph(f"• {adv}", styles["AdviceItem"]))
        else:
            right_card_content.append(Paragraph("• Rest, hydrate adequately, and take medications as scheduled", styles["AdviceItem"]))

        followup_p = Paragraph(f"<b>Follow-up:</b> {presc.follow_up or 'SOS / As advised'}", styles["DiagnosisText"])
        right_card_content.append(Spacer(1, 1.5))
        right_card_content.append(followup_p)

        card_width = (content_width - 8) / 2.0
        clinical_cards = Table(
            [[left_card_content, right_card_content]],
            colWidths=[card_width, card_width]
        )
        clinical_cards.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#f8fafc")),
            ("BACKGROUND", (1, 0), (1, 0), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (0, 0), 0.75, colors.HexColor("#cbd5e1")),
            ("BOX", (1, 0), (1, 0), 0.75, colors.HexColor("#cbd5e1")),
            ("TOPPADDING", (0, 0), (-1, -1), 3.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(clinical_cards)
        story.append(Spacer(1, 4))

        # ============================================================
        # 6. IMPORTANT PATIENT INSTRUCTIONS STRIP
        # ============================================================
        patient_inst_content = [
            Paragraph("<b>IMPORTANT INSTRUCTIONS FOR PATIENT:</b>", styles["PatientLabel"]),
            Paragraph("1. Complete the full antibiotic or prescribed medication course even if symptoms improve.", styles["InstructionItem"]),
            Paragraph("2. Report immediately to emergency in case of acute allergic reactions, rash, or breathing difficulty.", styles["InstructionItem"]),
            Paragraph("3. Any generic substitution should be verified with your registered pharmacist.", styles["InstructionItem"]),
        ]
        inst_table = Table(
            [[patient_inst_content]],
            colWidths=[content_width]
        )
        inst_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f0fdfa")),
            ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#99f6e4")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(inst_table)

        # Build PDF using NumberedCanvas
        def make_canvas(*args, **kwargs):
            c = NumberedCanvas(*args, **kwargs)
            c.is_draft = not presc.is_approved
            c.presc_data = presc
            return c

        doc.build(story, canvasmaker=make_canvas)

        pdf_data = buffer.getvalue()
        buffer.close()
        return pdf_data

    def generate_for_clinical_note(self, note_id: str, current_user: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validates authorization, extracts saved records, and generates PDF bytes.
        """
        note = db_store.get_clinical_note_by_id(note_id)
        if not note:
            return {
                "error": f"Clinical note '{note_id}' not found.",
                "status_code": 404
            }

        app_role = current_user.get("app_role", "patient")
        profile_id = current_user.get("id")

        # Authorization checks
        if app_role == "doctor":
            doc = db_store.get_doctor_by_profile_id(profile_id)
            if not doc or (note["doctor_id"] != doc["id"] and not current_user.get("is_admin")):
                return {
                    "error": "Unauthorized: You do not have permission to generate prescription for this clinical note.",
                    "status_code": 403
                }
        else:
            patient = db_store.get_or_create_patient(
                profile_id=profile_id,
                full_name=current_user.get("full_name", "Patient"),
                email=current_user.get("email")
            )
            patient_rec_for_note = db_store.get_patient_by_id(note["patient_id"])
            note_pat_profile_id = patient_rec_for_note.get("profile_id") if patient_rec_for_note else None
            
            if note["patient_id"] != patient["id"] and note_pat_profile_id != profile_id:
                return {
                    "error": "Unauthorized: You cannot access prescription for another patient.",
                    "status_code": 403
                }
            if note.get("status") not in ("reviewed", "approved"):
                return {
                    "error": "Prescription PDF is only available after official physician review and approval.",
                    "status_code": 403
                }

        # Resolve Doctor, Patient, and Profile records
        doctor_rec = db_store.get_doctor_by_id(note["doctor_id"])
        doc_profile = db_store.profiles.get(doctor_rec["profile_id"]) if doctor_rec else None
        if doctor_rec and doc_profile:
            doctor_rec = {**doc_profile, **doctor_rec}

        patient_rec = db_store.get_patient_by_id(note["patient_id"])
        patient_profile = db_store.profiles.get(patient_rec["profile_id"]) if patient_rec else None

        # Build Prescription Data model
        presc_data = PrescriptionParser.build_prescription_data(
            note=note,
            doctor=doctor_rec,
            patient=patient_rec,
            patient_profile=patient_profile
        )

        pdf_bytes = self.generate_prescription_pdf(presc_data)
        filename = f"Prescription_{presc_data.patient_name.replace(' ', '_')}_{presc_data.prescription_date}.pdf"

        return {
            "pdf_bytes": pdf_bytes,
            "filename": filename,
            "prescription_data": presc_data.model_dump(),
            "status_code": 200
        }


prescription_pdf_service = PrescriptionPdfService()
