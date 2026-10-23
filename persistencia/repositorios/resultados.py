"""Repositorio de resultados de análisis."""

from __future__ import annotations

from dominio import ResultadoAnalisis
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioResultados(RepositorioBase):
    TABLAS = (Tabla("resultado_analisis", "id_resultado", ResultadoAnalisis),)
    PRINCIPAL = ResultadoAnalisis

    def obtener_por_muestra(self, id_muestra: int) -> ResultadoAnalisis | None:
        return self._buscar_uno(ResultadoAnalisis, "id_muestra = ?", (id_muestra,))

    def listar_por_orden(self, id_orden: int) -> list[ResultadoAnalisis]:
        return self._buscar(
            ResultadoAnalisis,
            "id_muestra IN (SELECT id_muestra FROM muestra WHERE id_orden = ?)",
            (id_orden,),
            orden="fecha_hora",
        )

    def listar_por_rango(self, desde: str, hasta: str) -> list[ResultadoAnalisis]:
        return self._buscar(
            ResultadoAnalisis, "fecha_hora >= ? AND fecha_hora < ?", (desde, hasta), orden="fecha_hora"
        )
