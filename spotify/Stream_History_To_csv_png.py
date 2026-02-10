#!/usr/bin/env python3

import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
from datetime import datetime

# Configuración de estilo para los gráficos
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")

def cargar_archivos_json(directorio='.'):
    """
    Carga todos los archivos JSON del historial de Spotify
    """
    archivos = Path(directorio).glob('Streaming_History_Audio_*.json')
    todos_los_datos = []
    
    for archivo in archivos:
        print(f"Cargando {archivo.name}...")
        with open(archivo, 'r', encoding='utf-8') as f:
            datos = json.load(f)
            todos_los_datos.extend(datos)
    
    print(f"Total de reproducciones cargadas: {len(todos_los_datos)}")
    return todos_los_datos

def procesar_datos(datos):
    """
    Convierte los datos JSON en un DataFrame de pandas y procesa las fechas
    """
    df = pd.DataFrame(datos)
    
    # Convertir timestamp a datetime
    df['ts'] = pd.to_datetime(df['ts'])
    
    # Convertir milisegundos a minutos
    df['minutos_reproducidos'] = df['ms_played'] / 60000
    
    # Extraer año, mes, día
    df['año'] = df['ts'].dt.year
    df['mes'] = df['ts'].dt.month
    df['año_mes'] = df['ts'].dt.to_period('M')
    df['nombre_mes'] = df['ts'].dt.strftime('%B %Y')
    
    # Filtrar solo canciones (no podcasts ni audiolibros)
    df = df[df['master_metadata_track_name'].notna()]
    
    return df

