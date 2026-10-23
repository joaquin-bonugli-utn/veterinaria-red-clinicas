"""Entidades de agenda y atención clínica: turnos, atenciones, vacunas y tratamientos."""

from __future__ import annotations

from datetime import datetime

from dominio import validaciones as v


class Turno:
    """Reserva de un veterinario para atender a una mascota."""

    ESTADOS = ("Reservado", "Atendido", "Cancelado", "Ausente")

    def __init__(
        self,
        id_veterinario: int,
        id_mascota: int,
        fecha_hora_inicio: str,
        fecha_hora_fin: str,
        estado: str = "Reservado",
        id_turno: int | None = None,
    ) -> None:
        self.id_turno = v.id_opcional(id_turno, "id_turno")
        self.id_veterinario = v.id_obligatorio(id_veterinario, "id_veterinario")
        self.id_mascota = v.id_obligatorio(id_mascota, "id_mascota")
        self.fecha_hora_inicio = v.fecha_hora_iso(fecha_hora_inicio, "fecha_hora_inicio")
        self.fecha_hora_fin = v.fecha_hora_iso(fecha_hora_fin, "fecha_hora_fin")
        if self.fin <= self.inicio:
            raise ValueError("La hora de fin del turno debe ser posterior a la de inicio.")
        self.estado = v.opcion(estado, "estado", self.ESTADOS)

    @property
    def inicio(self) -> datetime:
        return v.a_fecha_hora(self.fecha_hora_inicio)

    @property
    def fin(self) -> datetime:
        return v.a_fecha_hora(self.fecha_hora_fin)

    def se_superpone_con(self, otro: Turno) -> bool:
        """True si ambos turnos activos del mismo veterinario se pisan en el tiempo."""
        if self.estado == "Cancelado" or otro.estado == "Cancelado":
            return False
        if self.id_veterinario != otro.id_veterinario:
            return False
        return self.inicio < otro.fin and self.fin > otro.inicio

    def __str__(self) -> str:
        return (
            f"Turno {self.fecha_hora_inicio} a {self.fecha_hora_fin[-5:]} "
            f"(vet. {self.id_veterinario}, mascota {self.id_mascota}) - {self.estado}"
        )


class TipoAtencion:
    """Tipo de atención con su precio base (Consulta, Control, Urgencia)."""

    def __init__(self, nombre: str, precio: float, id_tipo_atencion: int | None = None) -> None:
        self.id_tipo_atencion = v.id_opcional(id_tipo_atencion, "id_tipo_atencion")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.precio = v.numero_no_negativo(precio, "precio")

    def __str__(self) -> str:
        return f"{self.nombre} (${self.precio:,.2f})"


class Atencion:
    """Acto clínico registrado en la historia de una mascota."""

    def __init__(
        self,
        id_historia: int,
        id_veterinario: int,
        id_clinica: int,
        id_tipo_atencion: int,
        fecha_hora: str,
        motivo: str,
        id_turno: int | None = None,
        diagnostico: str | None = None,
        peso_kg: float | None = None,
        id_atencion: int | None = None,
    ) -> None:
        self.id_atencion = v.id_opcional(id_atencion, "id_atencion")
        self.id_historia = v.id_obligatorio(id_historia, "id_historia")
        self.id_veterinario = v.id_obligatorio(id_veterinario, "id_veterinario")
        self.id_clinica = v.id_obligatorio(id_clinica, "id_clinica")
        self.id_tipo_atencion = v.id_obligatorio(id_tipo_atencion, "id_tipo_atencion")
        self.id_turno = v.id_opcional(id_turno, "id_turno")
        self.fecha_hora = v.fecha_hora_iso(fecha_hora, "fecha_hora")
        self.motivo = v.texto_obligatorio(motivo, "motivo")
        self.diagnostico = v.texto_opcional(diagnostico, "diagnostico")
        self.peso_kg = v.numero_no_negativo_opcional(peso_kg, "peso_kg")

    def __str__(self) -> str:
        return f"Atención {self.fecha_hora} - {self.motivo}"


