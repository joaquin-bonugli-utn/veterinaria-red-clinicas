"""Datos de prueba: reinicia veterinaria.db, aplica db/schema.sql y carga datos realistas.

Todo se carga a través de los SERVICIOS (no hay INSERT directos), así cada dato
pasa por las mismas validaciones y reglas de negocio que usa la aplicación.

Uso:  python db/seed.py

Las fechas son relativas al día de ejecución (últimos 3 meses + 2 semanas de
agenda futura) y el azar usa una semilla fija, así el resultado es reproducible.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:  # permite ejecutar "python db/seed.py" desde la raíz
    sys.path.insert(0, str(RAIZ))

from dominio import (  # noqa: E402
    Atencion,
    Clinica,
    Conservadora,
    Especie,
    Laboratorio,
    Mascota,
    Muestra,
    TipoAnalisis,
    TipoAtencion,
    Transportista,
    Vacuna,
    Veterinario,
)
from dominio.excepciones import TurnoSuperpuestoError  # noqa: E402
from persistencia.conexion import RUTA_DB, Conexion  # noqa: E402
from persistencia.repositorios import (  # noqa: E402
    RepositorioDerivaciones,
    RepositorioEnvios,
    RepositorioTurnos,
)
from servicios import (  # noqa: E402
    ServicioAtencion,
    ServicioCatalogos,
    ServicioClientes,
    ServicioDerivacion,
    ServicioEnvios,
    ServicioFacturacion,
    ServicioLaboratorio,
    ServicioMascotas,
    ServicioTurnos,
    ServicioVeterinarios,
    TratamientoIndicado,
    VacunaAAplicar,
)

SEMILLA = 2026

# --- Datos fijos -------------------------------------------------------------------------

CLINICAS = [
    ("Sede Centro", "Av. Colón 1250, Córdoba", "351-4221100"),
    ("Sede Nueva Córdoba", "Bv. Chacabuco 850, Córdoba", "351-4689250"),
    ("Sede Cerro de las Rosas", "Av. Rafael Núñez 4560, Córdoba", "351-4812300"),
]

VETERINARIOS = [  # (matrícula, nombre, apellido, índice de clínica, especialidad)
    ("MP-1021", "Ana", "Pérez", 0, "Clínica general"),
    ("MP-1187", "Martín", "Gutiérrez", 0, "Cirugía"),
    ("MP-1254", "Sofía", "Romero", 1, "Clínica general"),
    ("MP-1302", "Diego", "Fernández", 1, "Dermatología"),
    ("MP-1419", "Valeria", "Castro", 2, "Felinos"),
    ("MP-1533", "Javier", "Molina", 2, "Animales exóticos"),
]

VACUNAS = {  # especie: [(nombre, obligatoria, edad_mínima_días, refuerzo_días, precio)]
    "Perro": [("Séxtuple", True, 45, 365, 9500), ("Antirrábica", True, 90, 365, 7000),
              ("Tos de las perreras", False, 60, 365, 8000)],
    "Gato": [("Triple felina", True, 60, 365, 9000), ("Antirrábica", True, 90, 365, 7000),
             ("Leucemia felina", False, 60, 365, 11000)],
    "Conejo": [("Mixomatosis", True, 60, 180, 8500), ("Enfermedad hemorrágica vírica", True, 60, 365, 9000)],
}

TIPOS_ATENCION = [("Consulta", 15000), ("Control", 11000), ("Urgencia", 26000)]

TIPOS_ANALISIS = [  # (nombre, tipo de muestra, temp mín, temp máx, horas de viabilidad, precio)
    ("Hemograma completo", "Sangre", 2, 8, 24, 18500),
    ("Bioquímica sanguínea", "Sangre", 2, 8, 48, 27000),
    ("Urianálisis", "Orina", 2, 8, 6, 12500),
    ("Coproparasitológico", "Materia fecal", 2, 8, 72, 9800),
]

TRANSPORTISTAS = [
    ("20311222", "Carlos Ruiz", "351-6112233", "Moto Honda CG 150"),
    ("27355444", "Marcela Ortiz", "351-6223344", "Utilitario Fiat Fiorino"),
    ("23288777", "Raúl Benítez", "351-6334455", "Moto Yamaha YBR 125"),
]

CLIENTES = [  # (dni, nombre, apellido, teléfono, email, dirección)
    ("30111222", "Juan", "Gómez", "351-5111001", "juan.gomez@mail.com", "Obispo Trejo 450"),
    ("28456789", "María", "López", "351-5111002", "maria.lopez@mail.com", "Av. Hipólito Yrigoyen 320"),
    ("33222111", "Lucas", "Martínez", "351-5111003", None, "Belgrano 1020"),
    ("35678901", "Camila", "Sánchez", "351-5111004", "cami.sanchez@mail.com", "Rondeau 210"),
    ("26789012", "Roberto", "Díaz", "351-5111005", None, "Av. Recta Martinolli 6100"),
    ("31890123", "Florencia", "Herrera", "351-5111006", "flor.herrera@mail.com", "Lima 880"),
    ("29901234", "Gustavo", "Álvarez", "351-5111007", "galvarez@mail.com", "Av. Fuerza Aérea 2900"),
    ("37012345", "Agustina", "Torres", "351-5111008", None, "Independencia 1450"),
    ("25123456", "Silvia", "Ramírez", "351-5111009", "silvia.ramirez@mail.com", "Av. Laplace 5600"),
    ("34234567", "Federico", "Acosta", "351-5111010", None, "Duarte Quirós 1800"),
    ("32345678", "Paula", "Medina", "351-5111011", "pmedina@mail.com", "Av. Vélez Sarsfield 1200"),
    ("36456789", "Nicolás", "Suárez", "351-5111012", None, "Ituzaingó 640"),
    ("27567890", "Laura", "Ríos", "351-5111013", "laura.rios@mail.com", "Av. Colón 3300"),
    ("38678901", "Tomás", "Navarro", "351-5111014", None, "San Lorenzo 410"),
    ("24789012", "Elena", "Paz", "351-5111015", "elena.paz@mail.com", "Av. Sabattini 2500"),  # sin mascotas
]

MASCOTAS = [  # (nombre, especie, raza, sexo, edad en días, peso kg, índice de cliente)
    ("Firulais", "Perro", "Mestizo", "M", 1850, 18.5, 0),
    ("Luna", "Perro", "Labrador", "H", 1100, 27.0, 0),
    ("Michi", "Gato", "Europeo común", "H", 1460, 4.2, 0),
    ("Rocco", "Perro", "Bulldog francés", "M", 2900, 12.3, 1),
    ("Olivia", "Gato", "Siamés", "H", 3300, 3.8, 1),
    ("Toby", "Perro", "Beagle", "M", 550, 11.0, 2),
    ("Kira", "Perro", "Ovejero alemán", "H", 120, 9.5, 3),
    ("Félix", "Gato", "Mestizo", "M", 730, 4.9, 3),
    ("Max", "Perro", "Golden retriever", "M", 3650, 31.0, 4),
    ("Copito", "Conejo", "Cabeza de león", "M", 365, 1.6, 5),
    ("Nala", "Perro", "Caniche", "H", 730, 5.2, 5),
    ("Garfield", "Gato", "Persa", "M", 2200, 6.1, 6),
    ("Bruno", "Perro", "Boxer", "M", 1460, 29.5, 6),
    ("Mora", "Perro", "Mestizo", "H", 200, 8.0, 7),
    ("Mía", "Gato", "Bengalí", "H", 130, 2.1, 7),
    ("Simón", "Perro", "Dachshund", "M", 2190, 9.0, 8),
    ("Tambor", "Conejo", "Holland lop", "M", 730, 1.9, 8),
    ("Lola", "Perro", "Border collie", "H", 95, 6.5, 9),
    ("Salem", "Gato", "Mestizo", "M", 1100, 5.0, 10),
    ("Thor", "Perro", "Rottweiler", "M", 2550, 42.0, 10),
    ("Canela", "Perro", "Cocker spaniel", "H", 1100, 13.5, 11),
    ("Pelusa", "Gato", "Angora", "H", 4000, 3.5, 12),
    ("Nieve", "Conejo", "Rex", "H", 150, 1.4, 12),
    ("Pancho", "Perro", "Mestizo", "M", 4380, 20.0, 13),
    ("Tom", "Gato", "Europeo común", "M", 365, 4.4, 13),
]

MOTIVOS = {
    "Consulta": ["Decaimiento y falta de apetito", "Vómitos ocasionales", "Diarrea", "Picazón y lesiones en piel",
                 "Tos persistente", "Cojera de miembro posterior", "Otitis", "Pérdida de peso"],
    "Control": ["Control anual", "Control de vacunación", "Control post-tratamiento", "Control de peso",
                "Control geriátrico"],
    "Urgencia": ["Traumatismo por caída", "Intoxicación", "Dificultad respiratoria", "Herida por mordedura",
                 "Convulsiones"],
}
DIAGNOSTICOS = ["Gastroenteritis leve", "Dermatitis alérgica", "Otitis externa", "Sano", "Sobrepeso leve",
                "Traqueobronquitis", "Contusión sin fractura", "Parasitosis intestinal"]
TRATAMIENTOS = [  # (medicamento, dosis, frecuencia, días)
    ("Amoxicilina + ác. clavulánico", "250 mg", "cada 12 h", 7), ("Meloxicam", "0,1 mg/kg", "cada 24 h", 5),
    ("Metronidazol", "250 mg", "cada 12 h", 5), ("Prednisolona", "5 mg", "cada 24 h", 10),
    ("Fenbendazol", "50 mg/kg", "cada 24 h", 3), ("Omeprazol", "1 mg/kg", "cada 24 h", 7),
]
VALORES = {
    "Hemograma completo": "Hto 44 %; Hb 14,8 g/dl; GB 10.200/mm³; Plaquetas 295.000/mm³",
    "Bioquímica sanguínea": "Urea 34 mg/dl; Creatinina 1,2 mg/dl; ALT 58 U/l; Glucemia 96 mg/dl",
    "Urianálisis": "Densidad 1.032; pH 6,5; Proteínas negativo; Sedimento sin particularidades",
    "Coproparasitológico": "Se observan huevos de Toxocara spp.",
}
BIOQUIMICOS = ["Bioq. Laura Méndez", "Bioq. Martín Sosa"]


@dataclass
class Contexto:
    """Lo creado durante la carga, para encadenar pasos y armar el resumen."""

    hoy: date
    rnd: random.Random
    clinicas: list[Clinica] = field(default_factory=list)
    laboratorio: Laboratorio | None = None
    especies: dict[str, Especie] = field(default_factory=dict)
    tipos_atencion: dict[str, TipoAtencion] = field(default_factory=dict)
    tipos_analisis: dict[str, TipoAnalisis] = field(default_factory=dict)
    transportistas: list[Transportista] = field(default_factory=list)
    conservadoras: dict[int, list[Conservadora]] = field(default_factory=dict)  # por id_clinica
    veterinarios: list[Veterinario] = field(default_factory=list)
    mascotas: list[Mascota] = field(default_factory=list)
    atenciones: list[Atencion] = field(default_factory=list)
    turnos_rechazados: int = 0
    ids_destacados: dict[str, int] = field(default_factory=dict)
    comprobantes: int = 0

    def fecha_hora(self, dias_atras: int, hora: str) -> str:
        return f"{(self.hoy - timedelta(days=dias_atras)).isoformat()} {hora}"

    def vets_de(self, indice_clinica: int) -> list[Veterinario]:
        id_clinica = self.clinicas[indice_clinica].id_clinica
        return [v for v in self.veterinarios if v.id_clinica == id_clinica]


# --- Carga por etapas ----------------------------------------------------------------------

def cargar_catalogos(ctx: Contexto) -> None:
    cat = ServicioCatalogos()
    ctx.clinicas = [cat.alta(Clinica(*datos)) for datos in CLINICAS]
    ctx.laboratorio = cat.alta(Laboratorio("Laboratorio Central de Diagnóstico Veterinario",
                                           "Av. Vélez Sarsfield 2100, Córdoba", "351-4689000"))
    for nombre_especie, vacunas in VACUNAS.items():
        especie = cat.alta(Especie(nombre_especie))
        ctx.especies[nombre_especie] = especie
        for nombre, obligatoria, edad, refuerzo, precio in vacunas:
            cat.alta(Vacuna(nombre, especie.id_especie, precio, obligatoria, edad, refuerzo))
    for nombre, precio in TIPOS_ATENCION:
        ctx.tipos_atencion[nombre] = cat.alta(TipoAtencion(nombre, precio))
    for datos in TIPOS_ANALISIS:
        ctx.tipos_analisis[datos[0]] = cat.alta(TipoAnalisis(*datos))
    ctx.transportistas = [cat.alta(Transportista(*datos)) for datos in TRANSPORTISTAS]
    for i, clinica in enumerate(ctx.clinicas, start=1):
        ctx.conservadoras[clinica.id_clinica] = [
            cat.alta(Conservadora(f"CONS-{i}{letra}", clinica.id_clinica, capacidad=6, temp_min=2, temp_max=8))
            for letra in "AB"
        ]
    servicio_vets = ServicioVeterinarios()
    ctx.veterinarios = [
        servicio_vets.alta(mat, nom, ape, ctx.clinicas[i].id_clinica, esp) for mat, nom, ape, i, esp in VETERINARIOS
    ]


def cargar_clientes_y_mascotas(ctx: Contexto) -> None:
    s_clientes, s_mascotas = ServicioClientes(), ServicioMascotas()
    clientes = [s_clientes.alta(*datos) for datos in CLIENTES]
    for nombre, especie, raza, sexo, edad, peso, i_cliente in MASCOTAS:
        nacimiento = ctx.hoy - timedelta(days=edad)
        apertura = max(nacimiento + timedelta(days=7), ctx.hoy - timedelta(days=400))
        ctx.mascotas.append(s_mascotas.alta(
            nombre, ctx.especies[especie].id_especie, nacimiento.isoformat(), clientes[i_cliente].id_cliente,
            raza, sexo, peso, fecha_apertura=apertura.isoformat(),
            alergias="Penicilina" if nombre in ("Rocco", "Pelusa") else None,
        ))
    # La última clienta no tiene mascotas y se da de baja (baja lógica).
    s_clientes.baja(clientes[-1].id_cliente)


def _mascotas_nacidas_antes(ctx: Contexto, fecha: date) -> list[Mascota]:
    return [m for m in ctx.mascotas if date.fromisoformat(m.fecha_nacimiento) + timedelta(days=30) <= fecha]


def _registrar_atencion(ctx: Contexto, mascota: Mascota, vet: Veterinario, tipo: str, fecha_hora: str,
                        id_turno: int | None = None, motivo: str | None = None,
                        diagnostico: str | None = None, con_vacunas: bool = True) -> Atencion:
    """Registra una atención realista: a veces con tratamiento y aplicando las vacunas pendientes."""
    rnd = ctx.rnd
    s_atencion = ServicioAtencion()
    tratamientos = []
    if rnd.random() < 0.35:
        med, dosis, frecuencia, dias = rnd.choice(TRATAMIENTOS)
        fin = (date.fromisoformat(fecha_hora[:10]) + timedelta(days=dias)).isoformat()
        tratamientos.append(TratamientoIndicado(med, dosis, frecuencia, fecha_fin=fin))
    vacunas = []
    if con_vacunas and rnd.random() < 0.75:
        pendientes = s_atencion.vacunas_pendientes(mascota.id_mascota, fecha_hora[:10])
        vacunas = [VacunaAAplicar(p.vacuna.id_vacuna, f"L{rnd.randint(10000, 99999)}") for p in pendientes]
    peso = round(mascota.peso_kg * rnd.uniform(0.97, 1.03), 1) if mascota.peso_kg and rnd.random() < 0.6 else None
    resultado = s_atencion.registrar(
        mascota.id_mascota, vet.id_veterinario, ctx.tipos_atencion[tipo].id_tipo_atencion, fecha_hora,
        motivo or rnd.choice(MOTIVOS[tipo]), id_turno=id_turno,
        diagnostico=diagnostico or rnd.choice(DIAGNOSTICOS), peso_kg=peso,
        tratamientos=tratamientos, vacunas=vacunas,
    )
    if peso is not None:
        mascota.peso_kg = peso
    ctx.atenciones.append(resultado.atencion)
    return resultado.atencion


def cargar_turnos_y_atenciones(ctx: Contexto) -> None:
    """Agenda de los últimos 3 meses (atendidos, cancelados, ausentes) + 2 semanas futuras."""
    rnd, s_turnos = ctx.rnd, ServicioTurnos()
    reservados = []
    for desplazamiento in range(-91, 15):
        dia = ctx.hoy + timedelta(days=desplazamiento)
        if dia.weekday() >= 5:  # solo lunes a viernes
            continue
        candidatas = _mascotas_nacidas_antes(ctx, dia)
        for _ in range(rnd.choice([0, 1, 1, 2])):
            vet = rnd.choice(ctx.veterinarios)
            hora, minuto = rnd.randint(9, 17), rnd.choice([0, 30])
            inicio = f"{dia.isoformat()} {hora:02d}:{minuto:02d}"
            fin = f"{dia.isoformat()} {hora + (minuto + 30) // 60:02d}:{(minuto + 30) % 60:02d}"
            try:
                reservados.append(s_turnos.reservar(vet.id_veterinario, rnd.choice(candidatas).id_mascota,
                                                    inicio, fin))
            except TurnoSuperpuestoError:
                ctx.turnos_rechazados += 1  # la regla de no superposición en acción

    # Intentos deliberados de doble reserva sobre turnos ya tomados: el servicio los rechaza.
    for turno in reservados[::20]:
        try:
            s_turnos.reservar(turno.id_veterinario, turno.id_mascota, turno.fecha_hora_inicio, turno.fecha_hora_fin)
        except TurnoSuperpuestoError:
            ctx.turnos_rechazados += 1

    vets = {v.id_veterinario: v for v in ctx.veterinarios}
    mascotas = {m.id_mascota: m for m in ctx.mascotas}
    for i, turno in enumerate(sorted(reservados, key=lambda t: t.fecha_hora_inicio)):
        if turno.fecha_hora_inicio[:10] >= ctx.hoy.isoformat():
            if i % 6 == 0:
                s_turnos.cancelar(turno.id_turno)
            continue
        # Reparto fijo (no aleatorio) para que siempre haya cancelados y ausentes en los reportes.
        if i % 11 == 3:
            s_turnos.cancelar(turno.id_turno)
        elif i % 13 == 5:
            s_turnos.marcar_ausente(turno.id_turno)
        else:
            tipo = "Consulta" if rnd.random() < 0.6 else "Control"
            _registrar_atencion(ctx, mascotas[turno.id_mascota], vets[turno.id_veterinario], tipo,
                                turno.fecha_hora_inicio, id_turno=turno.id_turno)

    # Urgencias nocturnas sin turno.
    for _ in range(8):
        dias_atras = rnd.randint(1, 90)
        candidatas = _mascotas_nacidas_antes(ctx, ctx.hoy - timedelta(days=dias_atras))
        _registrar_atencion(ctx, rnd.choice(candidatas), rnd.choice(ctx.veterinarios), "Urgencia",
                            ctx.fecha_hora(dias_atras, f"{rnd.randint(20, 22)}:{rnd.choice(['00', '30'])}"),
                            con_vacunas=False)


def cargar_derivaciones(ctx: Contexto) -> dict[str, int]:
    """10 órdenes y 5 remitos que recorren todos los caminos del patrón State.

    R1 completo y analizado · R2 precinto roto · R3 una muestra con viabilidad vencida ·
    R4 recibido con resultados parciales · R5 en tránsito · órdenes 9 y 10 sin empaquetar.
    """
    s_der, s_env, s_lab = ServicioDerivacion(), ServicioEnvios(), ServicioLaboratorio()
    ta = ctx.tipos_analisis
    hemo, bioq, uri, copro = (ta["Hemograma completo"], ta["Bioquímica sanguínea"], ta["Urianálisis"],
                              ta["Coproparasitológico"])
    pacientes = iter([m for m in ctx.mascotas if m.nombre in (
        "Firulais", "Rocco", "Max", "Bruno", "Garfield", "Simón", "Thor", "Pancho", "Olivia", "Canela")])

    def orden(i_clinica: int, dias_atras: int, hora: str, tipos: list[TipoAnalisis]):
        vet = ctx.vets_de(i_clinica)[0]
        atencion = _registrar_atencion(ctx, next(pacientes), vet, "Consulta", ctx.fecha_hora(dias_atras, hora),
                                       diagnostico="Pendiente de resultados de laboratorio", con_vacunas=False)
        return s_der.emitir_orden(atencion.id_atencion, ctx.laboratorio.id_laboratorio,
                                  [(t.id_tipo_analisis, 3.0 if t.tipo_muestra == "Sangre" else 10.0) for t in tipos],
                                  indicaciones="Ayuno de 8 h" if bioq in tipos else None)

    remitos_creados = []

    def remito(i_clinica: int, ordenes, dias_atras: int, empaque: str, precinto: str, tramos):
        clinica = ctx.clinicas[i_clinica]
        rotacion = len(remitos_creados) + 1  # cada remito arranca con otro transportista
        muestras = [m.id_muestra for o in ordenes for m in o.muestras]
        rem = s_env.empaquetar(muestras, ctx.conservadoras[clinica.id_clinica][0].id_conservadora, precinto,
                               4.5, fecha_hora=ctx.fecha_hora(dias_atras, empaque))
        origenes = [clinica.nombre, "Centro logístico Córdoba", ctx.laboratorio.nombre]
        for n, (salida, llegada, temperatura) in enumerate(tramos):
            transportista = ctx.transportistas[(n + rotacion) % len(ctx.transportistas)]
            s_env.registrar_tramo(rem.id_remito, transportista.id_transportista,
                                  origenes[n], origenes[n + 1], ctx.fecha_hora(dias_atras, salida),
                                  ctx.fecha_hora(dias_atras, llegada) if llegada else None, temperatura)
        remitos_creados.append(rem)
        return rem

    def resultados(muestras, dias_atras: int, hora: str) -> None:
        nombres = {t.id_tipo_analisis: t.nombre for t in ta.values()}
        for m in muestras:
            s_lab.registrar_resultado(m.id_muestra, ctx.rnd.choice(BIOQUIMICOS), VALORES[nombres[m.id_tipo_analisis]],
                                      ctx.rnd.choice(["Dentro de parámetros normales",
                                                      "Leve alteración; repetir en 30 días"]),
                                      fecha_hora=ctx.fecha_hora(dias_atras, hora))

    # R1 (Sede Centro, hace 45 días): todo el circuito y todos los resultados.
    o1, o2 = orden(0, 45, "08:30", [hemo, bioq]), orden(0, 45, "09:15", [uri])
    r1 = remito(0, [o1, o2], 45, "10:00", "PS-000101",
                [("10:30", "11:15", 5.0), ("11:45", "12:30", 5.5)])
    s_lab.recibir(r1.id_remito, "Téc. Andrea Vega", True, 5.2, fecha_hora=ctx.fecha_hora(45, "13:00"))
    resultados(o1.muestras + o2.muestras, 44, "09:00")

    # R2 (Sede Nueva Córdoba, hace 30 días): llega con el precinto roto.
    o3, o4 = orden(1, 30, "09:00", [hemo]), orden(1, 30, "09:40", [bioq, copro])
    r2 = remito(1, [o3, o4], 30, "10:30", "PS-000102",
                [("11:00", "12:00", 5.0), ("12:30", "13:30", 6.0)])
    s_lab.recibir(r2.id_remito, "Téc. Andrea Vega", False, 6.1, fecha_hora=ctx.fecha_hora(30, "14:00"),
                  observaciones="Precinto violentado al momento de la recepción")

    # R3 (Sede Cerro, hace 18 días): demora en el envío; el urianálisis (6 h) llega vencido.
    o5, o6 = orden(2, 18, "08:00", [uri]), orden(2, 18, "08:45", [hemo])
    r3 = remito(2, [o5, o6], 18, "09:30", "PS-000103",
                [("10:00", "11:30", 5.0), ("12:30", "15:00", 6.5)])
    s_lab.recibir(r3.id_remito, "Téc. Pablo Luna", True, 6.0, fecha_hora=ctx.fecha_hora(18, "15:30"))
    resultados(o6.muestras, 17, "10:00")

    # R4 (Sede Centro, hace 6 días): recibido, solo el hemograma tiene resultado.
    o7 = orden(0, 6, "10:00", [hemo, bioq, uri])
    r4 = remito(0, [o7], 6, "10:45", "PS-000104", [("11:15", "12:00", 4.8), ("12:20", "13:00", 5.0)])
    s_lab.recibir(r4.id_remito, "Téc. Pablo Luna", True, 4.9, fecha_hora=ctx.fecha_hora(6, "13:30"))
    resultados(o7.muestras[:1], 5, "09:30")

    # R5 (Sede Nueva Córdoba, ayer): en tránsito, el segundo tramo todavía no llegó.
    o8 = orden(1, 1, "16:00", [hemo, copro])
    remito(1, [o8], 1, "16:30", "PS-000105", [("17:00", "17:40", 5.0), ("18:00", None, None)])

    # Órdenes 9 y 10: muestras extraídas, todavía sin empaquetar.
    orden(2, 1, "11:00", [bioq])
    orden(0, 0, "09:00", [hemo, uri])
    return {"remito_precinto_roto": r2.id_remito, "remito_viabilidad_vencida": r3.id_remito}


def cargar_comprobantes(ctx: Contexto) -> int:
    """Factura las atenciones en orden cronológico (numeración correlativa), salvo las de los
    últimos 2 días y algunas al azar, que quedan pendientes de facturar."""
    s_fact = ServicioFacturacion()
    limite = (ctx.hoy - timedelta(days=2)).isoformat()
    emitidos = 0
    for atencion in sorted(ctx.atenciones, key=lambda a: a.fecha_hora):
        if atencion.fecha_hora[:10] > limite or ctx.rnd.random() < 0.1:
            continue
        s_fact.emitir_comprobante(atencion.id_atencion, atencion.fecha_hora[:10])
        emitidos += 1
    return emitidos


def cargar_datos(hoy: date | None = None, semilla: int = SEMILLA) -> Contexto:
    """Carga todos los datos sobre la conexión Singleton vigente (con el esquema ya aplicado)."""
    ctx = Contexto(hoy or date.today(), random.Random(semilla))
    cargar_catalogos(ctx)
    cargar_clientes_y_mascotas(ctx)
    cargar_turnos_y_atenciones(ctx)
    ctx.ids_destacados = cargar_derivaciones(ctx)
    ctx.comprobantes = cargar_comprobantes(ctx)
    return ctx


# --- Ejecución -------------------------------------------------------------------------------

def _contar_por(valores) -> str:
    conteo: dict[str, int] = {}
    for valor in valores:
        conteo[valor] = conteo.get(valor, 0) + 1
    return ", ".join(f"{k}: {n}" for k, n in sorted(conteo.items()))


def imprimir_resumen(conexion: Conexion, ctx: Contexto) -> None:
    cantidades = conexion.cantidades_por_tabla()
    ancho = max(map(len, cantidades))
    print(f"\n{'Tabla':<{ancho}}  Filas")
    print(f"{'-' * ancho}  -----")
    for tabla, n in cantidades.items():
        print(f"{tabla:<{ancho}}  {n:>5}")
    print(f"{'-' * ancho}  -----")
    print(f"{'TOTAL':<{ancho}}  {sum(cantidades.values()):>5}")

    der, env = RepositorioDerivaciones(), RepositorioEnvios()
    desde, hasta = (ctx.hoy - timedelta(days=91)).isoformat(), (ctx.hoy + timedelta(days=15)).isoformat()
    print("\nDetalle por estado")
    print("  Turnos:   ", _contar_por(t.estado for t in RepositorioTurnos().listar_por_rango(desde, hasta)))
    print("  Órdenes:  ", _contar_por(o.estado for o in der.listar()))
    print("  Remitos:  ", _contar_por(r.estado for r in env.listar()))
    print("  Muestras: ", _contar_por(m.estado_actual for m in der.listar(Muestra)))
    print(f"  Reservas rechazadas por superposición de turnos: {ctx.turnos_rechazados}")

    print("\nCasos destacados")
    for clave, titulo in (("remito_precinto_roto", "Precinto roto"),
                          ("remito_viabilidad_vencida", "Viabilidad vencida")):
        remito = env.obtener_por_id(ctx.ids_destacados[clave])
        print(f"  {titulo}: remito {remito.numero} ({remito.estado})")
        for muestra in der.listar_muestras_por_remito(remito.id_remito):
            print(f"    - {muestra.codigo}: {muestra.estado_actual}"
                  + (f" · {muestra.ultimo_cambio.observacion}" if muestra.estado_actual == "Rechazada" else ""))


def main() -> None:
    for sufijo in ("", "-journal", "-wal", "-shm"):
        Path(f"{RUTA_DB}{sufijo}").unlink(missing_ok=True)
    conexion = Conexion.obtener(str(RUTA_DB))
    conexion.inicializar_esquema()
    print(f"Base reiniciada: {RUTA_DB}")
    ctx = cargar_datos()
    imprimir_resumen(conexion, ctx)
    conexion.cerrar()


if __name__ == "__main__":
    main()
