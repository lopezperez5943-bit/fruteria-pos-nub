from fastapi import FastAPI
from sqlalchemy import create_engine, text
from pydantic import BaseModel

# --- 1. CONFIGURACIÓN DE LA BASE DE DATOS ---
# IMPORTANTE: Cambia TU_CONTRASEÑA por la contraseña real de postgres
URL_BASE_DATOS = "postgresql://postgres:Chevrolets10@localhost:5432/fruteria_db"

engine = create_engine(
    URL_BASE_DATOS, 
    connect_args={'client_encoding': 'utf8'} # Protegido contra acentos y eñes
)
app = FastAPI(title="API Inventario y Finanzas - Frutería")

# --- 2. MODELOS DE DATOS ---
class ProductoNuevo(BaseModel):
    nombre: str
    unidad_medida: str = "Kilogramos" # O "Piezas"

class LoteNuevo(BaseModel):
    id_producto: int
    cantidad_inicial: float
    costo_compra_total: float
    precio_venta_sugerido: float

class VentaNueva(BaseModel):
    id_lote: int
    cantidad_vendida: float
    precio_final_unidad: float
    tipo_venta: str = "Menudeo"
    metodo_pago: str = "Efectivo"
    id_cliente: int = 1 # <-- ¡NUEVO CAMPO PARA SABER QUIÉN COMPRA!

class ClienteNuevo(BaseModel):
    nombre: str
    telefono: str = ""

class Abono(BaseModel):
    id_cliente: int
    monto: float

class GastoNuevo(BaseModel):
    categoria: str # Ej. "Flete", "Bolsas", "Sueldos", "Luz"
    monto: float
    descripcion: str = ""

class MermaNueva(BaseModel):
    id_lote: int
    cantidad_mermada: float
    motivo: str = "Podrido / Dañado"

class LoginUsuario(BaseModel):
    nombre_usuario: str
    pin_acceso: str

class UsuarioNuevo(BaseModel):
    nombre_usuario: str
    pin_acceso: str
    rol: str = "Cajero" # Puede ser "Admin" o "Cajero"

# --- 3. RUTAS / ENDPOINTS DEL SISTEMA ---

@app.get("/")
def probar_conexion():
    return {"Estado": "¡Éxito! Motor de la frutería operando al 100%."}

# A) CATÁLOGO DE PRODUCTOS
@app.post("/productos/")
def agregar_producto(producto: ProductoNuevo):
    try:
        with engine.connect() as conexion:
            query = text("INSERT INTO productos (nombre, unidad_medida) VALUES (:nombre, :unidad) RETURNING id_producto")
            res = conexion.execute(query, {"nombre": producto.nombre, "unidad": producto.unidad_medida})
            conexion.commit() 
            return {"mensaje": "¡Fruta agregada!", "id_producto": res.fetchone()[0], "producto": producto.nombre}
    except Exception as e:
        return {"Error": "No se pudo guardar", "Detalle": str(e)}

@app.get("/productos/")
def ver_productos():
    try:
        with engine.connect() as conexion:
            res = conexion.execute(text("SELECT id_producto, nombre, unidad_medida FROM productos"))
            return [{"id": fila[0], "nombre": fila[1], "unidad": fila[2]} for fila in res.fetchall()]
    except Exception as e:
        return {"Error": str(e)}

# B) COMPRAS / ENTRADA DE MERCANCÍA
@app.post("/lotes/")
def registrar_lote(lote: LoteNuevo):
    try:
        with engine.connect() as conexion:
            query = text("""
                INSERT INTO lotes_entrada 
                (id_producto, cantidad_inicial, cantidad_actual, costo_compra_total, precio_venta_sugerido) 
                VALUES (:id_prod, :cant, :cant, :costo, :precio)
                RETURNING id_lote
            """)
            res = conexion.execute(query, {
                "id_prod": lote.id_producto, "cant": lote.cantidad_inicial, 
                "costo": lote.costo_compra_total, "precio": lote.precio_venta_sugerido
            })
            conexion.commit()
            return {"mensaje": "¡Mercancía registrada con éxito!", "id_lote": res.fetchone()[0]}
    except Exception as e:
        return {"Error": "No se pudo guardar", "Detalle": str(e)}

