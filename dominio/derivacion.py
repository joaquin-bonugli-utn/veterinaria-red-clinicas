"""Entidades de derivación a laboratorio: análisis, órdenes, conservadoras, remitos y muestras.

``Muestra`` y ``RemitoBiologico`` son los contextos del patrón State: delegan
sus transiciones en los objetos de estado_muestra.py y estados_remito.py.
"""

from __future__ import annotations

from datetime import datetime

from dominio import estados_muestra, estados_remito
from dominio import validaciones as v
from dominio.estados_muestra import EstadoMuestra
from dominio.estados_remito import EstadoRemito

ESTADOS_MUESTRA = ("Extraída", "Empaquetada", "En tránsito", "Recibida", "Analizada", "Rechazada")


class TipoAnalisis:
    """Análisis que ofrece el laboratorio, con sus condiciones de conservación."""

    def __init__(
        self,
        nombre: str,
        tipo_muestra: str,
        temp_min: float,
        temp_max: float,
        horas_viabilidad: int,
        precio: float,
        id_tipo_analisis: int | None = None,
    ) -> None:
        self.id_tipo_analisis = v.id_opcional(id_tipo_analisis, "id_tipo_analisis")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.tipo_muestra = v.texto_obligatorio(tipo_muestra, "tipo_muestra")
        self.temp_min = v.numero(temp_min, "temp_min")
        self.temp_max = v.numero(temp_max, "temp_max")
        if self.temp_max < self.temp_min:
            raise ValueError("La temperatura máxima no puede ser menor que la mínima.")
        self.horas_viabilidad = v.entero_positivo(horas_viabilidad, "horas_viabilidad")
        self.precio = v.numero_no_negativo(precio, "precio")

    def admite_temperatura(self, temperatura: float) -> bool:
        """True si la muestra puede conservarse a esa temperatura."""
        return self.temp_min <= temperatura <= self.temp_max

    def __str__(self) -> str:
        return (
            f"{self.nombre} ({self.tipo_muestra}, {self.temp_min:g} a {self.temp_max:g} °C, "
            f"{self.horas_viabilidad} h)"
        )


class OrdenDerivacion:
    """Orden emitida en una atención para enviar muestras a un laboratorio."""

    PRIORIDADES = ("Normal", "Urgente")
    ESTADOS = ("Emitida", "En proceso", "Finalizada", "Anulada")

    def __init__(
        self,
        id_atencion: int,
        id_laboratorio: int,
        fecha_emision: str,
        prioridad: str = "Normal",
        indicaciones: str | None = None,
        estado: str = "Emitida",
        id_orden: int | None = None,
    ) -> None:
        self.id_orden = v.id_opcional(id_orden, "id_orden")
        self.id_atencion = v.id_obligatorio(id_atencion, "id_atencion")
        self.id_laboratorio = v.id_obligatorio(id_laboratorio, "id_laboratorio")
        self.fecha_emision = v.fecha_iso(fecha_emision, "fecha_emision")
        self.prioridad = v.opcion(prioridad, "prioridad", self.PRIORIDADES)
        self.indicaciones = v.texto_opcional(indicaciones, "indicaciones")
        self.estado = v.opcion(estado, "estado", self.ESTADOS)

    def __str__(self) -> str:
        numero = self.id_orden if self.id_orden is not None else "s/n"
        return f"Orden N° {numero} ({self.prioridad}) emitida {self.fecha_emision} - {self.estado}"


class Conservadora:
    """Contenedor isotérmico reutilizable para transportar muestras."""

    ESTADOS = ("Disponible", "En uso", "Fuera de servicio")

    def __init__(
        self,
        codigo: str,
        id_clinica: int,
        capacidad: int,
        temp_min: float,
        temp_max: float,
        estado: str = "Disponible",
        id_conservadora: int | None = None,
    ) -> None:
        self.id_conservadora = v.id_opcional(id_conservadora, "id_conservadora")
        self.codigo = v.texto_obligatorio(codigo, "codigo")
        self.id_clinica = v.id_obligatorio(id_clinica, "id_clinica")
        self.capacidad = v.entero_positivo(capacidad, "capacidad")
        self.temp_min = v.numero(temp_min, "temp_min")
        self.temp_max = v.numero(temp_max, "temp_max")
        if self.temp_max < self.temp_min:
            raise ValueError("La temperatura máxima no puede ser menor que la mínima.")
        self.estado = v.opcion(estado, "estado", self.ESTADOS)

    @property
    def disponible(self) -> bool:
        return self.estado == "Disponible"

    def admite_temperatura(self, temperatura: float) -> bool:
        """True si la conservadora puede operar a esa temperatura."""
        return self.temp_min <= temperatura <= self.temp_max

    def es_compatible_con(self, tipo: TipoAnalisis) -> bool:
        """Regla 7: los rangos de la conservadora y del análisis se solapan, es decir,
        existe al menos una temperatura válida para ambos."""
        return self.temp_min <= tipo.temp_max and tipo.temp_min <= self.temp_max

    def __str__(self) -> str:
        return (
            f"Conservadora {self.codigo} (cap. {self.capacidad}, "
            f"{self.temp_min:g} a {self.temp_max:g} °C) - {self.estado}"
        )