def minutos_por_mes(df):
    """
    Calcula y grafica los minutos reproducidos por mes
    """
    minutos_mes = df.groupby('año_mes')['minutos_reproducidos'].sum().reset_index()
    minutos_mes['año_mes'] = minutos_mes['año_mes'].astype(str)
    
    plt.figure(figsize=(15, 6))
    plt.bar(minutos_mes['año_mes'], minutos_mes['minutos_reproducidos'], color='#1DB954')
    plt.xlabel('Mes', fontsize=12)
    plt.ylabel('Minutos Reproducidos', fontsize=12)
    plt.title('Minutos Reproducidos por Mes', fontsize=16, fontweight='bold')
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig('minutos_por_mes.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return minutos_mes

def top_artistas_mes(df, año, mes, top_n=10):
    """
    Obtiene el top 10 de artistas de un mes específico
    """
    df_mes = df[(df['año'] == año) & (df['mes'] == mes)]
    
    if len(df_mes) == 0:
        return None
    
    top_artistas = df_mes.groupby('master_metadata_album_artist_name')['minutos_reproducidos'].sum().sort_values(ascending=False).head(top_n)
    
    plt.figure(figsize=(12, 8))
    top_artistas.plot(kind='barh', color='#1DB954')
    plt.xlabel('Minutos Reproducidos', fontsize=12)
    plt.ylabel('Artista', fontsize=12)
    plt.title(f'Top {top_n} Artistas - {mes:02d}/{año}', fontsize=16, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(f'top_artistas_{año}_{mes:02d}.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return top_artistas

def top_artistas_año(df, año, top_n=10):
    """
    Obtiene el top 10 de artistas de un año específico
    """
    df_año = df[df['año'] == año]
    
    if len(df_año) == 0:
        return None
    
    top_artistas = df_año.groupby('master_metadata_album_artist_name')['minutos_reproducidos'].sum().sort_values(ascending=False).head(top_n)
    
    plt.figure(figsize=(12, 8))
    top_artistas.plot(kind='barh', color='#1ED760')
    plt.xlabel('Minutos Reproducidos', fontsize=12)
    plt.ylabel('Artista', fontsize=12)
    plt.title(f'Top {top_n} Artistas - {año}', fontsize=16, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(f'top_artistas_{año}.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return top_artistas

def top_canciones_mes(df, año, mes, top_n=10):
    """
    Obtiene el top 10 de canciones de un mes específico
    """
    df_mes = df[(df['año'] == año) & (df['mes'] == mes)]
    
    if len(df_mes) == 0:
        return None
    
    df_mes['cancion_artista'] = df_mes['master_metadata_track_name'] + ' - ' + df_mes['master_metadata_album_artist_name']
    top_canciones = df_mes.groupby('cancion_artista')['minutos_reproducidos'].sum().sort_values(ascending=False).head(top_n)
    
    plt.figure(figsize=(12, 10))
    top_canciones.plot(kind='barh', color='#1DB954')
    plt.xlabel('Minutos Reproducidos', fontsize=12)
    plt.ylabel('Canción', fontsize=12)
    plt.title(f'Top {top_n} Canciones - {mes:02d}/{año}', fontsize=16, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(f'top_canciones_{año}_{mes:02d}.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return top_canciones

def top_canciones_año(df, año, top_n=10):
    """
    Obtiene el top 10 de canciones de un año específico
    """
    df_año = df[df['año'] == año]
    
    if len(df_año) == 0:
        return None
    
    df_año['cancion_artista'] = df_año['master_metadata_track_name'] + ' - ' + df_año['master_metadata_album_artist_name']
    top_canciones = df_año.groupby('cancion_artista')['minutos_reproducidos'].sum().sort_values(ascending=False).head(top_n)
    
    plt.figure(figsize=(12, 10))
    top_canciones.plot(kind='barh', color='#1ED760')
    plt.xlabel('Minutos Reproducidos', fontsize=12)
    plt.ylabel('Canción', fontsize=12)
    plt.title(f'Top {top_n} Canciones - {año}', fontsize=16, fontweight='bold')
    plt.gca().invert_yaxis()
    plt.tight_layout()
    plt.savefig(f'top_canciones_{año}.png', dpi=300, bbox_inches='tight')
    plt.close()
    
    return top_canciones

def resumen_estadisticas(df):
    """
    Muestra un resumen de estadísticas generales
    """
    print("\n" + "="*60)
    print("RESUMEN DE ESTADÍSTICAS")
    print("="*60)
    print(f"Total de reproducciones: {len(df):,}")
    print(f"Total de minutos reproducidos: {df['minutos_reproducidos'].sum():,.2f}")
    print(f"Total de horas reproducidas: {df['minutos_reproducidos'].sum()/60:,.2f}")
    print(f"Artistas únicos: {df['master_metadata_album_artist_name'].nunique():,}")
    print(f"Canciones únicas: {df['master_metadata_track_name'].nunique():,}")
    print(f"Período: {df['ts'].min().date()} a {df['ts'].max().date()}")
    print("="*60 + "\n")

def generar_todos_los_graficos(df):
    """
    Genera todos los gráficos para cada año y cada mes disponible
    """
    # Obtener años y meses únicos
    años = sorted(df['año'].unique())
    
    print("\n" + "="*60)
    print("GENERANDO GRÁFICOS")
    print("="*60)
    
    # Generar gráficos por año
    print("\n📊 Generando gráficos anuales...")
    for año in años:
        print(f"  - Año {año}")
        top_artistas_año(df, año)
        top_canciones_año(df, año)
    
    # Generar gráficos por mes
    print("\n📊 Generando gráficos mensuales...")
    for año in años:
        meses_del_año = sorted(df[df['año'] == año]['mes'].unique())
        for mes in meses_del_año:
            print(f"  - {año}-{mes:02d}")
            top_artistas_mes(df, año, mes)
            top_canciones_mes(df, año, mes)
    
    print("\n✅ Todos los gráficos generados!")

# EJECUCIÓN PRINCIPAL
if __name__ == "__main__":
    # 1. Cargar datos
    datos = cargar_archivos_json()
    
    # 2. Procesar datos
    df = procesar_datos(datos)
    
    # 3. Mostrar resumen
    resumen_estadisticas(df)
    
    # 4. Gráfico de minutos por mes
    print("📊 Generando gráfico general de minutos por mes...")
    minutos_mes = minutos_por_mes(df)
    
    # 5. Guardar CSV de Año-Mes-Minutos
    print("\n💾 Guardando CSV de minutos por mes...")
    minutos_mes_csv = df.groupby(['año', 'mes'])['minutos_reproducidos'].sum().reset_index()
    minutos_mes_csv.columns = ['Año', 'Mes', 'Minutos']
    minutos_mes_csv = minutos_mes_csv.sort_values(['Año', 'Mes'])
    minutos_mes_csv.to_csv('minutos_por_año_mes.csv', index=False, encoding='utf-8')
    print("✅ CSV guardado: minutos_por_año_mes.csv")
    
    # 6. Generar todos los gráficos
    generar_todos_los_graficos(df)
    
    # 7. Guardar datos procesados completos en CSV
    print("\n💾 Guardando datos procesados completos en CSV...")
    df.to_csv('historial_spotify_procesado.csv', index=False, encoding='utf-8')
    print("✅ CSV guardado: historial_spotify_procesado.csv")
    
    print("\n" + "="*60)
    print("🎉 ANÁLISIS COMPLETADO")
    print("="*60)
    print("\nArchivos generados:")
    print("  📊 minutos_por_mes.png")
    print("  📊 top_artistas_[año].png (para cada año)")
    print("  📊 top_canciones_[año].png (para cada año)")
    print("  📊 top_artistas_[año]_[mes].png (para cada mes)")
    print("  📊 top_canciones_[año]_[mes].png (para cada mes)")
    print("  📄 minutos_por_año_mes.csv")
    print("  📄 historial_spotify_procesado.csv")
    print("="*60 + "\n")
