import sys
from io import BytesIO
from typing import List, Dict

# --- ReportLab Imports ---
# Base document template and flowables
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# Page size and units
from reportlab.lib.pagesizes import A5
from reportlab.lib.units import inch, mm

# Colors
from reportlab.lib import colors

# Paragraph styles
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

# Ensure we can find the reportlab library
try:
    from reportlab.lib.styles import getSampleStyleSheet
except ImportError:
    print("ReportLab library not found. Please install it: pip install reportlab")
    sys.exit(1)


class AssayReportGenerator:
    """
    Generates an A5 assay report PDF using ReportLab Platypus,
    mimicking the layout structure of the C# iTextSharp example.
    """

    def __init__(self):
        """
        Initialize the generator with company details.
        """
        self.company_name = "GLOBAL ASSAY SERVICES PTY LTD"
        self.company_address_one = "123 Assay Street, Metallurgy City"
        self.company_address_two = "State/Province, 54321, Country"
        self.company_phone_one = "+1 (555) 123-4567"
        self.company_phone_two = "+1 (555) 987-6543"
        self.styles = self.create_styles()

    def create_styles(self) -> Dict[str, ParagraphStyle]:
        """
        Create custom ParagraphStyles to match the C# example's fonts.
        """
        styles = {}
        base_font = "Helvetica"
        bold_font = "Helvetica-Bold"

        # Base style
        styles["Base"] = ParagraphStyle(
            name="Base",
            fontName=base_font,
            fontSize=8,
        )

        # Company name (C#: title_bold_helvetica)
        styles["CompanyName"] = ParagraphStyle(
            name="CompanyName",
            fontName=bold_font,
            fontSize=14,
            spaceAfter=5,
        )

        # Address (C#: medium_helvetica)
        styles["Address"] = ParagraphStyle(
            name="Address",
            parent=styles["Base"],
            fontSize=8,
        )

        # Phone/Date (C#: medium_helvetica, but with alignments)
        styles["Phone"] = ParagraphStyle(
            name="Phone",
            parent=styles["Base"],
            alignment=TA_LEFT,
        )
        styles["Date"] = ParagraphStyle(
            name="Date",
            parent=styles["Base"],
            fontName=bold_font,
            alignment=TA_RIGHT,
        )

        # Customer (C#: title_bold_helvetica for name)
        styles["CustomerLabel"] = ParagraphStyle(
            name="CustomerLabel",
            parent=styles["Base"],
            spaceBefore=0,
            spaceAfter=5,
        )

        # --- Table Styles ---

        # Table Header
        styles["TableHeader"] = ParagraphStyle(
            name="TableHeader",
            fontName=bold_font,
            fontSize=12,
            alignment=TA_LEFT
        )
        styles["TableSmallHeader"] = ParagraphStyle(
            name="TableSmallHeader",
            fontName=base_font,
            fontSize=7,
            alignment=TA_CENTER
        )
        styles["TableFinenessHeader"] = ParagraphStyle(
            name="TableFinenessHeader",
            fontName=bold_font,
            fontSize=11.5,
            alignment=TA_CENTER,
        )
        # Table Body
        styles["TableItemCode"] = ParagraphStyle(
            name="TableItemCode",
            fontName=bold_font,
            fontSize=14,
            alignment=TA_LEFT
        )
        styles["TableWeight"] = ParagraphStyle(
            name="TableWeight",
            fontName=base_font,
            fontSize=7,
            alignment=TA_CENTER,
            leading=8,
        )
        styles["TableFineness"] = ParagraphStyle(
            name="TableFineness",
            fontName=bold_font,
            fontSize=14,
            alignment=TA_CENTER,
        )

        # Terms & Footer
        styles["Terms"] = ParagraphStyle(
            name="Terms", parent=styles["Base"], fontSize=8, leading=10, spaceBefore=5, spaceAfter=10
        )
        styles["Footer"] = ParagraphStyle(
            name="Footer",
            parent=styles["Base"],
            fontSize=11,
            spaceBefore=40,
        )

        return styles

    def generate_pdf(
        self, customer_name: str, date: str, formcode_items: List[Dict]
    ) -> BytesIO:
        """
        Generate PDF for assay results using Platypus flowables.
        """
        buffer = BytesIO()

        # Set A5 page size and margins
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A5,
            leftMargin=15,
            rightMargin=15,
            topMargin=10,
            bottomMargin=10,
        )

        Story = []

        # 1-4. Header Content
        Story.append(Paragraph(self.company_name, self.styles["CompanyName"]))
        address_text = f"{self.company_address_one}, {self.company_address_two}"
        Story.append(Paragraph(address_text, self.styles["Address"]))

        contact_para = Paragraph(
            f"{self.company_phone_one} {self.company_phone_two}", self.styles["Phone"]
        )
        date_para = Paragraph(f"Date: {date}", self.styles["Date"])
        layout_data = [[contact_para, date_para]]
        layout_table = Table(layout_data, colWidths=["70%", "30%"])
        layout_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
        Story.append(layout_table)

        customer_text = f"<font name='Helvetica-Bold' size=14>{customer_name}</font>"
        Story.append(Paragraph(customer_text, self.styles["CustomerLabel"]))

        # 5. Result Table setup
        total_width = (A5[0] - doc.leftMargin - doc.rightMargin)
        total_ratio = 9.5
        col_widths = [
            (total_width * 7.0) / total_ratio,
            (total_width * 1.0) / total_ratio,
            (total_width * 1.5) / total_ratio,
        ]

        table_data = []

        # -- Table Header --
        header_item = Paragraph("ITEM CODE", self.styles["TableHeader"])

        # Nested header for S.Weight/S.Return
        nested_header_data = [
            [Paragraph("S.Weight", self.styles["TableSmallHeader"])],
            [Paragraph("S.Return", self.styles["TableSmallHeader"])],
        ]
        # FIX: Explicitly set row heights in the nested header table
        nested_header_table = Table(nested_header_data, colWidths=[col_widths[1]], rowHeights=[11, 11])
        nested_header_table.setStyle(
            TableStyle(
                [
                    ("ALIGN", (0,0), (-1,-1), "CENTER"),
                    ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0, colors.transparent),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )

        header_fineness = Paragraph("Fineness", self.styles["TableFinenessHeader"])
        table_data.append([header_item, nested_header_table, header_fineness])

        # -- Table Data Rows (14 rows total) --
        for i in range(14):
            item = formcode_items[i] if i < len(formcode_items) else {}

            itemcode = item.get("itemcode", "")
            sampleweight = item.get("sampleweight", "")
            samplereturn = item.get("samplereturn", "")
            finalresult = item.get("finalresult", "")

            item_code_para = Paragraph(itemcode, self.styles["TableItemCode"])

            # Nested data for S.Weight/S.Return
            nested_data = [
                [Paragraph(sampleweight, self.styles["TableWeight"])],
                [Paragraph(samplereturn, self.styles["TableWeight"])],
            ]
            # FIX: Explicitly set row heights in the nested data table
            nested_data_table = Table(nested_data, colWidths=[col_widths[1]], rowHeights=[11, 11])
            nested_data_table.setStyle(
                TableStyle(
                    [
                        ("ALIGN", (0,0), (-1,-1), "CENTER"),
                        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
                        ("GRID", (0, 0), (-1, -1), 0, colors.transparent),
                        ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                        ("LEFTPADDING", (0, 0), (-1, -1), 0),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                        ("TOPPADDING", (0, 0), (-1, -1), 0),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                    ]
                )
            )

            fineness_para = Paragraph(finalresult, self.styles["TableFineness"])

            table_data.append([item_code_para, nested_data_table, fineness_para])

        # Create the main table
        row_heights = [23] + [23] * 14
        result_table = Table(
            table_data, colWidths=col_widths, rowHeights=row_heights
        )
        result_table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    # Alignment for Item Code and Fineness (Top) for data rows
                    ("VALIGN", (0, 1), (0, -1), "TOP"),
                    ("VALIGN", (2, 1), (2, -1), "TOP"),
                    # Padding for outer cells
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                    # Padding reset for nested table column (index 1)
                    ("LEFTPADDING", (1, 0), (1, -1), 0),
                    ("RIGHTPADDING", (1, 0), (1, -1), 0),
                    ("TOPPADDING", (1, 0), (1, -1), 0),
                    ("BOTTOMPADDING", (1, 0), (1, -1), 0),
                ]
            )
        )

        Story.append(result_table)

        # 6. Terms
        terms_text = (
            "<b>NOTE:</b><br/>"
            "1. The gold fire assay is conducted following the standardized reference utilized by assay laboratories globally for the purpose of hallmarking.<br/>"
            "2. The indicated fineness of the precious metal content serves as a reference only and is not officially certified for any hallmarking purposes.<br/>"
            "3. We shall not assume any legal liability for discrepancies identified.<br/>"
            "4. We strongly encourage customer to take back their sample left as soon as possible.<br/>"
            "5. We shall not assume any legal liability for any loss, damage, or theft of samples left."
        )
        Story.append(Paragraph(terms_text, self.styles["Terms"]))

        # 7. Footer
        Story.append(
            Paragraph("Received by: ____________________", self.styles["Footer"])
        )

        # Build the PDF
        try:
            doc.build(Story)
        except Exception as e:
            print(f"Error building PDF: {e}")
            buffer = BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A5)
            Story = [Paragraph(f"Error generating PDF: {e}", self.styles["Base"])]
            doc.build(Story)
            buffer.seek(0)
            return buffer

        buffer.seek(0)
        return buffer


