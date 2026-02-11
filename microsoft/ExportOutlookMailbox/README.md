# Outlook Email Backup Tool

A Python GUI application that exports emails from Microsoft Outlook/Exchange accounts to local files using the Microsoft Graph API.

## Features

- **Dual Authentication Methods:**
  - Interactive OAuth2 login (browser-based)
  - Service account credentials (Client Credentials flow)

- **Multiple Export Formats:**
  - MBOX (single file, compatible with Thunderbird/Outlook)
  - EML (individual files per email)
  - Both formats simultaneously

- **Flexible Options:**
  - Include/exclude attachments
  - Preserve folder structure


## Requirements

### System Requirements
- Python 3.7 or higher
- Windows, macOS, or Linux
- Microsoft Azure Account (for application registration)

## Installation

1. Clone or download the project
2. Install Python dependencies:
```bash
pip install requests
```

3. Register an Azure Application

## Azure Application Setup

You need to register an application in Azure AD to use this tool. Follow these steps:

### 1. Register Application in Azure Portal

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to "Azure Active Directory" → "App registrations"
3. Click "New registration"
4. Fill in the details:
   - **Name:** e.g., "Outlook Backup Tool"
   - **Supported account types:** "Accounts in this organizational directory only" (single-tenant)
   - **Redirect URI:** 
     - For interactive login: `http://localhost:8000`
     - For service account: Leave empty
5. Click "Register"

### 2. Configure API Permissions

1. In the app settings, go to "API permissions"
2. Click "Add a permission"
3. Select "Microsoft Graph"
4. Choose **Delegated permissions** (for interactive login) OR **Application permissions** (for service account):
   - Search and select:
     - `Mail.Read`
     - `Mail.ReadWrite`
     - `offline_access` (only for interactive login)
5. Click "Add permissions"

### 3. For Service Account Method Only

1. Go to "Certificates & secrets"
2. Click "New client secret"
3. Set expiration and create
4. **Copy the secret value immediately** (you won't see it again)

### 4. Get Your Credentials

From the app overview page, copy:
- **Application (client) ID** - Use as "Client ID"
- **Directory (tenant) ID** - Use as "Tenant ID"

## Usage

### Running the Application

```bash
python ExportOutlookMailbox.pyw
```

Or on Windows, you can double-click the `.pyw` file.

### Authentication Methods

#### Method 1: Interactive OAuth2 Login (Recommended for Users)

1. Select "Interactive login (OAuth2)" radio button
2. Click "Connect"
3. A dialog will ask for:
   - **Client ID** (from Azure app registration)
   - **Tenant ID** (from Azure app registration)
   - **Redirect URI** (default: `http://localhost:8000`)
4. Your default browser will open - sign in with your email
5. After authentication, you'll be redirected back to the app
6. The tool will be ready to backup emails

#### Method 2: Service Account (Client Credentials Flow)

1. Select "Service account (Client Credentials)" radio button
2. Credential fields will appear
3. Fill in:
   - **Client ID** - From Azure app registration
   - **Tenant ID** - From Azure app registration
   - **Client Secret** - Created in "Certificates & secrets"
4. Enter the email address of the mailbox to backup
5. Click "Connect"

### Backup Process

1. **Select authentication method** and provide credentials
2. **Enter email address** to backup (for service account method)
3. **Choose export format:**
   - MBOX - Recommended for single archive file
   - EML - Individual files per email (better for editing)
   - Both - Export in both formats
4. **Select options:**
   - ☑ Include attachments (uncheck to skip attachments)
   - ☑ Preserve folder structure (mirror Outlook folder hierarchy)
5. **Select output folder** - Where to save the backup
6. **Click "START BACKUP"** - Start the backup process
7. **Monitor progress** - Watch the log and progress bar
8. **Click "STOP BACKUP"** to cancel if needed

### Output Structure

```
outlook_backup_email@example_com_20260211_143022/
├── Inbox/
│   ├── message1.eml
│   ├── message2.eml
│   └── Inbox.mbox
├── Sent Items/
│   ├── message1.eml
│   ├── message2.eml
│   └── Sent Items.mbox
├── Archive/
│   └── ...
```

## Export Formats Explained

### MBOX Format
- **Single file** containing all emails from a folder
- **Compatible with:** Thunderbird, Outlook, Apple Mail, many email clients

### EML Format
- **Individual files** for each email (one .eml file per message)
- **Compatible with:** All email clients

## Troubleshooting

### Error: "Authentication failed"

- **Interactive login:**
  - Verify Client ID and Tenant ID are correct
  - Check that permissions are granted in Azure AD
  - Ensure redirect URI matches exactly in Azure (including http vs https)

- **Service account:**
  - Verify Client Secret hasn't expired
  - Confirm application has required permissions
  - Check email address format

### Error: "Folder access denied"

- The mailbox account may have restricted shared mailbox permissions
- For shared mailboxes with service account, ensure proper delegation

### Port 8000 already in use

- Change redirect URI in Azure app settings
- Update the redirect URI in the tool
- Use a different port (e.g., `http://localhost:8001`)


## API Limits

Microsoft Graph API has rate limits:
- 4 requests per second (for multi-tenant apps)
- The tool includes delays to stay within limits

If you hit rate limits:
- The tool will retry automatically
- Try with "Stop" and continue later
