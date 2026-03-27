import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import traceback  # Para diagnosticar cada error que salte

# 1. CONFIGURACIÓN (URL COMPLETA + ID)
# Usamos la URL completa para la conexión de escritura (evita el ValueError anterior)
SHEET_URL = "https://docs.google.com/spreadsheets/d/18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM/edit#gid=0"
SHEET_ID_SOLO = "18sNSVjpX0N14Nk2TdMw3O9Hp317R7qSzZarlTJJacSM"

st.set_page_config(page_title="Tennis Hub Pro - Reportes", layout="centered")

# Conexión oficial para escritura
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=5)
def cargar_jugadores():
    try:
        # Método de lectura rápido y estable
        url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID_SOLO}/export?format=csv&gid=0"
        df = pd.read_csv(url)
        df.columns = df.columns.str.strip()
        
        # Ajuste de Cédula
        col_ced = next((c for c in df.columns if "Cedula" in c or "Cédula" in c), None)
        if col_ced:
            df[col_ced] = df[col_ced].astype(str).str.strip().str.zfill(10)
            df = df.rename(columns={col_ced: 'Cedula'})
        return df
    except Exception as e:
        st.error(f"Error de lectura inicial: {e}")
        return pd.DataFrame()

def app_reporte():
    st.title("🎾 Tennis Hub Pro")
    st.subheader("Centro de Reportes Oficial")
    
    df_jugadores = cargar_jugadores()
    
    if df_jugadores.empty:
        st.warning("No se pudo cargar la lista de jugadores.")
        return

    # PANEL LATERAL
    with st.sidebar:
        st.header("🔐 Acceso")
        cedula_input = st.text_input("Tu Cédula", type="password")
    
    if not cedula_input:
        st.info("👈 Ingresa tu cédula para reportar tu victoria.")
        return

    cedula_user = cedula_input.strip().zfill(10)
    user_data = df_jugadores[df_jugadores['Cedula'] == cedula_user]

    if user_data.empty:
        st.error("❌ Cédula no registrada.")
    else:
        nombre_usuario = user_data['Nombre'].values[0]
        cat_usuario = user_data['Categoría'].values[0]
        grupo_usuario = user_data['Grupo'].values[0]
        
        st.success(f"✅ ¡Hola {nombre_usuario}!")

        with st.container(border=True):
            st.markdown("### 📝 Registrar Resultado")
            
            rivales = df_jugadores[
                (df_jugadores['Grupo'].astype(str) == str(grupo_usuario)) & 
                (df_jugadores['Categoría'] == cat_usuario) & 
                (df_jugadores['Nombre'] != nombre_usuario)
            ]['Nombre'].unique()

            if len(rivales) == 0:
                st.warning("No se encontraron rivales en tu grupo.")
            else:
                with st.form("form_reporte", clear_on_submit=True):
                    perdedor = st.selectbox("¿A quién le ganaste?", rivales)
                    c1, c2 = st.columns(2)
                    mis_juegos = c1.number_input("Tus Juegos", 0, 8, 8)
                    juegos_rival = c2.number_input("Juegos Rival", 0, 8, 0)
                    
                    enviar = st.form_submit_button("🚀 Subir Resultado")

                    if enviar:
                        if mis_juegos <= juegos_rival:
                            st.error("Error: El ganador debe tener más juegos.")
                        else:
                            # Preparamos la nueva fila
                            nueva_fila = pd.DataFrame([{
                                "Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
                                "Ganador": nombre_usuario,
                                "Perdedor": perdedor,
                                "Score": f"{mis_juegos}-{juegos_rival}",
                                "Estado": "Pendiente",
                                "Categoria": cat_usuario,
                                "Grupo": grupo_usuario
                            }])

                            try:
                                # INTENTO DE GUARDADO CON RASTREADOR
                                st.write("⏳ Conectando con la base de datos...")
                                
                                # Leemos lo que hay (usando la URL completa)
                                df_actual = conn.read(spreadsheet=SHEET_URL, worksheet="Reportes", ttl=0)
                                
                                # Concatenamos
                                df_final = pd.concat([df_actual, nueva_fila], ignore_index=True)
                                
                                # Actualizamos
                                conn.update(spreadsheet=SHEET_URL, worksheet="Reportes", data=df_final)
                                
                                st.success("✅ ¡Registrado correctamente!")
                                st.balloons()
                                
                            except Exception:
                                # Si algo falla, el Rastreador nos dirá qué es
                                error_info = traceback.format_exc()
                                st.error("❌ ERROR DETECTADO DURANTE EL GUARDADO:")
                                st.code(error_info)
                                st.info("Si ves un error nuevo, pásame el texto del cuadro negro.")

if __name__ == "__main__":
    app_reporte()