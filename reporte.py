import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CONFIGURACIÓN CENTRALIZADA
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM/edit#gid=0"
SHEET_ID_SOLO = "18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM"
# CAMBIA ESTO POR TU URL REAL CUANDO LA PUBLIQUES (Ej: https://tennis-guayaquil.streamlit.app)
URL_DE_TU_APP = "https://tennis-hub-pro.streamlit.app" 

st.set_page_config(page_title="Tennis Hub Pro", layout="centered", page_icon="🎾")

# ==========================================
# 2. MOTOR DE CARGA DE JUGADORES (Caché 30 min)
# ==========================================
@st.cache_data(ttl=1800) 
def cargar_jugadores_veloz():
    try:
        # Petición directa CSV (Veloz)
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid=0"
        df = pd.read_csv(url)
        # Limpieza estándar de columnas
        df.columns = df.columns.str.strip().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        
        # Mapeo de columnas críticas
        mapeo = {
            'Nombre': 'Nombre',
            'Cedula': 'Cedula',
            'Telefono': 'Telefono',
            'Categoria': 'Categoria',
            'Grupo': 'Grupo'
        }
        for col_standard, col_final in mapeo.items():
            if col_standard in df.columns:
                df = df.rename(columns={col_standard: col_final})
            else:
                # Intento de encontrar la columna si tiene tildes (ej: Categoría)
                col_real = next((c for c in df.columns if col_standard.lower() in c.lower()), None)
                if col_real: df = df.rename(columns={col_real: col_final})
        
        # Formateo de Cédula a 10 dígitos string
        df['Cedula'] = df['Cedula'].astype(str).str.strip().str.zfill(10)
        return df
    except:
        return pd.DataFrame()

