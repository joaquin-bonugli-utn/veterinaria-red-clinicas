"""Infraestructura común de los reportes PDF (ReportLab + Matplotlib).

Cada reporte hereda de ``Reporte`` (patrón Template Method): la base arma el
documento con ``SimpleDocTemplate``, el encabezado con los filtros y el pie con
el número de página; la subclase solo aporta ``contenido()``. Los gráficos de
Matplotlib se insertan como imagen a través de un ``BytesIO`` (sin archivos temporales).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

import matplotlib

matplotlib.use("Agg")  # backend sin ventana: genera imágenes en memoria
import matplotlib.pyplot as plt  # noqa: E402
from reportlab.lib import colors  # noqa: E402
from reportlab.lib.enums import TA_CENTER, TA_RIGHT  # noqa: E402
from reportlab.lib.pagesizes import A4  # noqa: E402
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet  # noqa: E402
from reportlab.lib.units import cm  # noqa: E402
from reportlab.platypus import (  # noqa: E402
    Flowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from dominio import validaciones as v  # noqa: E402
from persistencia.conexion import RAIZ_PROYECTO  # noqa: E402
from persistencia.repositorios import RepositorioReportes  # noqa: E402

CARPETA_SALIDA = RAIZ_PROYECTO / "salida"

AZUL = colors.HexColor("#1F4E79")
AZUL_CLARO = colors.HexColor("#DCE6F1")
GRIS = colors.HexColor("#F2F2F2")
PALETA = ["#1F4E79", "#2E86AB", "#F18F01", "#C73E1D", "#6A994E", "#7B2CBF"]

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

_estilos = getSampleStyleSheet()
ESTILO_TITULO = ParagraphStyle("Titulo", parent=_estilos["Title"], textColor=AZUL, fontSize=17, spaceAfter=4)
ESTILO_SUBTITULO = ParagraphStyle("Subtitulo", parent=_estilos["Heading2"], textColor=AZUL, spaceBefore=10)
ESTILO_H3 = ParagraphStyle("H3", parent=_estilos["Heading3"], textColor=AZUL, spaceBefore=8, spaceAfter=3)
ESTILO_NORMAL = ParagraphStyle("Normal9", parent=_estilos["Normal"], fontSize=9, leading=11)
ESTILO_CELDA = ParagraphStyle("Celda", parent=_estilos["Normal"], fontSize=8, leading=9.5)
ESTILO_CELDA_DERECHA = ParagraphStyle("CeldaDerecha", parent=ESTILO_CELDA, alignment=TA_RIGHT)
ESTILO_ENCABEZADO = ParagraphStyle("Encabezado", parent=ESTILO_CELDA, fontName="Helvetica-Bold",
                                   textColor=colors.white)
ESTILO_FILTROS = ParagraphStyle("Filtros", parent=ESTILO_NORMAL, alignment=TA_CENTER, textColor=colors.grey)


# --- Filtros ----------------------------------------------------------------------------

@dataclass(frozen=True)
class FiltrosReporte:
    """Filtros comunes: fechas desde/hasta INCLUSIVAS ('YYYY-MM-DD') y clínica opcional."""

    desde: str
    hasta: str
    id_clinica: int | None = None

    def __post_init__(self) -> None:
        v.fecha_iso(self.desde, "desde")
        v.fecha_iso(self.hasta, "hasta")
        if self.hasta < self.desde:
            raise ValueError("La fecha 'hasta' no puede ser anterior a 'desde'.")
        if self.id_clinica is not None:
            v.id_obligatorio(self.id_clinica, "id_clinica")

    @property
    def hasta_exclusivo(self) -> str:
        """Día siguiente a 'hasta', para consultar el rango semiabierto [desde, hasta+1)."""
        return (v.a_fecha(self.hasta) + timedelta(days=1)).isoformat()

    @property
    def parametros(self) -> tuple[str, str, int | None]:
        return self.desde, self.hasta_exclusivo, self.id_clinica

    @classmethod
    def ultimos_dias(cls, dias: int = 91, id_clinica: int | None = None, hoy: date | None = None) -> FiltrosReporte:
        hoy = hoy or date.today()
        return cls((hoy - timedelta(days=dias)).isoformat(), hoy.isoformat(), id_clinica)


# --- Formatos ---------------------------------------------------------------------------

def moneda(valor: float | None) -> str:
    """$ 1.234.567,89 (formato argentino)."""
    if valor is None:
        return "-"
    texto = f"{abs(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{'-' if valor < 0 else ''}$ {texto}"


def decimal(valor: float, decimales: int = 1) -> str:
    """Número con coma decimal (para etiquetas de gráficos)."""
    return f"{valor:.{decimales}f}".replace(".", ",")


def horas(valor: float | None) -> str:
    return "-" if valor is None else f"{valor:.1f} h".replace(".", ",")


def porcentaje(parte: float, total: float) -> str:
    return "-" if not total else f"{100 * parte / total:.1f} %".replace(".", ",")


def mes_legible(mes_iso: str) -> str:
    """'2026-08' → 'Ago 2026'."""
    anio, mes = mes_iso.split("-")
    return f"{MESES[int(mes) - 1]} {anio}"


def fecha_legible(fecha_iso: str) -> str:
    """'2026-08-15' o '2026-08-15 10:30' → '15/08/2026' o '15/08/2026 10:30'."""
    d = fecha_iso[:10].split("-")
    return f"{d[2]}/{d[1]}/{d[0]}" + fecha_iso[10:]


# --- Bloques de contenido ----------------------------------------------------------------

def tabla(
    filas: list[list[Any]],
    anchos: list[float] | None = None,
    con_totales: bool = False,
    alinear_derecha_desde: int | None = None,
) -> Table:
    """Tabla con encabezado azul, filas alternadas y, opcionalmente, fila de totales en negrita.

    Las celdas de texto se convierten en Paragraph para que hagan salto de línea
    dentro del ancho de su columna en lugar de invadir la vecina.
    """
    ultima = len(filas) - 1

    def celda(valor: Any, i_fila: int, i_col: int) -> Any:
        if not isinstance(valor, str):
            return valor
        texto = escape(valor).replace("\n", "<br/>")
        if i_fila == 0:
            return Paragraph(texto, ESTILO_ENCABEZADO)
        if con_totales and i_fila == ultima:
            texto = f"<b>{texto}</b>"
        derecha = alinear_derecha_desde is not None and i_col >= alinear_derecha_desde
        return Paragraph(texto, ESTILO_CELDA_DERECHA if derecha else ESTILO_CELDA)

    filas = [[celda(c, i, j) for j, c in enumerate(fila)] for i, fila in enumerate(filas)]
    t = Table(filas, colWidths=anchos, repeatRows=1)
    estilo = [
        ("BACKGROUND", (0, 0), (-1, 0), AZUL),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BFBFBF")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, GRIS]),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]
    if alinear_derecha_desde is not None:
        estilo.append(("ALIGN", (alinear_derecha_desde, 1), (-1, -1), "RIGHT"))
    if con_totales:
        estilo += [
            ("BACKGROUND", (0, -1), (-1, -1), AZUL_CLARO),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ]
    t.setStyle(TableStyle(estilo))
    return t


def grafico(fig: plt.Figure, ancho_cm: float = 17) -> Image:
    """Convierte una figura de Matplotlib en un Image de ReportLab vía BytesIO."""
    buffer = BytesIO()
    fig.savefig(buffer, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buffer.seek(0)
    ancho_px, alto_px = fig.get_size_inches()
    ancho = ancho_cm * cm
    return Image(buffer, width=ancho, height=ancho * alto_px / ancho_px)


def parrafo(texto: str, estilo: ParagraphStyle = ESTILO_NORMAL) -> Paragraph:
    return Paragraph(texto, estilo)


# --- Template Method -------------------------------------------------------------------

class Reporte(ABC):
    """Esqueleto común: título, filtros, contenido y pie con numeración de página."""

    titulo: str = ""
    nombre_archivo: str = ""
    descripcion: str = ""

    def __init__(self, repositorio: RepositorioReportes | None = None) -> None:
        self.repo = repositorio or RepositorioReportes()

    def generar(self, filtros: FiltrosReporte, carpeta: Path | str = CARPETA_SALIDA) -> Path:
        """Genera el PDF y devuelve su ruta."""
        carpeta = Path(carpeta)
        carpeta.mkdir(parents=True, exist_ok=True)
        sufijo = f"_clinica{filtros.id_clinica}" if filtros.id_clinica else ""
        ruta = carpeta / f"{self.nombre_archivo}{sufijo}.pdf"

        doc = SimpleDocTemplate(
            str(ruta), pagesize=A4, title=self.titulo, author="Red de Clínicas Veterinarias",
            leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.5 * cm, bottomMargin=1.6 * cm,
        )
        historia: list[Flowable] = [
            parrafo(self.titulo, ESTILO_TITULO),
            parrafo(self._texto_filtros(filtros), ESTILO_FILTROS),
            Spacer(1, 0.3 * cm),
        ]
        if self.descripcion:
            historia += [parrafo(self.descripcion), Spacer(1, 0.2 * cm)]
        contenido = self.contenido(filtros)
        historia += contenido or [parrafo("<i>No hay datos para los filtros seleccionados.</i>")]
        doc.build(historia, onFirstPage=self._pie, onLaterPages=self._pie)
        return ruta

    @abstractmethod
    def contenido(self, filtros: FiltrosReporte) -> list[Flowable]:
        """Flowables del cuerpo del reporte; lista vacía si no hay datos."""

    # --- Auxiliares ------------------------------------------------------------------

    def _texto_filtros(self, filtros: FiltrosReporte) -> str:
        clinica = (self.repo.nombre_clinica(filtros.id_clinica) or f"#{filtros.id_clinica}") \
            if filtros.id_clinica else "Todas las clínicas"
        return (f"Período: {fecha_legible(filtros.desde)} al {fecha_legible(filtros.hasta)} · "
                f"Clínica: {clinica}")

    def _pie(self, canvas, doc) -> None:
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        generado = datetime.now().strftime("%d/%m/%Y %H:%M")
        canvas.drawString(doc.leftMargin, 0.9 * cm, f"Red de Clínicas Veterinarias · Generado el {generado}")
        canvas.drawRightString(A4[0] - doc.rightMargin, 0.9 * cm, f"Página {doc.page}")
        canvas.restoreState()