# C) VENTAS Y SALIDAS CON CORTE Y CRÉDITO
@app.post("/ventas/")
def registrar_venta(venta: VentaNueva):
    try:
        with engine.connect() as conexion:
            total_ticket = float(venta.cantidad_vendida) * float(venta.precio_final_unidad)
            
            # Guardamos la venta en el historial
            query_venta = text("""
                INSERT INTO ventas (id_lote, cantidad_vendida, precio_final_unidad, tipo_venta, metodo_pago, id_cliente)
                VALUES (:lote, :cant, :precio, :tipo, :pago, :cli) RETURNING id_venta
            """)
            res = conexion.execute(query_venta, {
                "lote": venta.id_lote, "cant": venta.cantidad_vendida, "precio": venta.precio_final_unidad, 
                "tipo": venta.tipo_venta, "pago": venta.metodo_pago, "cli": venta.id_cliente
            })
            id_ticket = res.fetchone()[0]
            
            # Descontamos existencias del inventario
            conexion.execute(text("UPDATE lotes_entrada SET cantidad_actual = cantidad_actual - :cant WHERE id_lote = :lote"), 
                             {"cant": venta.cantidad_vendida, "lote": venta.id_lote})
            
            # ¡LÓGICA DE CRÉDITO! Si el método es fiado, le sumamos la deuda al cliente
            if venta.metodo_pago == "Crédito (Fiado)":
                conexion.execute(text("UPDATE clientes SET deuda_actual = deuda_actual + :deuda WHERE id_cliente = :cli"),
                                 {"deuda": total_ticket, "cli": venta.id_cliente})
                
            conexion.commit()
            
        return {"mensaje": "¡Venta registrada!", "ticket": id_ticket, "total_cobrado": total_ticket}
    except Exception as e:
        return {"Error": "No se pudo registrar la venta", "Detalle": str(e)}

# ¡NUEVA RUTA! CORTE DE CAJA DEL DÍA
@app.get("/corte_caja/")
def corte_de_caja():
    try:
        with engine.connect() as conexion:
            # Sumamos el dinero agrupándolo por método de pago
            query = text("""
                SELECT metodo_pago, COALESCE(SUM(cantidad_vendida * precio_final_unidad), 0) AS total, COUNT(*) AS tickets
                FROM ventas
                GROUP BY metodo_pago
            """)
            res = conexion.execute(query).fetchall()
            
            corte = {"Efectivo": 0.0, "Tarjeta": 0.0, "Transferencia": 0.0, "Total_General": 0.0, "Tickets_Totales": 0}
            for fila in res:
                metodo = fila[0] if fila[0] in corte else "Efectivo"
                total_metodo = float(fila[1])
                tickets = int(fila[2])
                corte[metodo] = total_metodo
                corte["Total_General"] += total_metodo
                corte["Tickets_Totales"] += tickets
                
        return corte
    except Exception as e:
        return {"Error": "No se pudo generar el corte", "Detalle": str(e)}

# D) INVENTARIO EN TIEMPO REAL CON SEMÁFORO DE FRESCURA
@app.get("/inventario/")
def ver_inventario():
    try:
        with engine.connect() as conexion:
            # Pedimos a PostgreSQL que nos calcule exactamente cuántos días han pasado desde que llegó el lote
            query = text("""
                SELECT l.id_lote, p.nombre, l.cantidad_actual, p.unidad_medida, l.precio_venta_sugerido,
                       COALESCE(EXTRACT(DAY FROM CURRENT_TIMESTAMP - l.fecha_lote), 0) AS dias
                FROM lotes_entrada l
                JOIN productos p ON l.id_producto = p.id_producto
                WHERE l.cantidad_actual > 0
                ORDER BY l.fecha_lote ASC
            """)
            res = conexion.execute(query).fetchall()
            
            inventario = []
            for f in res:
                dias = int(f[5])
                # LÓGICA DEL SEMÁFORO
                if dias <= 2:
                    semaforo = f"🟢 Fresco ({dias} días)"
                elif dias <= 4:
                    semaforo = f"🟡 Atención ({dias} días) - Sugerido: Rebaja 15%"
                else:
                    semaforo = f"🔴 Crítico ({dias} días) - ¡Mandar a Remate!"
                    
                inventario.append({
                    "lote_id": f[0],
                    "producto": f[1],
                    "disponible": f[2],
                    "medida": f[3],
                    "precio_sugerido": f[4],
                    "dias_almacen": dias,
                    "semaforo": semaforo
                })
        return inventario
    except Exception as e:
        return {"Error": "No se pudo cargar el inventario", "Detalle": str(e)}

