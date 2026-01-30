"""
PDF export service for routes and plans.
"""

import io
from datetime import date, datetime

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class PDFExporter:
    """Export routes and plans to PDF."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom styles."""
        self.styles.add(
            ParagraphStyle(
                name="Title_Custom",
                parent=self.styles["Title"],
                fontSize=18,
                spaceAfter=20,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="Subtitle",
                parent=self.styles["Normal"],
                fontSize=12,
                textColor=colors.gray,
                spaceAfter=10,
            )
        )
        self.styles.add(
            ParagraphStyle(
                name="TableHeader",
                parent=self.styles["Normal"],
                fontSize=10,
                textColor=colors.white,
                alignment=TA_CENTER,
            )
        )

    def export_daily_plan(
        self,
        agent_name: str,
        plan_date: date,
        visits: list[dict],
        total_distance_km: float,
        total_duration_minutes: int,
    ) -> bytes:
        """
        Export daily visit plan to PDF.

        Args:
            agent_name: Name of the agent
            plan_date: Date of the plan
            visits: List of visit dictionaries
            total_distance_km: Total route distance
            total_duration_minutes: Total duration

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        # Title
        elements.append(Paragraph("Daily Visit Plan", self.styles["Title_Custom"]))

        # Agent and date info
        elements.append(Paragraph(f"Agent: {agent_name}", self.styles["Normal"]))
        elements.append(
            Paragraph(f"Date: {plan_date.strftime('%d.%m.%Y')} ({plan_date.strftime('%A')})", self.styles["Subtitle"])
        )

        # Summary
        elements.append(Spacer(1, 10 * mm))
        summary_data = [
            ["Total Visits", str(len(visits))],
            ["Total Distance", f"{total_distance_km:.1f} km"],
            ["Total Duration", f"{total_duration_minutes // 60}h {total_duration_minutes % 60}m"],
        ]
        summary_table = Table(summary_data, colWidths=[5 * cm, 4 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(summary_table)

        # Visits table
        elements.append(Spacer(1, 15 * mm))
        elements.append(Paragraph("Visit Schedule", self.styles["Heading2"]))

        if visits:
            # Table header
            table_data = [["#", "Time", "Client", "Address", "Distance", "Duration"]]

            # Table rows
            for visit in visits:
                table_data.append(
                    [
                        str(visit.get("sequence_number", "")),
                        visit.get("planned_time", ""),
                        visit.get("client_name", "")[:30],
                        visit.get("client_address", "")[:40] if visit.get("client_address") else "-",
                        f"{visit.get('distance_from_previous_km', 0):.1f} km",
                        f"{visit.get('duration_from_previous_minutes', 0)} min",
                    ]
                )

            visits_table = Table(
                table_data,
                colWidths=[1 * cm, 2 * cm, 4 * cm, 5.5 * cm, 2 * cm, 2 * cm],
            )
            visits_table.setStyle(
                TableStyle(
                    [
                        # Header style
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, 0), 9),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
                        # Body style
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ("ALIGN", (0, 1), (0, -1), "CENTER"),  # # column
                        ("ALIGN", (1, 1), (1, -1), "CENTER"),  # Time column
                        ("ALIGN", (4, 1), (5, -1), "RIGHT"),  # Distance/Duration
                        # Grid
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                        # Padding
                        ("PADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(visits_table)

        # Footer note
        elements.append(Spacer(1, 20 * mm))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}", self.styles["Subtitle"]))

        doc.build(elements)
        return buffer.getvalue()

    def export_weekly_plan(
        self,
        agent_name: str,
        week_start: date,
        daily_plans: list[dict],
        total_visits: int,
        total_distance_km: float,
    ) -> bytes:
        """
        Export weekly plan to PDF.

        Args:
            agent_name: Name of the agent
            week_start: Monday of the week
            daily_plans: List of daily plan dictionaries
            total_visits: Total visits for the week
            total_distance_km: Total distance for the week

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        # Title
        elements.append(Paragraph("Weekly Visit Plan", self.styles["Title_Custom"]))

        # Agent and week info
        elements.append(Paragraph(f"Agent: {agent_name}", self.styles["Normal"]))
        elements.append(
            Paragraph(
                f"Week: {week_start.strftime('%d.%m.%Y')} - "
                f"{(week_start + __import__('datetime').timedelta(days=4)).strftime('%d.%m.%Y')}",
                self.styles["Subtitle"],
            )
        )

        # Weekly summary
        elements.append(Spacer(1, 10 * mm))
        summary_data = [
            ["Total Visits", str(total_visits)],
            ["Total Distance", f"{total_distance_km:.1f} km"],
            ["Days Planned", str(len([d for d in daily_plans if d.get("visits")]))],
        ]
        summary_table = Table(summary_data, colWidths=[5 * cm, 4 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(summary_table)

        # Daily breakdown
        elements.append(Spacer(1, 15 * mm))
        elements.append(Paragraph("Daily Breakdown", self.styles["Heading2"]))

        days_data = [["Day", "Date", "Visits", "Distance", "Duration"]]
        for plan in daily_plans:
            days_data.append(
                [
                    plan.get("day_of_week", ""),
                    plan.get("date", ""),
                    str(len(plan.get("visits", []))),
                    f"{plan.get('total_distance_km', 0):.1f} km",
                    f"{plan.get('total_duration_minutes', 0)} min",
                ]
            )

        days_table = Table(days_data, colWidths=[3 * cm, 3 * cm, 2 * cm, 3 * cm, 3 * cm])
        days_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                    ("PADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(days_table)

        # Detailed daily plans
        for plan in daily_plans:
            if not plan.get("visits"):
                continue

            elements.append(PageBreak())
            elements.append(
                Paragraph(f"{plan.get('day_of_week', '')} - {plan.get('date', '')}", self.styles["Heading2"])
            )

            visits_data = [["#", "Time", "Client", "Address"]]
            for visit in plan.get("visits", []):
                visits_data.append(
                    [
                        str(visit.get("sequence_number", "")),
                        visit.get("planned_time", ""),
                        visit.get("client_name", "")[:35],
                        visit.get("client_address", "")[:45] if visit.get("client_address") else "-",
                    ]
                )

            visits_table = Table(
                visits_data,
                colWidths=[1 * cm, 2 * cm, 5 * cm, 6.5 * cm],
            )
            visits_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("ALIGN", (0, 0), (1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                        ("PADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            elements.append(visits_table)

        # Footer
        elements.append(Spacer(1, 20 * mm))
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}", self.styles["Subtitle"]))

        doc.build(elements)
        return buffer.getvalue()

    def export_delivery_route(
        self,
        vehicle_name: str,
        license_plate: str,
        route_date: date,
        stops: list[dict],
        total_distance_km: float,
        total_weight_kg: float,
    ) -> bytes:
        """
        Export delivery route to PDF.

        Args:
            vehicle_name: Name of the vehicle
            license_plate: Vehicle license plate
            route_date: Date of the route
            stops: List of stop dictionaries
            total_distance_km: Total route distance
            total_weight_kg: Total cargo weight

        Returns:
            PDF file as bytes
        """
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2 * cm,
            leftMargin=2 * cm,
            topMargin=2 * cm,
            bottomMargin=2 * cm,
        )

        elements = []

        # Title
        elements.append(Paragraph("Delivery Route Sheet", self.styles["Title_Custom"]))

        # Vehicle info
        elements.append(Paragraph(f"Vehicle: {vehicle_name} ({license_plate})", self.styles["Normal"]))
        elements.append(Paragraph(f"Date: {route_date.strftime('%d.%m.%Y')}", self.styles["Subtitle"]))

        # Summary
        elements.append(Spacer(1, 10 * mm))
        summary_data = [
            ["Total Stops", str(len(stops))],
            ["Total Distance", f"{total_distance_km:.1f} km"],
            ["Total Weight", f"{total_weight_kg:.1f} kg"],
        ]
        summary_table = Table(summary_data, colWidths=[5 * cm, 4 * cm])
        summary_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, -1), colors.lightgrey),
                    ("FONTSIZE", (0, 0), (-1, -1), 10),
                    ("PADDING", (0, 0), (-1, -1), 5),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(summary_table)

        # Stops table
        elements.append(Spacer(1, 15 * mm))
        elements.append(Paragraph("Delivery Schedule", self.styles["Heading2"]))

        if stops:
            table_data = [["#", "ETA", "Client", "Address", "Weight", "Status"]]

            for stop in stops:
                arrival = stop.get("planned_arrival", "")
                if isinstance(arrival, str) and "T" in arrival:
                    arrival = arrival.split("T")[1][:5]

                table_data.append(
                    [
                        str(stop.get("sequence_number", "")),
                        arrival,
                        stop.get("client_name", "")[:25],
                        stop.get("client_address", "")[:35] if stop.get("client_address") else "-",
                        f"{stop.get('weight_kg', 0):.0f} kg",
                        "[ ]",  # Checkbox for driver
                    ]
                )

            stops_table = Table(
                table_data,
                colWidths=[1 * cm, 1.5 * cm, 4 * cm, 5 * cm, 2 * cm, 1.5 * cm],
            )
            stops_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#059669")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("FONTSIZE", (0, 0), (-1, 0), 9),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 1), (-1, -1), 8),
                        ("ALIGN", (0, 0), (1, -1), "CENTER"),
                        ("ALIGN", (4, 0), (-1, -1), "CENTER"),
                        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
                        ("PADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            elements.append(stops_table)

        # Driver signature section
        elements.append(Spacer(1, 30 * mm))
        elements.append(Paragraph("Driver Signature: _______________________", self.styles["Normal"]))
        elements.append(Spacer(1, 5 * mm))
        elements.append(Paragraph("Notes:", self.styles["Normal"]))
        elements.append(Spacer(1, 30 * mm))

        # Footer
        elements.append(Paragraph(f"Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}", self.styles["Subtitle"]))

        doc.build(elements)
        return buffer.getvalue()


# Singleton instance
pdf_exporter = PDFExporter()
