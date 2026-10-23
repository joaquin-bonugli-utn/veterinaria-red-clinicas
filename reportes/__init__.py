"""Reportes PDF (ReportLab + Matplotlib). Las consultas viven en RepositorioReportes."""

from reportes.atenciones_derivaciones import ReporteAtencionesDerivaciones
from reportes.base import CARPETA_SALIDA, FiltrosReporte, Reporte
from reportes.facturacion import ReporteFacturacion
from reportes.rechazos_transporte import ReporteRechazosTransporte
from reportes.tiempos_laboratorio import ReporteTiemposLaboratorio
from reportes.tratamientos_vacunas import ReporteTratamientosVacunas

REPORTES: tuple[type[Reporte], ...] = (
    ReporteAtencionesDerivaciones,
    ReporteRechazosTransporte,
    ReporteTratamientosVacunas,
    ReporteFacturacion,
    ReporteTiemposLaboratorio,
)

__all__ = [
    "CARPETA_SALIDA", "REPORTES", "FiltrosReporte", "Reporte", "ReporteAtencionesDerivaciones",
    "ReporteFacturacion", "ReporteRechazosTransporte", "ReporteTiemposLaboratorio", "ReporteTratamientosVacunas",
]