# E) GASTOS OPERATIVOS (¡El que nos faltaba!)
# REGISTRAR GASTO OPERATIVO
@app.post("/gastos/")
def registrar_gasto(gasto: GastoNuevo):
    try:
        with engine.connect() as conexion:
            query = text("""
                INSERT INTO gastos (categoria, monto, descripcion)
                VALUES (:cat, :monto, :desc) RETURNING id_gasto
            """)
            res = conexion.execute(query, {
                "cat": gasto.categoria, 
                "monto": float(gasto.monto), 
                "desc": gasto.descripcion
            })
            id_g = res.fetchone()[0]
            conexion.commit()
        return {"mensaje": "Gasto guardado con éxito", "id_gasto": id_g}
    except Exception as e:
        return {"Error": "No se pudo guardar el gasto", "Detalle": str(e)}

# F) REPORTE FINANCIERO CON FILTROS DE TIEMPO
@app.get("/finanzas/")
def calcular_finanzas(periodo: str = "Historico"):
    try:
        with engine.connect() as conexion:
            # Configuración del filtro de fecha según el periodo seleccionado
            if periodo == "Hoy":
                filtro_tiempo = "WHERE fecha_venta >= CURRENT_DATE"
                filtro_tiempo_m = "WHERE fecha_merma >= CURRENT_DATE"
                filtro_tiempo_g = "WHERE fecha_gasto >= CURRENT_DATE"
            elif periodo == "Semana":
                filtro_tiempo = "WHERE fecha_venta >= CURRENT_DATE - INTERVAL '7 days'"
                filtro_tiempo_m = "WHERE fecha_merma >= CURRENT_DATE - INTERVAL '7 days'"
                filtro_tiempo_g = "WHERE fecha_gasto >= CURRENT_DATE - INTERVAL '7 days'"
            elif periodo == "Mes":
                filtro_tiempo = "WHERE fecha_venta >= CURRENT_DATE - INTERVAL '30 days'"
                filtro_tiempo_m = "WHERE fecha_merma >= CURRENT_DATE - INTERVAL '30 days'"
                filtro_tiempo_g = "WHERE fecha_gasto >= CURRENT_DATE - INTERVAL '30 days'"
            else:
                # Histórico (Todo el tiempo)
                filtro_tiempo = ""
                filtro_tiempo_m = ""
                filtro_tiempo_g = ""

            # 1. Ingresos por Ventas en el periodo
            query_ingresos = text(f"SELECT COALESCE(SUM(cantidad_vendida * precio_final_unidad), 0) FROM ventas {filtro_tiempo}")
            ingresos_totales = conexion.execute(query_ingresos).scalar()

            # 2. Inversión en mercancía (Costo de lo que realmente se vendió)
            query_inversion = text(f"""
                SELECT COALESCE(SUM(v.cantidad_vendida * (l.costo_compra_total / l.cantidad_inicial)), 0)
                FROM ventas v
                JOIN lotes_entrada l ON v.id_lote = l.id_lote
                {filtro_tiempo}
            """)
            inversion_vendida = conexion.execute(query_inversion).scalar()

            # 3. Mermas del periodo (Pérdidas)
            query_mermas = text(f"SELECT COALESCE(SUM(costo_predido if 'costo_perdido' in table else costo_perdido), 0) FROM mermas {filtro_tiempo_m}")
            # Corrección de typo común en bases de datos locales:
            try:
                mermas_totales = conexion.execute(text(f"SELECT COALESCE(SUM(costo_perdido), 0) FROM mermas {filtro_tiempo_m}")).scalar()
            except:
                mermas_totales = conexion.execute(text(f"SELECT COALESCE(SUM(costo_predido), 0) FROM mermas {filtro_tiempo_m}")).scalar()

            # 4. Gastos Operativos (Fletes, Luz, Sueldos)
            query_gastos = text(f"SELECT COALESCE(SUM(monto), 0) FROM gastos {filtro_tiempo_g}")
            gastos_operativos = conexion.execute(query_gastos).scalar()

            # CÁLCULO DE LA GANANCIA NETA REAL
            # Ingresos - Costo de Mercancía - Pérdidas por Merma - Gastos Fijos
            ganancia_neta = float(ingresos_totales) - float(inversion_vendida) - float(mermas_totales) - float(gastos_operativos)

        return {
            "periodo_seleccionado": periodo,
            "1_ingresos_totales_ventas": round(float(ingresos_totales), 2),
            "2_inversion_en_mercancia": round(float(inversion_vendida), 2),
            "3_perdidas_por_merma": round(float(mermas_totales), 2),
            "4_gastos_operativos": round(float(gastos_operativos), 2),
            "5_ganancia_neta_real": round(ganancia_neta, 2)
        }
    except Exception as e:
        return {"Error": "No se pudo calcular el reporte financiero", "Detalle": str(e)}
    
