#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import requests
from datetime import datetime
import threading
import os
import base64
import email
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import mailbox
import time
import webbrowser
from urllib.parse import urlencode, parse_qs
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import json
import re

CLIENT_ID = "your_client_id"
TENANT_ID = "your_tenant_id"
CLIENT_SECRET = "your_client_secret"

class OutlookBackup:
	def __init__(self, root):
		self.root = root
		self.root.title("Mail Backup - Microsoft Graph API")
		self.root.geometry("1000x850")
		
		# Variables
		self.access_token = None
		self.refresh_token = None
		self.user_email = None
		self.output_folder = None
		self.is_running = False
		self.auth_code = None
		
		# Configuración API
		self.auth_method = tk.StringVar(value="interactive")
		self.CLIENT_ID = CLIENT_ID
		self.TENANT_ID = TENANT_ID
		self.CLIENT_SECRET = CLIENT_SECRET
		
		# Estadísticas
		self.total_emails = 0
		self.downloaded_emails = 0
		self.failed_emails = 0
		
		self.setup_ui()
		
	def setup_ui(self):
		# Frame principal
		main_frame = ttk.Frame(self.root, padding="10")
		main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
		
		# 0. Selección de método de autenticación
		ttk.Label(main_frame, text="0. Authentication method:", font=('Arial', 10, 'bold')).grid(
			row=0, column=0, sticky=tk.W, pady=(0,5))
		
		auth_frame = ttk.LabelFrame(main_frame, text="Choose method", padding="10")
		auth_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0,15))
		
		# Left side: Radio buttons
		rb_frame = ttk.Frame(auth_frame)
		rb_frame.grid(row=0, column=0, sticky=tk.NW, padx=(0, 20))
		
		ttk.Radiobutton(rb_frame, text="Interactive Login (OAuth2)", 
					   variable=self.auth_method, value="interactive", 
					   command=self._update_auth_ui).grid(row=0, column=0, sticky=tk.W, pady=5)
		ttk.Radiobutton(rb_frame, text="Service Account (Client Credentials)", 
					   variable=self.auth_method, value="service", 
					   command=self._update_auth_ui).grid(row=1, column=0, sticky=tk.W, pady=5)
		
		# Right side: Service credentials frame (visible only if service account is selected)
		self.service_frame = ttk.LabelFrame(auth_frame, text="Application Credentials", padding="10")
		self.service_frame.grid(row=0, column=1, sticky=(tk.W, tk.E, tk.N, tk.S))
		
		ttk.Label(self.service_frame, text="Client ID:").grid(row=0, column=0, sticky=tk.W, padx=(0,10))
		self.client_id_entry = ttk.Entry(self.service_frame, width=50)
		self.client_id_entry.grid(row=0, column=1, sticky=(tk.W, tk.E))
		self.client_id_entry.insert(0, CLIENT_ID)
		
		ttk.Label(self.service_frame, text="Tenant ID:").grid(row=1, column=0, sticky=tk.W, padx=(0,10), pady=(5,0))
		self.tenant_id_entry = ttk.Entry(self.service_frame, width=50)
		self.tenant_id_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), pady=(5,0))
		self.tenant_id_entry.insert(0, TENANT_ID)
		
		ttk.Label(self.service_frame, text="Client Secret:").grid(row=2, column=0, sticky=tk.W, padx=(0,10), pady=(5,0))
		self.client_secret_entry = ttk.Entry(self.service_frame, width=50, show="*")
		self.client_secret_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), pady=(5,0))
		self.client_secret_entry.insert(0, CLIENT_SECRET)
		
		# 1. Configuración de cuenta
		ttk.Label(main_frame, text="1. Account Configuration:", font=('Arial', 10, 'bold')).grid(
			row=2, column=0, sticky=tk.W, pady=(15,5))
		
		account_frame = ttk.Frame(main_frame)
		account_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0,15))
		
		ttk.Label(account_frame, text="Email address:").grid(row=0, column=0, sticky=tk.W, padx=(0,10))
		self.email_entry = ttk.Entry(account_frame, width=40)
		self.email_entry.grid(row=0, column=1, sticky=tk.W)
		self.email_entry.insert(0, "email@example.com")
		
		ttk.Button(account_frame, text="Connect", command=self.connect_account).grid(
			row=0, column=2, padx=(10,0))
		
		self.connection_label = ttk.Label(account_frame, text="Not connected", foreground="red")
		self.connection_label.grid(row=0, column=3, padx=(10,0))
		
		# 2. Opciones de exportación
		ttk.Label(main_frame, text="2. Export Options:", font=('Arial', 10, 'bold')).grid(
			row=4, column=0, sticky=tk.W, pady=(15,5))
		
		options_frame = ttk.LabelFrame(main_frame, text="Export Options", padding="10")
		options_frame.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0,15))
		
		# Format block (Left)
		format_block = ttk.Frame(options_frame)
		format_block.grid(row=0, column=0, sticky=tk.NW, padx=(0, 20))
		
		self.export_format = tk.StringVar(value="mbox")
		ttk.Radiobutton(format_block, text="MBOX (single file, compatible with Thunderbird/Outlook)", 
					   variable=self.export_format, value="mbox").grid(row=0, column=0, sticky=tk.W, pady=2)
		ttk.Radiobutton(format_block, text="EML (individual files per email)", 
					   variable=self.export_format, value="eml").grid(row=1, column=0, sticky=tk.W, pady=2)
		ttk.Radiobutton(format_block, text="Both formats", 
					   variable=self.export_format, value="both").grid(row=2, column=0, sticky=tk.W, pady=2)
		
		# Additional options block (Right)
		misc_block = ttk.Frame(options_frame)
		misc_block.grid(row=0, column=1, sticky=tk.NW, padx=(10, 0))
		
		self.include_attachments = tk.BooleanVar(value=True)
		ttk.Checkbutton(misc_block, text="Include attachments", 
					   variable=self.include_attachments).grid(row=0, column=0, sticky=tk.W, pady=2)
		
		self.include_folders = tk.BooleanVar(value=True)
		ttk.Checkbutton(misc_block, text="Keep folder structure", 
					   variable=self.include_folders).grid(row=1, column=0, sticky=tk.W, pady=2)
		
		# 3. Carpeta de destino
		ttk.Label(main_frame, text="3. Destination folder:", font=('Arial', 10, 'bold')).grid(
			row=6, column=0, sticky=tk.W, pady=(15,5))
		
		folder_frame = ttk.Frame(main_frame)
		folder_frame.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0,15))
		
		self.folder_label = ttk.Label(folder_frame, text="No folder selected", foreground="gray")
		self.folder_label.pack(side=tk.LEFT, padx=(0,10))
		
		ttk.Button(folder_frame, text="Select folder...", command=self.select_output_folder).pack(side=tk.LEFT)
		
		# 4. Botón de inicio
		button_frame = ttk.Frame(main_frame)
		button_frame.grid(row=8, column=0, columnspan=3, pady=(10,15))
		
		self.start_button = ttk.Button(button_frame, text="START BACKUP", 
									   command=self.start_backup, state="disabled")
		self.start_button.pack(side=tk.LEFT, padx=5)
		
		self.stop_button = ttk.Button(button_frame, text="STOP", 
									  command=self.stop_backup, state="disabled")
		self.stop_button.pack(side=tk.LEFT, padx=5)
		
		# 5. Progreso
		ttk.Label(main_frame, text="Progress:", font=('Arial', 10, 'bold')).grid(
			row=9, column=0, sticky=tk.W, pady=(0,5))
		
		self.progress = ttk.Progressbar(main_frame, mode='determinate', length=400)
		self.progress.grid(row=10, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0,5))
		
		self.progress_label = ttk.Label(main_frame, text="0 / 0 emails downloaded")
		self.progress_label.grid(row=11, column=0, columnspan=3, sticky=tk.W, pady=(0,15))
		
		# 6. Log
		ttk.Label(main_frame, text="Log:", font=('Arial', 10, 'bold')).grid(
			row=12, column=0, sticky=tk.W, pady=(0,5))
		
		self.log_text = scrolledtext.ScrolledText(main_frame, height=10, width=100, state="disabled")
		self.log_text.grid(row=13, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0,10))
		
		# Configurar expansión
		self.root.columnconfigure(0, weight=1)
		self.root.rowconfigure(0, weight=1)
		main_frame.columnconfigure(0, weight=1)
		main_frame.columnconfigure(1, weight=1)
		
		# Mostrar/ocultar frame de credenciales
		self._update_auth_ui()
	
	def _update_auth_ui(self):
		"""Muestra u oculta el frame de credenciales según el método seleccionado"""
		if self.auth_method.get() == "service":
			self.service_frame.grid()
		else:
			self.service_frame.grid_remove()
		
	def log_message(self, message):
		"""Añade un mensaje al log"""
		self.log_text.config(state="normal")
		self.log_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n")
		self.log_text.see(tk.END)
		self.log_text.config(state="disabled")
		self.root.update()
		
	def get_access_token(self):
		"""Obtiene el access token según el método de autenticación seleccionado"""
		if self.auth_method.get() == "interactive":
			return self._get_token_interactive()
		else:
			return self._get_token_client_credentials()
	
	def _get_token_client_credentials(self):
		"""Obtiene el access token usando Client Credentials"""
		client_id = self.client_id_entry.get().strip()
		tenant_id = self.tenant_id_entry.get().strip()
		client_secret = self.client_secret_entry.get().strip()
		
		if not all([client_id, tenant_id, client_secret]):
			raise ValueError("Client ID, Tenant ID and Client Secret are required")
		
		url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
		
		data = {
			'client_id': client_id,
			'client_secret': client_secret,
			'scope': 'https://graph.microsoft.com/.default',
			'grant_type': 'client_credentials'
		}
		
		response = requests.post(url, data=data)
		response.raise_for_status()
		
		return response.json()['access_token']
	
	def _get_token_interactive(self):
		"""Obtiene el access token usando Authorization Code Flow"""
		# Pedir Client ID y Tenant ID
		dialog = tk.Toplevel(self.root)
		dialog.title("Application Credentials")
		dialog.geometry("500x220")
		dialog.transient(self.root)
		dialog.grab_set()
		
		dialog.columnconfigure(1, weight=1)
		
		ttk.Label(dialog, text="For interactive login you need:", font=('Arial', 10, 'bold')).grid(row=0, column=0, columnspan=2, pady=(15, 5))
		ttk.Label(dialog, text="Enter your registered application data:").grid(row=1, column=0, columnspan=2, pady=(0, 10))
		
		ttk.Label(dialog, text="Client ID:").grid(row=2, column=0, sticky=tk.E, padx=(20, 10), pady=5)
		client_id_entry = ttk.Entry(dialog, width=50)
		client_id_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 20), pady=5)
		
		ttk.Label(dialog, text="Tenant ID:").grid(row=3, column=0, sticky=tk.E, padx=(20, 10), pady=5)
		tenant_id_entry = ttk.Entry(dialog, width=50)
		tenant_id_entry.grid(row=3, column=1, sticky=(tk.W, tk.E), padx=(0, 20), pady=5)
		
		ttk.Label(dialog, text="Redirect URI:").grid(row=4, column=0, sticky=tk.E, padx=(20, 10), pady=5)
		redirect_uri_entry = ttk.Entry(dialog, width=50)
		redirect_uri_entry.insert(0, "http://localhost:8000")
		redirect_uri_entry.grid(row=4, column=1, sticky=(tk.W, tk.E), padx=(0, 20), pady=5)
		
		result = {"ok": False}
		
		def on_ok():
			result["client_id"] = client_id_entry.get().strip()
			result["tenant_id"] = tenant_id_entry.get().strip()
			result["redirect_uri"] = redirect_uri_entry.get().strip()
			if all([result["client_id"], result["tenant_id"], result["redirect_uri"]]):
				result["ok"] = True
				dialog.destroy()
			else:
				messagebox.showwarning("Error", "All fields are required", parent=dialog)
		
		ttk.Button(dialog, text="Continue", command=on_ok).grid(row=5, column=0, columnspan=2, pady=15)
		
		self.root.wait_window(dialog)
		
		if not result["ok"]:
			raise ValueError("Interactive login was cancelled")
		
		client_id = result["client_id"]
		tenant_id = result["tenant_id"]
		redirect_uri = result["redirect_uri"]
		
		self.log_message("Starting interactive login in browser...")
		
		# Generar auth URL
		auth_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/authorize"
		params = {
			'client_id': client_id,
			'redirect_uri': redirect_uri,
			'scope': 'Mail.Read Mail.ReadWrite offline_access',
			'response_type': 'code',
			'prompt': 'login'
		}
		
		full_auth_url = auth_url + '?' + urlencode(params)
		
		# Abrir navegador
		webbrowser.open(full_auth_url)
		
		# Iniciar servidor local para capturar el código
		self.log_message("Waiting for browser response...")
		auth_code = self._start_callback_server(redirect_uri)
		
		if not auth_code:
			raise ValueError("No authorization code received")
		
		# Intercambiar código por token
		token_url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
		token_data = {
			'client_id': client_id,
			'code': auth_code,
			'redirect_uri': redirect_uri,
			'scope': 'Mail.Read Mail.ReadWrite offline_access',
			'grant_type': 'authorization_code'
		}
		
		response = requests.post(token_url, data=token_data)
		response.raise_for_status()
		
		response_json = response.json()
		self.refresh_token = response_json.get('refresh_token')
		
		return response_json['access_token']
	
	def _start_callback_server(self, redirect_uri):
		"""Inicia un servidor local para capturar el código de autorización"""
		port = int(redirect_uri.split(':')[-1])
		auth_code_holder = {"code": None}
		
		class CallbackHandler(BaseHTTPRequestHandler):
			def do_GET(handler_self):
				# Parsear la query string
				query = handler_self.path.split('?')[1] if '?' in handler_self.path else ""
				params = parse_qs(query)
				
				if 'code' in params:
					auth_code_holder["code"] = params['code'][0]
					handler_self.send_response(200)
					handler_self.send_header('Content-type', 'text/html; charset=utf-8')
					handler_self.end_headers()
					html = """
					<html>
						<head><title>Authentication completed</title></head>
						<body style="font-family: Arial;">
							<h2>&#10003; Authentication completed</h2>
							<p>You can close this window and return to the application.</p>
						</body>
					</html>
					"""
					handler_self.wfile.write(html.encode())
				elif 'error' in params:
					handler_self.send_response(400)
					handler_self.send_header('Content-type', 'text/html; charset=utf-8')
					handler_self.end_headers()
					error_desc = params.get('error_description', [''])[0]
					html = f"""
					<html>
						<head><title>Authentication Error</title></head>
						<body style="font-family: Arial;">
							<h2>Error: {params['error'][0]}</h2>
							<p>{error_desc}</p>
						</body>
					</html>
					"""
					handler_self.wfile.write(html.encode())
				
			def log_message(handler_self, format, *args):
				pass  # Suprimir logs del servidor
		
		try:
			server = HTTPServer(('localhost', port), CallbackHandler)
			server.timeout = 120  # Esperar máximo 2 minutos
			
			while auth_code_holder["code"] is None:
				server.handle_request()
				if not server.timeout:
					break
			
			return auth_code_holder["code"]
		
		except Exception as e:
			self.log_message(f"Error in callback server: {str(e)}")
			return None
		
		finally:
			try:
				server.server_close()
			except:
				pass

	def _make_api_request(self, url, method='GET', **kwargs):
		"""Realiza una petición a la API con renovación automática de token"""
		max_retries = 2
		
		for attempt in range(max_retries):
			headers = kwargs.get('headers', {})
			headers['Authorization'] = f'Bearer {self.access_token}'
			kwargs['headers'] = headers
			
			if method == 'GET':
				response = requests.get(url, **kwargs)
			else:
				response = requests.post(url, **kwargs)
			
			# Si es 401, renovar token y reintentar
			if response.status_code == 401 and attempt < max_retries - 1:
				self.log_message("⚠ Token expired, renewing...")
				if self.auth_method.get() == "interactive" and self.refresh_token:
					self.access_token = self._refresh_access_token()
				else:
					self.access_token = self.get_access_token()
				continue
			
			response.raise_for_status()
			return response
		
		return response
	
	def _refresh_access_token(self):
		"""Refresca el access token usando el refresh token (para flujo interactivo)"""
		# Mostrar diálogo para obtener credenciales nuevamente ya que no tenemos el refresh token almacenado
		# En producción, estos datos deberían almacenarse de forma segura
		dialog = tk.Toplevel(self.root)
		dialog.title("Application Credentials")
		dialog.geometry("550x200")
		dialog.transient(self.root)
		dialog.grab_set()
		
		dialog.columnconfigure(1, weight=1)
		
		ttk.Label(dialog, text="Credentials are needed to renew the token:").grid(row=0, column=0, columnspan=2, pady=10)
		
		ttk.Label(dialog, text="Client ID:").grid(row=1, column=0, sticky=tk.E, padx=(20, 10), pady=5)
		client_id_entry = ttk.Entry(dialog, width=50)
		client_id_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 20), pady=5)
		
		ttk.Label(dialog, text="Tenant ID:").grid(row=2, column=0, sticky=tk.E, padx=(20, 10), pady=5)
		tenant_id_entry = ttk.Entry(dialog, width=50)
		tenant_id_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(0, 20), pady=5)
		
		result = {"ok": False}
		
		def on_ok():
			result["client_id"] = client_id_entry.get().strip()
			result["tenant_id"] = tenant_id_entry.get().strip()
			result["redirect_uri"] = "http://localhost:8000"
			if result["client_id"] and result["tenant_id"]:
				result["ok"] = True
				dialog.destroy()
			else:
				messagebox.showwarning("Error", "All fields are required", parent=dialog)
		
		ttk.Button(dialog, text="Renew", command=on_ok).grid(row=3, column=0, columnspan=2, pady=15)
		
		self.root.wait_window(dialog)
		
		if not result["ok"]:
			raise ValueError("Token renewal was cancelled")
		
		token_url = f"https://login.microsoftonline.com/{result['tenant_id']}/oauth2/v2.0/token"
		token_data = {
			'client_id': result["client_id"],
			'refresh_token': self.refresh_token,
			'grant_type': 'refresh_token',
			'scope': 'Mail.Read Mail.ReadWrite offline_access'
		}
		
		response = requests.post(token_url, data=token_data)
		response.raise_for_status()
		
		response_json = response.json()
		if 'refresh_token' in response_json:
			self.refresh_token = response_json['refresh_token']
		
		return response_json['access_token']
	
	def connect_account(self):
		"""Conecta con la cuenta de Outlook"""
		self.user_email = self.email_entry.get().strip()
		
		if not self.user_email:
			messagebox.showwarning("Warning", "Please enter an email address")
			return
		
		try:
			self.log_message("Obtaining access token...")
			self.access_token = self.get_access_token()
			self.log_message("✓ Token obtained successfully")
			
			# Verificar acceso a la cuenta
			headers = {'Authorization': f'Bearer {self.access_token}'}
			url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/mailFolders"
			response = self._make_api_request(url)
			
			self.connection_label.config(text="✓ Connected", foreground="green")
			self.log_message(f"✓ Connected to {self.user_email}")
			
			# Contar correos totales
			self.count_total_emails()
			
		except Exception as e:
			messagebox.showerror("Error", f"Error connecting:\n{str(e)}")
			self.log_message(f"❌ Error: {str(e)}")
			self.connection_label.config(text="✗ Error", foreground="red")
	
	def count_total_emails(self):
		"""Cuenta el total de correos en la cuenta"""
		try:
			headers = {'Authorization': f'Bearer {self.access_token}'}
			url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages/$count"
			response = self._make_api_request(url)
			
			self.total_emails = int(response.text)
			self.log_message(f"Total emails found: {self.total_emails}")
			self.progress_label.config(text=f"0 / {self.total_emails} emails downloaded")
			
			if self.output_folder:
				self.start_button.config(state="normal")
				
		except Exception as e:
			self.log_message(f"⚠ Could not count emails: {str(e)}")
	
	def select_output_folder(self):
		"""Selecciona la carpeta de destino"""
		folder = filedialog.askdirectory(title="Select destination folder")
		
		if folder:
			self.output_folder = folder
			self.folder_label.config(text=folder, foreground="black")
			self.log_message(f"Destination folder: {folder}")
			
			if self.access_token:
				self.start_button.config(state="normal")
	
	def start_backup(self):
		"""Inicia el proceso de backup"""
		if not self.access_token or not self.output_folder:
			messagebox.showerror("Error", "You must connect the account and select a destination folder")
			return
		
		# Confirmar
		if not messagebox.askyesno("Confirm", 
								   f"Start backup of {self.total_emails} emails?\n\n"
								   f"This may take several minutes."):
			return
		
		# Deshabilitar controles
		self.start_button.config(state="disabled")
		self.stop_button.config(state="normal")
		self.is_running = True
		
		# Resetear contadores
		self.downloaded_emails = 0
		self.failed_emails = 0
		
		# Iniciar en thread separado
		thread = threading.Thread(target=self._do_backup)
		thread.daemon = True
		thread.start()
	
	def stop_backup(self):
		"""Detiene el proceso de backup"""
		self.is_running = False
		self.log_message("⚠ Stopping backup...")
		self.stop_button.config(state="disabled")
	
	def _do_backup(self):
		"""Realiza el backup en un thread separado"""
		try:
			self.log_message("="*60)
			self.log_message("STARTING BACKUP")
			self.log_message(f"Account: {self.user_email}")
			self.log_message(f"Format: {self.export_format.get()}")
			self.log_message(f"Attachments: {'Yes' if self.include_attachments.get() else 'No'}")
			self.log_message("="*60)
			
			# Crear estructura de carpetas
			timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
			embkuptxt = str(self.user_email).replace("@","_").replace(".","_")
			backup_folder = os.path.join(self.output_folder, f"outlook_backup_{embkuptxt}_{timestamp}")
			os.makedirs(backup_folder, exist_ok=True)
			
			# No inicializar MBOX aquí, se creará uno por carpeta
			formato = self.export_format.get()
			self.log_message(f"Selected format: '{formato}'")
			
			# Obtener todas las carpetas de correo
			folders = self._get_all_folders()
			self.log_message(f"Folders found: {len(folders)}")
			
			# Descargar correos de cada carpeta
			for folder in folders:
				if not self.is_running:
					break
					
				folder_name = folder['displayName']
				folder_id = folder['id']
				
				self.log_message(f"\n📁 Processing folder: {folder_name}")
				
				# Crear subcarpeta si es necesario
				if self.export_format.get() in ["eml", "both"] and self.include_folders.get():
					folder_path = os.path.join(backup_folder, self._sanitize_filename(folder_name))
					os.makedirs(folder_path, exist_ok=True)
				else:
					folder_path = backup_folder
				
				# Descargar correos de cada carpeta
				folder_downloaded, folder_failed = self._download_folder_emails(folder_id, folder_name, folder_path, backup_folder)
				self.log_message(f"   📊 Folder summary '{folder_name}': ✓ {folder_downloaded} downloaded | ❌ {folder_failed} errors")
			
			# Resumen final
			self.log_message("="*60)
			self.log_message("BACKUP COMPLETED")
			self.log_message(f"✓ Emails downloaded: {self.downloaded_emails}")
			self.log_message(f"❌ Errors: {self.failed_emails}")
			self.log_message(f"📁 Location: {backup_folder}")
			self.log_message("="*60)
			
			self.root.after(0, lambda: messagebox.showinfo("Backup completed", 
						   f"Backup finished:\n\n"
						   f"✓ Downloaded: {self.downloaded_emails}\n"
						   f"❌ Errors: {self.failed_emails}\n\n"
						   f"Location: {backup_folder}"))
			
		except Exception as e:
			self.log_message(f"❌ Critical error: {str(e)}")
			self.root.after(0, lambda: messagebox.showerror("Error", f"Error during backup:\n{str(e)}"))
		
		finally:
			self.is_running = False
			self.start_button.config(state="normal")
			self.stop_button.config(state="disabled")
	
	def _get_all_folders(self):
		"""Obtiene todas las carpetas de correo recursivamente, con paginación"""
		folders = []
		visited_ids = set()
		pages_scanned = 0
		start_scan = time.time()
		self.log_message("🔎 Scanning mailbox folders...")

		def get_folders_recursive(parent_id=None):
			nonlocal pages_scanned
			if parent_id:
				url = (
					f"https://graph.microsoft.com/v1.0/users/{self.user_email}/mailFolders/"
					f"{parent_id}/childFolders?$top=100&includeHiddenFolders=true"
				)
			else:
				url = (
					f"https://graph.microsoft.com/v1.0/users/{self.user_email}/mailFolders"
					"?$top=100&includeHiddenFolders=true"
				)

			while url and self.is_running:
				response = self._make_api_request(url)
				data = response.json()
				folder_list = data.get('value', [])
				pages_scanned += 1

				if pages_scanned % 25 == 0:
					elapsed = int(time.time() - start_scan)
					self.log_message(
						f"   🔄 Scan in progress: {len(folders)} folders found, {pages_scanned} API pages, {elapsed}s"
					)

				for folder in folder_list:
					folder_id = folder.get('id')
					if not folder_id or folder_id in visited_ids:
						continue

					visited_ids.add(folder_id)
					folders.append(folder)

					if len(folders) % 250 == 0:
						elapsed = int(time.time() - start_scan)
						self.log_message(
							f"   📁 {len(folders)} folders found so far ({elapsed}s)"
						)

					# Recursivamente obtener subcarpetas
					get_folders_recursive(folder_id)

				url = data.get('@odata.nextLink')

		get_folders_recursive()
		elapsed = int(time.time() - start_scan)
		self.log_message(f"✅ Folder scan completed: {len(folders)} folders in {elapsed}s")
		return folders
	
	def _download_folder_emails(self, folder_id, folder_name, folder_path, backup_folder):
		"""Descarga todos los correos de una carpeta"""
		headers = {'Authorization': f'Bearer {self.access_token}'}
		url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/mailFolders/{folder_id}/messages?$top=100"
		folder_downloaded = 0
		folder_failed = 0
		
		
		# Crear MBOX específico para esta carpeta si es necesario
		folder_mbox = None
		if self.export_format.get() in ["mbox", "both"]:
			mbox_filename = f"{self._sanitize_filename(folder_name)}.mbox"
			mbox_path = os.path.join(folder_path if self.include_folders.get() else backup_folder, mbox_filename)
			folder_mbox = mailbox.mbox(mbox_path)
			folder_mbox.lock()  # AÑADIR ESTA LÍNEA
			self.log_message(f"   Creating MBOX: {mbox_filename}")
		
		while url and self.is_running:
			try:
				response = self._make_api_request(url)
				
				data = response.json()
				messages = data.get('value', [])
				
				for message in messages:
					if not self.is_running:
						break
					
					try:
						self._save_email(message, folder_name, folder_path, folder_mbox)
						self.downloaded_emails += 1
						folder_downloaded += 1
						
						# Actualizar progreso
						if self.total_emails > 0:
							progress = (self.downloaded_emails / self.total_emails) * 100
							self.progress['value'] = progress
						
						self.progress_label.config(
							text=f"{self.downloaded_emails} / {self.total_emails} emails downloaded")
						
						if self.downloaded_emails % 50 == 0:
							self.log_message(f"   ✓ {self.downloaded_emails} emails processed...")
						
					except Exception as e:
						self.failed_emails += 1
						folder_failed += 1
						self.log_message(f"   ❌ Error in email: {str(e)}")
				
				# Siguiente página
				url = data.get('@odata.nextLink')
				
				# Pequeña pausa para no saturar la API
				time.sleep(0.1)

			except Exception as e:
				self.log_message(f"❌ Error downloading folder {folder_name}: {str(e)}")
				break
		
		# Cerrar MBOX de la carpeta
		if folder_mbox is not None:
			folder_mbox.flush()
			folder_mbox.unlock()
			folder_mbox.close()

		return folder_downloaded, folder_failed
			

	
	def _save_email(self, message, folder_name, folder_path, mbox):
		"""Guarda un correo en el formato seleccionado"""
		# Crear mensaje MIME
		msg = self._create_mime_message(message)


		# Guardar en MBOX
		if mbox is not None and self.export_format.get() in ["mbox", "both"]:
			try:
				# Convertir a formato mailbox.mboxMessage
				mbox_msg = mailbox.mboxMessage(msg)
				mbox.add(mbox_msg)
				
				# Log cada 20 correos para verificar
				# if self.downloaded_emails % 20 == 0:
					# self.log_message(f"   📧 MBOX: {len(mbox)} correos guardados")
					# mbox.flush()
			except Exception as e:
				self.log_message(f"   ❌ Error saving to MBOX: {str(e)}")

		# Guardar como EML
		if self.export_format.get() in ["eml", "both"]:
			# Usar el ID del mensaje como nombre de archivo
			message_id = message.get('id', '')
			filename = f"{message_id}.eml"
			filepath = os.path.join(folder_path, filename)

			with open(filepath, 'wb') as f:
				f.write(msg.as_bytes())
	
	def _create_mime_message(self, message):
		"""Crea un mensaje MIME a partir de un mensaje de Graph API"""
		msg = MIMEMultipart()
		
		# Headers básicos
		msg['Subject'] = message.get('subject', 'No subject')
		msg['From'] = message.get('from', {}).get('emailAddress', {}).get('address', '')
		
		to_recipients = message.get('toRecipients', [])
		if to_recipients:
			msg['To'] = ', '.join([r.get('emailAddress', {}).get('address', '') for r in to_recipients])
		
		msg['Date'] = message.get('receivedDateTime', '')
		
		# Cuerpo del mensaje
		body = message.get('body', {})
		content = body.get('content', '')
		content_type = body.get('contentType', 'text')
		
		if content_type.lower() == 'html':
			msg.attach(MIMEText(content, 'html', 'utf-8'))
		else:
			msg.attach(MIMEText(content, 'plain', 'utf-8'))
		
		# Adjuntos
		if self.include_attachments.get() and message.get('hasAttachments'):
			self._add_attachments(msg, message['id'])
		
		return msg
	
	def _add_attachments(self, msg, message_id):
		"""Añade los adjuntos a un mensaje MIME"""
		try:
			headers = {'Authorization': f'Bearer {self.access_token}'}
			url = f"https://graph.microsoft.com/v1.0/users/{self.user_email}/messages/{message_id}/attachments"
			
			response = self._make_api_request(url)
			
			attachments = response.json().get('value', [])
			
			for attachment in attachments:
				if attachment.get('@odata.type') == '#microsoft.graph.fileAttachment':
					content_bytes = base64.b64decode(attachment.get('contentBytes', ''))
					
					part = MIMEBase('application', 'octet-stream')
					part.set_payload(content_bytes)
					encoders.encode_base64(part)
					part.add_header('Content-Disposition', 
								   f'attachment; filename="{attachment.get("name", "attachment")}"')
					msg.attach(part)
					
		except Exception as e:
			self.log_message(f"   ⚠ Error downloading attachments: {str(e)}")
	
	def _sanitize_filename(self, filename):
		"""Limpia un nombre de archivo de caracteres no válidos"""
		if filename is None:
			filename = ""

		filename = str(filename)

		# Reemplazar caracteres no válidos en Windows
		invalid_chars = '<>:"/\\|?*'
		for char in invalid_chars:
			filename = filename.replace(char, '_')

		# Reemplazar caracteres de control (incluye tabs, saltos de línea, etc.)
		filename = re.sub(r'[\x00-\x1F\x7F]', '_', filename)

		# No permitir nombres que terminen en punto o espacio en Windows
		filename = filename.strip().rstrip('. ')

		# Evitar nombres reservados de Windows
		reserved_names = {
			'CON', 'PRN', 'AUX', 'NUL',
			'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
			'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
		}
		if filename.upper() in reserved_names:
			filename = f"_{filename}_"

		# Fallback si después de sanear queda vacío
		if not filename:
			filename = "carpeta_sin_nombre"

		return filename[:200]  # Limitar longitud


def main():
	root = tk.Tk()
	app = OutlookBackup(root)
	root.mainloop()

if __name__ == "__main__":
	main()