"""Casos de uso de la agenda de turnos."""

from __future__ import annotations

from datetime import timedelta

from dominio import Turno
from dominio import validaciones as v
from dominio.excepciones import ReglaNegocioError, TurnoSuperpuestoError
from persistencia.repositorios import RepositorioMascotas, RepositorioTurnos, RepositorioVeterinarios
from servicios.base import ServicioBase


class ServicioTurnos(ServicioBase):
    def __init__(
        self,
        repo_turnos: RepositorioTurnos | None = None,
        repo_veterinarios: RepositorioVeterinarios | None = None,
        repo_mascotas: RepositorioMascotas | None = None,
    ) -> None:
        self.turnos = repo_turnos or RepositorioTurnos()
        self.veterinarios = repo_veterinarios or RepositorioVeterinarios()
        self.mascotas = repo_mascotas or RepositorioMascotas()

    # --- Casos de uso que modifican datos ------------------------------------------------

    def reservar(self, id_veterinario: int, id_mascota: int, inicio: str, fin: str) -> Turno:
        """Reserva un turno. Lanza TurnoSuperpuestoError si el veterinario ya tiene
        un turno no cancelado que se pisa (inicio_nuevo < fin_existente AND fin_nuevo > inicio_existente).
        """
        turno = Turno(id_veterinario, id_mascota, inicio, fin)
        try:
            self._requerir_activo(self.veterinarios.obtener_por_id(id_veterinario), "el veterinario")
            self._requerir_activo(self.mascotas.obtener_por_id(id_mascota), "la mascota")
            self._verificar_superposicion(turno)
            self.turnos.agregar(turno)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            turno.id_turno = None
            raise
        return turno

    def reprogramar(self, id_turno: int, inicio: str, fin: str) -> Turno:
        """Cambia el horario de un turno Reservado (sin chocar consigo mismo)."""
        try:
            turno = self._turno_reservado(id_turno, "reprogramar")
            nuevo = Turno(turno.id_veterinario, turno.id_mascota, inicio, fin, id_turno=id_turno)
            self._verificar_superposicion(nuevo)
            self.turnos.modificar(nuevo)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return nuevo

    def cancelar(self, id_turno: int) -> None:
        self._cambiar_estado(id_turno, "Cancelado", "cancelar")

    def marcar_ausente(self, id_turno: int) -> None:
        self._cambiar_estado(id_turno, "Ausente", "marcar como ausente")

    # --- Consultas ---------------------------------------------------------------------

    def obtener(self, id_turno: int) -> Turno:
        return self._requerir(self.turnos.obtener_por_id(id_turno), "el turno")

    def turnos_de_veterinario(self, id_veterinario: int, desde: str, hasta: str) -> list[Turno]:
        """Turnos con inicio en [desde, hasta)."""
        return self.turnos.listar_por_veterinario(id_veterinario, desde, hasta)

    def turnos_del_dia(self, fecha: str, id_veterinario: int | None = None) -> list[Turno]:
        dia = v.a_fecha(fecha)
        desde, hasta = dia.isoformat(), (dia + timedelta(days=1)).isoformat()
        if id_veterinario is None:
            return self.turnos.listar_por_rango(desde, hasta)
        return self.turnos.listar_por_veterinario(id_veterinario, desde, hasta)

    def turnos_de_mascota(self, id_mascota: int) -> list[Turno]:
        return self.turnos.listar_por_mascota(id_mascota)

    # --- Auxiliares --------------------------------------------------------------------

    def _verificar_superposicion(self, turno: Turno) -> None:
        choques = self.turnos.buscar_superpuestos(
            turno.id_veterinario, turno.fecha_hora_inicio, turno.fecha_hora_fin, excluir_id=turno.id_turno
        )
        if choques:
            otro = choques[0]
            raise TurnoSuperpuestoError(
                f"El veterinario ya tiene un turno de {otro.fecha_hora_inicio} a "
                f"{otro.fecha_hora_fin[-5:]} que se superpone con el horario pedido."
            )

    def _turno_reservado(self, id_turno: int, accion: str) -> Turno:
        turno = self._requerir(self.turnos.obtener_por_id(id_turno), "el turno")
        if turno.estado != "Reservado":
            raise ReglaNegocioError(f"No se puede {accion} un turno en estado '{turno.estado}'.")
        return turno

    def _cambiar_estado(self, id_turno: int, nuevo_estado: str, accion: str) -> None:
        try:
            turno = self._turno_reservado(id_turno, accion)
            turno.estado = nuevo_estado
            self.turnos.modificar(turno)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
