"""Casos de uso del envío: empaquetado en conservadora y tramos de la cadena de custodia.

Las transiciones de muestras y remitos las decide el patrón State
(``muestra.empaquetar()``, ``remito.despachar()``...): si una no corresponde, el
estado lanza TransicionInvalidaError y la transacción completa se deshace.
"""

from __future__ import annotations

from collections.abc import Sequence

from dominio import (
    Clinica,
    Conservadora,
    Muestra,
    PrecintoSanitario,
    RemitoBiologico,
    TipoAnalisis,
    TramoEnvio,
    Transportista,
)
from dominio import validaciones as v
from dominio.excepciones import ReglaNegocioError
from persistencia.repositorios import (
    RepositorioAtenciones,
    RepositorioCatalogos,
    RepositorioDerivaciones,
    RepositorioEnvios,
)
from servicios.base import ServicioBase, ahora


class ServicioEnvios(ServicioBase):
    def __init__(
        self,
        repo_envios: RepositorioEnvios | None = None,
        repo_derivaciones: RepositorioDerivaciones | None = None,
        repo_atenciones: RepositorioAtenciones | None = None,
        repo_catalogos: RepositorioCatalogos | None = None,
    ) -> None:
        self.envios = repo_envios or RepositorioEnvios()
        self.derivaciones = repo_derivaciones or RepositorioDerivaciones()
        self.atenciones = repo_atenciones or RepositorioAtenciones()
        self.catalogos = repo_catalogos or RepositorioCatalogos()

    # --- 2. Empaquetado ----------------------------------------------------------------

    def empaquetar(
        self,
        ids_muestras: Sequence[int],
        id_conservadora: int,
        numero_precinto: str,
        temp_cierre: float,
        *,
        fecha_hora: str | None = None,
        responsable: str | None = None,
    ) -> RemitoBiologico:
        """Empaqueta muestras en una conservadora y genera remito y precinto.

        Valida (regla 7): conservadora Disponible, capacidad suficiente y que
        temp_cierre esté dentro del rango de cada tipo de análisis y de la
        conservadora. Todas las muestras deben ir al mismo laboratorio y salir de
        la clínica dueña de la conservadora.
        Resultado: remito REM-AAAA-NNNNN (Emitido), precinto Colocado, muestras
        Empaquetada y conservadora En uso; las órdenes Emitidas pasan a En proceso.
        """
        if not ids_muestras:
            raise ReglaNegocioError("Hay que indicar al menos una muestra para empaquetar.")
        if len(set(ids_muestras)) != len(ids_muestras):
            raise ReglaNegocioError("Hay muestras repetidas en la lista.")
        temp_cierre = v.numero(temp_cierre, "temp_cierre")
        fecha_hora = v.fecha_hora_iso(fecha_hora or ahora(), "fecha_hora")
        try:
            conservadora: Conservadora = self._requerir(
                self.envios.obtener_por_id(id_conservadora, Conservadora), "la conservadora"
            )
            if not conservadora.disponible:
                raise ReglaNegocioError(
                    f"La conservadora {conservadora.codigo} no está disponible (estado: {conservadora.estado})."
                )
            if len(ids_muestras) > conservadora.capacidad:
                raise ReglaNegocioError(
                    f"La conservadora {conservadora.codigo} admite {conservadora.capacidad} muestras "
                    f"y se quieren empaquetar {len(ids_muestras)}."
                )
            if not conservadora.admite_temperatura(temp_cierre):
                raise ReglaNegocioError(
                    f"La temperatura de cierre ({temp_cierre:g} °C) está fuera del rango de la conservadora "
                    f"({conservadora.temp_min:g} a {conservadora.temp_max:g} °C)."
                )

            muestras = [self._requerir(self.derivaciones.obtener_por_id(id_m, Muestra), f"la muestra {id_m}")
                        for id_m in ids_muestras]
            ordenes = {m.id_orden: self.derivaciones.obtener_por_id(m.id_orden) for m in muestras}
            self._validar_destino_y_origen(ordenes.values(), conservadora)
            for muestra in muestras:
                tipo: TipoAnalisis = self.catalogos.obtener_por_id(muestra.id_tipo_analisis, TipoAnalisis)
                if not conservadora.es_compatible_con(tipo):
                    raise ReglaNegocioError(
                        f"La conservadora {conservadora.codigo} ({conservadora.temp_min:g} a "
                        f"{conservadora.temp_max:g} °C) no es compatible con {tipo.nombre} "
                        f"({tipo.temp_min:g} a {tipo.temp_max:g} °C)."
                    )
                if not tipo.admite_temperatura(temp_cierre):
                    raise ReglaNegocioError(
                        f"La temperatura de cierre ({temp_cierre:g} °C) está fuera del rango de "
                        f"{tipo.nombre} ({tipo.temp_min:g} a {tipo.temp_max:g} °C) para la muestra {muestra.codigo}."
                    )
            if self.envios.buscar_precinto_por_numero(numero_precinto) is not None:
                raise ReglaNegocioError(f"Ya existe un precinto con número {numero_precinto}.")

            if responsable is None:
                clinica = self.catalogos.obtener_por_id(conservadora.id_clinica, Clinica)
                responsable = f"Clínica {clinica.nombre}"

            id_laboratorio = next(iter(ordenes.values())).id_laboratorio
            remito = RemitoBiologico(self._siguiente_numero_remito(fecha_hora[:4]), conservadora.id_clinica,
                                     id_laboratorio, conservadora.id_conservadora, fecha_hora[:10])
            self.envios.agregar(remito)
            self.envios.agregar(PrecintoSanitario(numero_precinto, remito.id_remito, fecha_hora, temp_cierre))

            for muestra in muestras:
                muestra.empaquetar(remito.id_remito, responsable, fecha_hora)  # State
                self.derivaciones.modificar(muestra)
            for orden in ordenes.values():
                if orden.estado == "Emitida":
                    orden.estado = "En proceso"
                    self.derivaciones.modificar(orden)

            conservadora.estado = "En uso"
            self.envios.modificar(conservadora)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return remito

    # --- 3. Tramos ---------------------------------------------------------------------

    def registrar_tramo(
        self,
        id_remito: int,
        id_transportista: int,
        origen: str,
        destino: str,
        salida: str,
        llegada: str | None = None,
        temperatura: float | None = None,
    ) -> TramoEnvio:
        """Registra un tramo de la cadena de custodia.

        El primer tramo despacha el remito y sus muestras (En tránsito). Los
        siguientes exigen que el anterior tenga llegada y salgan después de ella.
        """
        try:
            remito: RemitoBiologico = self._requerir(self.envios.obtener_por_id(id_remito), "el remito")
            transportista: Transportista = self._requerir(
                self.catalogos.obtener_por_id(id_transportista, Transportista), "el transportista"
            )
            if remito.estado not in ("Emitido", "En tránsito"):
                raise ReglaNegocioError(f"El remito {remito.numero} ya fue {remito.estado.lower()}.")

            anteriores = self.envios.listar_tramos_por_remito(id_remito)
            tramo = TramoEnvio(id_remito, transportista.id_transportista, len(anteriores) + 1, origen, destino,
                               salida, llegada, temperatura)
            if anteriores:
                previo = anteriores[-1]
                if previo.fecha_hora_llegada is None:
                    raise ReglaNegocioError(f"El tramo {previo.nro_tramo} todavía no registró su llegada.")
                if tramo.fecha_hora_salida < previo.fecha_hora_llegada:
                    raise ReglaNegocioError("El tramo no puede salir antes de la llegada del tramo anterior.")
            self.envios.agregar(tramo)

            if remito.estado == "Emitido":
                remito.despachar()  # State: Emitido -> En tránsito
                self.envios.modificar(remito)
                for muestra in self.derivaciones.listar_muestras_por_remito(id_remito):
                    muestra.despachar(transportista.nombre, tramo.fecha_hora_salida)  # State
                    self.derivaciones.modificar(muestra)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return tramo

    def registrar_llegada_tramo(self, id_tramo: int, llegada: str, temperatura: float | None = None) -> TramoEnvio:
        """Completa la llegada de un tramo que se registró sin ella."""
        try:
            tramo: TramoEnvio = self._requerir(self.envios.obtener_por_id(id_tramo, TramoEnvio), "el tramo")
            if tramo.finalizado:
                raise ReglaNegocioError(f"El tramo {tramo.nro_tramo} ya tiene registrada la llegada.")
            actualizado = TramoEnvio(tramo.id_remito, tramo.id_transportista, tramo.nro_tramo, tramo.origen,
                                     tramo.destino, tramo.fecha_hora_salida, llegada,
                                     tramo.temperatura if temperatura is None else temperatura, tramo.id_tramo)
            self.envios.modificar(actualizado)
            self.conexion.commit()
        except Exception:
            self.conexion.rollback()
            raise
        return actualizado

    # --- Consultas ---------------------------------------------------------------------

    def listar_remitos(self, estado: str | None = None) -> list[RemitoBiologico]:
        """Todos los remitos (o los de un estado), del más reciente al más antiguo."""
        remitos = self.envios.listar_remitos_por_estado(estado) if estado else self.envios.listar()
        return sorted(remitos, key=lambda r: r.numero, reverse=True)

    def obtener_remito(self, id_remito: int) -> RemitoBiologico:
        return self._requerir(self.envios.obtener_por_id(id_remito), "el remito")

    def obtener_precinto(self, id_remito: int) -> PrecintoSanitario | None:
        return self.envios.obtener_precinto_por_remito(id_remito)

    def tramos_de(self, id_remito: int) -> list[TramoEnvio]:
        return self.envios.listar_tramos_por_remito(id_remito)

    def muestras_de_remito(self, id_remito: int) -> list[Muestra]:
        return self.derivaciones.listar_muestras_por_remito(id_remito)

    def conservadoras_disponibles(self, id_clinica: int | None = None) -> list[Conservadora]:
        return self.envios.listar_conservadoras_disponibles(id_clinica)

    def muestras_pendientes_de_envio(self, id_clinica: int | None = None) -> list[Muestra]:
        """Muestras Extraídas (aún sin empaquetar), opcionalmente solo las atendidas en una clínica."""
        pendientes = []
        for muestra in self.derivaciones.listar_muestras_por_estado("Extraída"):
            if id_clinica is not None:
                orden = self.derivaciones.obtener_por_id(muestra.id_orden)
                if self.atenciones.obtener_por_id(orden.id_atencion).id_clinica != id_clinica:
                    continue
            pendientes.append(muestra)
        return pendientes

    # --- Auxiliares --------------------------------------------------------------------

    def _validar_destino_y_origen(self, ordenes, conservadora: Conservadora) -> None:
        ordenes = list(ordenes)
        laboratorios = {o.id_laboratorio for o in ordenes}
        if len(laboratorios) > 1:
            raise ReglaNegocioError("Todas las muestras de un remito deben ir al mismo laboratorio.")
        for orden in ordenes:
            if orden.estado in ("Anulada", "Finalizada"):
                raise ReglaNegocioError(f"La orden {orden.id_orden} está {orden.estado.lower()}.")
            atencion = self.atenciones.obtener_por_id(orden.id_atencion)
            if atencion.id_clinica != conservadora.id_clinica:
                raise ReglaNegocioError(
                    f"La orden {orden.id_orden} es de otra clínica que la conservadora {conservadora.codigo}."
                )

    def _siguiente_numero_remito(self, anio: str) -> str:
        """Número correlativo por año: REM-AAAA-00001, REM-AAAA-00002..."""
        prefijo = f"REM-{anio}-"
        ultimo = self.envios.ultimo_numero_remito(prefijo)
        siguiente = int(ultimo[len(prefijo):]) + 1 if ultimo else 1
        return f"{prefijo}{siguiente:05d}"
