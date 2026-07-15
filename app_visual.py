import streamlit as st
import requests
import urllib.parse

API_URL = "https://fruteria-pos-nub.onrender.com"

st.set_page_config(page_title="Frutería POS & Inventario", page_icon="🍏", layout="wide")

# --- 1. MEMORIA DE SESIÓN (CIBERSEGURIDAD) ---
if "logueado" not in st.session_state:
    st.session_state["logueado"] = False
    st.session_state["usuario"] = ""
    st.session_state["rol"] = ""

# --- 2. PANTALLA DE LOGIN (SI NO ESTÁ IDENTIFICADO, SE FRENA AQUÍ) ---
if not st.session_state["logueado"]:
    st.title("🍏 Sistema de Gestión y Punto de Venta")
    st.divider()
    
    col_vacia1, col_login, col_vacia2 = st.columns([1, 2, 1])
    with col_login:
        st.subheader("🔒 Control de Acceso al Sistema")
        with st.form("form_login"):
            usuario_input = st.text_input("👤 Nombre de Usuario:", placeholder="ej. dueño_admin o cajero_turno1")
            pin_input = st.text_input("🔑 PIN de Seguridad:", type="password", placeholder="****")
            btn_entrar = st.form_submit_button("🚀 Iniciar Sesión", type="primary", use_container_width=True)
            
            if btn_entrar:
                if usuario_input and pin_input:
                    try:
                        res = requests.post(f"{API_URL}/login/", json={"nombre_usuario": usuario_input, "pin_acceso": pin_input}).json()
                        if res.get("exito"):
                            st.session_state["logueado"] = True
                            st.session_state["usuario"] = usuario_input
                            st.session_state["rol"] = res.get("rol")
                            st.success(res["mensaje"])
                            st.rerun()
                        else:
                            st.error(res.get("Error"))
                    except Exception as e:
                        st.error(f"Error al conectar con el servidor: {e}")
                else:
                    st.warning("Por favor escribe tu usuario y PIN.")
                    
    
    # ¡ESTE COMANDO ES EL ESCUDO! Detiene el dibujo de la pantalla si no estás logueado
    st.stop()

# --- 3. BARRA DE ESTADO Y BOTÓN DE SALIDA (LOGOUT) ---
with st.sidebar:
    st.title("🍏 Panel de Control")
    st.write(f"👤 **Usuario:** {st.session_state['usuario']}")
    
    if st.session_state["rol"] == "Admin":
        st.success(f"👑 **Rol:** Administrador / Dueño")
    else:
        st.info(f"🛡️ **Rol:** {st.session_state['rol']}")
        
    st.divider()
    if st.button("🚪 Cerrar Sesión", type="secondary", use_container_width=True):
        st.session_state["logueado"] = False
        st.session_state["usuario"] = ""
        st.session_state["rol"] = ""
        st.rerun()

st.title(f"🍏 Frutería POS - Bienvenido, {st.session_state['usuario']}")

# --- PESTAÑAS DE NAVEGACIÓN 
pestaña1, pestaña2, pestaña3, pestaña4, pestaña5, pestaña6, pestaña7 = st.tabs([
    "🛒 Punto de Venta (Caja)", 
    "📦 Inventario en Vivo", 
    "📥 Compras y Catálogo", 
    "💰 Reporte Financiero", 
    "🚨 Mermas y Gastos",
    "🤝 Mayoristas y Créditos",
    "👥 Gestión de Personal",
])

