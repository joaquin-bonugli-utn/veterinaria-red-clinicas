"""Repositorio de atenciones, con sus tratamientos y aplicaciones de vacuna."""

from __future__ import annotations

from dominio import AplicacionVacuna, Atencion, Tratamiento
from persistencia.repositorios.base import RepositorioBase, Tabla


class RepositorioAtenciones(RepositorioBase):
    TABLAS = (
        Tabla("atencion", "id_atencion", Atencion),
        Tabla("tratamiento", "id_tratamiento", Tratamiento),
        Tabla("aplicacion_vacuna", "id_aplicacion", AplicacionVacuna),
    )
    PRINCIPAL = Atencion

    def listar_por_historia(self, id_historia: int) -> list[Atencion]:
        return self._buscar(Atencion, "id_historia = ?", (id_historia,), orden="fecha_hora")

    def listar_por_mascota(self, id_mascota: int) -> list[Atencion]:
        return self._buscar(
            Atencion,
            "id_historia IN (SELECT id_historia FROM historia_clinica WHERE id_mascota = ?)",
            (id_mascota,),
            orden="fecha_hora",
        )

    def listar_por_rango(self, desde: str, hasta: str, id_clinica: int | None = None) -> list[Atencion]:
        """Atenciones con fecha_hora en [desde, hasta), opcionalmente de una clínica."""
        condicion = "fecha_hora >= ? AND fecha_hora < ?"
        parametros: list = [desde, hasta]
        if id_clinica is not None:
            condicion += " AND id_clinica = ?"
            parametros.append(id_clinica)
        return self._buscar(Atencion, condicion, parametros, orden="fecha_hora")

    def obtener_por_turno(self, id_turno: int) -> Atencion | None:
        return self._buscar_uno(Atencion, "id_turno = ?", (id_turno,))

    # --- Tratamientos -------------------------------------------------------------

    def listar_tratamientos(self, id_atencion: int) -> list[Tratamiento]:
        return self._buscar(Tratamiento, "id_atencion = ?", (id_atencion,), orden="fecha_inicio")

    # --- Aplicaciones de vacuna ---------------------------------------------------

    def listar_aplicaciones(self, id_atencion: int) -> list[AplicacionVacuna]:
        return self._buscar(AplicacionVacuna, "id_atencion = ?", (id_atencion,), orden="fecha_aplicacion")

    def listar_aplicaciones_por_mascota(self, id_mascota: int) -> list[AplicacionVacuna]:
        """Todas las vacunas aplicadas a la mascota (para controlar el esquema)."""
        return self._buscar(
            AplicacionVacuna,
            "id_atencion IN (SELECT a.id_atencion FROM atencion a "
            "JOIN historia_clinica h ON h.id_historia = a.id_historia WHERE h.id_mascota = ?)",
            (id_mascota,),
            orden="fecha_aplicacion, id_aplicacion",
        )
