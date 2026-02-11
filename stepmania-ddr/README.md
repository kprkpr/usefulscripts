# Herramientas de StepMania DDR

Este repositorio contiene dos herramientas útiles para trabajar con fichreos de **StepMania DDR (Dance Dance Revolution)**:

## 📋 Tabla de Contenidos

1. [StepMania Simplifier](#stepmania-simplifier)
2. [StepMania SM Generator](#stepmania-sm-generator)
3. [Requisitos Generales](#requisitos-generales)

---

## 🔨 StepMania Simplifier

### ¿Qué hace?

**stepmania_simplifier.py** es una herramienta con interfaz gráfica (GUI) que permite **simplificar ficheros sm de StepMania existentes**. Es perfecta para:

- Crear versiones más fáciles de un gráfico base
- Reducir la dificultad eliminando patrones complejos
- Generar nuevas dificultades automáticamente a partir de una existente

### Características

La herramienta permite:

- **Eliminar notas rápidas**: Manteniendo o no además un porcentaje de ellas.

- **Eliminar saltos**: Opción para eliminar notas simultáneas (jumps)

- **Simplificar patrones**: Convertiendo holds largos en notas normales

- **Crear nueva dificultad**: La dificultad simplificada se guarda como una nueva dificultad con un nombre personalizado

### Dependencias

- Tkinter, incluida en Python en casi todos los casos.

### Cómo usar

1. Abre la aplicación:

2. Selecciona un archivo `.sm` (click en "Examinar")

3. El programa analizará automáticamente el archivo y mostrará las dificultades disponibles

4. Elige la dificultad base desde el dropdown "Chart Base"

5. Configura las opciones de simplificación según tus necesidades

6. Define el nombre para la nueva dificultad

7. Click en "Generar Versión Simplificada"

8. El archivo se guardará con la nueva dificultad añadida

---

## 🎵 StepMania SM Generator

### ¿Qué hace?

**stepmania_sm_generator.py** es un **generador automático de ficheros de StepMania a partir de archivos de audio**. Analiza la música y genera automáticamente los steps (pasos) con dificultades variables.

### Características

- Detección automática de **BPM** (tempo)
- Detección de **beats** y downbeats
- Detección de **onsets** (cambios musicales)
- Análisis espectral para posicionamiento inteligente de flechas
- Generación de múltiples niveles de dificultad (Beginner → Challenge)
- Conversión automática de audio a MP3 y videos a MP4 sin audio

### Dependencias

#### Requeridas:

```bash
pip install librosa numpy soundfile
```

**⚠️ Dependencia Opcional madmom, recomendada**: 

La detección de BPM es MUCHO más precisa con `madmom`. Sin madmom, el programa usa `librosa` que puede equivocarse con géneros sincopados (reggaeton, trap, etc.)

Para Python > 3.9, instala desde el repositorio de GitHub:
```bash
pip install git+https://github.com/CPJKU/madmom.git
```

Para Python 3.8 o anterior:
```bash
pip install madmom
```

#### Sistema:

- **ffmpeg**: Necesario para decodificar audio y video
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: Descarga desde https://ffmpeg.org/download.html

### Cómo usar

1. Selecciona un archivo de audio (MP3, WAV, OGG, FLAC, etc.)

2. Selecciona un archivo de vídeo (Opcional)

3. El programa:
   - Analiza automáticamente el audio
   - Detecta el BPM y beats
   - Genera los steps para múltiples dificultades
   - Convierte archivos de video si es necesario
   - Genera el archivo `.sm` final


### 🎯 Notas Importantes sobre BPM

El **BPM correcto es fundamental** para la calidad del gráfico generado. Si el programa no lo reconoce correctamente:

#### ¿Por qué es importante el BPM?

- Un BPM incorrecto hace que los beats no sincronicen con la música
- Los steps quedarán desalineados
- El gráfico será injugable

#### ¿Qué hacer si el BPM es incorrecto?

1. **Verificar el BPM manualmente** usando herramientas web:
   - [BPM Detector Online](https://www.online-convert.com/file-converter)
   - [Spotify](https://open.spotify.com) - Ver detalles de la canción
   - [Tunebat](https://tunebat.com) - Detecta BPM de canciones

2. **Editar el BPM manualmente**: Añádelo en la GUI en el apartado de forzar BPM


---


## 🐛 Solución de Problemas

### "ffmpeg not found"
- Linux: `sudo apt install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: Descarga e instala desde https://ffmpeg.org/

### BPM detectado incorrectamente
- Asegúrate de tener **madmom** instalado
- Verifica manualmente el BPM usando herramientas web
- Edita el BPM en la GUI antes de hacer el proceso.


---

## 📝 Licencia

Estas herramientas fueron creadas para trabajar con ficheros de StepMania DDR (.sm).