# --- PESTAÑA 1: PUNTO DE VENTA (CAJA) ---
with pestaña1:
    st.header("🛒 Registrar Nueva Venta y Emitir Ticket")
    try:
        res_inv = requests.get(f"{API_URL}/inventario/").json()
        res_cli = requests.get(f"{API_URL}/clientes/").json()
        
        if isinstance(res_inv, list) and len(res_inv) > 0:
            opciones_inv = {f"{item['producto']} (Lote #{item['lote_id']} - Disp: {item['disponible']} {item['medida']})": item for item in res_inv}
            seleccion_prod = st.selectbox("Selecciona el producto a vender:", list(opciones_inv.keys()))
            item_sel = opciones_inv[seleccion_prod]
            
            opciones_cli = {f"{c['nombre']} (Deuda actual: ${c['deuda']:,.2f})": c['id'] for c in res_cli}
            sel_cli = st.selectbox("¿Quién está comprando?", list(opciones_cli.keys()))
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                cant = st.number_input(f"Cantidad ({item_sel['medida']}):", min_value=0.1, max_value=float(item_sel['disponible']), value=1.0, step=0.5)
            with col2:
                precio = st.number_input("Precio por unidad ($):", min_value=0.0, value=float(item_sel['precio_sugerido']), step=1.0)
            with col3:
                tipo = st.selectbox("Tipo de venta:", ["Menudeo", "Mayoreo", "Remate"])
            with col4:
                pago = st.selectbox("Método de pago:", ["Efectivo", "Tarjeta", "Transferencia", "Crédito (Fiado)"])
                
            total = cant * precio
            st.subheader(f"Total a Cobrar ({pago}): **${total:,.2f} pesos**")
            
            if st.button("💵 Cobrar y Generar Ticket", type="primary", use_container_width=True):
                datos_venta = {
                    "id_lote": item_sel["lote_id"], "cantidad_vendida": cant, 
                    "precio_final_unidad": precio, "tipo_venta": tipo, 
                    "metodo_pago": pago, "id_cliente": opciones_cli[sel_cli]
                }
                res = requests.post(f"{API_URL}/ventas/", json=datos_venta)
                
                if res.status_code == 200:
                    data_res = res.json()
                    ticket_id = data_res.get("ticket", "001")
                    nombre_cliente = sel_cli.split(" (")[0]
                    
                    tel_cliente = ""
                    for c in res_cli:
                        if c["id"] == opciones_cli[sel_cli]:
                            tel_cliente = c.get("telefono", "")
                            break
                            
                    st.success(f"¡Venta #{ticket_id} registrada con éxito!")
                    
                    texto_ticket = f"""🍏 *FRUTERÍA - TICKET DE VENTA #{ticket_id}*
----------------------------------
*Cliente:* {nombre_cliente}
*Producto:* {item_sel['producto']}
*Cantidad:* {cant} {item_sel['medida']}
*Precio Unitario:* ${precio:,.2f}
----------------------------------
*TOTAL PAGADO:* ${total:,.2f} MXN
*Método de pago:* {pago}
*Atendido por:* {st.session_state['usuario']}
----------------------------------
¡Gracias por su preferencia en nuestro abasto! 🍏"""
                    
                    st.divider()
                    st.subheader("📄 Comprobante de Venta Digital")
                    st.code(texto_ticket, language="markdown")
                    
                    if tel_cliente and tel_cliente != "None" and len(str(tel_cliente).strip()) > 5:
                        tel_limpio = "".join(filter(str.isdigit, str(tel_cliente)))
                        if len(tel_limpio) == 10:
                            tel_limpio = f"52{tel_limpio}"
                        url_wa = f"https://wa.me/{tel_limpio}?text={urllib.parse.quote(texto_ticket)}"
                        st.link_button("📲 Enviar Ticket por WhatsApp al Cliente", url_wa, type="primary", use_container_width=True)
                    else:
                        st.info("💡 Consejo: Si registras el teléfono del mayorista, aquí aparecerá el botón para enviarlo por WhatsApp.")
                    
                    if st.button("🔄 Siguiente Venta / Limpiar Pantalla", type="secondary", use_container_width=True):
                        st.rerun()
                else:
                    st.error("Error al registrar la venta.")
        else:
            st.info("No hay inventario disponible. Ve a la pestaña '📥 Compras y Catálogo' para surtir.")
    except Exception as e:
        st.error(f"Asegúrate de que el motor de FastAPI esté encendido. Error: {e}")

# --- PESTAÑA 2: INVENTARIO EN VIVO ---
with pestaña2:
    st.header("📦 Existencias y Semáforo de Frescura en Almacén")
    if st.button("🔄 Actualizar Tabla"):
        st.rerun()
    try:
        inv = requests.get(f"{API_URL}/inventario/").json()
        if isinstance(inv, list) and len(inv) > 0:
            tabla_limpia = []
            for item in inv:
                tabla_limpia.append({
                    "Lote": f"#{item['lote_id']}",
                    "Producto": item["producto"],
                    "Disponible": f"{item['disponible']} {item['medida']}",
                    "Precio Sugerido": f"${item['precio_sugerido']:,.2f}",
                    "Semáforo de Frescura": item["semaforo"]
                })
            st.dataframe(tabla_limpia, use_container_width=True)
        else:
            st.write("Tu inventario está vacío.")
    except Exception as e:
        st.error(f"No se pudo conectar con el servidor: {e}")

