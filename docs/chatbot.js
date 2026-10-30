// ==========================================
// HR ASSISTANT CHATBOT (Frontend)
// ==========================================
const chatbotToggle = document.getElementById("chatbotToggle");
const chatbotModal = document.getElementById("chatbotModal");
const chatbotClose = document.getElementById("chatbotClose");
const chatbotClear = document.getElementById("chatbotClear");
const chatbotInput = document.getElementById("chatbotInput");
const chatbotSend = document.getElementById("chatbotSend");
const chatbotMessages = document.getElementById("chatbotMessages");

let conversationHistory = [];
let cachedToken = null;

function getApiBase() {
  return window.location.hostname === "localhost" ? "https://krypton-hr.onrender.com" : "https://127.0.0.1:8000";
}

async function getToken() {
  if (cachedToken) return cachedToken;
  const baseUrl = getApiBase();
  try {
    const res = await fetch(`${baseUrl}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: "admin", password: "Admin@123" })
    });
    if (res.ok) {
      const data = await res.json();
      cachedToken = data.access_token;
      return cachedToken;
    }
  } catch (e) {}
  return null;
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function formatMarkdown(text) {
  // Convert markdown to HTML
  let html = escapeHtml(text);
  // Code blocks
  html = html.replace(/```([\s\S]*?)```/g, '<pre>$1</pre>');
  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
  // Bold
  html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*([^*]+)\*/g, '<em>$1</em>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  return html;
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `chatbot-message ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  if (role === "bot") {
    bubble.innerHTML = formatMarkdown(text);
  } else {
    bubble.textContent = text;
  }
  div.appendChild(bubble);
  chatbotMessages.appendChild(div);
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function showTyping() {
  const div = document.createElement("div");
  div.className = "chatbot-message bot";
  div.id = "typingIndicator";
  div.innerHTML = '<div class="message-bubble chatbot-typing"><span></span><span></span><span></span></div>';
  chatbotMessages.appendChild(div);
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

function hideTyping() {
  const indicator = document.getElementById("typingIndicator");
  if (indicator) indicator.remove();
}

function toggleChatbot(open) {
  if (open) {
    chatbotModal.classList.add("active");
    chatbotInput.focus();
  } else {
    chatbotModal.classList.remove("active");
  }
}

async function sendMessage() {
  const message = chatbotInput.value.trim();
  if (!message) return;

  addMessage("user", message);
  chatbotInput.value = "";
  chatbotSend.disabled = true;

  showTyping();

  try {
    const token = await getToken();
    const baseUrl = getApiBase();
    const res = await fetch(`${baseUrl}/chatbot/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "Authorization": `Bearer ${token}` } : {})
      },
      body: JSON.stringify({
        message: message,
        history: conversationHistory
      })
    });

    hideTyping();

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    addMessage("bot", data.response);

    // Save to history
    conversationHistory.push({ user: message, assistant: data.response });
    if (conversationHistory.length > 10) {
      conversationHistory = conversationHistory.slice(-10);
    }
  } catch (err) {
    hideTyping();
    addMessage("bot", `⚠️ Error: ${err.message}. Please check your Gemini API key in backend/.env.`);
  } finally {
    chatbotSend.disabled = false;
    chatbotInput.focus();
  }
}

// Event Listeners
chatbotToggle.addEventListener("click", () => toggleChatbot(true));
chatbotClose.addEventListener("click", () => toggleChatbot(false));
chatbotClear.addEventListener("click", () => {
  chatbotMessages.innerHTML = `
    <div class="chatbot-message bot">
      <div class="message-bubble">
        Hi! I'm your HR Assistant. I can help you look up employee info, attendance, leaves, payroll, and more. What would you like to know?
      </div>
    </div>
  `;
  conversationHistory = [];
});
chatbotSend.addEventListener("click", sendMessage);
chatbotInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    sendMessage();
  }
});

// Close modal when clicking outside
chatbotModal.addEventListener("click", (e) => {
  if (e.target === chatbotModal) toggleChatbot(false);
});