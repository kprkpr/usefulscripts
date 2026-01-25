#!/bin/bash

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Función para mostrar mensajes con colores
print_colored() {
    echo -e "${2}${1}${NC}"
}

# Función para validar número
is_number() {
    [[ $1 =~ ^[0-9]+$ ]]
}

# Función para obtener duración del video
get_duration() {
    ffprobe -v quiet -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$1" 2>/dev/null | cut -d. -f1
}

# Función para detectar hardware disponible
detect_hardware() {
    hw_available=""
    if nvidia-smi &>/dev/null; then hw_available="${hw_available}nvenc "; fi
    if [ -d "/dev/dri" ] && ls /dev/dri/render* &>/dev/null; then hw_available="${hw_available}vaapi "; fi
    echo "$hw_available"
}

# Función para mostrar opciones de encoder
show_encoder_options() {
    local hw=$(detect_hardware)
    print_colored "\n=== OPCIONES DE ENCODER ===" "$YELLOW"
    echo "1) SOFTWARE (x265) - Mejor calidad, más lento"
    [[ $hw == *"nvenc"* ]] && echo "2) NVIDIA (NVENC) - Rápido, buena calidad"
    [[ $hw == *"vaapi"* ]] && echo "3) VAAPI (Intel/AMD) - Rápido, calidad variable"
    echo -e "\nHardware detectado: ${hw:-ninguno}"
}

# Función para mostrar valores de calidad
show_quality_info() {
    case $encoder_type in
        "software")
            print_colored "\n=== CALIDAD CRF (x265) ===" "$YELLOW"
            echo "18-20: Excelente | 22-24: Muy alta (Rec.) | 26-28: Buena | 30-32: Aceptable" ;;
        "nvenc")
            print_colored "\n=== CALIDAD CQ (NVENC) ===" "$YELLOW"
            echo "19-21: Excelente | 23-25: Muy alta (Rec.) | 27-29: Buena | 31-33: Aceptable" ;;
        "vaapi")
            print_colored "\n=== CALIDAD ICQ (VAAPI) ===" "$YELLOW"
            echo "18-20: Excelente | 22-24: Muy alta (Rec.) | 26-28: Buena | 30-32: Aceptable" ;;
    esac
}

# Función para pedir encoder
ask_encoder() {
    show_encoder_options
    while true; do
        read -p "Selecciona el encoder (1-3): " encoder_choice
        case $encoder_choice in
            1) encoder_type="software"; break ;;
            2) [[ $(detect_hardware) == *"nvenc"* ]] && { encoder_type="nvenc"; break; } || print_colored "NVENC no disponible." "$RED" ;;
            3) [[ $(detect_hardware) == *"vaapi"* ]] && { encoder_type="vaapi"; break; } || print_colored "VAAPI no disponible." "$RED" ;;
            *) print_colored "Opción inválida." "$RED" ;;
        esac
    done
}

# Función para pedir calidad
ask_quality() {
    show_quality_info
    case $encoder_type in
        "software"|"vaapi") quality_range="18-32" ;;
        "nvenc") quality_range="19-33" ;;
    esac
    
    while true; do
        read -p "Introduce el valor de calidad ($quality_range): " quality_value
        local min=$(echo $quality_range | cut -d'-' -f1)
        local max=$(echo $quality_range | cut -d'-' -f2)
        if is_number "$quality_value" && [ "$quality_value" -ge "$min" ] && [ "$quality_value" -le "$max" ]; then break; else print_colored "Error: Introduce un número entre $quality_range." "$RED"; fi
    done
}

# Función para construir los argumentos de audio dinámicamente
build_audio_args() {
    local input_file="$1"
    local mode="$2"
    local audio_args=""

    # Si el modo NO requiere tocar audio (1 y 3), copiamos todo
    if [ "$mode" == "1" ] || [ "$mode" == "3" ]; then
        echo "-c:a copy"
        return
    fi

    # Obtenemos el número de streams de audio
    local num_audio_streams=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$input_file" | wc -l)

    # Si no hay audio, no ponemos argumentos de audio
    if [ "$num_audio_streams" -eq 0 ]; then
        return
    fi

    # Iteramos por cada stream de audio (índice 0 hasta N-1)
    for ((i=0; i<num_audio_streams; i++)); do
        # Obtenemos el bitrate de ESTE stream específico
        local bitrate=$(ffprobe -v error -select_streams a:$i -show_entries stream=bit_rate -of default=noprint_wrappers=1:nokey=1 "$input_file")
        
        # Convertir a kbps si es número, si es "N/A" asumimos 0
        if is_number "$bitrate"; then
            bitrate_kbps=$((bitrate / 1000))
        else
            bitrate_kbps=0
        fi

        # Lógica de decisión por pista
        # Si es > 0 y < 256k, copiamos. Si es >= 256k o desconocido (0), convertimos.
        if [ "$bitrate_kbps" -gt 0 ] && [ "$bitrate_kbps" -lt 256 ]; then
            audio_args="$audio_args -c:a:$i copy"
        else
            audio_args="$audio_args -c:a:$i ac3 -b:a:$i 256k"
        fi
    done

    echo "$audio_args"
}

