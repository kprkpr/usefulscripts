#!/bin/bash
# --- CONFIGURACIÓN DE COLORES ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# --- CONFIGURACIÓN DE LÍMITES ---
DEFAULT_UPLOAD="8" #MB
DEFAULT_POST="8" #MB
DEFAULT_TIME="30"
RAM_HIGH="256"
PROCESS_LIMIT=5  # Límite para marcar en rojo los procesos
SERVER=$(curl -s --connect-timeout 2 -4 ifconfig.me || hostname -I | awk '{print $1}') # Auto-detectar IP servidor

# --- PRE-CALCULO DE PROCESOS PHP-FPM ---
declare -A PROCESS_MAP

echo "Analizando procesos PHP-FPM..."

while read -r count domain; do
    domain=$(echo "$domain" | xargs)
    PROCESS_MAP["$domain"]=$count
done < <(ps aux | grep 'php-fpm: pool' | grep -v grep | awk '{print $NF}' | sort | uniq -c)

# --- OBTENER DOMINIOS ---
if command -v plesk &> /dev/null; then
    DOMAINS=$(plesk bin site --list)
else
    DOMAINS=$(ls /var/www/vhosts/ | grep "\.")
fi

# --- IMPRIMIR CABECERA ---
printf "%-30s %-8s %-12s %-12s %-12s %-10s %-10s %-20s %-15s\n" "DOMINIO" "PROCS" "RAM (Lim)" "UPLOAD" "POST" "TIME" "PHP VER" "HANDLER" "IP (DNS)"
printf "%s\n" "------------------------------------------------------------------------------------------------------------------------------------------------"