# G) CONTROL DE MERMAS Y PÉRDIDAS
@app.post("/mermas/")
def registrar_merma(merma: MermaNueva):
    try:
        with engine.connect() as conexion:
            query_costo = text("SELECT costo_compra_total / cantidad_inicial FROM lotes_entrada WHERE id_lote = :lote")
            costo_por_kilo = conexion.execute(query_costo, {"lote": merma.id_lote}).scalar()
            
            # --- ¡AQUÍ ESTÁ LA CORRECCIÓN! ---
            # Envolvemos costo_por_kilo con float() para que Python pueda multiplicarlo sin error
            dinero_perdido = float(merma.cantidad_mermada) * float(costo_por_kilo)
            # ---------------------------------
            
            query_merma = text("""
                INSERT INTO mermas (id_lote, cantidad_mermada, motivo, costo_perdido)
                VALUES (:lote, :cant, :motivo, :perdido) RETURNING id_merma
            """)
            res = conexion.execute(query_merma, {
                "lote": merma.id_lote, "cant": merma.cantidad_mermada, "motivo": merma.motivo, "perdido": dinero_perdido
            })
            id_m = res.fetchone()[0]
            
            # Descontamos la fruta podrida del stock
            conexion.execute(text("UPDATE lotes_entrada SET cantidad_actual = cantidad_actual - :cant WHERE id_lote = :lote"), 
                             {"cant": merma.cantidad_mermada, "lote": merma.id_lote})
            conexion.commit()
            
        return {
            "mensaje": "¡Merma registrada y descontada del inventario!",
            "id_merma": id_m, "kilos_descontados": merma.cantidad_mermada, "dinero_perdido_estimado": round(dinero_perdido, 2)
        }
    except Exception as e:
        return {"Error": "No se pudo registrar la merma", "Detalle": str(e)}
    
    # H) CLIENTES MAYORISTAS Y CUENTAS POR COBRAR
@app.post("/clientes/")
def crear_cliente(cliente: ClienteNuevo):
    try:
        with engine.connect() as conexion:
            conexion.execute(text("INSERT INTO clientes (nombre, telefono) VALUES (:nom, :tel)"), 
                             {"nom": cliente.nombre, "tel": cliente.telefono})
            conexion.commit()
        return {"mensaje": f"¡Cliente {cliente.nombre} registrado con éxito!"}
    except Exception as e:
        return {"Error": "No se pudo crear el cliente (¿quizás ya existe ese nombre?)", "Detalle": str(e)}

@app.get("/clientes/")
def ver_clientes():
    with engine.connect() as conexion:
        res = conexion.execute(text("SELECT id_cliente, nombre, telefono, deuda_actual FROM clientes ORDER BY id_cliente ASC")).fetchall()
        return [{"id": f[0], "nombre": f[1], "telefono": f[2], "deuda": float(f[3])} for f in res]

@app.post("/abonos/")
def registrar_abono(abono: Abono):
    try:
        with engine.connect() as conexion:
            # Restamos el dinero que nos está pagando de su deuda total
            conexion.execute(text("UPDATE clientes SET deuda_actual = deuda_actual - :monto WHERE id_cliente = :cli"),
                             {"monto": abono.monto, "cli": abono.id_cliente})
            conexion.commit()
        return {"mensaje": "¡Abono registrado y descontado de la deuda!"}
    except Exception as e:
        return {"Error": "No se pudo registrar el abono", "Detalle": str(e)}

@app.delete("/clientes/{id_cliente}")
def eliminar_cliente(id_cliente: int):
    try:
        # El cliente #1 (Mostrador) es sagrado y protegido, nunca se debe borrar
        if id_cliente == 1:
            return {"Error": "No se puede eliminar el cliente por defecto del mostrador."}
            
        with engine.connect() as conexion:
            # Primero verificamos si el cliente tiene alguna deuda pendiente antes de borrarlo
            query_deuda = text("SELECT deuda_actual FROM clientes WHERE id_cliente = :id")
            deuda = conexion.execute(query_deuda, {"id": id_cliente}).scalar()
            
            if deuda and float(deuda) > 0:
                return {"Error": f"No puedes eliminar a este cliente porque todavía te debe ${float(deuda):,.2f} pesos."}
            
            # Si su saldo es 0, procedemos a borrarlo con seguridad
            conexion.execute(text("DELETE FROM clientes WHERE id_cliente = :id"), {"id": id_cliente})
            conexion.commit()
            
        return {"mensaje": "Cliente eliminado correctamente del sistema."}
    except Exception as e:
        return {"Error": "No se pudo eliminar el cliente", "Detalle": str(e)}
    
