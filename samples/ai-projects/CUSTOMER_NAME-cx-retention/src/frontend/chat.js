/**
 * CUSTOMER_NAME - Assistente Bollette
 * Chat Widget (Vanilla JS, SSE streaming via fetch + ReadableStream)
 *
 * No external dependencies.
 */

"use strict";

/* ==========================================================================
   Utility: HTML escaping for XSS prevention
   ========================================================================== */

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string} text - Raw text.
 * @returns {string} Escaped HTML string.
 */
function escapeHtml(text) {
  const map = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  };
  return text.replace(/[&<>"']/g, function (ch) {
    return map[ch];
  });
}

/* ==========================================================================
   Utility: Simple Markdown renderer
   Supports: **bold**, *italic*, `code`, line breaks, bullet lists
   ========================================================================== */

/**
 * Render a minimal subset of Markdown to HTML.
 * Input is assumed to already be HTML-escaped.
 * @param {string} escapedText - HTML-escaped text.
 * @returns {string} HTML string with markdown formatting.
 */
function renderMarkdown(escapedText) {
  var html = escapedText;

  // Bold: **text**
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");

  // Italic: *text* (but not inside a <strong> tag created above)
  html = html.replace(/(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)/g, "<em>$1</em>");

  // Inline code: `text`
  html = html.replace(/`([^`]+?)`/g, "<code>$1</code>");

  // Bullet lists: lines starting with "- " or "* "
  // Split into lines, group consecutive bullet lines into <ul>
  var lines = html.split("\n");
  var result = [];
  var inList = false;

  for (var i = 0; i < lines.length; i++) {
    var trimmed = lines[i].trimStart();
    var isBullet = /^[-*]\s+/.test(trimmed);

    if (isBullet) {
      if (!inList) {
        result.push("<ul>");
        inList = true;
      }
      var content = trimmed.replace(/^[-*]\s+/, "");
      result.push("<li>" + content + "</li>");
    } else {
      if (inList) {
        result.push("</ul>");
        inList = false;
      }
      result.push(lines[i]);
    }
  }
  if (inList) {
    result.push("</ul>");
  }

  html = result.join("\n");

  // Paragraphs: double line breaks become paragraph breaks
  html = html.replace(/\n\n+/g, "</p><p>");

  // Single line breaks within paragraphs
  html = html.replace(/\n/g, "<br>");

  // Wrap in a paragraph
  html = "<p>" + html + "</p>";

  // Clean up empty paragraphs
  html = html.replace(/<p>\s*<\/p>/g, "");

  return html;
}

/* ==========================================================================
   ChatWidget Class
   ========================================================================== */

class ChatWidget {
  /**
   * @param {Object} config
   * @param {string} config.apiBaseUrl - Base URL for the API (empty string = same origin).
   */
  constructor(config) {
    this.apiBaseUrl = (config && config.apiBaseUrl) || "";

    // Session
    this.sessionId = null;
    this.currentMessageId = null;
    this.billRef = null;

    // State
    this.isStreaming = false;
    this.abortController = null;

    // DOM references
    this.messagesEl = document.getElementById("chat-messages");
    this.inputEl = document.getElementById("chat-input");
    this.sendBtn = document.getElementById("send-button");
    this.billRefBadge = document.getElementById("bill-ref-badge");
    this.billRefBadgeValue = document.getElementById("bill-ref-badge-value");
    this.billRefRemoveBtn = document.getElementById("bill-ref-remove");
    this.billRefSection = document.getElementById("bill-ref-section");
    this.billRefToggle = document.getElementById("bill-ref-toggle");
    this.billRefInput = document.getElementById("bill-ref-input");
    this.billRefConfirm = document.getElementById("bill-ref-confirm");

    this._bindEvents();
    this._restoreSession();
    this._showWelcome();
  }

  /* ------------------------------------------------------------------
     Event Binding
     ------------------------------------------------------------------ */

  _bindEvents() {
    var self = this;

    // Send message
    this.sendBtn.addEventListener("click", function () {
      self._handleSend();
    });
    this.inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        self._handleSend();
      }
    });

    // Bill reference toggle
    this.billRefToggle.addEventListener("click", function () {
      var isOpen = !self.billRefSection.classList.contains("hidden");
      if (isOpen) {
        self.billRefSection.classList.add("hidden");
        self.billRefToggle.setAttribute("aria-expanded", "false");
      } else {
        self.billRefSection.classList.remove("hidden");
        self.billRefToggle.setAttribute("aria-expanded", "true");
        self.billRefInput.focus();
      }
    });

    // Bill reference confirm
    this.billRefConfirm.addEventListener("click", function () {
      self._confirmBillRef();
    });
    this.billRefInput.addEventListener("keydown", function (e) {
      if (e.key === "Enter") {
        e.preventDefault();
        self._confirmBillRef();
      }
    });

    // Bill reference remove
    this.billRefRemoveBtn.addEventListener("click", function () {
      self._removeBillRef();
    });
  }

  /* ------------------------------------------------------------------
     Session Management
     ------------------------------------------------------------------ */

  _restoreSession() {
    try {
      var stored = localStorage.getItem("CUSTOMER_NAME_session_id");
      if (stored) {
        this.sessionId = stored;
      }
      var storedRef = localStorage.getItem("CUSTOMER_NAME_bill_ref");
      if (storedRef) {
        this.billRef = storedRef;
        this._showBillRefBadge(storedRef);
      }
    } catch (_e) {
      // localStorage may be unavailable (private mode, etc.)
    }
  }

  _saveSession() {
    try {
      if (this.sessionId) {
        localStorage.setItem("CUSTOMER_NAME_session_id", this.sessionId);
      }
    } catch (_e) {
      // Silently ignore storage errors
    }
  }

  /* ------------------------------------------------------------------
     Welcome Message
     ------------------------------------------------------------------ */

  _showWelcome() {
    // Only show welcome if there are no existing messages
    if (this.messagesEl.children.length > 0) {
      return;
    }
    var welcomeText =
      "Ciao! Sono l'assistente virtuale di CUSTOMER_NAME. " +
      "Posso aiutarti a capire la tua bolletta energetica. " +
      "Puoi farmi domande generali sulle tariffe o inserire " +
      "il numero della tua bolletta per una spiegazione personalizzata.";

    this._addAssistantMessage(welcomeText, null, false);
  }

  /* ------------------------------------------------------------------
     Bill Reference
     ------------------------------------------------------------------ */

  _confirmBillRef() {
    var value = this.billRefInput.value.trim();
    if (!value) {
      return;
    }
    this.billRef = value;
    try {
      localStorage.setItem("CUSTOMER_NAME_bill_ref", value);
    } catch (_e) {
      // Ignore
    }
    this._showBillRefBadge(value);
    this.billRefInput.value = "";
    this.billRefSection.classList.add("hidden");
    this.billRefToggle.setAttribute("aria-expanded", "false");
  }

  _showBillRefBadge(value) {
    this.billRefBadgeValue.textContent = value;
    this.billRefBadge.classList.remove("hidden");
  }

  _removeBillRef() {
    this.billRef = null;
    this.billRefBadge.classList.add("hidden");
    this.billRefBadgeValue.textContent = "";
    try {
      localStorage.removeItem("CUSTOMER_NAME_bill_ref");
    } catch (_e) {
      // Ignore
    }
  }

  /* ------------------------------------------------------------------
     Sending Messages
     ------------------------------------------------------------------ */

  _handleSend() {
    if (this.isStreaming) {
      return;
    }
    var text = this.inputEl.value.trim();
    if (!text) {
      return;
    }
    this.inputEl.value = "";
    this._addUserMessage(text);
    this._streamResponse(text);
  }

  /* ------------------------------------------------------------------
     DOM: Add User Message
     ------------------------------------------------------------------ */

  _addUserMessage(text) {
    var wrapper = document.createElement("div");
    wrapper.className = "message-wrapper message-wrapper--user";
    wrapper.setAttribute("role", "listitem");

    var bubble = document.createElement("div");
    bubble.className = "message-bubble message-bubble--user";
    bubble.textContent = text;

    wrapper.appendChild(bubble);
    this.messagesEl.appendChild(wrapper);
    this._scrollToBottom();
  }

  /* ------------------------------------------------------------------
     DOM: Add Assistant Message (static, for welcome / completed)
     ------------------------------------------------------------------ */

  /**
   * Add a fully-formed assistant message to the chat.
   * @param {string} text - Plain text (will be escaped and markdown-rendered).
   * @param {string|null} messageId - Backend message id for feedback.
   * @param {boolean} showFeedback - Whether to show feedback buttons.
   * @returns {HTMLElement} The wrapper element.
   */
  _addAssistantMessage(text, messageId, showFeedback) {
    var wrapper = document.createElement("div");
    wrapper.className = "message-wrapper message-wrapper--assistant";
    wrapper.setAttribute("role", "listitem");

    var bubble = document.createElement("div");
    bubble.className = "message-bubble message-bubble--assistant";
    bubble.innerHTML = renderMarkdown(escapeHtml(text));

    wrapper.appendChild(bubble);

    // Disclaimer
    var disclaimer = document.createElement("div");
    disclaimer.className = "message-disclaimer";
    disclaimer.textContent =
      "Risposta generata dall'AI - Per informazioni ufficiali contattare il servizio clienti CUSTOMER_NAME";
    wrapper.appendChild(disclaimer);

    // Feedback
    if (showFeedback && messageId) {
      wrapper.appendChild(this._createFeedbackRow(messageId));
    }

    this.messagesEl.appendChild(wrapper);
    this._scrollToBottom();
    return wrapper;
  }

  /* ------------------------------------------------------------------
     DOM: Streaming Assistant Message (built token by token)
     ------------------------------------------------------------------ */

  /**
   * Create an empty assistant bubble for streaming tokens into.
   * @returns {{ wrapper: HTMLElement, bubble: HTMLElement, rawText: string }}
   */
  _createStreamingBubble() {
    var wrapper = document.createElement("div");
    wrapper.className = "message-wrapper message-wrapper--assistant";
    wrapper.setAttribute("role", "listitem");

    var bubble = document.createElement("div");
    bubble.className = "message-bubble message-bubble--assistant";
    bubble.textContent = "";
    wrapper.appendChild(bubble);

    this.messagesEl.appendChild(wrapper);
    this._scrollToBottom();

    return { wrapper: wrapper, bubble: bubble, rawText: "" };
  }

  /**
   * Append a token to the streaming bubble, re-render markdown.
   * @param {Object} streamCtx - Context from _createStreamingBubble.
   * @param {string} token - Token text to append.
   */
  _appendToken(streamCtx, token) {
    streamCtx.rawText += token;
    streamCtx.bubble.innerHTML = renderMarkdown(escapeHtml(streamCtx.rawText));
    this._scrollToBottom();
  }

  /**
   * Finalize a streaming bubble: add disclaimer and feedback.
   * @param {Object} streamCtx
   * @param {string|null} messageId
   */
  _finalizeStream(streamCtx, messageId) {
    var disclaimer = document.createElement("div");
    disclaimer.className = "message-disclaimer";
    disclaimer.textContent =
      "Risposta generata dall'AI - Per informazioni ufficiali contattare il servizio clienti CUSTOMER_NAME";
    streamCtx.wrapper.appendChild(disclaimer);

    if (messageId) {
      streamCtx.wrapper.appendChild(this._createFeedbackRow(messageId));
    }
    this._scrollToBottom();
  }

  /* ------------------------------------------------------------------
     DOM: Typing Indicator
     ------------------------------------------------------------------ */

  _showTypingIndicator() {
    this._removeTypingIndicator();
    var wrapper = document.createElement("div");
    wrapper.className = "message-wrapper message-wrapper--assistant";
    wrapper.id = "typing-indicator";
    wrapper.setAttribute("aria-label", "L'assistente sta scrivendo");

    var indicator = document.createElement("div");
    indicator.className = "typing-indicator";
    for (var i = 0; i < 3; i++) {
      var dot = document.createElement("span");
      dot.className = "typing-dot";
      indicator.appendChild(dot);
    }

    wrapper.appendChild(indicator);
    this.messagesEl.appendChild(wrapper);
    this._scrollToBottom();
  }

  _removeTypingIndicator() {
    var existing = document.getElementById("typing-indicator");
    if (existing) {
      existing.remove();
    }
  }

  /* ------------------------------------------------------------------
     DOM: Error Message
     ------------------------------------------------------------------ */

  _addErrorMessage(text) {
    var wrapper = document.createElement("div");
    wrapper.className = "message-wrapper message-wrapper--assistant";
    wrapper.setAttribute("role", "listitem");

    var bubble = document.createElement("div");
    bubble.className = "message-bubble message-bubble--error";
    bubble.textContent = text;

    wrapper.appendChild(bubble);
    this.messagesEl.appendChild(wrapper);
    this._scrollToBottom();
  }

  /* ------------------------------------------------------------------
     DOM: Feedback Row
     ------------------------------------------------------------------ */

  /**
   * Create a feedback row with thumbs up/down buttons.
   * @param {string} messageId
   * @returns {HTMLElement}
   */
  _createFeedbackRow(messageId) {
    var self = this;
    var row = document.createElement("div");
    row.className = "feedback-row";

    var thumbUp = document.createElement("button");
    thumbUp.className = "feedback-btn";
    thumbUp.type = "button";
    thumbUp.setAttribute("aria-label", "Risposta utile");
    thumbUp.title = "Utile";
    // Thumbs-up SVG
    thumbUp.innerHTML =
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3H14z"/>' +
      '<path d="M7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"/></svg>';

    var thumbDown = document.createElement("button");
    thumbDown.className = "feedback-btn";
    thumbDown.type = "button";
    thumbDown.setAttribute("aria-label", "Risposta non utile");
    thumbDown.title = "Non utile";
    // Thumbs-down SVG
    thumbDown.innerHTML =
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3H10z"/>' +
      '<path d="M17 2h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"/></svg>';

    row.appendChild(thumbUp);
    row.appendChild(thumbDown);

    thumbUp.addEventListener("click", function () {
      self._submitFeedback(messageId, "up", thumbUp, thumbDown, row);
    });
    thumbDown.addEventListener("click", function () {
      self._submitFeedback(messageId, "down", thumbUp, thumbDown, row);
    });

    return row;
  }

  /* ------------------------------------------------------------------
     API: Submit Feedback
     ------------------------------------------------------------------ */

  /**
   * Send feedback to the backend and update UI.
   * @param {string} messageId
   * @param {string} rating - "up" or "down"
   * @param {HTMLElement} thumbUpBtn
   * @param {HTMLElement} thumbDownBtn
   * @param {HTMLElement} row
   */
  async _submitFeedback(messageId, rating, thumbUpBtn, thumbDownBtn, row) {
    // Disable both buttons immediately
    thumbUpBtn.disabled = true;
    thumbDownBtn.disabled = true;

    // Highlight selected
    if (rating === "up") {
      thumbUpBtn.classList.add("feedback-btn--selected");
    } else {
      thumbDownBtn.classList.add("feedback-btn--selected");
    }

    // Add thanks text
    var thanks = document.createElement("span");
    thanks.className = "feedback-thanks";
    thanks.textContent = "Grazie per il feedback!";
    row.appendChild(thanks);

    // Send to API (fire and forget with error handling)
    try {
      await fetch(this.apiBaseUrl + "/api/v1/chat/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: this.sessionId,
          message_id: messageId,
          rating: rating,
          comment: "",
        }),
      });
    } catch (_err) {
      // Feedback submission failure is non-critical; do not show error.
    }
  }

  /* ------------------------------------------------------------------
     API: Stream Chat Response
     ------------------------------------------------------------------ */

  /**
   * Send a chat message and stream the response via SSE.
   * Uses fetch + ReadableStream (not EventSource) since we need POST.
   * @param {string} userMessage
   */
  async _streamResponse(userMessage) {
    this.isStreaming = true;
    this._setInputEnabled(false);
    this._showTypingIndicator();

    var body = {
      message: userMessage,
    };
    if (this.sessionId) {
      body.session_id = this.sessionId;
    }
    if (this.billRef) {
      body.bill_ref = this.billRef;
    }

    this.abortController = new AbortController();
    var streamCtx = null;
    var receivedFirstToken = false;

    try {
      var response = await fetch(this.apiBaseUrl + "/api/v1/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: this.abortController.signal,
      });

      if (!response.ok) {
        this._removeTypingIndicator();
        var errorText = await this._getErrorText(response);
        this._addErrorMessage(errorText);
        this._finishStreaming();
        return;
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder("utf-8");
      var buffer = "";

      while (true) {
        var result = await reader.read();
        if (result.done) {
          break;
        }

        buffer += decoder.decode(result.value, { stream: true });

        // Process complete SSE lines from the buffer
        var lines = buffer.split("\n");
        // Keep the last (possibly incomplete) line in the buffer
        buffer = lines.pop() || "";

        for (var i = 0; i < lines.length; i++) {
          var line = lines[i].trim();
          if (!line.startsWith("data:")) {
            continue;
          }

          var jsonStr = line.substring(5).trim();
          if (!jsonStr || jsonStr === "[DONE]") {
            continue;
          }

          var parsed;
          try {
            parsed = JSON.parse(jsonStr);
          } catch (_parseErr) {
            continue;
          }

          if (parsed.done) {
            // Stream complete
            if (parsed.session_id) {
              this.sessionId = parsed.session_id;
              this._saveSession();
            }
            if (parsed.message_id) {
              this.currentMessageId = parsed.message_id;
            }
            if (streamCtx) {
              this._finalizeStream(streamCtx, this.currentMessageId);
            }
          } else if (parsed.token !== undefined) {
            // First token: remove typing indicator and create bubble
            if (!receivedFirstToken) {
              receivedFirstToken = true;
              this._removeTypingIndicator();
              streamCtx = this._createStreamingBubble();
            }
            this._appendToken(streamCtx, parsed.token);
          }
        }
      }

      // If no tokens were received at all, show a generic error
      if (!receivedFirstToken) {
        this._removeTypingIndicator();
        this._addErrorMessage(
          "Non ho ricevuto una risposta dal server. Riprova tra qualche istante."
        );
      }
    } catch (err) {
      this._removeTypingIndicator();
      if (err.name === "AbortError") {
        // User or system aborted; no action needed
      } else {
        this._addErrorMessage(
          "Errore di connessione. Controlla la tua rete e riprova."
        );
      }
    }

    this._finishStreaming();
  }

  /**
   * Extract a user-friendly error message from an HTTP response.
   * @param {Response} response
   * @returns {Promise<string>}
   */
  async _getErrorText(response) {
    try {
      var data = await response.json();
      if (data && data.detail) {
        return "Errore: " + data.detail;
      }
    } catch (_e) {
      // Fall through to generic message
    }
    if (response.status === 429) {
      return "Troppe richieste. Attendi qualche secondo e riprova.";
    }
    if (response.status >= 500) {
      return "Il servizio non e' al momento disponibile. Riprova tra qualche istante.";
    }
    return "Si e' verificato un errore (codice " + response.status + "). Riprova.";
  }

  /**
   * Clean up after streaming completes or errors.
   */
  _finishStreaming() {
    this.isStreaming = false;
    this.abortController = null;
    this._setInputEnabled(true);
    this.inputEl.focus();
  }

  /* ------------------------------------------------------------------
     UI Helpers
     ------------------------------------------------------------------ */

  _setInputEnabled(enabled) {
    this.inputEl.disabled = !enabled;
    this.sendBtn.disabled = !enabled;
  }

  _scrollToBottom() {
    // Use requestAnimationFrame to ensure DOM has updated
    var el = this.messagesEl;
    requestAnimationFrame(function () {
      el.scrollTop = el.scrollHeight;
    });
  }
}

/* ==========================================================================
   Initialisation
   ========================================================================== */

document.addEventListener("DOMContentLoaded", function () {
  window.chatWidget = new ChatWidget({
    apiBaseUrl: "", // Same origin
  });
});