# --- PESTAÑA 3: COMPRAS, CATÁLOGO Y ELIMINACIÓN DE LOTES ---
with pestaña3:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Agregar Nuevo Producto al Catálogo")
        nombre_prod = st.text_input("Nombre del producto (ej. Sandia, Tomate):")
        medida_prod = st.selectbox("¿Cómo se vende?", ["Kilogramos", "Piezas"])
        if st.button("✨ Guardar Producto en Catálogo"):
            if nombre_prod:
                res = requests.post(f"{API_URL}/productos/", json={"nombre": nombre_prod, "unidad_medida": medida_prod})
                if res.status_code == 200:
                    st.success(f"¡{nombre_prod} agregado al catálogo!")
                    st.rerun()
                else:
                    st.error("Ese producto ya existe en tu catálogo.")
            else:
                st.warning("Escribe un nombre para el producto.")
                
    with col2:
        st.subheader("2. Registrar Llegada de Mercancía (Lote)")
        try:
            prods = requests.get(f"{API_URL}/productos/").json()
            if isinstance(prods, list) and len(prods) > 0:
                opciones_p = {f"{p['nombre']} ({p['unidad']})": p['id'] for p in prods}
                sel_p = st.selectbox("Selecciona qué producto compraste:", list(opciones_p.keys()))
                
                cant_compra = st.number_input("Cantidad comprada (Kilos o Piezas):", min_value=1.0, step=10.0)
                costo_total = st.number_input("Costo total pagado al proveedor ($):", min_value=0.0, step=100.0)
                precio_sug = st.number_input("Precio al que recomiendas venderlo ($):", min_value=0.0, step=5.0)
                
                if st.button("🚚 Meter Mercancía al Almacén", type="primary"):
                    datos_lote = {
                        "id_producto": opciones_p[sel_p], "cantidad_inicial": cant_compra,
                        "costo_compra_total": costo_total, "precio_venta_sugerido": precio_sug
                    }
                    requests.post(f"{API_URL}/lotes/", json=datos_lote)
                    st.success("¡Cargamento registrado y listo para venderse!")
                    st.rerun()
            else:
                st.info("Primero agrega productos en el formulario de la izquierda.")
        except Exception:
            st.error("Error al cargar el catálogo de productos.")

    st.divider()
    
    # --- CANDADO DE SEGURIDAD 1: SOLO ADMIN PUEDE ELIMINAR LOTES ---
    if st.session_state["rol"] == "Admin":
        st.subheader("⚠️ Zona de Peligro: Eliminar Lote Registrado por Error")
        try:
            res_inv_del = requests.get(f"{API_URL}/inventario/").json()
            if isinstance(res_inv_del, list) and len(res_inv_del) > 0:
                opciones_lotes_del = {f"Lote #{item['lote_id']} - {item['producto']} ({item['disponible']} disponibles)": item['lote_id'] for item in res_inv_del}
                sel_lote_del = st.selectbox("Selecciona el lote erróneo que deseas borrar por completo:", list(opciones_lotes_del.keys()))
                
                if st.button("❌ Eliminar Lote del Almacén", type="secondary"):
                    res_del_lote = requests.delete(f"{API_URL}/lotes/{opciones_lotes_del[sel_lote_del]}").json()
                    if "Error" in res_del_lote:
                        st.error(res_del_lote["Error"])
                    else:
                        st.success(res_del_lote["mensaje"])
                        st.rerun()
            else:
                st.info("No hay lotes en almacén que se puedan eliminar.")
        except Exception:
            st.error("No se pudo cargar el módulo de eliminación de lotes.")
    else:
        st.info("🔒 **Zona de Peligro Restringida:** Solo el perfil Administrador puede eliminar lotes del almacén.")