for DOMAIN in $DOMAINS; do
    # Ignorar carpetas del sistema
    if [[ "$DOMAIN" == "system" || "$DOMAIN" == "chroot" || "$DOMAIN" == "default" ]]; then continue; fi

    # 1. BUSCAR PHP.INI
    if [ -f "/var/www/vhosts/system/$DOMAIN/etc/php.ini" ]; then
        PHP_CONFIG="/var/www/vhosts/system/$DOMAIN/etc/php.ini"
    elif [ -f "/var/www/vhosts/$DOMAIN/etc/php.ini" ]; then
        PHP_CONFIG="/var/www/vhosts/$DOMAIN/etc/php.ini"
    else
        PHP_CONFIG=""
    fi

    # 2. OBTENER VERSIÓN DE PHP Y HANDLER (Vía Plesk DB)
    if command -v plesk &> /dev/null; then
	HANDLER_RAW=$(plesk db "select h.php_handler_id from domains d join hosting h on h.dom_id=d.id WHERE d.name='$DOMAIN'" -N 2>/dev/null | grep -v "^\+" | sed 's/|//g' | xargs)

        # Extraemos solo los números para la lógica de colores
        PHP_RAW_VER=$(echo "$HANDLER_RAW" | grep -o "[0-9]*" | head -1)

        if [ -z "$PHP_RAW_VER" ]; then
             PHP_DISPLAY="?"
             PHP_RAW_VER=0
        else
             # Formatear 74 -> 7.4, 81 -> 8.1
             if [ ${#PHP_RAW_VER} -ge 2 ]; then
                PHP_DISPLAY="${PHP_RAW_VER:0:1}.${PHP_RAW_VER:1:1}"
             else
                PHP_DISPLAY="$PHP_RAW_VER"
             fi
        fi
    else
        PHP_DISPLAY="No CLI"
        HANDLER_RAW="-"
        PHP_RAW_VER=0
    fi

    # 3. LEER DATOS
    if [ ! -z "$PHP_CONFIG" ]; then
        MEMORY_LIMIT=$(grep -i "^memory_limit" "$PHP_CONFIG" | cut -d= -f2 | tr -d '[:space:]')

        UPLOAD_MAX=$(grep -i "^upload_max_filesize" "$PHP_CONFIG" | cut -d= -f2 | tr -d '[:space:]')
        UPLOAD_NUM=${UPLOAD_MAX//[!0-9]/}

        POST_MAX=$(grep -i "^post_max_size" "$PHP_CONFIG" | cut -d= -f2 | tr -d '[:space:]')
        POST_NUM=${POST_MAX//[!0-9]/}

        MAX_EXEC=$(grep -i "^max_execution_time" "$PHP_CONFIG" | cut -d= -f2 | tr -d '[:space:]')
    else
        MEMORY_LIMIT="No ini"
        UPLOAD_MAX="0"; UPLOAD_NUM=0
        POST_MAX="0";   POST_NUM=0
        MAX_EXEC="0"
    fi

    # 4. OBTENER PROCESOS DEL ARRAY
    PROC_COUNT=${PROCESS_MAP["$DOMAIN"]}
    if [ -z "$PROC_COUNT" ]; then PROC_COUNT=0; fi

    # --- LÓGICA DE COLORES ---

    # A) Procesos
    COLOR_PROC=$NC
    if [ "$PROC_COUNT" -gt "$PROCESS_LIMIT" ]; then COLOR_PROC=$RED; fi

    # B) RAM
    COLOR_RAM=$NC
    if [[ "$MEMORY_LIMIT" != "No ini" ]]; then
        if [[ "$MEMORY_LIMIT" == *"-1"* ]]; then
            COLOR_RAM=$GREEN
        else
            RAM_VAL=$(echo "$MEMORY_LIMIT" | sed 's/[^0-9]*//g')
            if [[ "$MEMORY_LIMIT" == *"G"* ]]; then RAM_VAL=$((RAM_VAL * 1024)); fi
            if [ "$RAM_VAL" -gt "$RAM_HIGH" ] 2>/dev/null; then COLOR_RAM=$RED; fi
        fi
    fi

    # C) Upload y Time
    COLOR_UPLOAD=$NC
    if [ "$UPLOAD_NUM" -gt "$DEFAULT_UPLOAD" ] && [ "$UPLOAD_MAX" != "-" ]; then COLOR_UPLOAD=$BLUE; fi

    COLOR_POST=$NC
    if [ "$POST_NUM" -gt "$DEFAULT_POST" ] && [ "$POST_MAX" != "-" ]; then COLOR_POST=$BLUE; fi

    COLOR_TIME=$NC
    if [ "$MAX_EXEC" -gt "$DEFAULT_TIME" ] && [ "$MAX_EXEC" != "-" ]; then COLOR_TIME=$BLUE; fi

    # D) PHP Version (Rojo si es 7.4 o inferior)
    COLOR_PHP=$GREEN
    if [ "$PHP_RAW_VER" -ne 0 ] && [ "$PHP_RAW_VER" -le 74 ] 2>/dev/null; then
        COLOR_PHP=$RED
    fi

    # E) NSLOOKUP
    DOMAIN_IP=$(nslookup -type=A "$DOMAIN" 8.8.8.8 2>/dev/null | grep "Address:" | tail -n +2 | head -1 | awk '{print $2}')
    if [ -z "$DOMAIN_IP" ]; then DOMAIN_IP="-"; fi

    COLOR_IP=$NC
    if [ "$DOMAIN_IP" != "$SERVER" ] && [ "$DOMAIN_IP" != "-" ]; then
        COLOR_IP=$RED
    fi

    # --- IMPRIMIR ---
    # Se añade HANDLER_RAW al final
    printf "%-30s ${COLOR_PROC}%-8s${NC} ${COLOR_RAM}%-12s${NC} ${COLOR_UPLOAD}%-12s${NC} ${COLOR_POST}%-12s${NC} ${COLOR_TIME}%-10s${NC} ${COLOR_PHP}%-10s${NC} %-20s ${COLOR_IP}%-15s${NC}\n" \
    "${DOMAIN:0:29}" "$PROC_COUNT" "$MEMORY_LIMIT" "$UPLOAD_MAX" "$POST_MAX" "$MAX_EXEC" "$PHP_DISPLAY" "$HANDLER_RAW" "$DOMAIN_IP"

done
