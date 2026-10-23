"""Entidades de la cadena de envío, recepción y resultados de laboratorio."""

from __future__ import annotations

from dominio import validaciones as v


class Transportista:
    """Persona que traslada las conservadoras en un tramo."""

    def __init__(
        self,
        documento: str,
        nombre: str,
        telefono: str | None = None,
        vehiculo: str | None = None,
        id_transportista: int | None = None,
    ) -> None:
        self.id_transportista = v.id_opcional(id_transportista, "id_transportista")
        self.documento = v.texto_obligatorio(documento, "documento")
        self.nombre = v.texto_obligatorio(nombre, "nombre")
        self.telefono = v.texto_opcional(telefono, "telefono")
        self.vehiculo = v.texto_opcional(vehiculo, "vehiculo")

    def __str__(self) -> str:
        vehiculo = f" - {self.vehiculo}" if self.vehiculo else ""
        return f"{self.nombre} (doc. {self.documento}){vehiculo}"


class TramoEnvio:
    """Tramo de la cadena de custodia de un remito."""

    def __init__(
        self,
        id_remito: int,
        id_transportista: int,
        nro_tramo: int,
        origen: str,
        destino: str,
        fecha_hora_salida: str,
        fecha_hora_llegada: str | None = None,
        temperatura: float | None = None,
        id_tramo: int | None = None,
    ) -> None:
        self.id_tramo = v.id_opcional(id_tramo, "id_tramo")
        self.id_remito = v.id_obligatorio(id_remito, "id_remito")
        self.id_transportista = v.id_obligatorio(id_transportista, "id_transportista")
        self.nro_tramo = v.entero_positivo(nro_tramo, "nro_tramo")
        self.origen = v.texto_obligatorio(origen, "origen")
        self.destino = v.texto_obligatorio(destino, "destino")
        self.fecha_hora_salida = v.fecha_hora_iso(fecha_hora_salida, "fecha_hora_salida")
        self.fecha_hora_llegada = v.fecha_hora_iso_opcional(fecha_hora_llegada, "fecha_hora_llegada")
        if self.fecha_hora_llegada is not None and self.fecha_hora_llegada < self.fecha_hora_salida:
            raise ValueError("La llegada del tramo no puede ser anterior a la salida.")
        self.temperatura = v.numero_opcional(temperatura, "temperatura")

    @property
    def finalizado(self) -> bool:
        return self.fecha_hora_llegada is not None

    def __str__(self) -> str:
        llegada = self.fecha_hora_llegada or "en curso"
        return f"Tramo {self.nro_tramo}: {self.origen} → {self.destino} ({self.fecha_hora_salida} / {llegada})"


class Recepcion:
    """Recepción de un remito en el laboratorio, con control del precinto."""

    ESTADOS_PRECINTO = ("Intacto", "Roto")

    def __init__(
        self,
        id_remito: int,
        fecha_hora: str,
        receptor: str,
        estado_precinto: str,
        aceptada: bool,
        temperatura_llegada: float | None = None,
        observaciones: str | None = None,
        id_recepcion: int | None = None,
    ) -> None:
        self.id_recepcion = v.id_opcional(id_recepcion, "id_recepcion")
        self.id_remito = v.id_obligatorio(id_remito, "id_remito")
        self.fecha_hora = v.fecha_hora_iso(fecha_hora, "fecha_hora")
        self.receptor = v.texto_obligatorio(receptor, "receptor")
        self.estado_precinto = v.opcion(estado_precinto, "estado_precinto", self.ESTADOS_PRECINTO)
        self.aceptada = v.booleano(aceptada, "aceptada")
        if self.estado_precinto == "Roto" and self.aceptada:
            raise ValueError("No se puede aceptar una recepción con el precinto roto.")
        self.temperatura_llegada = v.numero_opcional(temperatura_llegada, "temperatura_llegada")
        self.observaciones = v.texto_opcional(observaciones, "observaciones")

    def __str__(self) -> str:
        resultado = "aceptada" if self.aceptada else "rechazada"
        return f"Recepción {self.fecha_hora} por {self.receptor}: precinto {self.estado_precinto}, {resultado}"


class ResultadoAnalisis:
    """Resultado cargado por el laboratorio para una muestra."""

    def __init__(
        self,
        id_muestra: int,
        fecha_hora: str,
        bioquimico: str,
        valores: str,
        conclusion: str | None = None,
        id_resultado: int | None = None,
    ) -> None:
        self.id_resultado = v.id_opcional(id_resultado, "id_resultado")
        self.id_muestra = v.id_obligatorio(id_muestra, "id_muestra")
        self.fecha_hora = v.fecha_hora_iso(fecha_hora, "fecha_hora")
        self.bioquimico = v.texto_obligatorio(bioquimico, "bioquimico")
        self.valores = v.texto_obligatorio(valores, "valores")
        self.conclusion = v.texto_opcional(conclusion, "conclusion")

    def __str__(self) -> str:
        conclusion = f": {self.conclusion}" if self.conclusion else ""
        return f"Resultado de muestra {self.id_muestra} ({self.fecha_hora}, {self.bioquimico}){conclusion}"