# --- PESTAÑA 4: REPORTE FINANCIERO ---
with pestaña4:
    # --- CANDADO DE SEGURIDAD 2: REPORTE FINANCIERO EXCLUSIVO DE ADMINS ---
    if st.session_state["rol"] != "Admin":
        st.error("🔒 **ACCESO RESTRINGIDO A FINANZAS**")
        st.warning("El módulo de Inteligencia Financiera, Balance de Resultados y Gráficos es de uso exclusivo para Dueños y Administradores. Si eres el dueño, inicia sesión con tu cuenta de Admin.")
    else:
        st.header("📊 Inteligencia Financiera y Reportes de Venta")
        
        periodo_sel = st.selectbox(
            "Selecciona el periodo que deseas auditar:",
            ["Hoy", "Esta Semana (Últimos 7 días)", "Este Mes (Últimos 30 días)", "Histórico General"]
        )
        
        mapa_periodos = {
            "Hoy": "Hoy",
            "Esta Semana (Últimos 7 días)": "Semana",
            "Este Mes (Últimos 30 días)": "Mes",
            "Histórico General": "Historico"
        }
        
        st.divider()
        try:
            fin = requests.get(f"{API_URL}/finanzas/?periodo={mapa_periodos[periodo_sel]}").json()
            
            if "Error" not in fin:
                st.subheader(f"📈 Balance de Resultados: *{periodo_sel}*")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("💵 Total Vendido (Ingresos)", f"${fin.get('1_ingresos_totales_ventas', 0):,.2f}")
                c2.metric("📦 Costo de Mercancía Vendida", f"${fin.get('2_inversion_en_mercancia', 0):,.2f}")
                
                ganancia = fin.get('5_ganancia_neta_real', 0)
                if ganancia >= 0:
                    c3.metric("🏆 Ganancia Neta Limpia", f"${ganancia:,.2f}")
                else:
                    c3.metric("🚨 Pérdida Neta en Periodo", f"${ganancia:,.2f}", delta="- ¡Alerta!")
                
                st.divider()
                st.subheader("🛑 Deducciones y Fugas de Capital")
                c4, c5 = st.columns(2)
                c4.metric("💸 Gastos Operativos (Fletes/Sueldos)", f"${fin.get('4_gastos_operativos', 0):,.2f}")
                c5.metric("🗑️ Pérdidas por Mermas (Desechos)", f"${fin.get('3_perdidas_por_merma', 0):,.2f}")
                
                st.divider()
                st.subheader("📊 Radiografía Visual de tu Negocio")
                col_graf1, col_graf2 = st.columns(2)
                
                with col_graf1:
                    st.write("**📈 Balance General (Ingresos vs Gastos vs Ganancia)**")
                    datos_balance = {
                        "Categoría": ["Ingresos (Ventas)", "Costo Mercancía", "Gastos Operativos", "Ganancia Neta"],
                        "Monto ($)": [
                            fin.get('1_ingresos_totales_ventas', 0),
                            fin.get('2_inversion_en_mercancia', 0),
                            fin.get('4_gastos_operativos', 0),
                            max(0, fin.get('5_ganancia_neta_real', 0))
                        ]
                    }
                    st.bar_chart(data=datos_balance, x="Categoría", y="Monto ($)", color="#2e7d32")
                    
                with col_graf2:
                    st.write("**🛑 Distribución de Salidas de Dinero (¿En qué se gasta/invierte?)**")
                    datos_fugas = {
                        "Concepto": ["Inversión en Fruta", "Gastos (Flete/Luz)", "Mermas (Desecho)"],
                        "Monto ($)": [
                            fin.get('2_inversion_en_mercancia', 0),
                            fin.get('4_gastos_operativos', 0),
                            fin.get('3_perdidas_por_merma', 0)
                        ]
                    }
                    st.bar_chart(data=datos_fugas, x="Concepto", y="Monto ($)", color="#d32f2f")
            else:
                st.error(f"Error en el motor: {fin.get('Detalle')}")
        except Exception as e:
            st.error(f"No se pudo conectar con el servidor de finanzas: {e}")