# Función para generar comando ffmpeg
generate_ffmpeg_command() {
    local input_file="$1"
    local output_file="$2"
    local mode="$3"
    
    local video_opts=""
    local filter_opts=""
    local pre_opts=""
    
    # 1. VIDEO
    if [ "$mode" == "2" ]; then
        video_opts="-c:v copy"
    else
        case $encoder_type in
            "software") video_opts="-c:v libx265 -crf $quality_value -preset medium" ;;
            "nvenc")    video_opts="-c:v hevc_nvenc -cq $quality_value -preset p4" ;;
            "vaapi")    
                pre_opts="-vaapi_device /dev/dri/renderD128"
                video_opts="-c:v hevc_vaapi -global_quality $quality_value" 
                ;;
        esac
    fi
    
    # 2. FILTROS (Escalado)
    if [ "$mode" == "3" ] || [ "$mode" == "4" ]; then
        if [ "$encoder_type" == "vaapi" ] && [ "$mode" != "2" ]; then
            filter_opts="-vf 'format=nv12,hwupload,scale_vaapi=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2'"
        elif [ "$mode" != "2" ]; then
            filter_opts="-vf 'scale=1920:1080:force_original_aspect_ratio=decrease:force_divisible_by=2'"
        fi
    else
        if [ "$encoder_type" == "vaapi" ] && [ "$mode" != "2" ]; then
            filter_opts="-vf 'format=nv12,hwupload'"
        fi
    fi
    
    # 3. AUDIO (Llamada a la nueva función inteligente)
    local audio_opts=$(build_audio_args "$input_file" "$mode")
    
    # 4. CONSTRUIR COMANDO
    # Usamos -map 0 para incluir todos los streams, luego aplicamos los codecs específicos
    echo "ffmpeg $pre_opts -i \"$input_file\" $video_opts $filter_opts -map 0 $audio_opts -c:s copy \"$output_file\""
}

# --- INICIO DEL SCRIPT ---

print_colored "====" "$CYAN"
print_colored "    SCRIPT DE RECODIFICACIÓN MEJORADO v3 (Audio Multi-Track)  " "$CYAN"
print_colored "====" "$CYAN"

if ! command -v ffmpeg &> /dev/null; then print_colored "Error: ffmpeg no está instalado." "$RED"; exit 1; fi

# Rutas
while true; do
    read -p "Introduce la ruta donde buscar los videos: " input_path
    input_path="${input_path/#\~/$HOME}"
    if [ -d "$input_path" ]; then break; else print_colored "Ruta inválida." "$RED"; fi
done

read -p "Introduce la ruta de salida (Enter para actual): " output_path
if [ -z "$output_path" ]; then output_path="."; else output_path="${output_path/#\~/$HOME}"; mkdir -p "$output_path"; fi

# Menú
print_colored "\n=== OPCIONES ===" "$YELLOW"
echo "1) CALIDAD: CONVERSIÓN A H.265"
echo "2) AUDIO: Solo Audio (Smart)"
echo "3) REDIMENSIONAR: 1080p (H.265)"
echo "4) COMPLETO: Convertir a 1080p (H.265) + Audio Smart"
echo "5) COMPLETO SIN REDIMENSION: CALIDAD (H.265) + Audio Smart"

while true; do
    read -p "Opción (1-5): " mode
    case $mode in 1|2|3|4|5) break;; *) print_colored "Inválido." "$RED";; esac
done

# Configuración Encoder
if [ "$mode" != "2" ]; then
    ask_encoder
    ask_quality
    case $encoder_type in
        "software") desc="H.265 Soft (CRF $quality_value)" ;;
        "nvenc")    desc="H.265 NVENC (CQ $quality_value)" ;;
        "vaapi")    desc="H.265 VAAPI (ICQ $quality_value)" ;;
    esac
else
    desc="Solo Audio"
fi
[[ "$mode" =~ [245] ]] && desc="$desc + Audio Smart"

# Guardar config
echo -e "Modo: $desc\nFecha: $(date)\nOrigen: $input_path" > "$output_path/log_$(date +%Y%m%d).txt"

# Buscar archivos
cd "$input_path" || exit 1
video_files=()
while IFS= read -r -d '' file; do video_files+=("$file"); done < <(find . -maxdepth 1 -type f \( -iname "*.mkv" -o -iname "*.mp4" -o -iname "*.avi" -o -iname "*.mov" \) -print0 2>/dev/null)

if [ ${#video_files[@]} -eq 0 ]; then print_colored "No hay videos." "$RED"; exit 1; fi
print_colored "Archivos encontrados: ${#video_files[@]}" "$GREEN"

# Procesar
processed=0; failed=0
for file in "${video_files[@]}"; do
    filename=$(basename "$file")
    output_file="$output_path/${filename%.*}_opt.mkv"
    
    if [ -f "$output_file" ]; then print_colored "Saltando $filename (ya existe)" "$YELLOW"; continue; fi
    
    print_colored "\nProcesando: $filename" "$CYAN"
    
    # Generar y ejecutar
    ffmpeg_cmd=$(generate_ffmpeg_command "$file" "$output_file" "$mode")
    
    # Debug: descomentar para ver qué comando se ejecuta realmente
    # echo "DEBUG CMD: $ffmpeg_cmd"
    
    if eval $ffmpeg_cmd; then
        ((processed++))
        print_colored "✓ Completado" "$GREEN"
    else
        ((failed++))
        print_colored "✗ Error" "$RED"
    fi
done

print_colored "\nFin. Procesados: $processed | Errores: $failed" "$GREEN"
