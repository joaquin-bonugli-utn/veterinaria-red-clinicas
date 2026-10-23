"""Reporte 2: muestras rechazadas por fallas en el transporte."""

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
    fecha_legible,
    grafico,
    parrafo,
    tabla,
)

CATEGORIAS = ["Precinto roto", "Viabilidad vencida", "Temperatura fuera de rango", "Otro"]


class ReporteRechazosTransporte(Reporte):
    titulo = "Muestras rechazadas por fallas en el transporte"
    nombre_archivo = "02_rechazos_transporte"
    descripcion = ("Muestras rechazadas al recibir el remito en el laboratorio: precinto roto, viabilidad vencida "
                   "por demora en la cadena de envío o temperatura de llegada fuera del rango del análisis. "
                   "Cada rechazo se atribuye al transportista que entregó el remito (último tramo) y a la "
                   "clínica de origen. El período se filtra por fecha de recepción.")

    def contenido(self, filtros: FiltrosReporte) -> list[Flowable]:
        filas = self.repo.muestras_rechazadas_en_transporte(*filtros.parametros)
        if not filas:
            return []
        remitos = len({f["remito"] for f in filas})
        return [
            parrafo(f"<b>{len(filas)}</b> muestras rechazadas en <b>{remitos}</b> remitos."),
            parrafo("Rechazos por transportista y clínica de origen", ESTILO_SUBTITULO),
            self._tabla_resumen(filas),
            Spacer(1, 0.4 * cm),
            grafico(self._grafico(filas), ancho_cm=15),
            parrafo("Detalle de muestras rechazadas", ESTILO_SUBTITULO),
            self._tabla_detalle(filas),
        ]

    @staticmethod
    def _categorias_presentes(filas: list[dict]) -> list[str]:
        presentes = {f["categoria"] for f in filas}
        return [c for c in CATEGORIAS if c in presentes]

    def _tabla_resumen(self, filas: list[dict]) -> Flowable:
        categorias = self._categorias_presentes(filas)
        conteo: dict[tuple[str, str], dict[str, int]] = {}
        for f in filas:
            grupo = conteo.setdefault((f["transportista"], f["clinica"]), dict.fromkeys(categorias, 0))
            grupo[f["categoria"]] += 1
        datos = [["Transportista", "Clínica de origen", *categorias, "Total"]]
        totales = dict.fromkeys(categorias, 0)
        for (transportista, clinica), por_cat in sorted(conteo.items()):
            datos.append([transportista, clinica, *[por_cat[c] for c in categorias], sum(por_cat.values())])
            for c in categorias:
                totales[c] += por_cat[c]
        datos.append(["TOTAL", "", *[totales[c] for c in categorias], sum(totales.values())])
        resto = (17.8 - 8.5) / (len(categorias) + 1)
        return tabla(datos, [4 * cm, 4.5 * cm] + [resto * cm] * (len(categorias) + 1),
                     con_totales=True, alinear_derecha_desde=2)

    @staticmethod
    def _tabla_detalle(filas: list[dict]) -> Flowable:
        datos = [["Transportista", "Clínica", "Remito", "Muestra", "Análisis", "Recepción", "Motivo"]]
        for f in filas:
            datos.append([f["transportista"], f["clinica"], f["remito"], f["muestra"], f["analisis"],
                          fecha_legible(f["fecha_recepcion"]), f["motivo"]])
        anchos = [2.3 * cm, 2.6 * cm, 2.8 * cm, 1.9 * cm, 2.5 * cm, 2.0 * cm, 3.7 * cm]
        return tabla(datos, anchos)

    def _grafico(self, filas: list[dict]) -> plt.Figure:
        categorias = self._categorias_presentes(filas)
        transportistas = sorted({f["transportista"] for f in filas})
        y = np.arange(len(transportistas))
        fig, eje = plt.subplots(figsize=(8, 0.6 * len(transportistas) + 1.8))
        acumulado = np.zeros(len(transportistas))
        for i, categoria in enumerate(categorias):
            valores = np.array([sum(1 for f in filas if f["transportista"] == t and f["categoria"] == categoria)
                                for t in transportistas])
            eje.barh(y, valores, 0.55, left=acumulado, label=categoria, color=PALETA[(i + 2) % len(PALETA)])
            acumulado += valores
        eje.set_yticks(y, transportistas)
        eje.set_xlabel("Muestras rechazadas")
        eje.xaxis.get_major_locator().set_params(integer=True)
        eje.set_title("Rechazos por transportista y motivo", fontsize=11)
        eje.legend(fontsize=8, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22),
                   ncol=len(categorias))
        eje.grid(axis="x", alpha=0.3)
        eje.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        return fig
