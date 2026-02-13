#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import concurrent.futures
import json
import os
import re
import shutil
import time
from datetime import datetime
from html import escape
from urllib.parse import urljoin, urlparse

import requests

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None

USER_UPLOADS_RE = re.compile(r'(https?://[^\s"\'<>]+?/user_uploads/[^\s"\'<>]+|/user_uploads/[^\s"\'<>]+)')
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tif", ".tiff", ".webp"}

HTML_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Zulip Archive</title>
  <style>
    :root {
      --bg: #f7f7fb;
      --card: #fff;
      --text: #111;
      --subtle: #555;
      --border: #e6e6f0;
      --highlight: #fff7cc;
      --active: #d6ebff;
    }
    body {
      font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
      margin: 0;
      background: var(--bg);
      color: var(--text);
    }
    .wrap {
      max-width: 1000px;
      margin: 0 auto;
      padding: 20px;
    }
    h1 {
      margin: 0 0 8px;
    }
    .meta {
      color: var(--subtle);
      margin-bottom: 12px;
    }
    .toolbar {
      position: sticky;
      top: 0;
      z-index: 100;
      background: var(--bg);
      border-bottom: 1px solid var(--border);
      padding: 12px 0;
      margin-bottom: 16px;
      display: flex;
      gap: 8px;
      align-items: center;
      flex-wrap: wrap;
    }
    .toolbar input[type="search"] {
      flex: 1;
      min-width: 260px;
      padding: 10px 12px;
      border: 1px solid #ccc;
      border-radius: 8px;
      font-size: 14px;
    }
    .toolbar input[type="date"] {
      min-width: 170px;
      padding: 10px 12px;
      border: 1px solid #ccc;
      border-radius: 8px;
      font-size: 14px;
      background: #fff;
    }
    .toolbar button {
      padding: 10px 12px;
      border: 1px solid #ccc;
      border-radius: 8px;
      background: #fff;
      cursor: pointer;
    }
    .toolbar button:disabled {
      opacity: 0.45;
      cursor: not-allowed;
    }
    .count {
      color: var(--subtle);
      font-size: 0.95rem;
      margin-left: 4px;
    }
    #messages {
      min-height: 180px;
    }
    .msg {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 14px 16px;
      margin: 12px 0;
      box-shadow: 0 1px 2px rgba(0,0,0,0.04);
      scroll-margin-top: 90px;
    }
    .msg-header {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 16px;
      font-size: 0.9rem;
      color: #444;
      margin-bottom: 8px;
    }
    .sender {
      font-weight: 600;
      color: #222;
    }
    .topic {
      background: #eef;
      padding: 2px 8px;
      border-radius: 999px;
    }
    .date {
      color: #666;
    }
    .content img {
      max-width: min(420px, 100%);
      max-height: 300px;
      width: auto;
      height: auto;
      border-radius: 8px;
      margin: 8px 0;
      cursor: zoom-in;
      display: block;
    }
    .attachment-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 8px 0;
    }
    .attachment-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid #cfd3df;
      border-radius: 8px;
      padding: 7px 11px;
      font-size: 0.9rem;
      text-decoration: none;
      color: #1f2937;
      background: #f8faff;
    }
    .attachment-btn:hover {
      background: #edf3ff;
      border-color: #bfc9e3;
    }
    .attachment-btn svg {
      width: 16px;
      height: 16px;
      display: block;
      flex: 0 0 16px;
    }
    .attachment-doc {
      background: #f7f7f9;
    }
    .attachment-name {
      color: #444;
      font-size: 0.88rem;
      margin: 4px 0 8px;
      word-break: break-all;
    }
    .hidden {
      display: none;
    }
    .match {
      background: var(--highlight);
    }
    .match.active {
      border-color: #8bb9ff;
      box-shadow: 0 0 0 2px var(--active);
    }
    #loading {
      color: var(--subtle);
      padding: 8px 0;
    }
    .modal {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.82);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 999;
      padding: 24px;
      box-sizing: border-box;
    }
    .modal.open {
      display: flex;
    }
    .modal-panel {
      width: min(96vw, 1200px);
      max-height: 95vh;
      display: flex;
      flex-direction: column;
      gap: 10px;
      align-items: stretch;
    }
    .modal-toolbar {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }
    .modal-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid rgba(255,255,255,0.42);
      border-radius: 8px;
      padding: 8px 12px;
      color: #fff;
      background: rgba(0,0,0,0.35);
      text-decoration: none;
      cursor: pointer;
      font-size: 0.9rem;
    }
    .modal-btn:hover {
      background: rgba(0,0,0,0.55);
    }
    .modal-btn svg {
      width: 16px;
      height: 16px;
      display: block;
      flex: 0 0 16px;
    }
    .modal-media {
      display: flex;
      justify-content: center;
      align-items: center;
      min-height: 180px;
    }
    .modal-media img {
      max-width: 95vw;
      max-height: 95vh;
      width: auto;
      height: auto;
      border-radius: 10px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
      cursor: default;
    }
    .modal-media iframe {
      width: min(95vw, 1100px);
      height: min(88vh, 900px);
      border: none;
      border-radius: 10px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.5);
      background: #fff;
    }
    .modal-hidden {
      display: none !important;
    }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Zulip Archive</h1>
    <div class="meta">__META__</div>

    <div class="toolbar">
      <input id="q" type="search" placeholder="Search messages..." />
      <button id="prevBtn" type="button" disabled>Previous</button>
      <button id="nextBtn" type="button" disabled>Next</button>
      <input id="dateQ" type="date" />
      <button id="goDateBtn" type="button">Go to date</button>
      <span class="count" id="count">0 results</span>
    </div>

    <div id="loading">Loading messages…</div>
    <div id="messages"></div>
  </div>

  <div class="modal" id="imgModal" aria-hidden="true">
    <div class="modal-panel">
      <div class="modal-toolbar">
        <a id="modalDownloadBtn" class="modal-btn" href="#" download>
          <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v8.59l2.3-2.29a1 1 0 1 1 1.4 1.41l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 1.4-1.41L11 12.59V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z"/></svg>
          Download
        </a>
        <button id="modalCloseBtn" class="modal-btn" type="button">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6.7 5.3a1 1 0 0 0-1.4 1.4L10.6 12l-5.3 5.3a1 1 0 1 0 1.4 1.4l5.3-5.3 5.3 5.3a1 1 0 0 0 1.4-1.4L13.4 12l5.3-5.3a1 1 0 1 0-1.4-1.4L12 10.6 6.7 5.3Z"/></svg>
          Close
        </button>
      </div>
      <div class="modal-media">
        <img id="modalImg" alt="Attachment preview" class="modal-hidden" />
        <iframe id="modalPdf" title="PDF preview" class="modal-hidden"></iframe>
      </div>
    </div>
  </div>

  <script id="embeddedMessages" type="application/json">__EMBEDDED_MESSAGES__</script>

  <script>
    const MESSAGES_JSON_URL = '__MESSAGES_JSON__';
    const RENDER_CHUNK_SIZE = __RENDER_CHUNK_SIZE__;

    const messagesContainer = document.getElementById('messages');
    const loadingEl = document.getElementById('loading');
    const searchInput = document.getElementById('q');
    const dateInput = document.getElementById('dateQ');
    const goDateBtn = document.getElementById('goDateBtn');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const countEl = document.getElementById('count');
    const modal = document.getElementById('imgModal');
    const modalImg = document.getElementById('modalImg');
    const modalPdf = document.getElementById('modalPdf');
    const modalDownloadBtn = document.getElementById('modalDownloadBtn');
    const modalCloseBtn = document.getElementById('modalCloseBtn');

    let allMessageElements = [];
    let currentMatches = [];
    let currentMatchIndex = -1;

    function normalize(s) {
      return (s || '').toLowerCase();
    }

    function isImagePath(pathname) {
      return /\.(jpe?g|png|gif|bmp|webp|tiff?)$/i.test(pathname || '');
    }

    function isPdfPath(pathname) {
      return /\.pdf$/i.test(pathname || '');
    }

    function getHrefPath(href) {
      try {
        return new URL(href, window.location.href).pathname || '';
      } catch (_) {
        return href || '';
      }
    }

    function getFileName(pathname) {
      const parts = (pathname || '').split('/').filter(Boolean);
      return parts.length ? decodeURIComponent(parts[parts.length - 1]) : 'file';
    }

    function iconSvg(kind) {
      if (kind === 'download') {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 3a1 1 0 0 1 1 1v8.59l2.3-2.29a1 1 0 1 1 1.4 1.41l-4 4a1 1 0 0 1-1.4 0l-4-4a1 1 0 0 1 1.4-1.41L11 12.59V4a1 1 0 0 1 1-1Zm-7 14a1 1 0 0 1 1 1v1h12v-1a1 1 0 1 1 2 0v2a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-2a1 1 0 0 1 1-1Z"/></svg>';
      }
      if (kind === 'pdf') {
        return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 2a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8.83a2 2 0 0 0-.59-1.41l-4.83-4.83A2 2 0 0 0 13.17 2H6Zm7 1.5c.13 0 .26.05.35.15l5 5a.5.5 0 0 1-.35.85h-4.5A1.5 1.5 0 0 1 12 8V3.5h1ZM8 14a1 1 0 0 1 1-1h1.5a2.5 2.5 0 0 1 0 5H10v1a1 1 0 1 1-2 0v-5Zm2 2v-1h.5a.5.5 0 0 1 0 1H10Zm4-2a1 1 0 0 1 1-1h2a1 1 0 1 1 0 2h-1v1h.5a1 1 0 1 1 0 2H16v1a1 1 0 1 1-2 0v-5Z"/></svg>';
      }
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 2a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9.17a2 2 0 0 0-.59-1.41l-4.17-4.17A2 2 0 0 0 13.83 3H6Zm8 1.5c.13 0 .26.05.35.15l4 4a.5.5 0 0 1-.35.85h-3.5A1.5 1.5 0 0 1 13 7V3.5h1ZM8 13a1 1 0 1 1 0-2h8a1 1 0 1 1 0 2H8Zm0 4a1 1 0 1 1 0-2h8a1 1 0 1 1 0 2H8Z"/></svg>';
    }

    function buildActionLink(href, label, kind, className = '') {
      const action = document.createElement('a');
      action.href = href;
      action.className = `attachment-btn ${className}`.trim();
      action.innerHTML = `${iconSvg(kind)}<span>${label}</span>`;
      return action;
    }

    function decorateAttachmentLink(anchor) {
      const href = anchor.getAttribute('href');
      if (!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('javascript:')) {
        return;
      }

      const pathname = getHrefPath(href);
      if (!pathname || isImagePath(pathname)) {
        return;
      }

      const fileName = getFileName(pathname);

      if (isPdfPath(pathname)) {
        const row = document.createElement('div');
        row.className = 'attachment-row';

        const previewBtn = buildActionLink(href, 'View PDF', 'pdf');
        previewBtn.addEventListener('click', (event) => {
          event.preventDefault();
          openModal(href, 'pdf', fileName);
        });

        const downloadBtn = buildActionLink(href, 'Download PDF', 'download');
        downloadBtn.setAttribute('download', fileName);

        row.appendChild(previewBtn);
        row.appendChild(downloadBtn);

        const name = document.createElement('div');
        name.className = 'attachment-name';
        name.textContent = fileName;

        const block = document.createElement('div');
        block.appendChild(row);
        block.appendChild(name);

        anchor.replaceWith(block);
        return;
      }

      const downloadBtn = buildActionLink(href, `Download ${fileName}`, 'download', 'attachment-doc');
      downloadBtn.setAttribute('download', fileName);
      anchor.replaceWith(downloadBtn);
    }

    function enhanceAttachmentLinks(scope) {
      const anchors = scope.querySelectorAll('.content a[href]');
      anchors.forEach((a) => decorateAttachmentLink(a));
    }

    function createMessageElement(msg) {
      const wrapper = document.createElement('div');
      wrapper.className = 'msg';
      wrapper.dataset.text = msg.search;
      wrapper.dataset.messageId = msg.id;
      wrapper.dataset.day = msg.day || (msg.date || '').slice(0, 10);
      wrapper.innerHTML = `
        <div class="msg-header">
          <span class="sender">${msg.sender}</span>
          <span class="topic">${msg.topic}</span>
          <span class="date">${msg.date}</span>
        </div>
        <div class="content">${msg.content}</div>
      `;

      const images = wrapper.querySelectorAll('.content img');
      images.forEach((img) => {
        img.addEventListener('click', (event) => {
          event.preventDefault();
          const fullSrc = img.getAttribute('src');
          openModal(fullSrc, 'image');
        });
      });

      enhanceAttachmentLinks(wrapper);

      return wrapper;
    }

    function renderChunks(messages, start = 0) {
      if (start >= messages.length) {
        loadingEl.textContent = `Loaded ${allMessageElements.length} messages`;
        updateSearch();
        return;
      }

      const fragment = document.createDocumentFragment();
      const end = Math.min(start + RENDER_CHUNK_SIZE, messages.length);
      for (let i = start; i < end; i += 1) {
        const msg = messages[i];
        const el = createMessageElement(msg);
        allMessageElements.push(el);
        fragment.appendChild(el);
      }
      messagesContainer.appendChild(fragment);
      loadingEl.textContent = `Loading… ${allMessageElements.length} messages`;

      requestAnimationFrame(() => renderChunks(messages, end));
    }

    async function loadMessages() {
      try {
        const embeddedEl = document.getElementById('embeddedMessages');
        const embeddedRaw = embeddedEl ? (embeddedEl.textContent || '').trim() : '';
        if (embeddedRaw && embeddedRaw !== 'null') {
          const payload = JSON.parse(embeddedRaw);
          const messages = Array.isArray(payload) ? payload : (payload.messages || []);
          renderChunks(messages, 0);
          return;
        }

        const response = await fetch(MESSAGES_JSON_URL, { cache: 'no-store' });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const payload = await response.json();
        const messages = Array.isArray(payload) ? payload : (payload.messages || []);
        renderChunks(messages, 0);
      } catch (error) {
        loadingEl.textContent = 'Error loading messages JSON. If you open this HTML with file://, use a local server.';
        console.error('Failed to load messages JSON:', error);
      }
    }

    function updateSearch() {
      const q = normalize(searchInput.value);
      currentMatches = [];
      currentMatchIndex = -1;

      allMessageElements.forEach((m) => {
        m.classList.remove('hidden', 'match', 'active');
        if (!q) {
          return;
        }

        const text = normalize(m.dataset.text || '');
        if (text.includes(q)) {
          m.classList.add('match');
          currentMatches.push(m);
        } else {
          m.classList.add('hidden');
        }
      });

      if (!q) {
        countEl.textContent = `${allMessageElements.length} messages`;
      } else if (currentMatches.length === 0) {
        countEl.textContent = '0 results';
      } else {
        currentMatchIndex = 0;
        focusCurrentMatch(false);
        countEl.textContent = `${currentMatchIndex + 1} / ${currentMatches.length}`;
      }

      const hasMatches = currentMatches.length > 0;
      prevBtn.disabled = !hasMatches;
      nextBtn.disabled = !hasMatches;
    }

    function focusCurrentMatch(shouldScroll = true) {
      if (!currentMatches.length) {
        return;
      }

      currentMatches.forEach((m) => m.classList.remove('active'));
      const target = currentMatches[currentMatchIndex];
      target.classList.add('active');
      if (shouldScroll) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      countEl.textContent = `${currentMatchIndex + 1} / ${currentMatches.length}`;
    }

    function goToNext() {
      if (!currentMatches.length) {
        return;
      }
      currentMatchIndex = (currentMatchIndex + 1) % currentMatches.length;
      focusCurrentMatch(true);
    }

    function goToPrev() {
      if (!currentMatches.length) {
        return;
      }
      currentMatchIndex = (currentMatchIndex - 1 + currentMatches.length) % currentMatches.length;
      focusCurrentMatch(true);
    }

    function goToDate() {
      const targetDay = (dateInput.value || '').trim();
      if (!targetDay) {
        return;
      }

      let target = allMessageElements.find((m) => (m.dataset.day || '') === targetDay);
      if (!target) {
        target = allMessageElements.find((m) => (m.dataset.day || '') > targetDay);
      }

      if (!target) {
        countEl.textContent = `No messages from ${targetDay}`;
        return;
      }

      allMessageElements.forEach((m) => m.classList.remove('active'));
      target.classList.remove('hidden');
      target.classList.add('active');
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      countEl.textContent = `Date: ${target.dataset.day}`;
    }

    function openModal(src, kind = 'image', downloadName = '') {
      const resolvedName = downloadName || getFileName(getHrefPath(src));
      modalDownloadBtn.href = src;
      modalDownloadBtn.setAttribute('download', resolvedName || 'file');
      modalDownloadBtn.dataset.downloadSrc = src;
      modalDownloadBtn.dataset.downloadName = resolvedName || 'file';

      if (kind === 'pdf') {
        modalImg.classList.add('modal-hidden');
        modalImg.src = '';
        modalPdf.classList.remove('modal-hidden');
        modalPdf.src = src;
      } else {
        modalPdf.classList.add('modal-hidden');
        modalPdf.src = '';
        modalImg.classList.remove('modal-hidden');
        modalImg.src = src;
      }

      modal.classList.add('open');
      modal.setAttribute('aria-hidden', 'false');
    }

    function closeModal() {
      modal.classList.remove('open');
      modal.setAttribute('aria-hidden', 'true');
      modalImg.src = '';
      modalPdf.src = '';
      modalPdf.classList.add('modal-hidden');
      modalImg.classList.add('modal-hidden');
      modalDownloadBtn.href = '#';
      delete modalDownloadBtn.dataset.downloadSrc;
      delete modalDownloadBtn.dataset.downloadName;
    }

    async function triggerDownload(url, fileName) {
      const response = await fetch(url, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const tempLink = document.createElement('a');
      tempLink.href = objectUrl;
      tempLink.download = fileName || 'file';
      document.body.appendChild(tempLink);
      tempLink.click();
      tempLink.remove();
      URL.revokeObjectURL(objectUrl);
    }

    searchInput.addEventListener('input', updateSearch);
    searchInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        if (event.shiftKey) {
          goToPrev();
        } else {
          goToNext();
        }
      }
    });
    prevBtn.addEventListener('click', goToPrev);
    nextBtn.addEventListener('click', goToNext);
    goDateBtn.addEventListener('click', goToDate);
    dateInput.addEventListener('keydown', (event) => {
      if (event.key === 'Enter') {
        goToDate();
      }
    });

    modal.addEventListener('click', (event) => {
      if (event.target === modal) {
        closeModal();
      }
    });
    modalDownloadBtn.addEventListener('click', async (event) => {
      event.preventDefault();
      const src = modalDownloadBtn.dataset.downloadSrc || modalDownloadBtn.getAttribute('href');
      const fileName = modalDownloadBtn.dataset.downloadName || 'file';
      if (!src || src === '#') {
        return;
      }
      try {
        await triggerDownload(src, fileName);
      } catch (error) {
        console.error('Download failed, falling back to direct link:', error);
        const fallbackLink = document.createElement('a');
        fallbackLink.href = src;
        fallbackLink.download = fileName;
        document.body.appendChild(fallbackLink);
        fallbackLink.click();
        fallbackLink.remove();
      }
    });
    modalCloseBtn.addEventListener('click', closeModal);
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeModal();
      }
    });

    loadMessages();
  </script>