if __name__ == "__main__":
    """
    A simple test script to generate a sample PDF with 14 unique samples.
    This will create a 'test_report.pdf' in the same directory.
    """
    print("Generating sample assay report with 14 unique samples...")

    sample_customer = "Acme Ore Refiners, Inc."
    sample_date = "2025-11-09"
    
    # Generate 14 unique sample items
    sample_items = []
    base_weight = 100.0
    base_fineness = 999.0

    for i in range(1, 15):
        weight = base_weight - (i * 0.5)
        return_weight = weight - (i * 0.05)
        fineness = base_fineness - (i * 0.1)

        sample_items.append(
            {
                "itemcode": f"Lot-{i:03d}",
                "sampleweight": f"{weight:.1f}g",
                "samplereturn": f"{return_weight:.1f}g",
                "finalresult": f"{fineness:.1f}",
            }
        )

    # Create generator instance
    generator = AssayReportGenerator()

    # Generate PDF in memory
    pdf_buffer = generator.generate_pdf(sample_customer, sample_date, sample_items)

    # Write the in-memory PDF to a file
    output_filename = "test_report.pdf"
    try:
        with open(output_filename, "wb") as f:
            f.write(pdf_buffer.getvalue())
        print(f"Successfully generated '{output_filename}'.")
    except IOError as e:
        print(f"Error writing file: {e}")


# Singleton instance
pdf_generator = AssayReportGenerator()
