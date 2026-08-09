function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
}

function showGateModal(type, resetTimeIso) {
  const glyph = document.getElementById('gate-modal-glyph');
  const title = document.getElementById('gate-modal-title');
  const text = document.getElementById('gate-modal-text');
  const buttons = document.getElementById('gate-modal-buttons');
  if (type === 'upgrade') {
    glyph.textContent = '⭐';
    title.textContent = 'Free limit reached';
    let resetLine = '';
    if (resetTimeIso) {
      const resetDate = new Date(resetTimeIso);
      const timeStr = resetDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      const now = new Date();
      const isToday = resetDate.toDateString() === now.toDateString();
      resetLine = `You can send more messages at ${timeStr}${isToday ? ' today' : ''}. `;
    }
    text.textContent = resetLine + 'Or upgrade to Premium for unlimited messages and image generation.';
    buttons.innerHTML = '<a class="secondary" href="/">Maybe later</a><a class="primary" href="/billing/plans/">View plans</a>';
  } else {
    glyph.textContent = '🔒';
    title.textContent = 'Free limit reached';
    text.textContent = "Log in or sign up to keep chatting — it's free.";
    buttons.innerHTML = '<a class="secondary" href="/login/">Log in</a><a class="primary" href="/signup/">Sign up</a>';
  }
  document.getElementById('login-modal-overlay').style.display = 'flex';
}

const THEME_KEY = 'myagent_theme';
const themeToggle = document.getElementById('theme-toggle');
function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  themeToggle.textContent = theme === 'light' ? '☀️' : '🌙';
  localStorage.setItem(THEME_KEY, theme);
}
applyTheme(localStorage.getItem(THEME_KEY) || 'light');
themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  applyTheme(current === 'light' ? 'dark' : 'light');
});

const SIDEBAR_KEY = 'myagent_sidebar_collapsed';
const sidebar = document.getElementById('sidebar');
const sidebarToggle = document.getElementById('sidebar-toggle');
function applySidebar(collapsed) {
  sidebar.classList.toggle('collapsed', collapsed);
  localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
}
applySidebar(localStorage.getItem(SIDEBAR_KEY) === '1');
sidebarToggle.addEventListener('click', () => {
  applySidebar(!sidebar.classList.contains('collapsed'));
});

const rotatingPhrases = [
  'I can help you with something today',
  'Ask me to search, read a file, or run code',
  'Upload a PDF and ask questions about it',
  "What's on your mind?",
];
let phraseIndex = 0;
const rotatingEl = document.getElementById('hero-rotating');
setInterval(() => {
  phraseIndex = (phraseIndex + 1) % rotatingPhrases.length;
  rotatingEl.style.opacity = 0;
  setTimeout(() => {
    rotatingEl.textContent = rotatingPhrases[phraseIndex];
    rotatingEl.style.opacity = 1;
  }, 250);
}, 3200);

const inputTemplate = document.getElementById('input-template');
const heroContainer = document.getElementById('hero-input-container');
const bottomBar = document.getElementById('input-bar');
const heroWrap = document.getElementById('hero-wrap');
const chatWindow = document.getElementById('chat-window');
const thread = document.getElementById('thread');

let conversationId = null;
let pendingFilename = null;
let inConversationMode = false;
let liveInputNode = null;
let pendingAttachmentEl = null;
let attachChipTextEl = null;

function clearPendingAttachment() {
  pendingFilename = null;
  if (pendingAttachmentEl) pendingAttachmentEl.style.display = 'none';
  if (attachChipTextEl) attachChipTextEl.textContent = '';
}

function mountInput(container) {
  if (!liveInputNode) {
    const node = inputTemplate.content.cloneNode(true);
    container.appendChild(node);
    liveInputNode = container.querySelector('#input-form');
    wireInputEvents(liveInputNode);
  } else {
    container.appendChild(liveInputNode);
  }
}

function enterConversationMode() {
  if (inConversationMode) return;
  inConversationMode = true;
  heroWrap.style.display = 'none';
  chatWindow.style.display = 'flex';
  bottomBar.style.display = 'flex';
  document.getElementById('header-bar').classList.remove('hero-header');
  mountInput(bottomBar);
}

function enterHeroMode() {
  inConversationMode = false;
  heroWrap.style.display = 'flex';
  chatWindow.style.display = 'none';
  bottomBar.style.display = 'none';
  mountInput(heroContainer);
  thread.innerHTML = '';
  clearPendingAttachment();
}