</body>
</html>
"""


def zulip_get_messages(session, base_url, narrow, anchor="newest", num_before=500, num_after=0):
    params = {
        "anchor": anchor,
        "num_before": num_before,
        "num_after": num_after,
        "narrow": json.dumps(narrow),
        "apply_markdown": "true"
    }
    url = urljoin(base_url, "/api/v1/messages")
    r = session.get(url, params=params)
    if r.status_code >= 400:
        print("ERROR STATUS:", r.status_code)
        print("ERROR BODY:", r.text)
    r.raise_for_status()
    return r.json()


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def sanitize_filename(name):
    return re.sub(r'[^A-Za-z0-9._-]+', '_', name)


def sanitize_output_basename(name):
    sanitized = re.sub(r'[^A-Za-z0-9]+', '_', name or '')
    sanitized = re.sub(r'_+', '_', sanitized).strip('_')
    return sanitized


def to_web_path(path):
    return path.replace("\\", "/")


def is_image_upload_url(upload_url):
    path = urlparse(upload_url).path
    ext = os.path.splitext(path)[1].lower()
    return ext in IMAGE_EXTENSIONS


def download_upload(session, base_url, upload_url, target_dir):
    if upload_url.startswith("/"):
        full_url = urljoin(base_url, upload_url)
    else:
        full_url = upload_url

    parsed = urlparse(full_url)
    filename = sanitize_filename(os.path.basename(parsed.path))
    local_path = os.path.join(target_dir, filename)

    if os.path.exists(local_path):
        return local_path

    try:
        r = session.get(full_url, stream=True)
        r.raise_for_status()
        with open(local_path, "wb") as file_obj:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    file_obj.write(chunk)
        return local_path
    except requests.exceptions.HTTPError as err:
        status = err.response.status_code if err.response is not None else "unknown"
        print(f"WARN: failed to download upload ({status}): {full_url}")
        return None
    except requests.exceptions.RequestException as err:
        print(f"WARN: network error downloading upload: {full_url} ({err})")
        return None


def convert_to_webp(local_path, webp_dir, quality):
    ext = os.path.splitext(local_path)[1].lower()
    if ext not in IMAGE_EXTENSIONS:
        return None

    if Image is None:
        return None

    base_name = os.path.splitext(os.path.basename(local_path))[0]
    webp_path = os.path.join(webp_dir, f"{base_name}.webp")

    if os.path.exists(webp_path):
        return webp_path

    try:
        with Image.open(local_path) as image:
            image = ImageOps.exif_transpose(image)
            if image.mode in ("RGBA", "LA", "P"):
                image = image.convert("RGBA")
            else:
                image = image.convert("RGB")
            image.save(webp_path, "WEBP", quality=quality, method=6)
        return webp_path
    except Exception as err:  # pylint: disable=broad-except
        print(f"WARN: could not convert to WEBP {local_path}: {err}")
        return None


def get_stream_id(session, base_url, stream_name):
    url = urljoin(base_url, "/api/v1/get_stream_id")
    response = session.get(url, params={"stream": stream_name})
    if response.status_code >= 400:
        print("WARN: could not resolve stream_id for topic verification")
        return None
    data = response.json()
    return data.get("stream_id")


def get_stream_topics(session, base_url, stream_id):
    url = urljoin(base_url, f"/api/v1/users/me/{stream_id}/topics")
    response = session.get(url)
    if response.status_code >= 400:
        print("WARN: could not fetch stream topics for verification")
        return set()
    data = response.json()
    return {topic.get("name", "") for topic in data.get("topics", []) if topic.get("name")}


def transform_message_content(session, base_url, content, uploads_dir, images_original_dir, out_dir):
    uploads = set(USER_UPLOADS_RE.findall(content))
    replacements = {}
    message_local_paths = set()

    for upload_url in uploads:
        target_dir = images_original_dir if is_image_upload_url(upload_url) else uploads_dir
        local_path = download_upload(session, base_url, upload_url, target_dir)
        if not local_path:
            continue

        rel_path = to_web_path(os.path.relpath(local_path, out_dir))
        replacements[upload_url] = rel_path
        message_local_paths.add(rel_path)

    transformed = content
    for original_url, rel_path in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        transformed = transformed.replace(original_url, rel_path)

    text_for_search = re.sub('<[^<]+?>', ' ', transformed)
    text_for_search = " ".join(text_for_search.split())

    return transformed, text_for_search, message_local_paths


def prepare_messages_json(messages, session, base_url, uploads_dir, images_original_dir, out_dir):
    js_messages = []
    all_local_paths = set()

    for message in messages:
        sender = message["sender_full_name"]
        topic = message["subject"] or "(no topic)"
        timestamp = datetime.fromtimestamp(message["timestamp"]).strftime("%Y-%m-%d %H:%M")
        raw_content = message["content"]

        transformed_content, search_text, message_local_paths = transform_message_content(
            session=session,
            base_url=base_url,
            content=raw_content,
            uploads_dir=uploads_dir,
            images_original_dir=images_original_dir,
            out_dir=out_dir,
        )
        all_local_paths.update(message_local_paths)

        combined_search = f"{sender} {topic} {search_text}"
        js_messages.append({
            "id": message["id"],
            "sender": escape(sender),
            "topic": escape(topic),
            "date": timestamp,
            "day": timestamp[:10],
            "content": transformed_content,
            "search": combined_search,
            "_local_paths": sorted(message_local_paths),
        })

    return js_messages, all_local_paths


def convert_uploads_to_webp_parallel(local_rel_paths, out_dir, webp_dir, quality, workers):
    if Image is None:
        return {}

    rel_paths = sorted(local_rel_paths)
    if not rel_paths:
        return {}

    webp_map = {}

    def convert_one(rel_path):
        local_path = os.path.join(out_dir, rel_path.replace("/", os.sep))
        webp_path = convert_to_webp(local_path, webp_dir, quality)
        if not webp_path:
            return rel_path, None
        webp_rel_path = to_web_path(os.path.relpath(webp_path, out_dir))
        return rel_path, webp_rel_path

    max_workers = max(1, workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(convert_one, rel_path): rel_path for rel_path in rel_paths}
        for future in concurrent.futures.as_completed(future_map):
            rel_path, webp_rel_path = future.result()
            if webp_rel_path:
                webp_map[rel_path] = webp_rel_path

    return webp_map


def apply_webp_replacements(js_messages, webp_map):
    for message in js_messages:
        content = message["content"]
        local_paths = message.pop("_local_paths", [])

        for original_rel_path in local_paths:
            webp_rel_path = webp_map.get(original_rel_path)
            if not webp_rel_path:
                continue

            content = content.replace(original_rel_path, webp_rel_path)

        message["content"] = content

    return js_messages


def build_html(meta, messages_json_filename, render_chunk_size):
    return build_html_with_messages(meta, messages_json_filename, render_chunk_size, None)


def build_html_with_messages(meta, messages_json_filename, render_chunk_size, messages_payload):
    embedded_json = "null"
    if messages_payload is not None:
        embedded_json = json.dumps({"messages": messages_payload}, ensure_ascii=False).replace("</", "<\\/")

    return (
        HTML_TEMPLATE
        .replace("__META__", escape(meta))
        .replace("__MESSAGES_JSON__", messages_json_filename)
        .replace("__RENDER_CHUNK_SIZE__", str(max(1, render_chunk_size)))
        .replace("__EMBEDDED_MESSAGES__", embedded_json)
    )


def verify_topics_if_needed(session, base_url, stream_name, exported_messages, topic_filter):
    if topic_filter:
        return

    stream_id = get_stream_id(session, base_url, stream_name)
    if stream_id is None:
        return

    api_topics = get_stream_topics(session, base_url, stream_id)
    exported_topics = {msg.get("subject", "") for msg in exported_messages if msg.get("subject")}

    missing = sorted(topic for topic in api_topics if topic not in exported_topics)

    print(f"INFO: topics detected in API: {len(api_topics)}")
    print(f"INFO: topics present in export: {len(exported_topics)}")
    if missing:
        print(f"WARN: missing {len(missing)} topics in export (sample): {missing[:10]}")
    else:
        print("OK: export includes all detectable stream topics.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export Zulip messages to HTML with optimized attachments.")
    parser.add_argument("--base-url", required=True, help="Zulip base URL, e.g. https://zulip.yourcompany.com")
    parser.add_argument("--email", required=True, help="Your Zulip email")
    parser.add_argument("--api-key", required=True, help="Your Zulip API key")
    parser.add_argument("--stream", required=True, help="Stream name")
    parser.add_argument("--topic", default=None, help="Topic name (optional)")
    parser.add_argument("--out", default="zulip_export", help="Output directory")
    parser.add_argument("--chunk-size", type=int, default=120, help="Messages per JS render chunk")
    parser.add_argument("--embed-html", dest="embed_html", action="store_true", default=True, help="Embed messages in generated HTML (default: enabled)")
    parser.add_argument("--no-embed-html", dest="embed_html", action="store_false", help="Do not embed messages; load from generated JSON")
    parser.add_argument("--webp-quality", type=int, default=72, help="WEBP quality (1-100)")
    parser.add_argument("--webp-workers", type=int, default=max(2, (os.cpu_count() or 4)), help="Worker threads for WEBP conversion")
    parser.add_argument("--delete-original-images", action="store_true", help="Delete uploads_originalimages after successful WEBP conversion")
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    out_dir = args.out
    uploads_dir = os.path.join(out_dir, "uploads")
    images_original_dir = os.path.join(out_dir, "uploads_originalimages")
    webp_dir = os.path.join(out_dir, "uploads_webp")
    ensure_dir(out_dir)
    ensure_dir(uploads_dir)
    ensure_dir(images_original_dir)
    ensure_dir(webp_dir)

    if Image is None:
        print("WARN: Pillow is not installed. Original images will be used without WEBP conversion.")

    session = requests.Session()
    session.auth = (args.email, args.api_key)

    narrow = [{"operator": "stream", "operand": args.stream}]
    if args.topic:
        narrow.append({"operator": "topic", "operand": args.topic})

    all_messages = []
    anchor = "newest"
    while True:
        data = zulip_get_messages(session, base_url, narrow, anchor=anchor, num_before=1000, num_after=0)
        messages = data.get("messages", [])
        if not messages:
            break

        all_messages.extend(messages)

        oldest_id = messages[0]["id"]
        anchor = oldest_id - 1

        if len(messages) < 1000:
            break

        time.sleep(0.2)

    all_messages = sorted(all_messages, key=lambda msg: msg["timestamp"])

    verify_topics_if_needed(
        session=session,
        base_url=base_url,
        stream_name=args.stream,
        exported_messages=all_messages,
        topic_filter=args.topic,
    )

    meta = (
        f"Stream: {args.stream}"
      + (f" · Topic: {args.topic}" if args.topic else " · All topics")
        + f" · Total: {len(all_messages)}"
    )

    webp_quality = max(1, min(100, args.webp_quality))

    messages_payload, local_paths = prepare_messages_json(
        messages=all_messages,
        session=session,
        base_url=base_url,
        uploads_dir=uploads_dir,
        images_original_dir=images_original_dir,
        out_dir=out_dir,
    )

    webp_map = convert_uploads_to_webp_parallel(
        local_rel_paths=local_paths,
        out_dir=out_dir,
        webp_dir=webp_dir,
        quality=webp_quality,
        workers=args.webp_workers,
    )
    messages_payload = apply_webp_replacements(messages_payload, webp_map)

    if Image is not None:
        print(f"INFO: WEBP conversions available: {len(webp_map)}")

    if args.delete_original_images:
      original_image_paths = {path for path in local_paths if path.startswith("uploads_originalimages/")}
      failed_image_paths = original_image_paths - set(webp_map.keys())
      if Image is None:
        print("WARN: --delete-original-images skipped because Pillow is not installed.")
      elif failed_image_paths:
        print(f"WARN: --delete-original-images skipped. {len(failed_image_paths)} image(s) still use originals.")
      elif os.path.isdir(images_original_dir):
        shutil.rmtree(images_original_dir, ignore_errors=True)
        print(f"OK: deleted {images_original_dir}")

    stream_base = sanitize_output_basename(args.stream) or "zulip_export"
    if args.topic:
        topic_base = sanitize_output_basename(args.topic)
        if topic_base:
            stream_base = f"{stream_base}_{topic_base}"
    messages_json_filename = f"{stream_base}.json"
    html_filename = f"{stream_base}.html"

    messages_json_path = os.path.join(out_dir, messages_json_filename)
    with open(messages_json_path, "w", encoding="utf-8") as file_obj:
        json.dump({"messages": messages_payload}, file_obj, ensure_ascii=False)

    html = build_html_with_messages(
        meta=meta,
        messages_json_filename=messages_json_filename,
        render_chunk_size=args.chunk_size,
        messages_payload=messages_payload if args.embed_html else None,
    )

    html_path = os.path.join(out_dir, html_filename)
    with open(html_path, "w", encoding="utf-8") as file_obj:
        file_obj.write(html)

    print(f"OK: {html_path}")
    print(f"OK: {messages_json_path}")