class RemitoBiologico:
    """Documento que acompaña el envío de una conservadora (contexto del patrón State)."""

    def __init__(
        self,
        numero: str,
        id_clinica: int,
        id_laboratorio: int,
        id_conservadora: int,
        fecha_emision: str,
        estado: str = "Emitido",
        id_remito: int | None = None,
    ) -> None:
        self.id_remito = v.id_opcional(id_remito, "id_remito")
        self.numero = v.texto_obligatorio(numero, "numero")
        self.id_clinica = v.id_obligatorio(id_clinica, "id_clinica")
        self.id_laboratorio = v.id_obligatorio(id_laboratorio, "id_laboratorio")
        self.id_conservadora = v.id_obligatorio(id_conservadora, "id_conservadora")
        self.fecha_emision = v.fecha_iso(fecha_emision, "fecha_emision")
        self._estado: EstadoRemito = estados_remito.estado_desde_nombre(estado)

    @property
    def estado(self) -> str:
        """Nombre del estado actual (lo que se guarda en la base)."""
        return self._estado.nombre

    @property
    def estado_obj(self) -> EstadoRemito:
        return self._estado

    def cambiar_estado(self, nuevo_estado: EstadoRemito) -> None:
        """Lo invocan los objetos estado al realizar una transición válida."""
        self._estado = nuevo_estado

    def despachar(self) -> None:
        self._estado.despachar(self)

    def recibir(self, precinto_intacto: bool) -> None:
        self._estado.recibir(self, precinto_intacto)

    def __str__(self) -> str:
        return f"Remito {self.numero} emitido {self.fecha_emision} - {self.estado}"


class PrecintoSanitario:
    """Precinto que sella la conservadora de un remito."""

    ESTADOS = ("Colocado", "Intacto", "Roto")

    def __init__(
        self,
        numero: str,
        id_remito: int,
        fecha_colocacion: str,
        temp_cierre: float | None = None,
        estado: str = "Colocado",
        id_precinto: int | None = None,
    ) -> None:
        self.id_precinto = v.id_opcional(id_precinto, "id_precinto")
        self.numero = v.texto_obligatorio(numero, "numero")
        self.id_remito = v.id_obligatorio(id_remito, "id_remito")
        self.fecha_colocacion = v.fecha_hora_iso(fecha_colocacion, "fecha_colocacion")
        self.temp_cierre = v.numero_opcional(temp_cierre, "temp_cierre")
        self.estado = v.opcion(estado, "estado", self.ESTADOS)

    @property
    def roto(self) -> bool:
        return self.estado == "Roto"

    def __str__(self) -> str:
        return f"Precinto {self.numero} ({self.estado})"