# --- PESTAÑA 5: MERMAS Y GASTOS ---
with pestaña5:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🚨 Registrar Merma (Desecho)")
        try:
            res_inv = requests.get(f"{API_URL}/inventario/").json()
            if isinstance(res_inv, list) and len(res_inv) > 0:
                opciones_m = {f"{item['producto']} (Lote #{item['lote_id']})": item['lote_id'] for item in res_inv}
                sel_m = st.selectbox("Producto dañado:", list(opciones_m.keys()), key="merma_sel")
                cant_m = st.number_input("Cantidad a desechar:", min_value=0.1, value=1.0)
                motivo_m = st.text_input("Motivo:", value="Fruta muy madura / Golpeada")
                
                if st.button("🗑️ Descontar Merma"):
                    datos_m = {"id_lote": opciones_m[sel_m], "cantidad_mermada": cant_m, "motivo": motivo_m}
                    res = requests.post(f"{API_URL}/mermas/", json=datos_m)
                    if res.status_code == 200 and "Error" not in res.json():
                        st.success("Merma registrada y descontada del inventario.")
                        st.rerun()
                    else:
                        st.error(f"El motor reportó un problema: {res.json().get('Detalle', res.json())}")
        except Exception:
            st.write("Conecta el backend para ver lotes.")
            
    with col2:
        st.subheader("🧾 Registrar Gasto Operativo")
        cat_g = st.selectbox("Categoría:", ["Flete", "Bolsas y Empaques", "Sueldos", "Luz / Agua", "Otro"])
        monto_g = st.number_input("Monto gastado ($):", min_value=0.0, step=50.0)
        desc_g = st.text_input("Descripción opcional:")
        if st.button("💸 Guardar Gasto"):
            res = requests.post(f"{API_URL}/gastos/", json={"categoria": cat_g, "monto": monto_g, "descripcion": desc_g})
            respuesta_json = res.json()
            if res.status_code == 200 and "Error" not in respuesta_json:
                st.success("Gasto guardado y restado en el reporte financiero.")
                st.rerun()
            else:
                st.error(f"El motor reportó un problema: {respuesta_json.get('Detalle', respuesta_json)}")

# --- PESTAÑA 6: MAYORISTAS Y CRÉDITOS ---
with pestaña6:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Registrar Nuevo Cliente Mayorista")
        nom_c = st.text_input("Nombre del negocio o cliente (ej. Taquería El Pastor):")
        tel_c = st.text_input("Teléfono / WhatsApp:")
        if st.button("✨ Guardar Cliente"):
            if nom_c:
                res = requests.post(f"{API_URL}/clientes/", json={"nombre": nom_c, "telefono": tel_c})
                if res.status_code == 200:
                    st.success(f"¡{nom_c} agregado a tu cartera de clientes!")
                    st.rerun()
                else:
                    st.error("Error: ¿Ese cliente ya está registrado?")
            else:
                st.warning("Escribe un nombre para el cliente.")
                
        st.divider()
        st.subheader("2. Registrar Abono o Pago de Deuda")
        try:
            clis = requests.get(f"{API_URL}/clientes/").json()
            deudores = {f"{c['nombre']} (Debe: ${c['deuda']:,.2f})": c['id'] for c in clis if c['deuda'] > 0}
            if len(deudores) > 0:
                sel_deudor = st.selectbox("Selecciona quién te está pagando:", list(deudores.keys()))
                monto_abono = st.number_input("Monto que está pagando ($):", min_value=1.0, step=100.0)
                if st.button("💸 Registrar Abono a la Cuenta", type="primary"):
                    requests.post(f"{API_URL}/abonos/", json={"id_cliente": deudores[sel_deudor], "monto": monto_abono})
                    st.success("¡Abono descontado de su deuda con éxito!")
                    st.rerun()
            else:
                st.success("🎉 ¡Excelente noticia! Nadie te debe dinero en este momento.")
        except Exception:
            st.error("Error al conectar con el servidor de clientes.")
            
        st.divider()
        
        # --- CANDADO DE SEGURIDAD 3: SOLO ADMIN BORRA CLIENTES ---
        if st.session_state["rol"] == "Admin":
            st.subheader("🗑️ Dar de Baja / Eliminar Cliente")
            try:
                opciones_borrar = {c['nombre']: c['id'] for c in clis if c['id'] != 1}
                if len(opciones_borrar) > 0:
                    sel_borrar = st.selectbox("Selecciona qué cliente deseas eliminar permanentemente:", list(opciones_borrar.keys()))
                    if st.button("❌ Eliminar Cliente del Sistema", type="secondary"):
                        res_del = requests.delete(f"{API_URL}/clientes/{opciones_borrar[sel_borrar]}").json()
                        if "Error" in res_del:
                            st.error(res_del["Error"])
                        else:
                            st.success(res_del["mensaje"])
                            st.rerun()
                else:
                    st.info("No hay clientes adicionales registrados para eliminar.")
            except Exception:
                st.error("Error al cargar módulo de bajas.")
        else:
            st.info("🔒 **Bajas Restringidas:** Solo un Administrador puede eliminar clientes mayoristas de la base de datos.")
            
    with col2:
        st.subheader("📋 Cartera de Clientes y Cuentas por Cobrar")
        if st.button("🔄 Actualizar Deudas"):
            st.rerun()
        try:
            clis = requests.get(f"{API_URL}/clientes/").json()
            tabla_cli = [{"ID": c['id'], "Cliente": c['nombre'], "Teléfono": c['telefono'], "Deuda Pendiente": f"${c['deuda']:,.2f}"} for c in clis]
            st.dataframe(tabla_cli, use_container_width=True)
        except Exception:
            st.error("No se pudieron cargar los clientes.")

