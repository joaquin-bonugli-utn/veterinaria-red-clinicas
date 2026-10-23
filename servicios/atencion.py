"""Casos de uso de la atención clínica: registro de atenciones y control de vacunas."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, timedelta

from dominio import (
    AplicacionVacuna,
    Atencion,
    Clinica,
    HistoriaClinica,
    Mascota,
    TipoAtencion,
    Tratamiento,
    Turno,
    Vacuna,
    Veterinario,
)
from dominio import validaciones as v
from dominio.excepciones import ReglaNegocioError
from persistencia.repositorios import (
    RepositorioAtenciones,
    RepositorioCatalogos,
    RepositorioMascotas,
    RepositorioTurnos,
    RepositorioVeterinarios,
)
from servicios.base import ServicioBase


# --- Datos de entrada / salida ---------------------------------------------------------

@dataclass(frozen=True)
class TratamientoIndicado:
    """Tratamiento a registrar; fecha_inicio por defecto es el día de la atención."""

    medicamento: str
    dosis: str
    frecuencia: str | None = None
    fecha_fin: str | None = None
    fecha_inicio: str | None = None


@dataclass(frozen=True)
class VacunaAAplicar:
    id_vacuna: int
    lote: str


@dataclass(frozen=True)
class VacunaPendiente:
    """Vacuna obligatoria que corresponde aplicar.

    situacion: 'Pendiente' (nunca aplicada) o 'Vencida' (refuerzo cumplido).
    fecha_limite: desde cuándo corresponde aplicarla.
    """

    vacuna: Vacuna
    situacion: str
    fecha_limite: str
    ultima_aplicacion: str | None = None

    def __str__(self) -> str:
        if self.situacion == "Vencida":
            return (f"{self.vacuna.nombre}: refuerzo vencido el {self.fecha_limite} "
                    f"(última dosis {self.ultima_aplicacion})")
        return f"{self.vacuna.nombre}: pendiente desde el {self.fecha_limite}"


@dataclass
class ResultadoAtencion:
    atencion: Atencion
    tratamientos: list[Tratamiento] = field(default_factory=list)
    aplicaciones: list[AplicacionVacuna] = field(default_factory=list)
    vacunas_pendientes: list[VacunaPendiente] = field(default_factory=list)


# --- Servicio -----------------------------------------------------------------------

class ServicioAtencion(ServicioBase):
    def __init__(
        self,
        repo_atenciones: RepositorioAtenciones | None = None,
        repo_mascotas: RepositorioMascotas | None = None,
        repo_veterinarios: RepositorioVeterinarios | None = None,
        repo_turnos: RepositorioTurnos | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
    ) -> None:
        self.atenciones = repo_atenciones or RepositorioAtenciones()
        self.mascotas = repo_mascotas or RepositorioMascotas()
        self.veterinarios = repo_veterinarios or RepositorioVeterinarios()
        self.turnos = repo_turnos or RepositorioTurnos()
        self.catalogos = repo_catalogos or RepositorioCatalogos()

    def registrar(
        self,
        id_mascota: int,
        id_veterinario: int,
        id_tipo_atencion: int,
        fecha_hora: str,
        motivo: str,
        *,
        id_clinica: int | None = None,
        id_turno: int | None = None,
        diagnostico: str | None = None,
        peso_kg: float | None = None,
        tratamientos: Iterable[TratamientoIndicado] = (),
        vacunas: Iterable[VacunaAAplicar] = (),
    ) -> ResultadoAtencion:
        """Registra la atención con sus tratamientos y vacunas en una sola transacción.

        - Con turno: el turno debe estar Reservado, ser de la misma mascota y
          veterinario, y pasa a Atendido. Sin turno (urgencia): id_turno = None.
        - id_clinica por defecto es la clínica del veterinario.
        - Si se informa peso_kg, se actualiza también el peso de la mascota.
        - Cada vacuna debe ser de la especie y la mascota tener la edad mínima;
          fecha_proxima_dosis = fecha + refuerzo_dias (None si es dosis única).
        Devuelve además las vacunas obligatorias pendientes o vencidas (regla 6).
        """
        fecha_hora = v.fecha_hora_iso(fecha_hora, "fecha_hora")
        fecha = fecha_hora[:10]
        try:
            mascota: Mascota = self._requerir_activo(self.mascotas.obtener_por_id(id_mascota), "la mascota")
            historia = self._requerir(self.mascotas.obtener_historia(id_mascota), "la historia clínica")
            vet: Veterinario = self._requerir_activo(
                self.veterinarios.obtener_por_id(id_veterinario), "el veterinario"
            )
            id_clinica = id_clinica or vet.id_clinica
            self._requerir(self.catalogos.obtener_por_id(id_clinica, Clinica), "la clínica")
            self._requerir(self.catalogos.obtener_por_id(id_tipo_atencion, TipoAtencion), "el tipo de atención")
            turno = self._validar_turno(id_turno, mascota, vet) if id_turno is not None else None

            atencion = Atencion(historia.id_historia, vet.id_veterinario, id_clinica, id_tipo_atencion,
                                fecha_hora, motivo, id_turno, diagnostico, peso_kg)
            self.atenciones.agregar(atencion)

            if turno is not None:
                turno.estado = "Atendido"
                self.turnos.modificar(turno)
            if peso_kg is not None:
                mascota.peso_kg = v.numero_no_negativo(peso_kg, "peso_kg")
                self.mascotas.modificar(mascota)

            registrados = []
            for indicado in tratamientos:
                tratamiento = Tratamiento(atencion.id_atencion, indicado.medicamento, indicado.dosis,
                                          indicado.fecha_inicio or fecha, indicado.frecuencia, indicado.fecha_fin)
                self.atenciones.agregar(tratamiento)
                registrados.append(tratamiento)

            aplicaciones = self._aplicar_vacunas(atencion, mascota, list(vacunas), fecha)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise

        return ResultadoAtencion(atencion, registrados, aplicaciones, self.vacunas_pendientes(id_mascota, fecha))

    def vacunas_pendientes(self, id_mascota: int, fecha: str | date | None = None) -> list[VacunaPendiente]:
        """Vacunas obligatorias de la especie que la mascota debería tener a `fecha` (hoy por defecto).

        - Pendiente: ya cumplió edad_minima_dias y nunca se la aplicaron.
        - Vencida: tiene refuerzo y la fecha de la próxima dosis ya llegó o pasó.
        """
        mascota = self._requerir(self.mascotas.obtener_por_id(id_mascota), "la mascota")
        referencia = date.today() if fecha is None else v.a_fecha(fecha)
        hoy_iso = referencia.isoformat()
        edad = mascota.edad_en_dias(referencia)
        nacimiento = v.a_fecha(mascota.fecha_nacimiento)
        aplicaciones = [a for a in self.atenciones.listar_aplicaciones_por_mascota(id_mascota)
                        if a.fecha_aplicacion <= hoy_iso]

        pendientes: list[VacunaPendiente] = []
        for vacuna in self.catalogos.vacunas_por_especie(mascota.id_especie, solo_obligatorias=True):
            if edad < vacuna.edad_minima_dias:
                continue
            previas = [a for a in aplicaciones if a.id_vacuna == vacuna.id_vacuna]
            if not previas:
                desde = (nacimiento + timedelta(days=vacuna.edad_minima_dias)).isoformat()
                pendientes.append(VacunaPendiente(vacuna, "Pendiente", desde))
            elif vacuna.refuerzo_dias is not None:
                ultima = max(previas, key=lambda a: a.fecha_aplicacion)
                vence = ultima.fecha_proxima_dosis or (
                    v.a_fecha(ultima.fecha_aplicacion) + timedelta(days=vacuna.refuerzo_dias)
                ).isoformat()
                if vence <= hoy_iso:
                    pendientes.append(VacunaPendiente(vacuna, "Vencida", vence, ultima.fecha_aplicacion))
        return pendientes

    # --- Consultas ---------------------------------------------------------------------

    def atenciones_de_mascota(self, id_mascota: int) -> list[Atencion]:
        return self.atenciones.listar_por_mascota(id_mascota)

    def obtener(self, id_atencion: int) -> Atencion:
        return self._requerir(self.atenciones.obtener_por_id(id_atencion), "la atención")

    def mascota_de_atencion(self, id_atencion: int) -> Mascota:
        """Mascota atendida (atención → historia clínica → mascota)."""
        atencion = self.obtener(id_atencion)
        historia = self._requerir(self.mascotas.obtener_por_id(atencion.id_historia, HistoriaClinica),
                                  "la historia clínica")
        return self._requerir(self.mascotas.obtener_por_id(historia.id_mascota), "la mascota")

    def tratamientos_de(self, id_atencion: int) -> list[Tratamiento]:
        return self.atenciones.listar_tratamientos(id_atencion)

    def vacunas_aplicadas_de(self, id_atencion: int) -> list[AplicacionVacuna]:
        return self.atenciones.listar_aplicaciones(id_atencion)

    # --- Auxiliares --------------------------------------------------------------------

    def _validar_turno(self, id_turno: int, mascota: Mascota, vet: Veterinario) -> Turno:
        turno: Turno = self._requerir(self.turnos.obtener_por_id(id_turno), "el turno")
        if turno.estado != "Reservado":
            raise ReglaNegocioError(f"El turno está en estado '{turno.estado}': no se puede atender.")
        if turno.id_mascota != mascota.id_mascota:
            raise ReglaNegocioError("El turno corresponde a otra mascota.")
        if turno.id_veterinario != vet.id_veterinario:
            raise ReglaNegocioError("El turno corresponde a otro veterinario.")
        return turno

    def _aplicar_vacunas(
        self, atencion: Atencion, mascota: Mascota, vacunas: list[VacunaAAplicar], fecha: str
    ) -> list[AplicacionVacuna]:
        ids = [va.id_vacuna for va in vacunas]
        if len(ids) != len(set(ids)):
            raise ReglaNegocioError("Una misma vacuna no puede aplicarse dos veces en la misma atención.")

        previas = {a.id_vacuna for a in self.atenciones.listar_aplicaciones_por_mascota(mascota.id_mascota)}
        edad = mascota.edad_en_dias(fecha)
        aplicaciones = []
        for va in vacunas:
            vacuna: Vacuna = self._requerir(self.catalogos.obtener_por_id(va.id_vacuna, Vacuna), "la vacuna")
            if vacuna.id_especie != mascota.id_especie:
                raise ReglaNegocioError(f"La vacuna {vacuna.nombre} no corresponde a la especie de la mascota.")
            if edad < vacuna.edad_minima_dias:
                raise ReglaNegocioError(
                    f"La vacuna {vacuna.nombre} requiere {vacuna.edad_minima_dias} días de edad "
                    f"y la mascota tiene {edad}."
                )
            if vacuna.es_dosis_unica and vacuna.id_vacuna in previas:
                raise ReglaNegocioError(f"La vacuna {vacuna.nombre} es de dosis única y ya fue aplicada.")
            proxima = None if vacuna.es_dosis_unica else (
                v.a_fecha(fecha) + timedelta(days=vacuna.refuerzo_dias)
            ).isoformat()
            aplicacion = AplicacionVacuna(atencion.id_atencion, vacuna.id_vacuna, fecha, va.lote, proxima)
            self.atenciones.agregar(aplicacion)
            aplicaciones.append(aplicacion)
        return aplicaciones