class Muestra:
    """Muestra biológica: núcleo de la trazabilidad (contexto del patrón State).

    Guarda el objeto estado actual y el historial de cambios, al que solo se
    puede agregar (``historial`` devuelve una tupla de solo lectura).
    """

    def __init__(
        self,
        codigo: str,
        id_orden: int,
        id_tipo_analisis: int,
        fecha_hora_extraccion: str,
        volumen_ml: float | None = None,
        id_remito: int | None = None,
        estado_actual: str = "Extraída",
        id_muestra: int | None = None,
    ) -> None:
        self.id_muestra = v.id_opcional(id_muestra, "id_muestra")
        self.codigo = v.texto_obligatorio(codigo, "codigo")
        self.id_orden = v.id_obligatorio(id_orden, "id_orden")
        self.id_tipo_analisis = v.id_obligatorio(id_tipo_analisis, "id_tipo_analisis")
        self.fecha_hora_extraccion = v.fecha_hora_iso(fecha_hora_extraccion, "fecha_hora_extraccion")
        self.volumen_ml = v.numero_no_negativo_opcional(volumen_ml, "volumen_ml")
        self.id_remito = v.id_opcional(id_remito, "id_remito")
        self._estado: EstadoMuestra = estados_muestra.estado_desde_nombre(estado_actual)
        self._historial: list[CambioEstadoMuestra] = []

    @classmethod
    def nueva(
        cls,
        codigo: str,
        id_orden: int,
        id_tipo_analisis: int,
        fecha_hora_extraccion: str,
        responsable: str,
        volumen_ml: float | None = None,
    ) -> Muestra:
        """Crea una muestra Extraída con su primer registro en el historial."""
        muestra = cls(codigo, id_orden, id_tipo_analisis, fecha_hora_extraccion, volumen_ml)
        muestra.agregar_al_historial(
            CambioEstadoMuestra(None, "Extraída", fecha_hora_extraccion, responsable, "Extracción")
        )
        return muestra

    # --- Estado e historial ----------------------------------------------------

    @property
    def estado_actual(self) -> str:
        """Nombre del estado actual (lo que se guarda en muestra.estado_actual)."""
        return self._estado.nombre

    @property
    def estado(self) -> EstadoMuestra:
        return self._estado

    @property
    def historial(self) -> tuple[CambioEstadoMuestra, ...]:
        """Cambios de estado en orden cronológico (solo lectura)."""
        return tuple(self._historial)

    @property
    def ultimo_cambio(self) -> CambioEstadoMuestra | None:
        return self._historial[-1] if self._historial else None

    def agregar_al_historial(self, cambio: CambioEstadoMuestra) -> None:
        """Agrega un registro al final (se usa también al reconstruir desde la base)."""
        if not isinstance(cambio, CambioEstadoMuestra):
            raise TypeError("El historial solo admite objetos CambioEstadoMuestra.")
        if self._historial and cambio.fecha_hora < self._historial[-1].fecha_hora:
            raise ValueError("El cambio de estado no puede ser anterior al último registrado.")
        self._historial.append(cambio)

    def cambiar_estado(
        self,
        nuevo_estado: EstadoMuestra,
        responsable: str,
        fecha_hora: str | None = None,
        observacion: str | None = None,
    ) -> None:
        """Lo invocan los objetos estado: cambia el estado y registra el cambio."""
        if fecha_hora is None:
            fecha_hora = datetime.now().strftime(v.FORMATO_FECHA_HORA)
        cambio = CambioEstadoMuestra(
            self.id_muestra, nuevo_estado.nombre, fecha_hora, responsable, observacion
        )
        self.agregar_al_historial(cambio)
        self._estado = nuevo_estado

    # --- Operaciones: delegan en el estado actual ------------------------------

    def empaquetar(self, id_remito: int, responsable: str, fecha_hora: str | None = None) -> None:
        id_remito = v.id_obligatorio(id_remito, "id_remito")
        self._estado.empaquetar(self, responsable, fecha_hora)
        self.id_remito = id_remito

    def despachar(self, responsable: str, fecha_hora: str | None = None) -> None:
        self._estado.despachar(self, responsable, fecha_hora)

    def recibir(self, precinto_intacto: bool, responsable: str, fecha_hora: str | None = None) -> None:
        self._estado.recibir(self, v.booleano(precinto_intacto, "precinto_intacto"), responsable, fecha_hora)

    def rechazar(self, motivo: str, responsable: str, fecha_hora: str | None = None) -> None:
        self._estado.rechazar(self, motivo, responsable, fecha_hora)

    def registrar_resultado(self, responsable: str, fecha_hora: str | None = None) -> None:
        self._estado.registrar_resultado(self, responsable, fecha_hora)

    def es_viable(self, momento: str | datetime, tipo: TipoAnalisis) -> bool:
        """True si no se superaron las horas de viabilidad del análisis."""
        transcurrido = v.a_fecha_hora(momento) - v.a_fecha_hora(self.fecha_hora_extraccion)
        return transcurrido.total_seconds() <= tipo.horas_viabilidad * 3600

    def __str__(self) -> str:
        return f"Muestra {self.codigo} (extraída {self.fecha_hora_extraccion}) - {self.estado_actual}"


class CambioEstadoMuestra:
    """Registro inmutable de un cambio de estado (tabla historial_estado_muestra)."""

    __slots__ = ("_id_historial", "_id_muestra", "_estado", "_fecha_hora", "_responsable", "_observacion")

    def __init__(
        self,
        id_muestra: int | None,
        estado: str,
        fecha_hora: str,
        responsable: str,
        observacion: str | None = None,
        id_historial: int | None = None,
    ) -> None:
        self._id_historial = v.id_opcional(id_historial, "id_historial")
        # None mientras la muestra no está persistida; el repositorio usa el id de la muestra.
        self._id_muestra = v.id_opcional(id_muestra, "id_muestra")
        self._estado = v.opcion(estado, "estado", ESTADOS_MUESTRA)
        self._fecha_hora = v.fecha_hora_iso(fecha_hora, "fecha_hora")
        self._responsable = v.texto_obligatorio(responsable, "responsable")
        self._observacion = v.texto_opcional(observacion, "observacion")

    # Solo lectura: el historial no se modifica una vez creado.
    id_historial = property(lambda self: self._id_historial)
    id_muestra = property(lambda self: self._id_muestra)
    estado = property(lambda self: self._estado)
    fecha_hora = property(lambda self: self._fecha_hora)
    responsable = property(lambda self: self._responsable)
    observacion = property(lambda self: self._observacion)

    @property
    def persistido(self) -> bool:
        return self._id_historial is not None

    def marcar_persistido(self, id_historial: int, id_muestra: int) -> None:
        """Asigna los ids tras el INSERT. Solo se puede hacer una vez."""
        if self.persistido:
            raise ValueError("Este cambio de estado ya fue guardado.")
        id_muestra = v.id_obligatorio(id_muestra, "id_muestra")
        if self._id_muestra is not None and self._id_muestra != id_muestra:
            raise ValueError("El cambio de estado pertenece a otra muestra.")
        self._id_historial = v.id_obligatorio(id_historial, "id_historial")
        self._id_muestra = id_muestra

    def __str__(self) -> str:
        obs = f" - {self.observacion}" if self.observacion else ""
        return f"{self.fecha_hora} {self.estado} ({self.responsable}){obs}"
