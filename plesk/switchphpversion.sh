#!/bin/bash
# REQUIRES: plesk
#
# Convierte domains de una versión de PHP a otra de forma masiva e interactiva.

# --- COLORES ---
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# --- CHECKS ---
if ! command -v plesk &> /dev/null; then
    echo -e "${RED}[!] Error: Este script requiere Plesk.${NC}"
    exit 1
fi

if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}[!] Este script debe ejecutarse como root.${NC}"
   exit 1
fi

# --- FUNCIONES ---

get_handlers() {
    # Obtenemos la lista de handlers. Formato esperado de 'plesk bin php_handler --list':
    #           id:                   display name:  full version:  version:    type:           cgi-bin:  php-cli:                        php.ini:  custom:  status:
    #         cgi             5.4.16 by OS vendor         5.4.16       5.4      cgi  /usr/bin/php-cgi                /usr/bin/php      /etc/php.ini     true  disabled
    
    # Usamos awk para extraer ID y DisplayName de las lineas que no son cabecera
    # Filtramos por status enabled/broken? Mejor solo mostrar los disponibles en NEW, pero mostrar todos en OLD.
    
    # Array global: HANDLER_IDS, HANDLER_NAMES
    HANDLER_IDS=()
    HANDLER_NAMES=()
    
    # Leer salida comando (saltando cabeceras que suelen tener 'id:')
    while read -r line; do
        # ID es la primera columna.
        local hid=$(echo "$line" | awk '{print $1}')
        if [[ "$hid" == "id:" || -z "$hid" ]]; then continue; fi
        
        HANDLER_IDS+=("$hid")
        
        # Extraer información relevante para mostrar al usuario
        # Versión: primer patrón que parezca un número de versión
        local ver=$(echo "$line" | grep -oE '[0-9]+\.[0-9]+(\.[0-9]+)?' | head -1)
        
        # Tipo: buscamos palabras clave conocidas (fpm, fastcgi, cgi)
        # Usamos espacios alrededor para evitar coincidencias parciales si es posible
        local type=$(echo "$line" | grep -oE '[[:space:]](fpm|fastcgi|cgi|module)[[:space:]]' | head -1 | awk '{print $1}')
        if [ -z "$type" ]; then
             # Fallback: intentar buscar sin espacios si está al final o principio (menos probable en medio del output de plesk)
             type=$(echo "$line" | grep -oE '(fpm|fastcgi|cgi|module)' | head -1)
        fi
        
        # Contar dominios usándolo
        local dcount=$(plesk db -Ne "SELECT COUNT(d.id) FROM domains d JOIN hosting h ON h.dom_id=d.id WHERE d.htype = 'vrt_hst' AND h.php_handler_id = '$hid'")
        
        # Formato: plesk-php83-fpm (PHP 8.3.30 - fpm) - Dominios: 5
        HANDLER_NAMES+=("$hid  (PHP $ver | $type) - Dominios: $dcount")
        
    done < <(plesk bin php_handler --list | grep -v "id:")
}

select_handler() {
    local prompt_msg="$1"
    echo -e "${BLUE}${prompt_msg}${NC}"
    
    count=1
    for i in "${!HANDLER_NAMES[@]}"; do
        # Formatear la salida para que se vea bonita
        echo -e "  [${YELLOW}$count${NC}] ${HANDLER_NAMES[$i]}"
        ((count++))
    done
    
    local selection
    while true; do
        read -p "Selecciona una opción (1-${#HANDLER_NAMES[@]}): " selection
        if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "${#HANDLER_NAMES[@]}" ]; then
            # Retornar el ID seleccionado (indice - 1)
            local idx=$((selection-1))
            RET_VAL="${HANDLER_IDS[$idx]}"
            return
        fi
        echo -e "${RED}Opción inválida.${NC}"
    done
}

# --- MAIN ---

echo -e "${GREEN}=== PLESK PHP VERSION SWITCHER ===${NC}"

# 1. Obtener lista
echo "Cargando handlers PHP..."
get_handlers

if [ ${#HANDLER_IDS[@]} -eq 0 ]; then
    echo -e "${RED}[!] No se encontraron handlers de PHP.${NC}"
    exit 1
fi

# 2. Seleccionar OLD
select_handler "Selecciona el handler ANTIGUO (origen):"
OLD_HANDLER="$RET_VAL"
echo -e "Has seleccionado OLD: ${GREEN}$OLD_HANDLER${NC}\n"

# 3. Seleccionar NEW
select_handler "Selecciona el handler NUEVO (destino):"
NEW_HANDLER="$RET_VAL"
echo -e "Has seleccionado NEW: ${GREEN}$NEW_HANDLER${NC}\n"

if [ "$OLD_HANDLER" == "$NEW_HANDLER" ]; then
    echo -e "${RED}[!] El handler origen y destino son el mismo. Saliendo.${NC}"
    exit 0
fi

# 4. Buscar dominios
echo -e "Buscando dominios con handler '$OLD_HANDLER'..."
# Consulta SQL para obtener dominios. 
# Solo filtramos que sea tipo 'vrt_hst' (virtual hosting)
DOMAINS=$(plesk db -Ne "SELECT d.name FROM domains d JOIN hosting h ON h.dom_id=d.id WHERE d.htype = 'vrt_hst' AND h.php_handler_id = '$OLD_HANDLER'")

if [ -z "$DOMAINS" ]; then
    echo -e "${YELLOW}No se encontraron dominios usando '$OLD_HANDLER'.${NC}"
    exit 0
fi

DOMAIN_COUNT=$(echo "$DOMAINS" | wc -l)
echo -e "Se han encontrado ${YELLOW}$DOMAIN_COUNT${NC} dominios."

# 5. Confirmar
echo -e "${RED}ATENCIÓN:${NC} Se va a cambiar el handler de todos estos dominios a '$NEW_HANDLER'."
echo -e "Esto también activará PHP en la configuración del dominio si estaba deshabilitado (al cambiar el handler, Plesk regenera config)."
read -p "¿Continuar? (y/N): " confirm
if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
    echo "Cancelado."
    exit 0
fi

# 6. Ejecutar
echo ""
counter=1
for domain in $DOMAINS; do
    echo -ne "[${counter}/${DOMAIN_COUNT}] Procesando ${BLUE}${domain}${NC}... "
    
    # Ejecutamos el cambio. 
    # Capturamos output y error
    OUT=$(plesk bin domain -u "$domain" -php_handler_id "$NEW_HANDLER" 2>&1)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}ERROR${NC}"
        echo "   -> $OUT"
    fi
    ((counter++))
done

echo -e "\n${GREEN}Proceso finalizado.${NC}"