# ==========================================
# 3. APLICACIÓN PRINCIPAL
# ==========================================
def app_reporte():
    st.title("🎾 Tennis Hub Pro")
    df_jugadores = cargar_jugadores_veloz()
    
    # Check de base de datos
    if df_jugadores.empty or 'Cedula' not in df_jugadores.columns:
        st.error("⚠️ Error de conexión con la base de datos de jugadores.")
        return

    # PANEL DE ACCESO
    with st.sidebar:
        st.header("🔐 Acceso")
        cedula_input = st.text_input("Tu Cédula", type="password", placeholder="0912345678")
        st.button("Verificar Jugador", use_container_width=True)

    if not cedula_input:
        st.info("👈 Ingresa tu cédula en el menú lateral para empezar.")
        return

    # VALIDACIÓN DEL USUARIO
    cedula_user = cedula_input.strip().zfill(10)
    user_data = df_jugadores[df_jugadores['Cedula'] == cedula_user]

    if user_data.empty:
        st.error("❌ Cédula no registrada en el torneo.")
        return
    
    # Extraemos info del jugador
    nombre_usuario = user_data['Nombre'].values[0]
    # Usamos try/except por si acaso hay un typo en la columna del excel
    try:
        cat_usuario = user_data['Categoria'].values[0]
        grupo_usuario = user_data['Grupo'].values[0]
    except KeyError as e:
        st.error(f"⚠️ Error: No se encontró la columna {e} en el Excel. Revisa los nombres de las columnas.")
        return
    
    # Mensaje de bienvenida unificado (Mobile Friendly)
    st.success(f"✅ ¡Hola {nombre_usuario}!")
    st.markdown(f"📊 **{cat_usuario} - Grupo {grupo_usuario}**")

    # ==========================================
    # --- FORMULARIO DE REPORTE DE VICTORIA ---
    # ==========================================
    with st.expander("📝 Subir Nuevo Resultado", expanded=False):
        with st.form("form_reporte", clear_on_submit=True):
            rivales = df_jugadores[
                (df_jugadores['Grupo'].astype(str) == str(grupo_usuario)) & 
                (df_jugadores['Categoria'] == cat_usuario) & 
                (df_jugadores['Nombre'] != nombre_usuario)
            ]['Nombre'].unique()

            if len(rivales) == 0:
                st.warning("No se encontraron rivales registrados en tu grupo.")
                perdedor = None
            else:
                perdedor = st.selectbox("¿A quién le ganaste?", rivales)
            
            # Formato móvil para puntuación
            c1, c2 = st.columns(2)
            mis_juegos = c1.number_input("Tus Juegos", 0, 8, 8, step=1, help="Cuántos juegos ganaste tú.")
            juegos_rival = c2.number_input("Juegos Rival", 0, 8, 0, step=1, help="Cuántos juegos ganó tu rival.")
            
            enviar = st.form_submit_button("🚀 Subir y Notificar al Rival", use_container_width=True)

            if enviar:
                if not perdedor:
                    st.error("Debes seleccionar un rival.")
                elif mis_juegos <= juegos_rival:
                    st.error("Error: Para reportar una victoria, tus juegos deben ser mayores a los del rival.")
                else:
                    try:
                        with st.spinner("Guardando en la nube y abriendo WhatsApp..."):
                            # 1. GUARDAR EN GOOGLE SHEETS
                            conn = st.connection("gsheets", type=GSheetsConnection)
                            df_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
                            
                            # Creamos el registro del nuevo partido
                            nueva_fila = pd.DataFrame([{
                                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "Ganador": nombre_usuario,
                                "Perdedor": perdedor,
                                "Score": f"{mis_juegos}-{juegos_rival}",
                                "Estado": "Pendiente",
                                "Categoria": cat_usuario,
                                "Grupo": grupo_usuario
                            }])
                            
                            # Unimos y subimos
                            df_final = pd.concat([df_actual, nueva_fila], ignore_index=True)
                            conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_final)
                            
                            # 2. PREPARAR NOTIFICACIÓN AUTOMÁTICA DE WHATSAPP
                            # Buscamos el teléfono del perdedor
                            if 'Telefono' in df_jugadores.columns:
                                tel_rival = df_jugadores[df_jugadores['Nombre'] == perdedor]['Telefono'].values[0]
                                tel_clean = str(tel_rival).replace(" ", "").replace("+", "")
                                
                                # Texto precargado para el ganador
                                mensaje = (
                                    f"🎾 *Tennis Hub Pro* \n\n"
                                    f"Hola {perdedor}, he registrado nuestro resultado.\n\n"
                                    f"🏆 Ganador: {nombre_usuario}\n"
                                    f"🔢 Marcador: {mis_juegos}-{juegos_rival}\n\n"
                                    f"Confírmalo rápido aquí:\n"
                                    f"{URL_DE_TU_APP}"
                                )
                                
                                # URL final de WhatsApp
                                link_ws = f"https://wa.me/{tel_clean}?text={mensaje.replace(' ', '%20').replace('\n', '%0A')}"

                                # 3. INTENTO DE APERTURA AUTOMÁTICA (JavaScript)
                                # El usuario debe 'permitir pop-ups' la primera vez
                                js = f"window.open('{link_ws}')"
                                st.components.v1.html(f"<script>{js}</script>", height=0)
                                
                                st.success("✅ Guardado. ¡Por favor, revisa tu WhatsApp y dale enviar al mensaje!")
                            else:
                                st.success("✅ Guardado en el Excel. (No se encontró columna 'Telefono' en la base de datos).")
                            
                            st.balloons()
                    except Exception as e:
                        st.error(f"Fallo crítico al guardar: {e}")

    # ==========================================
    # --- ZONA DE CONFIRMACIÓN (NUEVA SECCIÓN) ---
    # ==========================================
    st.divider()
    st.subheader("🔔 Confirmar Mis Partidos Perdidos")
    st.info("Abajo aparecen partidos donde tu rival te marcó como perdedor. Confirma o rechaza el resultado.")
    
    try:
        # Volvemos a leer los reportes para ver qué hay pendiente de validación
        conn = st.connection("gsheets", type=GSheetsConnection)
        df_reportes = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
        
        # Filtramos partidos donde el usuario validado es el PERDEDOR y el estado es PENDIENTE
        pendientes = df_reportes[
            (df_reportes['Perdedor'] == nombre_usuario) & 
            (df_reportes['Estado'] == 'Pendiente')
        ]

        if pendientes.empty:
            st.success("🎉 ¡No tienes resultados pendientes de confirmar!")
        else:
            # Iteramos por cada partido pendiente
            for index, fila in pendientes.iterrows():
                # Cuadro expansible Mobile Friendly
                with st.expander(f"Confirmar contra {fila['Ganador']} ({fila['Score']})", expanded=True):
                    st.write(f"📅 Fecha: {fila['Fecha']}")
                    st.write(f"📊 Categoría: {fila['Categoria']}")
                    
                    # Botones grandes para celular
                    col_a, col_b = st.columns(2)
                    
                    if col_a.button("✅ Confirmar", key=f"conf_{index}", use_container_width=True):
                        # Cambiamos estado en el DataFrame local
                        df_reportes.at[index, 'Estado'] = 'Confirmado'
                        with st.spinner("Actualizando sistema..."):
                            conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_reportes)
                        st.success("✅ Resultado confirmado. Gracias por tu transparencia.")
                        st.balloons()
                        # Refrescamos la página para que desaparezca
                        st.rerun()
                        
                    if col_b.button("❌ Rechazar", key=f"rech_{index}", use_container_width=True):
                        # Marcamos como rechazado para revisión manual
                        df_reportes.at[index, 'Estado'] = 'Rechazado'
                        with st.spinner("Reportando discrepancia..."):
                            conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_reportes)
                        st.warning("⚠️ Resultado rechazado. El administrador revisará el caso con ambos jugadores.")
                        st.rerun()
    except:
        st.write("Cargando sistema de validación...")

if __name__ == "__main__":
    app_reporte()