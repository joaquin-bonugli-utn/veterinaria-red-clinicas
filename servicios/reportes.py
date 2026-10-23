"""Caso de uso de generación de reportes PDF (fachada para la UI)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from servicios.base import ServicioBase


@dataclass(frozen=True)
class ReporteDisponible:
    clave: str
    titulo: str
    descripcion: str


class ServicioReportes(ServicioBase):
    """Expone los 5 reportes sin que la UI conozca ReportLab ni el repositorio de reportes.

    Los módulos de reportes/ se importan dentro de los métodos porque a su vez usan
    servicios (p. ej. ServicioAtencion): así se evita un import circular.
    """

    def disponibles(self) -> list[ReporteDisponible]:
        from reportes import REPORTES

        return [ReporteDisponible(clase.nombre_archivo, clase.titulo, _texto_plano(clase.descripcion))
                for clase in REPORTES]

    def generar(self, clave: str, desde: str, hasta: str, id_clinica: int | None = None,
                carpeta: Path | str | None = None) -> Path:
        """Genera el reporte `clave` para el período [desde, hasta] (inclusivo) y devuelve la ruta del PDF."""
        from reportes import CARPETA_SALIDA, REPORTES, FiltrosReporte

        clases = {clase.nombre_archivo: clase for clase in REPORTES}
        if clave not in clases:
            raise ValueError(f"Reporte desconocido: {clave!r}.")
        return clases[clave]().generar(FiltrosReporte(desde, hasta, id_clinica), carpeta or CARPETA_SALIDA)


def _texto_plano(html: str) -> str:
    for etiqueta in ("<b>", "</b>", "<i>", "</i>"):
        html = html.replace(etiqueta, "")
    return html