class Vacuna:
    """Vacuna del esquema de una especie."""

    def __init__(
        self,
        nombre: str,
        id_especie: int,
        precio: float,
        obligatoria: bool = False,
        edad_minima_dias: int = 0,
        refuerzo_dias: int | None = None,
        id_vacuna: int | None = None,
    ) -> None:
        self.id_vacuna = v.id_opcional(id_vacuna, "id_vacuna")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.id_especie = v.id_obligatorio(id_especie, "id_especie")
        self.precio = v.numero_no_negativo(precio, "precio")
        self.obligatoria = v.booleano(obligatoria, "obligatoria")
        self.edad_minima_dias = v.entero_no_negativo(edad_minima_dias, "edad_minima_dias")
        self.refuerzo_dias = (
            None if refuerzo_dias is None else v.entero_positivo(refuerzo_dias, "refuerzo_dias")
        )

    @property
    def es_dosis_unica(self) -> bool:
        return self.refuerzo_dias is None

    def __str__(self) -> str:
        tipo = "obligatoria" if self.obligatoria else "opcional"
        refuerzo = "dosis única" if self.es_dosis_unica else f"refuerzo cada {self.refuerzo_dias} días"
        return f"{self.nombre} ({tipo}, desde {self.edad_minima_dias} días, {refuerzo})"


class AplicacionVacuna:
    """Aplicación de una vacuna durante una atención."""

    def __init__(
        self,
        id_atencion: int,
        id_vacuna: int,
        fecha_aplicacion: str,
        lote: str,
        fecha_proxima_dosis: str | None = None,
        id_aplicacion: int | None = None,
    ) -> None:
        self.id_aplicacion = v.id_opcional(id_aplicacion, "id_aplicacion")
        self.id_atencion = v.id_obligatorio(id_atencion, "id_atencion")
        self.id_vacuna = v.id_obligatorio(id_vacuna, "id_vacuna")
        self.fecha_aplicacion = v.fecha_iso(fecha_aplicacion, "fecha_aplicacion")
        self.lote = v.texto_obligatorio(lote, "lote")
        self.fecha_proxima_dosis = v.fecha_iso_opcional(fecha_proxima_dosis, "fecha_proxima_dosis")
        if self.fecha_proxima_dosis is not None and self.fecha_proxima_dosis <= self.fecha_aplicacion:
            raise ValueError("La próxima dosis debe ser posterior a la fecha de aplicación.")

    def __str__(self) -> str:
        proxima = f", próxima {self.fecha_proxima_dosis}" if self.fecha_proxima_dosis else ""
        return f"Vacuna {self.id_vacuna} aplicada {self.fecha_aplicacion} (lote {self.lote}{proxima})"


class Tratamiento:
    """Medicación indicada en una atención."""

    def __init__(
        self,
        id_atencion: int,
        medicamento: str,
        dosis: str,
        fecha_inicio: str,
        frecuencia: str | None = None,
        fecha_fin: str | None = None,
        id_tratamiento: int | None = None,
    ) -> None:
        self.id_tratamiento = v.id_opcional(id_tratamiento, "id_tratamiento")
        self.id_atencion = v.id_obligatorio(id_atencion, "id_atencion")
        self.medicamento = v.texto_obligatorio(medicamento, "medicamento")
        self.dosis = v.texto_obligatorio(dosis, "dosis")
        self.fecha_inicio = v.fecha_iso(fecha_inicio, "fecha_inicio")
        self.frecuencia = v.texto_opcional(frecuencia, "frecuencia")
        self.fecha_fin = v.fecha_iso_opcional(fecha_fin, "fecha_fin")
        if self.fecha_fin is not None and self.fecha_fin < self.fecha_inicio:
            raise ValueError("La fecha de fin del tratamiento no puede ser anterior a la de inicio.")

    def __str__(self) -> str:
        frecuencia = f" {self.frecuencia}" if self.frecuencia else ""
        return f"{self.medicamento} {self.dosis}{frecuencia} desde {self.fecha_inicio}"
