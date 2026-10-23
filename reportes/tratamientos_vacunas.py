"""Reporte 3: tratamientos aplicados y vacunas pendientes/vencidas por mascota."""

from __future__ import annotations

from collections import Counter
from datetime import date

import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.units import cm
from reportlab.platypus import Flowable, KeepTogether, Spacer

from reportes.base import (
    ESTILO_H3,
    ESTILO_SUBTITULO,
    PALETA,
    FiltrosReporte,
    Reporte,
    fecha_legible,
    grafico,
    parrafo,
    tabla,
)
from servicios import ServicioAtencion, VacunaPendiente


class ReporteTratamientosVacunas(Reporte):
    titulo = "Tratamientos aplicados y vacunas pendientes por mascota"
    nombre_archivo = "03_tratamientos_vacunas"

    def __init__(self, repositorio=None, servicio_atencion: ServicioAtencion | None = None) -> None:
        super().__init__(repositorio)
        self.servicio_atencion = servicio_atencion or ServicioAtencion()

    def contenido(self, filtros: FiltrosReporte) -> list[Flowable]:
        mascotas = self.repo.mascotas_atendidas(*filtros.parametros)
        if not mascotas:
            return []
        corte = min(filtros.hasta, date.today().isoformat())
        tratamientos: dict[int, list[dict]] = {}
        for t in self.repo.tratamientos_aplicados(*filtros.parametros):
            tratamientos.setdefault(t["id_mascota"], []).append(t)
        # Regla 6: la lógica de vacunas pendientes vive en el servicio, no se duplica en SQL.
        pendientes = {m["id_mascota"]: self.servicio_atencion.vacunas_pendientes(m["id_mascota"], corte)
                      for m in mascotas}

        historia: list[Flowable] = [
            parrafo(f"Mascotas atendidas en el período: <b>{len(mascotas)}</b>. Las vacunas obligatorias "
                    f"pendientes o vencidas se calculan al <b>{fecha_legible(corte)}</b> según la especie y la "
                    f"edad de cada mascota."),
            parrafo("Resumen", ESTILO_SUBTITULO),
            self._tabla_resumen(mascotas, tratamientos, pendientes),
            Spacer(1, 0.4 * cm),
            grafico(self._grafico(mascotas, tratamientos, pendientes)),
            parrafo("Detalle por mascota", ESTILO_SUBTITULO),
        ]
        for m in mascotas:
            historia.append(self._bloque_mascota(m, tratamientos.get(m["id_mascota"], []), pendientes[m["id_mascota"]]))
        return historia

    @staticmethod
    def _tabla_resumen(mascotas, tratamientos, pendientes) -> Flowable:
        datos = [["Mascota", "Especie", "Responsable", "Teléfono", "Atenc.", "Trat.", "Pend.", "Venc."]]
        for m in mascotas:
            lista = pendientes[m["id_mascota"]]
            datos.append([m["mascota"], m["especie"], m["responsable"], m["telefono"] or "-", m["atenciones"],
                          len(tratamientos.get(m["id_mascota"], [])),
                          sum(p.situacion == "Pendiente" for p in lista),
                          sum(p.situacion == "Vencida" for p in lista)])
        anchos = [2.4 * cm, 1.8 * cm, 4.2 * cm, 2.6 * cm, 1.5 * cm, 1.4 * cm, 1.4 * cm, 1.4 * cm]
        return tabla(datos, anchos, alinear_derecha_desde=4)

    @staticmethod
    def _bloque_mascota(m: dict, tratamientos: list[dict], pendientes: list[VacunaPendiente]) -> Flowable:
        raza = f", {m['raza']}" if m["raza"] else ""
        contacto = " · ".join(x for x in (f"DNI {m['dni']}", m["telefono"], m["email"]) if x)
        partes: list[Flowable] = [
            parrafo(f"{m['mascota']} ({m['especie']}{raza}, nac. {fecha_legible(m['fecha_nacimiento'])})", ESTILO_H3),
            parrafo(f"<b>Responsable:</b> {m['responsable']} · {contacto}"),
            Spacer(1, 0.15 * cm),
        ]
        if tratamientos:
            datos = [["Atención", "Clínica", "Veterinario", "Medicamento", "Dosis", "Frecuencia", "Hasta"]]
            for t in tratamientos:
                datos.append([fecha_legible(t["fecha_hora"]), t["clinica"], t["veterinario"], t["medicamento"],
                              t["dosis"], t["frecuencia"] or "-", fecha_legible(t["fecha_fin"]) if t["fecha_fin"] else "-"])
            partes.append(tabla(datos, [2.3 * cm, 2.7 * cm, 2.6 * cm, 3.4 * cm, 1.8 * cm, 2.2 * cm, 1.9 * cm]))
        else:
            partes.append(parrafo("<i>Sin tratamientos indicados en el período.</i>"))
        partes.append(Spacer(1, 0.15 * cm))
        if pendientes:
            datos = [["Vacuna obligatoria", "Situación", "Corresponde desde", "Última dosis"]]
            for p in pendientes:
                datos.append([p.vacuna.nombre, p.situacion, fecha_legible(p.fecha_limite),
                              fecha_legible(p.ultima_aplicacion) if p.ultima_aplicacion else "Nunca aplicada"])
            partes.append(tabla(datos, [6 * cm, 3 * cm, 4 * cm, 4 * cm]))
        else:
            partes.append(parrafo("<i>Vacunación obligatoria al día.</i>"))
        partes.append(Spacer(1, 0.3 * cm))
        return KeepTogether(partes)

    @staticmethod
    def _grafico(mascotas, tratamientos, pendientes) -> plt.Figure:
        fig, (eje_med, eje_vac) = plt.subplots(1, 2, figsize=(11, 4))

        medicamentos = Counter(t["medicamento"] for lista in tratamientos.values() for t in lista).most_common(6)
        if medicamentos:
            nombres, cantidades = zip(*reversed(medicamentos))
            eje_med.barh(nombres, cantidades, color=PALETA[1])
        eje_med.set_title("Medicamentos más indicados", fontsize=11)
        eje_med.xaxis.get_major_locator().set_params(integer=True)

        especies = sorted({m["especie"] for m in mascotas})
        conteo = {e: Counter() for e in especies}
        for m in mascotas:
            conteo[m["especie"]].update(p.situacion for p in pendientes[m["id_mascota"]])
        x = np.arange(len(especies))
        pend = [conteo[e]["Pendiente"] for e in especies]
        venc = [conteo[e]["Vencida"] for e in especies]
        eje_vac.bar(x, pend, 0.6, label="Pendiente", color=PALETA[2])
        eje_vac.bar(x, venc, 0.6, bottom=pend, label="Vencida", color=PALETA[3])
        eje_vac.set_xticks(x, especies)
        eje_vac.yaxis.get_major_locator().set_params(integer=True)
        eje_vac.set_title("Vacunas obligatorias sin aplicar por especie", fontsize=11)
        eje_vac.legend(fontsize=8, frameon=False)
        for eje in (eje_med, eje_vac):
            eje.grid(axis="x" if eje is eje_med else "y", alpha=0.3)
            eje.spines[["top", "right"]].set_visible(False)
        fig.tight_layout()
        return fig