function scrollToBottom() { chatWindow.scrollTop = 999999; }
const IMAGE_URL_REGEX = /(https?:\/\/image\.pollinations\.ai\/prompt\/[^\s)]+|https?:\/\/\S+\.(?:png|jpg|jpeg|gif|webp)(?:\?\S+)?)/gi;

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function convertMarkdownTables(text) {
  const lines = text.split('\n');
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    const next = lines[i + 1] || '';
    const isHeaderRow = /^\s*\|.*\|\s*$/.test(line);
    const isSeparatorRow = /^\s*\|?[\s:-]+\|[\s:|-]*\|?\s*$/.test(next) && next.includes('-');
    if (isHeaderRow && isSeparatorRow) {
      const headers = line.split('|').map(s => s.trim()).filter(Boolean);
      let j = i + 2;
      const rows = [];
      while (j < lines.length && /^\s*\|.*\|\s*$/.test(lines[j])) {
        rows.push(lines[j].split('|').map(s => s.trim()).filter(Boolean));
        j++;
      }
      let html = '<table class="md-table"><thead><tr>' + headers.map(h => `<th>${h}</th>`).join('') + '</tr></thead><tbody>';
      rows.forEach(r => { html += '<tr>' + r.map(c => `<td>${c}</td>`).join('') + '</tr>'; });
      html += '</tbody></table>';
      out.push(html);
      i = j;
    } else {
      out.push(line);
      i++;
    }
  }
  return out.join('\n');
}

function mdToHtml(text) {
  let html = escapeHtml(text);
  html = convertMarkdownTables(html);
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|&lt;(https?:\/\/[^\s&]+)&gt;|(https?:\/\/[^\s<>"]+)/g,
    (match, mdText, mdUrl, angleUrl, bareUrl) => {
      if (mdUrl) return `<a href="${mdUrl}" target="_blank" rel="noopener">${mdText}</a>`;
      if (angleUrl) return `<a href="${angleUrl}" target="_blank" rel="noopener">${angleUrl}</a>`;
      if (bareUrl) return `<a href="${bareUrl}" target="_blank" rel="noopener">${bareUrl}</a>`;
      return match;
    }
  );
  html = html.replace(/\n/g, '<br>');
  return html;
}

function renderBubbleContent(bubbleEl, text) {
  const matches = text.match(IMAGE_URL_REGEX);
  const cleanText = (text || '').replace(IMAGE_URL_REGEX, '').trim();
  bubbleEl.innerHTML = mdToHtml(cleanText);
  if (matches) {
    matches.forEach(url => {
      const img = document.createElement('img');
      img.src = url;
      img.alt = 'Generated image';
      img.loading = 'lazy';
      img.style.cssText = 'max-width:100%;border-radius:12px;margin-top:8px;display:block;';
      bubbleEl.appendChild(img);
    });
  }
}

function addUserBubble(text) {
  const row = document.createElement('div');
  row.className = 'row user';
  const time = formatTime(new Date());
  row.innerHTML = `
    <div class="bubble" title="${time}"></div>
    <div class="msg-actions">
      <button type="button" class="msg-action-btn copy-btn" title="Copy">⧉</button>
      <button type="button" class="msg-action-btn edit-btn" title="Edit">✎</button>
      <span class="msg-time">${time}</span>
    </div>`;
  row.querySelector('.bubble').textContent = text;
  wireMessageActions(row, text);
  thread.appendChild(row);
  scrollToBottom();
}

function addAssistantBubble(text) {
  const row = document.createElement('div');
  row.className = 'row assistant';
  const time = formatTime(new Date());
  row.innerHTML = `
    <div class="bubble" title="${time}"></div>
    <div class="msg-actions">
      <button type="button" class="msg-action-btn copy-btn" title="Copy">⧉</button>
      <span class="msg-time">${time}</span>
    </div>`;
  renderBubbleContent(row.querySelector('.bubble'), text);
  wireMessageActions(row, text);
  thread.appendChild(row);
  scrollToBottom();
}

function wireMessageActions(row, rawText) {
  const copyBtn = row.querySelector('.copy-btn');
  if (copyBtn) {
    copyBtn.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(rawText);
        copyBtn.textContent = '✓';
        setTimeout(() => { copyBtn.textContent = '⧉'; }, 1200);
      } catch (err) {}
    });
  }
  const editBtn = row.querySelector('.edit-btn');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      const activeInput = document.getElementById('message-input');
      if (activeInput) {
        activeInput.value = rawText;
        activeInput.focus();
        activeInput.dispatchEvent(new Event('input'));
      }
    });
  }
}

