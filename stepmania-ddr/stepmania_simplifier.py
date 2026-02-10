#!/usr/bin/env python3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import os
import re
from typing import List, Dict, Tuple
import copy
import random

class StepManiaSimplifier:
    def __init__(self, root):
        self.root = root
        self.root.title("StepMania Chart Simplifier v2")
        self.root.geometry("800x850") # Aumentado un poco el alto para las nuevas opciones

        self.current_file = None
        self.chart_data = {}

        # Configuración para las opciones de notas
        self.note_options_config = [
            {"color": "🟣", "text": "Eliminar notas púrpura (24th+) - Muy rápidas", "var_name": "24th", "default_remove": True},
            {"color": "🟢", "text": "Eliminar notas verdes (16th) - Semicorcheas", "var_name": "16th", "default_remove": True},
            {"color": "🟡", "text": "Eliminar notas amarillas (12th) - Tripletes", "var_name": "12th", "default_remove": False},
            {"color": "🔵", "text": "Eliminar notas azules (8th) - Corcheas", "var_name": "8th", "default_remove": False},
        ]
        self.keep_percentage_values = ["0%", "10%", "25%", "50%", "75%"]

        self.setup_ui()

    def create_note_option_frame(self, parent, row, config):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0), pady=2)

        # Variable para "Eliminar X notas"
        remove_var = tk.BooleanVar(value=config["default_remove"])
        setattr(self, f"remove_{config['var_name']}", remove_var)

        # Variable para el porcentaje de "Dejar algunas"
        keep_percentage_var = tk.StringVar(value=self.keep_percentage_values[0]) # Default a 0%
        setattr(self, f"keep_percentage_{config['var_name']}", keep_percentage_var)

        ttk.Checkbutton(frame, text=f"{config['color']} {config['text']}",
                       variable=remove_var,
                       command=lambda vn=config['var_name']: self.toggle_keep_percentage_option(vn)).pack(side=tk.LEFT)

        ttk.Label(frame, text="Dejar algunas:").pack(side=tk.LEFT, padx=(10, 2))
        
        keep_combo = ttk.Combobox(frame, textvariable=keep_percentage_var,
                                     values=self.keep_percentage_values,
                                     width=5, state="disabled" if not config["default_remove"] else "readonly")
        keep_combo.pack(side=tk.LEFT, padx=(0, 0))
        setattr(self, f"combo_keep_percentage_{config['var_name']}", keep_combo)
        
        # Inicializar estado del combobox
        self.toggle_keep_percentage_option(config['var_name'])


        return frame

    def create_jump_option_frame(self, parent, row):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), padx=(10, 0))

        self.remove_jumps = tk.BooleanVar(value=False)
        ttk.Checkbutton(frame, text="Eliminar saltos (notas simultáneas)",
                       variable=self.remove_jumps,
                       command=self.toggle_jump_options).pack(side=tk.LEFT)

        self.keep_some_jumps = tk.BooleanVar(value=False) # Este controla si se aplica el porcentaje
        self.jump_percentage_val = tk.IntVar(value=50) # Este es el valor del slider

        self.check_jumps_some = ttk.Checkbutton(frame, text="Dejar algunos:",
                                               variable=self.keep_some_jumps,
                                               state="normal" if self.remove_jumps.get() else "disabled",
                                               command=self.toggle_jump_slider_visibility) # Comando para mostrar/ocultar slider
        self.check_jumps_some.pack(side=tk.LEFT, padx=(10, 0))

        self.jump_scale = ttk.Scale(frame, from_=0, to=100, variable=self.jump_percentage_val,
                                   orient=tk.HORIZONTAL, length=100, state="disabled") # Inicia deshabilitado
        self.jump_scale.pack(side=tk.LEFT, padx=(5, 0))

        self.jump_label = ttk.Label(frame, text="50%", state="disabled") # Inicia deshabilitado
        self.jump_label.pack(side=tk.LEFT, padx=(5, 0))

        self.jump_percentage_val.trace_add('write', self.update_jump_label)
        self.toggle_jump_options() # Para setear estado inicial correcto
        self.toggle_jump_slider_visibility() # Para setear estado inicial correcto del slider/label

        return frame

    def toggle_keep_percentage_option(self, var_name):
        remove_var = getattr(self, f"remove_{var_name}")
        combo_widget = getattr(self, f"combo_keep_percentage_{var_name}")
        keep_percentage_var = getattr(self, f"keep_percentage_{var_name}")

        if remove_var.get():
            combo_widget.config(state="readonly")
        else:
            combo_widget.config(state="disabled")
            keep_percentage_var.set("0%") # Si no se eliminan, no se dejan algunas

    def toggle_jump_options(self):
        # Habilita/deshabilita el checkbox "Dejar algunos" para saltos
        if self.remove_jumps.get():
            self.check_jumps_some.config(state="normal")
        else:
            self.check_jumps_some.config(state="disabled")
            self.keep_some_jumps.set(False) # Si no se eliminan saltos, no se "dejan algunos"
        self.toggle_jump_slider_visibility() # Actualiza visibilidad del slider y label

    def toggle_jump_slider_visibility(self):
        # Muestra/oculta el slider y label de porcentaje de saltos
        # Solo se muestran si "Eliminar saltos" Y "Dejar algunos" están activos
        if self.remove_jumps.get() and self.keep_some_jumps.get():
            self.jump_scale.config(state="normal")
            self.jump_label.config(state="normal")
        else:
            self.jump_scale.config(state="disabled")
            self.jump_label.config(state="disabled")


    def update_jump_label(self, *args):
        self.jump_label.config(text=f"{self.jump_percentage_val.get()}%")

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)

        self.setup_file_selection(main_frame, 0)
        self.setup_chart_selection(main_frame, 1)
        self.setup_options(main_frame, 2)
        self.setup_buttons(main_frame, 3)
        self.setup_info_area(main_frame, 4)
        self.setup_debug_area(main_frame, 5)

    def setup_file_selection(self, parent, row):
        ttk.Label(parent, text="Archivo .sm:").grid(row=row, column=0, sticky=tk.W, pady=5)

        file_frame = ttk.Frame(parent)
        file_frame.grid(row=row, column=1, sticky=(tk.W, tk.E), pady=5)
        file_frame.columnconfigure(0, weight=1)

        self.file_var = tk.StringVar()
        self.file_entry = ttk.Entry(file_frame, textvariable=self.file_var, state="readonly")
        self.file_entry.grid(row=0, column=0, sticky=(tk.W, tk.E), padx=(0, 5))

        ttk.Button(file_frame, text="Examinar", command=self.browse_file).grid(row=0, column=1)

    def setup_chart_selection(self, parent, row):
        base_frame = ttk.LabelFrame(parent, text="Chart Base", padding="10")
        base_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        base_frame.columnconfigure(1, weight=1)

        ttk.Label(base_frame, text="Seleccionar chart base:").grid(row=0, column=0, sticky=tk.W)
        self.base_chart_var = tk.StringVar()
        self.base_chart_combo = ttk.Combobox(base_frame, textvariable=self.base_chart_var, state="readonly")
        self.base_chart_combo.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=5)

    def setup_options(self, parent, row):
        options_frame = ttk.LabelFrame(parent, text="Opciones de Simplificación", padding="10")
        options_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        options_frame.columnconfigure(1, weight=1)

        current_row = 0

        ttk.Label(options_frame, text="Eliminar notas rápidas:", font=('TkDefaultFont', 9, 'bold')).grid(
            row=current_row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        current_row += 1

        for config in self.note_options_config:
            self.create_note_option_frame(options_frame, current_row, config)
            current_row +=1

        ttk.Separator(options_frame, orient='horizontal').grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        current_row += 1

        ttk.Label(options_frame, text="Simplificar patrones:", font=('TkDefaultFont', 9, 'bold')).grid(
            row=current_row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        current_row += 1

        self.create_jump_option_frame(options_frame, current_row)
        current_row += 1

        self.simplify_holds = tk.BooleanVar(value=False)
        ttk.Checkbutton(options_frame, text="Convertir holds largos en notas normales",
                       variable=self.simplify_holds).grid(row=current_row, column=0, columnspan=2, sticky=tk.W, padx=(10, 0))
        current_row += 1

        ttk.Separator(options_frame, orient='horizontal').grid(row=current_row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        current_row += 1

        ttk.Label(options_frame, text="Nuevo chart:", font=('TkDefaultFont', 9, 'bold')).grid(
            row=current_row, column=0, columnspan=2, sticky=tk.W, pady=(0, 5))
        current_row += 1

        ttk.Label(options_frame, text="Nombre nueva dificultad:").grid(row=current_row, column=0, sticky=tk.W, padx=(10, 0))
        self.new_difficulty_name = tk.StringVar(value="Easy")
        ttk.Entry(options_frame, textvariable=self.new_difficulty_name, width=15).grid(row=current_row, column=1, sticky=tk.W, padx=5)

    def setup_buttons(self, parent, row):
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=row, column=0, columnspan=2, pady=10)

        # El botón de Analizar ya no es necesario aquí, se hace al cargar
        # ttk.Button(button_frame, text="Analizar Archivo", command=self.analyze_file).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Generar Versión Simplificada", command=self.generate_simplified).pack(side=tk.LEFT, padx=5)

    def setup_info_area(self, parent, row):
        info_frame = ttk.LabelFrame(parent, text="Información del Archivo", padding="10")
        info_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=10)
        info_frame.columnconfigure(0, weight=1)
        info_frame.rowconfigure(0, weight=1)
        parent.rowconfigure(row, weight=1)

        self.info_text = scrolledtext.ScrolledText(info_frame, height=10, width=70, wrap=tk.WORD) # wrap=tk.WORD
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

    def setup_debug_area(self, parent, row):
        debug_frame = ttk.LabelFrame(parent, text="Debug Output", padding="10")
        debug_frame.grid(row=row, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=10)
        debug_frame.columnconfigure(0, weight=1)

        self.debug_text = scrolledtext.ScrolledText(debug_frame, height=5, width=70, wrap=tk.WORD) # wrap=tk.WORD
        self.debug_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

    def browse_file(self):
        filename = filedialog.askopenfilename(
            title="Seleccionar archivo .sm",
            filetypes=[("StepMania files", "*.sm"), ("All files", "*.*")]
        )
        if filename:
            self.file_var.set(filename)
            self.current_file = filename
            self.analyze_file() # <--- ANÁLISIS AUTOMÁTICO

    def parse_sm_file(self, filepath: str) -> Dict:
        # Intenta con 'utf-8' primero, que es lo más común y robusto
        encodings_to_try = ['utf-8', 'cp1252', 'iso-8859-1', 'latin1']
        content = None
        
        for encoding in encodings_to_try:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    content = f.read()
                self.debug_print(f"Archivo leído exitosamente con encoding: {encoding}")
                break 
            except UnicodeDecodeError:
                self.debug_print(f"Fallo al leer con encoding: {encoding}")
                continue
            except Exception as e:
                self.debug_print(f"Error inesperado al abrir el archivo con {encoding}: {e}")
                continue
        
        if content is None:
            # Si todos fallan, intenta con errors='ignore' como último recurso
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                self.debug_print("Archivo leído con encoding utf-8 e ignorando errores.")
            except Exception as e:
                 messagebox.showerror("Error de Lectura", f"No se pudo leer el archivo '{os.path.basename(filepath)}' con los encodings probados.\n{e}")
                 return {}


        data = {}
        patterns = {
            'title': r'#TITLE:([^;]+);',
            'artist': r'#ARTIST:([^;]+);',
            'bpms': r'#BPMS:([^;]+);',
            'offset': r'#OFFSET:([^;]+);'
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            data[key] = match.group(1).strip() if match else 'Unknown'

        charts = []
        # Patrón mejorado para ser más tolerante con espacios y saltos de línea
        chart_pattern = r'#NOTES:\s*([^:]*):\s*([^:]*):\s*([^:]*):\s*([^:]*):\s*([^:]*):\s*([^;]+);'

        for match in re.finditer(chart_pattern, content, re.DOTALL | re.IGNORECASE):
            chart = {
                'type': match.group(1).strip(),
                'description': match.group(2).strip(),         # Author/Description
                'difficulty': match.group(3).strip(),        # Difficulty Name
                'level': match.group(4).strip(),             # Difficulty Meter
                'radar': match.group(5).strip().replace('\n','').replace('\r','').replace(' ',''), # Radar values
                'notes': match.group(6).strip()              # Note data
            }
            charts.append(chart)

        data['charts'] = charts
        data['original_content'] = content
        return data

    def analyze_file(self):
        if not self.current_file:
            # Esto no debería ocurrir si se llama desde browse_file, pero por si acaso
            messagebox.showerror("Error", "Por favor selecciona un archivo .sm primero")
            return
        
        self.info_text.delete(1.0, tk.END) # Limpiar info anterior
        self.debug_text.delete(1.0, tk.END) # Limpiar debug anterior
        self.base_chart_combo['values'] = [] # Limpiar combobox de charts
        self.base_chart_var.set("")

        try:
            self.debug_print(f"Analizando archivo: {self.current_file}")
            self.chart_data = self.parse_sm_file(self.current_file)
            if not self.chart_data: # Si parse_sm_file devolvió vacío por error
                return
            self.display_file_info()
            self.debug_print("Análisis completado.")
        except Exception as e:
            messagebox.showerror("Error", f"Error al analizar el archivo: {str(e)}")
            self.debug_print(f"Excepción en analyze_file: {str(e)}")


    def display_file_info(self):
        info = f"=== INFORMACIÓN DEL ARCHIVO ===\n"
        info += f"Título: {self.chart_data.get('title', 'N/A')}\n"
        info += f"Artista: {self.chart_data.get('artist', 'N/A')}\n"
        info += f"BPMs: {self.chart_data.get('bpms', 'N/A')}\n"
        info += f"Offset: {self.chart_data.get('offset', 'N/A')}\n\n"

        info += "=== CHARTS DISPONIBLES ===\n"
        chart_options = []

        if not self.chart_data.get('charts'):
            info += "No se encontraron charts válidos en el archivo.\n"
            self.debug_print("No se encontraron charts en los datos parseados.")
        else:
            for i, chart in enumerate(self.chart_data.get('charts', [])):
                chart_name = f"{chart.get('difficulty','UnknownDif')} (Lv.{chart.get('level','?')}) - {chart.get('description','NoDesc')}"
                chart_options.append(chart_name)

                info += f"{i+1}. {chart_name}\n"
                info += f"   Tipo: {chart.get('type','N/A')}\n"

                notes_analysis = self.analyze_notes_summary(chart['notes'])
                info += f"   Notas totales: {notes_analysis['total_notes']}\n"
                info += f"   Saltos: {notes_analysis['jumps']}\n"
                info += f"   Holds: {notes_analysis['holds']}\n"
                info += f"   Minas: {notes_analysis['mines']}\n"
                info += f"   Compases estimados: {notes_analysis['measures']}\n\n"


        self.base_chart_combo['values'] = chart_options
        if chart_options:
            self.base_chart_combo.current(0)
        else:
            self.base_chart_var.set("No hay charts disponibles")


        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, info)

    def analyze_notes_summary(self, notes_data: str) -> Dict:
        lines = [line.strip() for line in notes_data.split('\n') if line.strip()]

        total_notes = 0
        jumps = 0
        holds_start = 0 # '2'
        mines = 0
        measures = 0

        for line in lines:
            if line.startswith(','):
                measures += 1
                continue
            
            # Solo procesar líneas que parecen ser de notas (longitud y caracteres)
            if len(line) >= 4 and all(c in '01234MFLK' for c in line[:4].upper()): # Simplificado
                note_count_in_line = 0
                for char_idx, char_val in enumerate(line[:4]):
                    if char_val == '1': # Tap note
                        total_notes += 1
                        note_count_in_line +=1
                    elif char_val == '2': # Hold start
                        total_notes += 1
                        holds_start += 1
                        note_count_in_line +=1
                    elif char_val == '4': # Roll start (contar como hold)
                        total_notes += 1
                        holds_start += 1
                        note_count_in_line +=1
                    elif char_val.upper() == 'M': # Mine
                        mines +=1
                
                if note_count_in_line > 1:
                    jumps +=1
        
        return {
            'total_notes': total_notes,
            'jumps': jumps,
            'holds': holds_start,
            'mines': mines,
            'measures': measures
        }

    def calculate_difficulty_level(self, original_level: int, notes_removed_percentage: float) -> int:
        if not isinstance(original_level, int) or original_level < 1:
            original_level = 1 # Default a 1 si el original no es válido

        # Reducción más pronunciada si se quitan muchas notas, menos si se quitan pocas.
        # Por ejemplo, quitar 50% de notas podría reducir el nivel a la mitad.
        # Quitar 10% de notas podría reducir el nivel un 10-20%.
        difficulty_reduction_factor = notes_removed_percentage * 0.7 # Ajustar este factor según se vea
        
        new_level = original_level * (1 - difficulty_reduction_factor)
        
        # Asegurar que el nivel no baje de 1 y redondear
        new_level = max(1, round(new_level))
        
        return new_level

    def simplify_chart(self, chart: Dict) -> Dict:
        simplified_chart = copy.deepcopy(chart)
        notes_lines = chart['notes'].split('\n')

        simplified_lines = []
        current_measure_lines = []
        notes_removed_count = 0
        original_tap_and_hold_notes_count = 0 # Contar solo '1' y '2' para el % de reducción

        # Primera pasada para contar notas originales relevantes
        for line_idx, line_content in enumerate(notes_lines):
            stripped_line = line_content.strip()
            if stripped_line == ',':
                continue
            if len(stripped_line) >= 4 and self.is_valid_note_line(stripped_line):
                for char_note in stripped_line[:4]:
                    if char_note in '124': # Tap, Hold start, Roll start
                        original_tap_and_hold_notes_count += 1
        
        self.debug_print(f"Notas originales (tap/hold/roll): {original_tap_and_hold_notes_count}")


        for line in notes_lines:
            stripped_line = line.strip()
            if not stripped_line: # Línea vacía
                if current_measure_lines: # Procesar compás acumulado si existe
                    processed_measure, removed_in_measure = self.process_measure(current_measure_lines)
                    simplified_lines.extend(processed_measure)
                    notes_removed_count += removed_in_measure
                    current_measure_lines = []
                simplified_lines.append(line) # Añadir la línea vacía
                continue

            if stripped_line == ',':
                if current_measure_lines:
                    processed_measure, removed_in_measure = self.process_measure(current_measure_lines)
                    simplified_lines.extend(processed_measure)
                    notes_removed_count += removed_in_measure
                    current_measure_lines = []
                simplified_lines.append(line) # Añadir la coma
                continue

            if self.is_valid_note_line(stripped_line):
                current_measure_lines.append(line) # Usar línea original con sus espacios
            else: # Líneas que no son de notas (comentarios, etc.)
                if current_measure_lines: # Procesar compás acumulado si lo hubiera antes de esta línea no-nota
                    processed_measure, removed_in_measure = self.process_measure(current_measure_lines)
                    simplified_lines.extend(processed_measure)
                    notes_removed_count += removed_in_measure
                    current_measure_lines = []
                simplified_lines.append(line)


        if current_measure_lines: # Procesar el último compás si queda algo
            processed_measure, removed_in_measure = self.process_measure(current_measure_lines)
            simplified_lines.extend(processed_measure)
            notes_removed_count += removed_in_measure

        simplified_chart['notes'] = '\n'.join(simplified_lines)

        try:
            original_level = int(chart['level'])
        except ValueError:
            self.debug_print(f"Nivel original '{chart['level']}' no es un número. Usando 5 por defecto.")
            original_level = 5 # Default si el nivel no es un número

        notes_removed_percentage = 0
        if original_tap_and_hold_notes_count > 0:
            notes_removed_percentage = notes_removed_count / original_tap_and_hold_notes_count
        
        self.debug_print(f"Notas eliminadas: {notes_removed_count}")
        self.debug_print(f"Porcentaje de notas eliminadas: {notes_removed_percentage:.2%}")

        new_level = self.calculate_difficulty_level(original_level, notes_removed_percentage)

        simplified_chart['difficulty'] = self.new_difficulty_name.get()
        simplified_chart['level'] = str(new_level)
        
        base_desc = chart['description']
        if "(Simplified)" not in base_desc and "(Easy)" not in base_desc: # Evitar duplicados
             simplified_chart['description'] = f"{base_desc} ({self.new_difficulty_name.get()})"
        else: # Si ya tiene un tag de simplificación, lo reemplazamos o usamos el nuevo
            parts = re.split(r'\s*\(.*\)', base_desc) # Quitar el (tag) viejo
            simplified_chart['description'] = f"{parts[0].strip()} ({self.new_difficulty_name.get()})"


        return simplified_chart


    def is_valid_note_line(self, line: str) -> bool:
        # Una línea de nota válida tiene al menos 4 caracteres y esos son 0-4, M, F, L, K
        # (considerando mayúsculas para MFLK)
        if len(line) < 4:
            return False
        return all(c in '01234MFLK' for c in line[:4].upper())


    def process_measure(self, measure_lines: List[str]) -> Tuple[List[str], int]:
        if not measure_lines:
            return [], 0

        processed_lines = []
        notes_removed_in_measure = 0
        
        num_lines_in_measure = len(measure_lines)

        for i, original_line_text in enumerate(measure_lines):
            line_text = original_line_text.strip() # Trabajar con la línea sin espacios extra al inicio/fin
            
            # Mantener los espacios originales del inicio para el formato
            leading_whitespace = ""
            match_whitespace = re.match(r"(\s*)", original_line_text)
            if match_whitespace:
                leading_whitespace = match_whitespace.group(1)

            modified_line_chars = list(line_text[:4]) # Solo los primeros 4 caracteres para notas
            rest_of_line = line_text[4:] # Comentarios, etc.

            # 1. Detección de subdivisión y eliminación de notas rápidas
            subdivision = self.detect_note_subdivision_in_measure(i, num_lines_in_measure)
            
            option_var_name = None
            if subdivision == "24th+": option_var_name = "24th"
            elif subdivision == "16th": option_var_name = "16th"
            elif subdivision == "12th": option_var_name = "12th"
            elif subdivision == "8th": option_var_name = "8th"

            line_had_notes = any(c in '124' for c in modified_line_chars)

            if option_var_name:
                remove_this_subdivision = getattr(self, f"remove_{option_var_name}").get()
                if remove_this_subdivision:
                    keep_percentage_str = getattr(self, f"keep_percentage_{option_var_name}").get()
                    keep_percentage = float(keep_percentage_str.replace('%','')) / 100.0
                    
                    if random.random() >= keep_percentage: # Si random es MAYOR o IGUAL, se elimina
                        for k_idx, k_char in enumerate(modified_line_chars):
                            if k_char in '124': # Tap, Hold, Roll
                                modified_line_chars[k_idx] = '0'
                                notes_removed_in_measure += 1
                        # self.debug_print(f"L{i} ({subdivision}) eliminada (o parte), %keep: {keep_percentage_str}")
                    # else:
                        # self.debug_print(f"L{i} ({subdivision}) MANTENIDA por % ({keep_percentage_str})")


            # 2. Simplificación de saltos (después de posible eliminación por subdivisión)
            current_notes_in_line = sum(1 for char_note in modified_line_chars if char_note in '124')
            if current_notes_in_line > 1 and self.remove_jumps.get():
                # self.debug_print(f"Salto detectado en L{i}: {''.join(modified_line_chars)}")
                notes_indices_in_jump = [idx for idx, char_note in enumerate(modified_line_chars) if char_note in '124']
                
                notes_to_keep_count = 1 # Por defecto, dejar 1 nota de un salto
                if self.keep_some_jumps.get(): # Si el checkbox "Dejar algunos [saltos]" está activo
                    percentage_to_keep_jumps = self.jump_percentage_val.get() / 100.0
                    # self.debug_print(f"  Intentando mantener {percentage_to_keep_jumps*100}% de {current_notes_in_line} notas del salto")
                    notes_to_keep_count = max(1, int(round(len(notes_indices_in_jump) * percentage_to_keep_jumps)))
                
                # self.debug_print(f"  Original: {notes_indices_in_jump}, a mantener: {notes_to_keep_count}")
                
                # Mantener las primeras 'notes_to_keep_count' notas, eliminar el resto
                random.shuffle(notes_indices_in_jump) # Aleatorizar cuáles se quedan
                notes_to_remove_from_jump = notes_indices_in_jump[notes_to_keep_count:]

                for idx_to_remove in notes_to_remove_from_jump:
                    if modified_line_chars[idx_to_remove] in '124':
                        modified_line_chars[idx_to_remove] = '0'
                        notes_removed_in_measure += 1
                # self.debug_print(f"  Salto simplificado L{i}: {''.join(modified_line_chars)}")


            # 3. Simplificación de holds (después de todo lo anterior)
            if self.simplify_holds.get():
                for k_idx, k_char in enumerate(modified_line_chars):
                    if k_char == '2': # Inicio de Hold
                        modified_line_chars[k_idx] = '1' # Convertir a Tap
                        # No contamos esto como nota eliminada, es una conversión
                    elif k_char == '3': # Fin de Hold
                        modified_line_chars[k_idx] = '0' # Eliminar marcador de fin
                    elif k_char == '4': # Inicio de Roll
                         modified_line_chars[k_idx] = '1' # Convertir a Tap
                    # No se tocan 'L' (fin de roll) ya que no tienen valor numérico en StepMania y son más raros

            processed_lines.append(leading_whitespace + "".join(modified_line_chars) + rest_of_line)
        
        return processed_lines, notes_removed_in_measure


    def detect_note_subdivision_in_measure(self, line_index: int, total_lines_in_measure: int) -> str:
        """
        Detecta la subdivisión de una nota basada en su índice dentro del compás y el total de líneas.
        Esta es una heurística y puede no ser perfecta para todos los casos de BPM changes o time signatures.
        Asume que las líneas de notas están distribuidas uniformemente dentro del compás.
        """
        if total_lines_in_measure == 0: return "Unknown"

        # Casos comunes para 4/4 time signature
        if total_lines_in_measure % 48 == 0: # Probablemente 48ths (o 24ths si son pares)
            beat_division = 48
        elif total_lines_in_measure % 32 == 0: # Probablemente 32nds
            beat_division = 32
        elif total_lines_in_measure % 24 == 0: # Probablemente 24ths
            beat_division = 24
        elif total_lines_in_measure % 16 == 0: # Probablemente 16ths
            beat_division = 16
        elif total_lines_in_measure % 12 == 0: # Probablemente 12ths (triplets over 4th)
            beat_division = 12
        elif total_lines_in_measure % 8 == 0:  # Probablemente 8ths
            beat_division = 8
        elif total_lines_in_measure % 6 == 0: # Probablemente 6ths (triplets over 8th, raro pero posible)
             beat_division = 6
        elif total_lines_in_measure % 4 == 0:  # Probablemente 4ths
            beat_division = 4
        elif total_lines_in_measure % 3 == 0 and total_lines_in_measure <= 12 : # Podría ser un compás de 3/4 en 4ths, o 4/4 en 3 notas por alguna razón
            beat_division = total_lines_in_measure # ej. 3 notas: 3rd, 6 notas: 6th
        elif total_lines_in_measure % 2 == 0 and total_lines_in_measure <= 8:
            beat_division = total_lines_in_measure
        else: # Casos menos comunes o compases con pocas notas
            if total_lines_in_measure > 16 : return "24th+" # Si hay muchas, default a muy rápidas
            if total_lines_in_measure > 12 : return "16th"
            if total_lines_in_measure > 8 : return "12th"
            if total_lines_in_measure > 4 : return "8th"
            return "4th"

        # Simplificación de la lógica de subdivisión
        # El `line_index` nos dice en qué "slot" de la subdivisión más fina cae esta línea.
        # Si `total_lines_in_measure` es 16 (16ths), y `line_index` es 0, 4, 8, 12, es un 4th.
        # Si es 2, 6, 10, 14, es un 8th (pero no 4th).
        # El resto son 16ths.

        if line_index % (beat_division / 4) == 0: return "4th"
        if beat_division >= 8 and line_index % (beat_division / 8) == 0: return "8th"
        if beat_division >= 12 and line_index % (beat_division / 12) == 0: return "12th"
        if beat_division >= 16 and line_index % (beat_division / 16) == 0: return "16th"
        if beat_division >= 24 : return "24th+" # Cubre 24th, 32nd, 48th, etc.
        
        return "Unknown" # Default por si acaso


    def debug_print(self, message):
        if hasattr(self, 'debug_text') and self.debug_text:
            try:
                self.debug_text.insert(tk.END, f"{message}\n")
                self.debug_text.see(tk.END)
                self.root.update_idletasks() # Forzar actualización de la UI
            except tk.TclError: # En caso de que el widget ya no exista (ej. al cerrar)
                pass
            print(f"DEBUG: {message}") # También imprimir a consola


    def remove_jump_notes(self, line: str) -> str:
        # Esta función ya no se usa directamente, su lógica está en process_measure
        # Se deja aquí por si se quiere reusar o como referencia, pero no es llamada.
        if len(line) < 4:
            return line

        chars = list(line)
        jump_notes_indices = [i for i, char_note in enumerate(chars[:4]) if char_note in '124']

        if len(jump_notes_indices) > 1: # Es un salto
            if self.remove_jumps.get(): # Si la opción general de eliminar saltos está activa
                notes_to_keep_count = 1 # Por defecto, dejar 1 nota
                
                if self.keep_some_jumps.get(): # Si el checkbox "Dejar algunos [saltos]" está activo
                    percentage_to_keep = self.jump_percentage_val.get() / 100.0
                    notes_to_keep_count = max(1, int(round(len(jump_notes_indices) * percentage_to_keep)))

                # Aleatorizar y seleccionar las notas a mantener
                random.shuffle(jump_notes_indices)
                notes_to_remove_indices = jump_notes_indices[notes_to_keep_count:]
                
                for idx_to_remove in notes_to_remove_indices:
                    chars[idx_to_remove] = '0'
        
        return "".join(chars)


    def simplify_hold_notes(self, line: str) -> str:
         # Esta función ya no se usa directamente, su lógica está en process_measure
        modified_line = list(line)
        for i, char_val in enumerate(modified_line[:4]):
            if char_val == '2': # Hold Start
                modified_line[i] = '1'
            elif char_val == '3': # Hold End
                modified_line[i] = '0'
            elif char_val == '4': # Roll Start
                modified_line[i] = '1'
        return "".join(modified_line)


    def generate_simplified(self):
        if not self.chart_data or not self.chart_data.get('charts'):
            messagebox.showerror("Error", "Por favor carga y analiza un archivo primero, o el archivo no contiene charts.")
            return

        if not self.base_chart_var.get() or "No hay charts" in self.base_chart_var.get():
            messagebox.showerror("Error", "Por favor selecciona un chart base válido.")
            return

        try:
            selected_index = self.base_chart_combo.current()
            if selected_index < 0 or selected_index >= len(self.chart_data['charts']):
                messagebox.showerror("Error", "Chart seleccionado no válido. Intenta recargar el archivo.")
                return

            base_chart = self.chart_data['charts'][selected_index]
            self.debug_print(f"Generando versión simplificada para: {base_chart.get('difficulty')} (Lv.{base_chart.get('level')})")

            simplified_chart = self.simplify_chart(base_chart)

            # Contar notas '1' (tap) en el chart simplificado para una verificación rápida
            simplified_tap_notes_count = 0
            for line_s in simplified_chart['notes'].split('\n'):
                if self.is_valid_note_line(line_s.strip()):
                    for char_s in line_s.strip()[:4]:
                        if char_s == '1':
                            simplified_tap_notes_count +=1
            
            self.debug_print(f"Chart simplificado: {simplified_tap_notes_count} notas '1' (tap) finales.")
            self.debug_print(f"Nivel original: {base_chart['level']}, Nivel calculado: {simplified_chart['level']}")

            if simplified_tap_notes_count == 0: # Chequeo más específico
                if not messagebox.askyesno("Advertencia",
                    "El chart simplificado no tiene notas '1' (tap notes).\n"
                    "Esto puede resultar en un chart vacío o no jugable.\n"
                    "¿Deseas generarlo de todas formas?"):
                    self.debug_print("Generación cancelada por el usuario debido a 0 notas tap.")
                    return

            new_content = self.chart_data['original_content']

            # Asegurarse de que el nuevo bloque de notas se añade al final del archivo
            if not new_content.endswith('\n\n'):
                if new_content.endswith('\n'):
                    new_content += '\n'
                else:
                    new_content += '\n\n'
            
            # Formato del bloque de notas
            # //---------------dance-single - [Simplificado (Easy)]----------------
            comment_desc = simplified_chart['description'].replace(':','-') # Evitar problemas con ':' en comentarios
            comment = f"//---------------{simplified_chart['type']} - {comment_desc}----------------\n"

            new_notes_block = comment
            new_notes_block += "#NOTES:\n"
            new_notes_block += f"     {simplified_chart['type']}:\n"
            new_notes_block += f"     {simplified_chart['description']}:\n" # Ya incluye el (Simplified) o (Easy)
            new_notes_block += f"     {simplified_chart['difficulty']}:\n"
            new_notes_block += f"     {simplified_chart['level']}:\n"
            new_notes_block += f"     {simplified_chart['radar']}:\n" # Usar el radar original
            new_notes_block += f"{simplified_chart['notes']};\n\n"

            new_content += new_notes_block

            original_path = self.current_file
            base_name = os.path.splitext(original_path)[0]
            
            # Construir nombre de archivo con tag de dificultad si es posible
            difficulty_tag = self.new_difficulty_name.get().replace(" ", "_")
            new_path = f"{base_name}_{difficulty_tag}_simplified.sm"
            
            # Intentar guardar con el encoding original si es conocido, sino utf-8
            source_encoding = 'utf-8' # Default
            # (No tenemos una forma fácil de saber el encoding original exacto después de leerlo)

            with open(new_path, 'w', encoding=source_encoding, errors='ignore') as f:
                f.write(new_content)

            messagebox.showinfo("Éxito", f"Archivo simplificado guardado como:\n{new_path}")
            self.debug_print(f"Archivo simplificado guardado en: {new_path}")

        except Exception as e:
            messagebox.showerror("Error", f"Error al generar archivo simplificado: {str(e)}")
            self.debug_print(f"Excepción en generate_simplified: {str(e)}")
            import traceback
            self.debug_print(traceback.format_exc())


def main():
    root = tk.Tk()
    app = StepManiaSimplifier(root)
    root.mainloop()

if __name__ == "__main__":
    main()
