"""Repositorio de turnos.

Los rangos son semiabiertos [desde, hasta) sobre fecha_hora_inicio y se
comparan como texto ISO, así que admiten 'YYYY-MM-DD' o 'YYYY-MM-DD HH:MM'
(p. ej. desde='2026-10-22', hasta='2026-10-23' = todo el día 22).
"""

from __future__ import annotations

from dominio import Turno
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioTurnos(RepositorioBase):
    TABLAS = (Tabla("turno", "id_turno", Turno),)
    PRINCIPAL = Turno

    def listar_por_veterinario(self, id_veterinario: int, desde: str, hasta: str) -> list[Turno]:
        return self._buscar(
            Turno,
            "id_veterinario = ? AND fecha_hora_inicio >= ? AND fecha_hora_inicio < ?",
            (id_veterinario, desde, hasta),
            orden="fecha_hora_inicio",
        )

    def listar_por_rango(self, desde: str, hasta: str) -> list[Turno]:
        return self._buscar(
            Turno, "fecha_hora_inicio >= ? AND fecha_hora_inicio < ?", (desde, hasta),
            orden="fecha_hora_inicio, id_veterinario",
        )

    def listar_por_mascota(self, id_mascota: int) -> list[Turno]:
        return self._buscar(Turno, "id_mascota = ?", (id_mascota,), orden="fecha_hora_inicio")

    def buscar_superpuestos(
        self, id_veterinario: int, inicio: str, fin: str, excluir_id: int | None = None
    ) -> list[Turno]:
        """Turnos no cancelados del veterinario que se pisan con [inicio, fin)."""
        condicion = (
            "id_veterinario = ? AND estado <> 'Cancelado' "
            "AND ? < fecha_hora_fin AND ? > fecha_hora_inicio"
        )
        parametros: list = [id_veterinario, inicio, fin]
        if excluir_id is not None:
            condicion += " AND id_turno <> ?"
            parametros.append(excluir_id)
        return self._buscar(Turno, condicion, parametros, orden="fecha_hora_inicio")