function formatTime(date) {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function addTypingIndicator() {
  const row = document.createElement('div');
  row.className = 'row assistant';
  row.id = 'typing-row';
  row.innerHTML = '<div class="bubble typing"><span></span><span></span><span></span></div>';
  thread.appendChild(row);
  scrollToBottom();
}

function replaceTypingWithReply(reply) {
  const row = document.getElementById('typing-row');
  if (!row) { addAssistantBubble(reply); return; }
  row.id = '';
  const time = formatTime(new Date());
  row.innerHTML = `
    <div class="bubble" title="${time}"></div>
    <div class="msg-actions">
      <button type="button" class="msg-action-btn copy-btn" title="Copy">⧉</button>
      <span class="msg-time">${time}</span>
    </div>`;
  renderBubbleContent(row.querySelector('.bubble'), reply);
  wireMessageActions(row, reply);
  scrollToBottom();
}

const historyList = document.getElementById('history-list');
const chatSearchInput = document.getElementById('chat-search-input');
let allConversations = [];

async function loadHistoryList() {
  try {
    const resp = await fetch('/api/agent/conversations/');
    const data = await resp.json();
    allConversations = data;
    renderHistoryList(chatSearchInput ? chatSearchInput.value : '');
  } catch (err) {}
}

function renderHistoryList(filterText) {
  const filter = (filterText || '').trim().toLowerCase();
  historyList.innerHTML = '';
  allConversations
    .filter(conv => !filter || (conv.title || 'untitled chat').toLowerCase().includes(filter))
    .forEach(conv => {
      const item = document.createElement('div');
      item.className = 'history-item' + (conv.id === conversationId ? ' active' : '');
      item.textContent = conv.title || 'Untitled chat';
      item.addEventListener('click', () => openConversation(conv.id));
      historyList.appendChild(item);
    });
}

if (chatSearchInput) {
  chatSearchInput.addEventListener('input', () => renderHistoryList(chatSearchInput.value));
}

async function openConversation(id) {
  conversationId = id;
  thread.innerHTML = '';
  enterConversationMode();
  try {
    const resp = await fetch(`/api/agent/conversations/${id}/`);
    const data = await resp.json();
    (data.messages || []).forEach(m => {
      if (m.role === 'user') {
        addUserBubble(typeof m.content === 'string' ? m.content : JSON.stringify(m.content));
      } else if (m.role === 'assistant') {
        let text = '';
        if (typeof m.content === 'string') text = m.content;
        else if (m.content && typeof m.content === 'object' && 'content' in m.content) text = m.content.content || '';
        if (text) addAssistantBubble(text);
      }
    });
  } catch (err) {}
  loadHistoryList();
}

document.getElementById('new-chat-btn').addEventListener('click', () => {
  conversationId = null;
  enterHeroMode();
  loadHistoryList();
});

function wireInputEvents(container) {
  const form = container;
  const input = container.querySelector('#message-input');
  const sendBtn = container.querySelector('#send-btn');
  const attachBtn = container.querySelector('#attach-btn');
  const attachMenu = container.querySelector('#attach-menu');
  const fileInput = container.querySelector('#file-input');
  const pendingAttachment = container.querySelector('#pending-attachment');
  const attachChipText = container.querySelector('#attach-chip-text');
  pendingAttachmentEl = pendingAttachment;
  attachChipTextEl = attachChipText;
  const menuUploadFile = container.querySelector('#menu-upload-file');
  const menuUploadImage = container.querySelector('#menu-upload-image');
  const micBtn = container.querySelector('#mic-btn');
  const styleSelector = container.querySelector('#style-selector');

  if (styleSelector) {
    styleSelector.value = window.__myagentStyle || 'normal';
    styleSelector.addEventListener('change', () => {
      window.__myagentStyle = styleSelector.value;
    });
  }

  if (micBtn) {
    const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognitionAPI) {
      micBtn.addEventListener('click', () => {
        alert('Voice input is not supported in this browser.');
      });
    } else {
      let recognizer = null;
      let isRecording = false;
      micBtn.addEventListener('click', () => {
        if (isRecording) {
          recognizer && recognizer.stop();
          return;
        }
        recognizer = new SpeechRecognitionAPI();
        recognizer.lang = 'hi-IN';
        recognizer.interimResults = false;
        recognizer.maxAlternatives = 1;
        recognizer.onstart = () => { isRecording = true; micBtn.classList.add('recording'); };
        recognizer.onend = () => { isRecording = false; micBtn.classList.remove('recording'); };
        recognizer.onerror = () => { isRecording = false; micBtn.classList.remove('recording'); };
        recognizer.onresult = (event) => {
          const transcript = event.results[0][0].transcript;
          input.value = (input.value ? input.value + ' ' : '') + transcript;
          input.dispatchEvent(new Event('input'));
          input.focus();
        };
        recognizer.start();
      });
    }
  }

  attachBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    attachMenu.classList.toggle('open');
  });
  document.addEventListener('click', () => attachMenu.classList.remove('open'));
  attachMenu.addEventListener('click', (e) => e.stopPropagation());

  menuUploadFile.addEventListener('click', () => { fileInput.accept = '.pdf,.docx,.txt,.md,.csv,.json'; fileInput.click(); attachMenu.classList.remove('open'); });
  menuUploadImage.addEventListener('click', () => { fileInput.accept = 'image/*'; fileInput.click(); attachMenu.classList.remove('open'); });

  const menuGenerateImage = container.querySelector('#menu-generate-image');
  if (menuGenerateImage) {
    menuGenerateImage.addEventListener('click', () => {
      attachMenu.classList.remove('open');
      if (window.__isPremium) {
        input.value = 'Generate an image of ';
        input.focus();
        input.dispatchEvent(new Event('input'));
      } else {
        window.location.href = '/billing/plans/';
      }
    });
  }

  fileInput.addEventListener('change', async () => {
    const file = fileInput.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    attachChipText.textContent = 'Uploading…';
    pendingAttachment.style.display = 'block';
    try {
      const resp = await fetch('/api/agent/upload/', {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
        body: formData,
      });
      const data = await resp.json();
      if (resp.ok) {
        pendingFilename = data.filename;
        attachChipText.textContent = '📎 ' + data.filename;
      } else {
        attachChipText.textContent = 'Error: ' + (data.error || 'upload failed');
        pendingFilename = null;
      }
    } catch (err) {
      attachChipText.textContent = 'Upload error';
      pendingFilename = null;
    }
  });

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let text = input.value.trim();
    if (!text && !pendingFilename) return;

    enterConversationMode();

    let displayText = text;
    if (pendingFilename) {
      text = `[Attached file: ${pendingFilename}] ${text}`;
      displayText = `📎 ${pendingFilename}\n${displayText}`.trim();
    }

    addUserBubble(displayText);
    clearPendingAttachment();

    const activeInput = document.getElementById('message-input');
    const activeSendBtn = document.getElementById('send-btn');
    if (activeInput) { activeInput.value = ''; activeInput.style.height = 'auto'; }
    if (activeSendBtn) activeSendBtn.disabled = true;

    addTypingIndicator();

    try {
      const resp = await fetch('/api/agent/chat/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
        body: JSON.stringify({ conversation_id: conversationId, message: text, style: window.__myagentStyle || 'normal' }),
      });
      const data = await resp.json();

      if (resp.status === 403 && data.login_required) {
        document.getElementById('typing-row')?.remove();
        showGateModal('login');
      } else if (resp.status === 403 && data.upgrade_required) {
        document.getElementById('typing-row')?.remove();
        showGateModal('upgrade', data.reset_time);
      } else if (!resp.ok) {
        replaceTypingWithReply('Error: ' + (data.detail || JSON.stringify(data)));
      } else {
        conversationId = data.conversation_id;
        replaceTypingWithReply(data.reply);
        loadHistoryList();
      }
    } catch (err) {
      replaceTypingWithReply('Network error: ' + err.message);
    } finally {
      const finalSendBtn = document.getElementById('send-btn');
      const finalInput = document.getElementById('message-input');
      if (finalSendBtn) finalSendBtn.disabled = false;
      if (finalInput) finalInput.focus();
    }
  });

  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 140) + 'px';
  });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
  });
}

const shareBtn = document.getElementById('share-btn');
if (shareBtn) {
  shareBtn.addEventListener('click', async () => {
    if (!conversationId) {
      alert('Pehle kuch chat karein, phir share karein.');
      return;
    }
    try {
      const resp = await fetch(`/api/agent/conversations/${conversationId}/share/`, {
        method: 'POST',
        headers: { 'X-CSRFToken': getCookie('csrftoken') },
      });
      const data = await resp.json();
      if (resp.ok && data.share_url) {
        await navigator.clipboard.writeText(data.share_url).catch(() => {});
        shareBtn.textContent = '✓ Link copied';
        setTimeout(() => { shareBtn.textContent = '🔗 Share'; }, 2000);
      } else {
        alert('Share link nahi ban paya: ' + (data.error || 'unknown error'));
      }
    } catch (err) {
      alert('Network error while sharing.');
    }
  });
}

mountInput(heroContainer);
loadHistoryList();