# I) ELIMINAR LOTES ERÓNEOS DEL INVENTARIO
@app.delete("/lotes/{id_lote}")
def eliminar_lote(id_lote: int):
    try:
        with engine.connect() as conexion:
            # 1. Verificamos si este lote ya tiene ventas registradas
            query_ventas = text("SELECT COUNT(*) FROM ventas WHERE id_lote = :id")
            tiene_ventas = conexion.execute(query_ventas, {"id": id_lote}).scalar()
            
            if tiene_ventas > 0:
                return {"Error": "No se puede eliminar este lote porque ya tiene ventas registradas. Si la mercancía se echó a perder, regístrala como Merma."}
            
            # 2. Verificamos si tiene mermas registradas
            query_mermas = text("SELECT COUNT(*) FROM mermas WHERE id_lote = :id")
            tiene_mermas = conexion.execute(query_mermas, {"id": id_lote}).scalar()
            
            if tiene_mermas > 0:
                # Si solo tiene mermas erróneas, limpiamos primero las mermas de ese lote
                conexion.execute(text("DELETE FROM mermas WHERE id_lote = :id"), {"id": id_lote})

            # 3. Eliminamos el lote del almacén
            conexion.execute(text("DELETE FROM lotes_entrada WHERE id_lote = :id"), {"id": id_lote})
            conexion.commit()
            
        return {"mensaje": f"Lote #{id_lote} eliminado correctamente del inventario."}
    except Exception as e:
        return {"Error": "No se pudo eliminar el lote", "Detalle": str(e)}

# J) SEGURIDAD Y CONTROL DE ACCESO (LOGIN)
@app.post("/login/")
def verificar_login(datos: LoginUsuario):
    try:
        with engine.connect() as conexion:
            query = text("SELECT rol FROM usuarios WHERE nombre_usuario = :nom AND pin_acceso = :pin")
            res = conexion.execute(query, {"nom": datos.nombre_usuario, "pin": datos.pin_acceso}).fetchone()
            
            if res:
                return {"exito": True, "rol": res[0], "mensaje": f"¡Bienvenido, {datos.nombre_usuario}!"}
            else:
                return {"exito": False, "Error": "Usuario o PIN incorrectos. Acceso denegado."}
    except Exception as e:
        return {"exito": False, "Error": "No se pudo conectar con el servidor de seguridad", "Detalle": str(e)}

# K) GESTIÓN DE PERSONAL Y USUARIOS
@app.post("/usuarios/")
def crear_usuario(usuario: UsuarioNuevo):
    try:
        with engine.connect() as conexion:
            conexion.execute(text("INSERT INTO usuarios (nombre_usuario, pin_acceso, rol) VALUES (:nom, :pin, :rol)"), 
                             {"nom": usuario.nombre_usuario, "pin": usuario.pin_acceso, "rol": usuario.rol})
            conexion.commit()
        return {"mensaje": f"¡Usuario '{usuario.nombre_usuario}' creado con éxito como {usuario.rol}!"}
    except Exception as e:
        return {"Error": "No se pudo crear el usuario (¿quizás ese nombre ya existe?)", "Detalle": str(e)}

@app.get("/usuarios/")
def ver_usuarios():
    with engine.connect() as conexion:
        res = conexion.execute(text("SELECT id_usuario, nombre_usuario, rol FROM usuarios ORDER BY id_usuario ASC")).fetchall()
        # Por seguridad cibernética, enviamos el ID y el nombre, pero JAMÁS enviamos los PINs de regreso a la pantalla
        return [{"id": f[0], "usuario": f[1], "rol": f[2]} for f in res]

@app.delete("/usuarios/{id_usuario}")
def eliminar_usuario(id_usuario: int):
    try:
        with engine.connect() as conexion:
            # Primero verificamos quién es el usuario que intentan borrar
            nom = conexion.execute(text("SELECT nombre_usuario FROM usuarios WHERE id_usuario = :id"), {"id": id_usuario}).scalar()
            
            # ¡ESCUDO DE SEGURIDAD! Protegemos al admin principal para no bloquear la tienda
            if nom == 'admin' or id_usuario == 1:
                return {"Error": "Por seguridad, no puedes eliminar la cuenta principal de Administrador."}
                
            conexion.execute(text("DELETE FROM usuarios WHERE id_usuario = :id"), {"id": id_usuario})
            conexion.commit()
        return {"mensaje": "Usuario eliminado y dado de baja del sistema correctamente."}
    except Exception as e:
        return {"Error": "No se pudo eliminar el usuario", "Detalle": str(e)}