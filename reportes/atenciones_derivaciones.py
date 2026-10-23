"""Reporte 1: atenciones clínicas y derivaciones por clínica y mes."""

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
    grafico,
    mes_legible,
    parrafo,
    porcentaje,
    tabla,
)


class ReporteAtencionesDerivaciones(Reporte):
    titulo = "Atenciones clínicas y derivaciones por clínica y mes"
    nombre_archivo = "01_atenciones_derivaciones"
    descripcion = ("Cantidad de atenciones por tipo (<b>Cons.</b> consultas, <b>Contr.</b> controles, <b>Urg.</b> "
                   "urgencias) y cuántas generaron órdenes de derivación a laboratorio. <b>Deriv.</b> = atenciones "
                   "con al menos una orden; <b>% deriv.</b> = Deriv. / total de atenciones; <b>Órd.</b> = órdenes.")

    def contenido(self, filtros: FiltrosReporte) -> list[Flowable]:
        filas = self.repo.atenciones_por_clinica_y_mes(*filtros.parametros)
        if not filas:
            return []
        return [
            parrafo("Resumen por clínica", ESTILO_SUBTITULO),
            self._tabla_resumen(filas),
            Spacer(1, 0.4 * cm),
            grafico(self._grafico(filas)),
            parrafo("Detalle por mes", ESTILO_SUBTITULO),
            self._tabla_detalle(filas),
        ]

    @staticmethod
    def _tabla_detalle(filas: list[dict]) -> Flowable:
        datos = [["Mes", "Clínica", "Atenc.", "Cons.", "Contr.", "Urg.", "Deriv.", "% deriv.", "Órd.", "Muestras"]]
        claves = ("atenciones", "consultas", "controles", "urgencias", "atenciones_derivadas", "ordenes", "muestras")
        totales = dict.fromkeys(claves, 0)
        for f in filas:
            datos.append([mes_legible(f["mes"]), f["clinica"], f["atenciones"], f["consultas"], f["controles"],
                          f["urgencias"], f["atenciones_derivadas"],
                          porcentaje(f["atenciones_derivadas"], f["atenciones"]), f["ordenes"], f["muestras"]])
            for k in claves:
                totales[k] += f[k]
        t = totales
        datos.append(["TOTAL", "", t["atenciones"], t["consultas"], t["controles"], t["urgencias"],
                      t["atenciones_derivadas"], porcentaje(t["atenciones_derivadas"], t["atenciones"]),
                      t["ordenes"], t["muestras"]])
        anchos = [1.9 * cm, 3.4 * cm, 1.3 * cm, 1.4 * cm, 1.4 * cm, 1.3 * cm, 1.5 * cm, 1.7 * cm, 1.3 * cm, 1.9 * cm]
        return tabla(datos, anchos, con_totales=True, alinear_derecha_desde=2)

    @staticmethod
    def _tabla_resumen(filas: list[dict]) -> Flowable:
        por_clinica: dict[str, dict[str, int]] = {}
        for f in filas:
            acum = por_clinica.setdefault(f["clinica"], {"atenciones": 0, "derivadas": 0, "ordenes": 0, "muestras": 0})
            acum["atenciones"] += f["atenciones"]
            acum["derivadas"] += f["atenciones_derivadas"]
            acum["ordenes"] += f["ordenes"]
            acum["muestras"] += f["muestras"]
        datos = [["Clínica", "Atenciones", "Derivadas", "% derivación", "Órdenes", "Muestras/orden"]]
        for clinica, a in sorted(por_clinica.items()):
            promedio = f"{a['muestras'] / a['ordenes']:.1f}".replace(".", ",") if a["ordenes"] else "-"
            datos.append([clinica, a["atenciones"], a["derivadas"], porcentaje(a["derivadas"], a["atenciones"]),
                          a["ordenes"], promedio])
        return tabla(datos, [5.5 * cm, 2.2 * cm, 2.2 * cm, 2.6 * cm, 2 * cm, 2.6 * cm], alinear_derecha_desde=1)

    @staticmethod
    def _grafico(filas: list[dict]) -> plt.Figure:
        meses = sorted({f["mes"] for f in filas})
        clinicas = sorted({f["clinica"] for f in filas})
        valor = {(f["clinica"], f["mes"]): f for f in filas}
        x = np.arange(len(meses))
        ancho = 0.8 / len(clinicas)

        fig, (eje_at, eje_der) = plt.subplots(1, 2, figsize=(11, 4))
        for i, clinica in enumerate(clinicas):
            desplazamiento = (i - (len(clinicas) - 1) / 2) * ancho
            atenciones = [valor.get((clinica, m), {}).get("atenciones", 0) for m in meses]
            ordenes = [valor.get((clinica, m), {}).get("ordenes", 0) for m in meses]
            eje_at.bar(x + desplazamiento, atenciones, ancho, label=clinica, color=PALETA[i % len(PALETA)])
            eje_der.bar(x + desplazamiento, ordenes, ancho, label=clinica, color=PALETA[i % len(PALETA)])
        for eje, titulo in ((eje_at, "Atenciones por mes"), (eje_der, "Órdenes de derivación por mes")):
            eje.set_title(titulo, fontsize=11)
            eje.set_xticks(x, [mes_legible(m) for m in meses])
            eje.yaxis.get_major_locator().set_params(integer=True)
            eje.grid(axis="y", alpha=0.3)
            eje.spines[["top", "right"]].set_visible(False)
        eje_at.legend(fontsize=8, frameon=False)
        fig.tight_layout()
        return fig
