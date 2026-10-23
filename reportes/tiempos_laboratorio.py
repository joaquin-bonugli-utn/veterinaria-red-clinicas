"""Reporte 5: tiempos promedio de tránsito y de procesamiento por tipo de análisis."""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, Spacer

from reportes.base import (
    ESTILO_SUBTITULO,
    PALETA,
    FiltrosReporte,
    Reporte,
    decimal,
    grafico,
    horas,
    parrafo,
    porcentaje,
    tabla,
)


class ReporteTiemposLaboratorio(Reporte):
    titulo = "Tiempos de tránsito y procesamiento por tipo de análisis"
    nombre_archivo = "05_tiempos_laboratorio"
    descripcion = ("<b>Tránsito</b>: desde la salida del primer tramo hasta la recepción en el laboratorio "
                   "(incluye muestras luego rechazadas). <b>Procesamiento</b>: desde la recepción hasta la carga "
                   "del resultado (solo muestras analizadas). <b>% viab.</b> = tránsito promedio sobre las horas de "
                   "viabilidad del análisis. Se consideran los remitos recibidos en el período.")

    def contenido(self, filtros: FiltrosReporte) -> list[Flowable]:
        filas = self.repo.tiempos_por_tipo_analisis(*filtros.parametros)
        if not filas:
            return []
        return [
            parrafo("Tiempos por tipo de análisis (en horas)", ESTILO_SUBTITULO),
            self._tabla(filas),
            Spacer(1, 0.5 * cm),
            grafico(self._grafico(filas), ancho_cm=16),
        ]

    @staticmethod
    def _promedio_ponderado(filas: list[dict], valor: str, peso: str) -> float | None:
        pares = [(f[valor], f[peso]) for f in filas if f[valor] is not None and f[peso]]
        total = sum(p for _, p in pares)
        return sum(v * p for v, p in pares) / total if total else None

    def _tabla(self, filas: list[dict]) -> Flowable:
        datos = [["Análisis", "Viabilidad", "Muestras", "Tránsito\nprom.", "Mín.", "Máx.", "% viab.",
                  "Analizadas", "Procesam.\nprom."]]
        for f in filas:
            datos.append([f["analisis"], horas(f["horas_viabilidad"]), f["muestras"], horas(f["transito_promedio"]),
                          horas(f["transito_minimo"]), horas(f["transito_maximo"]),
                          porcentaje(f["transito_promedio"], f["horas_viabilidad"]), f["analizadas"],
                          horas(f["procesamiento_promedio"])])
        datos.append(["TOTAL (ponderado)", "", sum(f["muestras"] for f in filas),
                      horas(self._promedio_ponderado(filas, "transito_promedio", "muestras")),
                      horas(min(f["transito_minimo"] for f in filas)),
                      horas(max(f["transito_maximo"] for f in filas)), "",
                      sum(f["analizadas"] for f in filas),
                      horas(self._promedio_ponderado(filas, "procesamiento_promedio", "analizadas"))])
        anchos = [3.6 * cm, 1.8 * cm, 1.6 * cm, 1.8 * cm, 1.5 * cm, 1.5 * cm, 1.6 * cm, 1.8 * cm, 2 * cm]
        return tabla(datos, anchos, con_totales=True, alinear_derecha_desde=1)

    @staticmethod
    def _grafico(filas: list[dict]) -> plt.Figure:
        nombres = [f["analisis"] for f in filas]
        y = np.arange(len(filas))
        alto = 0.38
        transito = [f["transito_promedio"] or 0 for f in filas]
        procesamiento = [f["procesamiento_promedio"] or 0 for f in filas]

        fig, eje = plt.subplots(figsize=(9, 0.9 * len(filas) + 1.8))
        eje.barh(y - alto / 2, transito, alto, label="Tránsito promedio", color=PALETA[1])
        eje.barh(y + alto / 2, procesamiento, alto, label="Procesamiento promedio", color=PALETA[2])
        eje.scatter([f["horas_viabilidad"] for f in filas], y - alto / 2, marker="|", s=400, color=PALETA[3],
                    label="Límite de viabilidad", zorder=3)
        for i, (t, p) in enumerate(zip(transito, procesamiento)):
            eje.text(t + 0.3, i - alto / 2, f"{decimal(t)} h", va="center", fontsize=8)
            if p:
                eje.text(p + 0.3, i + alto / 2, f"{decimal(p)} h", va="center", fontsize=8)
        eje.set_yticks(y, nombres)
        eje.invert_yaxis()
        eje.set_xlabel("Horas")
        eje.set_title("Tiempos promedio por tipo de análisis", fontsize=11)
        eje.legend(fontsize=8, frameon=False, loc="lower right")
        eje.grid(axis="x", alpha=0.3)
        eje.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        return fig