# --- PESTAÑA 7: GESTIÓN DE PERSONAL ---
with pestaña7:
    # --- CANDADO DE SEGURIDAD: EXCLUSIVO PARA ADMINS ---
    if st.session_state["rol"] != "Admin":
        st.error("🔒 **ACCESO RESTRINGIDO A GESTIÓN DE PERSONAL**")
        st.warning("Solo los Administradores y Dueños pueden dar de alta, modificar o eliminar usuarios y cajeros del sistema.")
    else:
        st.header("👥 Control de Usuarios y Personal del Negocio")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("1. Registrar Nuevo Cajero o Administrador")
            nom_u = st.text_input("Nombre de Usuario (para iniciar sesión):", placeholder="ej. cajero_mañana o carlos_vendedor")
            pin_u = st.text_input("PIN de Seguridad (Contraseña):", type="password", placeholder="****")
            rol_u = st.selectbox("Nivel de Permisos (Rol):", ["Cajero", "Admin"])
            
            if st.button("✨ Guardar Nuevo Usuario", type="primary"):
                if nom_u and pin_u:
                    res = requests.post(f"{API_URL}/usuarios/", json={"nombre_usuario": nom_u, "pin_acceso": pin_u, "rol": rol_u}).json()
                    if "Error" in res:
                        st.error(res["Error"])
                    else:
                        st.success(res["mensaje"])
                        st.rerun()
                else:
                    st.warning("Escribe un nombre de usuario y un PIN de acceso.")
                    
            st.divider()
            st.subheader("🗑️ Dar de Baja / Revocar Acceso")
            try:
                usrs = requests.get(f"{API_URL}/usuarios/").json()
                # Ocultamos de la lista al usuario actual y al admin principal por seguridad
                opciones_borrar_u = {f"{u['usuario']} ({u['rol']})": u['id'] for u in usrs if u['usuario'] != 'admin' and u['usuario'] != st.session_state['usuario']}
                
                if len(opciones_borrar_u) > 0:
                    sel_borrar_u = st.selectbox("Selecciona qué empleado deseas eliminar del sistema:", list(opciones_borrar_u.keys()))
                    if st.button("❌ Eliminar Empleado / Cajero", type="secondary"):
                        res_del_u = requests.delete(f"{API_URL}/usuarios/{opciones_borrar_u[sel_borrar_u]}").json()
                        if "Error" in res_del_u:
                            st.error(res_del_u["Error"])
                        else:
                            st.success(res_del_u["mensaje"])
                            st.rerun()
                else:
                    st.info("No hay usuarios adicionales disponibles para eliminar.")
            except Exception:
                st.error("Error al cargar el módulo de bajas.")
                
        with col2:
            st.subheader("📋 Personal Activo en el Sistema")
            if st.button("🔄 Actualizar Lista de Personal"):
                st.rerun()
            try:
                usrs = requests.get(f"{API_URL}/usuarios/").json()
                tabla_u = [{"ID": u['id'], "Usuario": u['usuario'], "Nivel / Rol": u['rol']} for u in usrs]
                st.dataframe(tabla_u, use_container_width=True)
            except Exception:
                st.error("No se pudieron cargar los usuarios.")
