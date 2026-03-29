import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from streamlit_gsheets import GSheetsConnection

# ==========================================
# 1. CONFIGURACIÓN CENTRALIZADA
# ==========================================
SHEET_URL = "https://docs.google.com/spreadsheets/d/18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM/edit#gid=0"
SHEET_ID_SOLO = "18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM"
URL_DE_TU_APP = "https://tennis-hub-pro.streamlit.app" 

st.set_page_config(page_title="Tennis Hub Pro", layout="centered", page_icon="🎾")

# ==========================================
# 2. MOTOR DE CARGA DE JUGADORES
# ==========================================
@st.cache_data(ttl=1800) 
def cargar_jugadores_veloz():
    try:
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid=0"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip().str.normalize('NFKD').str.encode('ascii', errors='ignore').str.decode('utf-8')
        
        mapeo = {'Nombre': 'Nombre', 'Cedula': 'Cedula', 'Telefono': 'Telefono', 'Categoria': 'Categoria', 'Grupo': 'Grupo'}
        for col_std, col_fin in mapeo.items():
            if col_std in df.columns:
                df = df.rename(columns={col_std: col_fin})
            else:
                col_real = next((c for c in df.columns if col_std.lower() in c.lower()), None)
                if col_real: df = df.rename(columns={col_real: col_fin})
        
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
    conn = st.connection("gsheets", type=GSheetsConnection)
    
    if df_jugadores.empty or 'Cedula' not in df_jugadores.columns:
        st.error("⚠️ Error de conexión con la base de datos.")
        return

    # PANEL DE ACCESO
    with st.sidebar:
        st.header("🔐 Acceso")
        cedula_input = st.text_input("Tu Cédula", type="password", placeholder="0912345678")
        st.button("Verificar Jugador", use_container_width=True)

    if not cedula_input:
        st.info("👈 Ingresa tu cédula en el menú lateral para empezar.")
        return

    cedula_user = cedula_input.strip().zfill(10)
    user_data = df_jugadores[df_jugadores['Cedula'] == cedula_user]

    if user_data.empty:
        st.error("❌ Cédula no registrada.")
        return
    
    nombre_usuario = user_data['Nombre'].values[0]
    cat_usuario = user_data['Categoria'].values[0]
    grupo_usuario = user_data['Grupo'].values[0]
    
    st.success(f"✅ ¡Hola {nombre_usuario}!")
    st.markdown(f"📊 **{cat_usuario} - Grupo {grupo_usuario}**")

    # ==========================================
    # --- ZONA DE CONFIRMACIÓN (Con Reloj de 1 Hora) ---
    # ==========================================
    st.divider()
    st.subheader("🔔 Confirmar Mis Partidos Perdidos")
    
    try:
        df_reportes = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
        # Convertimos fecha para cálculos
        df_reportes['Fecha_dt'] = pd.to_datetime(df_reportes['Fecha'], format="%d/%m/%Y %H:%M", errors='coerce')
        ahora = datetime.now()
        limite_hora = ahora - timedelta(hours=1)

        pendientes = df_reportes[
            (df_reportes['Perdedor'] == nombre_usuario) & 
            (df_reportes['Estado'] == 'Pendiente')
        ]

        if pendientes.empty:
            st.success("🎉 ¡No tienes resultados pendientes!")
        else:
            for index, fila in pendientes.iterrows():
                # Cálculo de tiempo restante para mostrar al usuario
                if pd.notnull(fila['Fecha_dt']):
                    minutos_pasados = (ahora - fila['Fecha_dt']).total_seconds() / 60
                    restantes = max(0, int(60 - minutos_pasados))
                else:
                    restantes = 0

                with st.expander(f"Confirmar contra {fila['Ganador']} ({fila['Score']})", expanded=True):
                    st.write(f"📅 Fecha reporte: {fila['Fecha']}")
                    if restantes > 0:
                        st.warning(f"⏳ Tienes {restantes} minutos para aceptar o rechazar. Después se aceptará solo.")
                    else:
                        st.error("⏰ El tiempo de validación expiró. Se confirmará al recargar.")

                    col_a, col_b = st.columns(2)
                    if col_a.button("✅ Confirmar", key=f"conf_{index}", use_container_width=True):
                        df_reportes.at[index, 'Estado'] = 'Confirmado'
                        conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_reportes.drop(columns=['Fecha_dt']))
                        st.rerun()
                        
                    if col_b.button("❌ Rechazar", key=f"rech_{index}", use_container_width=True):
                        df_reportes.at[index, 'Estado'] = 'Rechazado'
                        conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_reportes.drop(columns=['Fecha_dt']))
                        st.rerun()
    except:
        st.write("Cargando validaciones...")

    # ==========================================
    # --- FORMULARIO DE REPORTE (Con Anti-duplicado 7 días) ---
    # ==========================================
    with st.expander("📝 Subir Nuevo Resultado", expanded=False):
        with st.form("form_reporte", clear_on_submit=True):
            rivales = df_jugadores[
                (df_jugadores['Grupo'].astype(str) == str(grupo_usuario)) & 
                (df_jugadores['Categoria'] == cat_usuario) & 
                (df_jugadores['Nombre'] != nombre_usuario)
            ]['Nombre'].unique()

            perdedor = st.selectbox("¿A quién le ganaste?", rivales) if len(rivales) > 0 else None
            c1, c2 = st.columns(2)
            mis_juegos = c1.number_input("Tus Juegos", 0, 8, 8)
            juegos_rival = c2.number_input("Juegos Rival", 0, 8, 0)
            
            enviar = st.form_submit_button("🚀 Subir y Notificar", use_container_width=True)

            if enviar and perdedor:
                if mis_juegos <= juegos_rival:
                    st.error("Debes ser el ganador.")
                else:
                    try:
                        # Verificación de duplicados (7 días)
                        df_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
                        df_actual['Fecha_dt'] = pd.to_datetime(df_actual['Fecha'], format="%d/%m/%Y %H:%M", errors='coerce')
                        
                        siete_dias_atras = ahora - timedelta(days=7)
                        ya_existe = df_actual[
                            (df_actual['Ganador'] == nombre_usuario) & 
                            (df_actual['Perdedor'] == perdedor) &
                            (df_actual['Estado'] != 'Rechazado') &
                            (df_actual['Fecha_dt'] > siete_dias_atras)
                        ]

                        if not ya_existe.empty:
                            st.warning("⚠️ Ya reportaste este resultado en los últimos 7 días.")
                        else:
                            # Guardar
                            nueva_fila = pd.DataFrame([{
                                "Fecha": ahora.strftime("%d/%m/%Y %H:%M"),
                                "Ganador": nombre_usuario,
                                "Perdedor": perdedor,
                                "Score": f"{mis_juegos}-{juegos_rival}",
                                "Estado": "Pendiente",
                                "Categoria": cat_usuario,
                                "Grupo": grupo_usuario
                            }])
                            df_final = pd.concat([df_actual.drop(columns=['Fecha_dt']), nueva_fila], ignore_index=True)
                            conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_final)
                            
                            # WhatsApp
                            tel_rival = df_jugadores[df_jugadores['Nombre'] == perdedor]['Telefono'].values[0]
                            tel_clean = str(tel_rival).replace(" ", "").replace("+", "")
                            mensaje = (f"🎾 *Tennis Hub Pro*\n\nHola {perdedor}, he registrado nuestro resultado: {mis_juegos}-{juegos_rival}.\n\n"
                                       f"Confírmalo aquí:\n{URL_DE_TU_APP}")
                            link_ws = f"https://wa.me/{tel_clean}?text={mensaje.replace(' ', '%20').replace('\n', '%0A')}"
                            st.components.v1.html(f"<script>window.open('{link_ws}')</script>", height=0)
                            
                            st.success("✅ ¡Guardado y Notificado!")
                            st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")

if __name__ == "__main__":
    app_reporte()