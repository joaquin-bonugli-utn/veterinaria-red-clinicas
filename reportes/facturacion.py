"""Reporte 4: facturación desglosada por clínica y por tipo de servicio."""

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
    moneda,
    parrafo,
    porcentaje,
    tabla,
)

TIPOS = ["Atención", "Vacuna", "Análisis"]


class ReporteFacturacion(Reporte):
    titulo = "Facturación por clínica y tipo de servicio"
    nombre_archivo = "04_facturacion"
    descripcion = ("Importes facturados según la fecha de emisión del comprobante. El <b>importe de lista</b> es "
                   "precio × cantidad; la diferencia con lo facturado refleja las tarifas aplicadas "
                   "(urgencia +30 %, control -20 %).")

    def contenido(self, filtros: FiltrosReporte) -> list[Flowable]:
        filas = self.repo.facturacion_por_clinica_y_tipo(*filtros.parametros)
        if not filas:
            return []
        resumen = self.repo.resumen_comprobantes(*filtros.parametros)
        return [
            self._tabla_indicadores(resumen),
            parrafo("Facturado por clínica y tipo de servicio", ESTILO_SUBTITULO),
            self._tabla_pivot(filas),
            Spacer(1, 0.4 * cm),
            grafico(self._grafico(filas)),
            parrafo("Efecto de las tarifas por tipo de servicio", ESTILO_SUBTITULO),
            self._tabla_tarifas(filas),
        ]

    @staticmethod
    def _tabla_indicadores(resumen: dict) -> Flowable:
        datos = [["Comprobantes emitidos", "Total facturado", "Ticket promedio"],
                 [resumen["comprobantes"], moneda(resumen["total"]), moneda(resumen["promedio"])]]
        return tabla(datos, [5.9 * cm] * 3)

    @staticmethod
    def _tabla_pivot(filas: list[dict]) -> Flowable:
        clinicas = sorted({f["clinica"] for f in filas})
        importe = {(f["clinica"], f["tipo_item"]): f["importe_facturado"] for f in filas}
        total_general = sum(importe.values())
        datos = [["Clínica", *TIPOS, "Total", "% del total"]]
        for clinica in clinicas:
            valores = [importe.get((clinica, t), 0) for t in TIPOS]
            datos.append([clinica, *map(moneda, valores), moneda(sum(valores)), porcentaje(sum(valores), total_general)])
        por_tipo = [sum(importe.get((c, t), 0) for c in clinicas) for t in TIPOS]
        datos.append(["TOTAL", *map(moneda, por_tipo), moneda(total_general), "100,0 %"])
        return tabla(datos, [4.2 * cm, 2.7 * cm, 2.7 * cm, 2.7 * cm, 3 * cm, 2.5 * cm],
                     con_totales=True, alinear_derecha_desde=1)

    @staticmethod
    def _tabla_tarifas(filas: list[dict]) -> Flowable:
        datos = [["Tipo de servicio", "Ítems", "Importe de lista", "Facturado", "Diferencia", "Variación"]]
        totales = {"items": 0, "importe_lista": 0.0, "importe_facturado": 0.0}
        for tipo in TIPOS:
            del_tipo = [f for f in filas if f["tipo_item"] == tipo]
            if not del_tipo:
                continue
            items = sum(f["items"] for f in del_tipo)
            lista = sum(f["importe_lista"] for f in del_tipo)
            facturado = sum(f["importe_facturado"] for f in del_tipo)
            datos.append([tipo, items, moneda(lista), moneda(facturado), moneda(facturado - lista),
                          porcentaje(facturado - lista, lista)])
            totales["items"] += items
            totales["importe_lista"] += lista
            totales["importe_facturado"] += facturado
        diferencia = totales["importe_facturado"] - totales["importe_lista"]
        datos.append(["TOTAL", totales["items"], moneda(totales["importe_lista"]),
                      moneda(totales["importe_facturado"]), moneda(diferencia),
                      porcentaje(diferencia, totales["importe_lista"])])
        return tabla(datos, [3.6 * cm, 1.6 * cm, 3.4 * cm, 3.4 * cm, 3.2 * cm, 2.6 * cm],
                     con_totales=True, alinear_derecha_desde=1)

    @staticmethod
    def _grafico(filas: list[dict]) -> plt.Figure:
        clinicas = sorted({f["clinica"] for f in filas})
        importe = {(f["clinica"], f["tipo_item"]): f["importe_facturado"] for f in filas}
        por_tipo = [sum(importe.get((c, t), 0) for c in clinicas) for t in TIPOS]
        presentes = [(t, v, PALETA[i]) for i, (t, v) in enumerate(zip(TIPOS, por_tipo)) if v > 0]

        fig, (eje_torta, eje_barras) = plt.subplots(1, 2, figsize=(11, 4.2), gridspec_kw={"width_ratios": [1, 1.3]})
        eje_torta.pie([v for _, v, _ in presentes], labels=[t for t, _, _ in presentes],
                      colors=[c for _, _, c in presentes], autopct=lambda p: f"{decimal(p)} %", startangle=90,
                      wedgeprops={"edgecolor": "white"}, textprops={"fontsize": 9})
        eje_torta.set_title("Facturación por tipo de servicio", fontsize=11)

        x = np.arange(len(clinicas))
        base = np.zeros(len(clinicas))
        for i, tipo in enumerate(TIPOS):
            valores = np.array([importe.get((c, tipo), 0) for c in clinicas]) / 1000
            eje_barras.bar(x, valores, 0.6, bottom=base, label=tipo, color=PALETA[i])
            base += valores
        eje_barras.set_xticks(x, [c.replace("Sede ", "") for c in clinicas], fontsize=9)
        eje_barras.set_ylabel("Miles de $")
        eje_barras.set_title("Facturación por clínica", fontsize=11)
        eje_barras.legend(fontsize=8, frameon=False)
        eje_barras.grid(axis="y", alpha=0.3)
        eje_barras.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        return fig
