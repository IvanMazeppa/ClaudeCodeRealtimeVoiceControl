const connectButton = document.getElementById("connect-btn");
const disconnectButton = document.getElementById("disconnect-btn");
const muteButton = document.getElementById("mute-btn");
const voiceSelect = document.getElementById("voice-select");
const turnSelect = document.getElementById("turn-select");
const styleSelect = document.getElementById("style-select");
const presetSelect = document.getElementById("preset-select");
const presetSummary = document.getElementById("preset-summary");
const customInstructionsInput = document.getElementById("custom-instructions");
const savePromptButton = document.getElementById("save-prompt-btn");
const clearPromptButton = document.getElementById("clear-prompt-btn");
const promptSaveStatus = document.getElementById("prompt-save-status");
const transcriptList = document.getElementById("transcript-list");
const eventLog = document.getElementById("event-log");
const liveBanner = document.getElementById("live-banner");
const statusText = document.getElementById("status-text");
const statusDot = document.getElementById("status-dot");
const expiryLabel = document.getElementById("expiry-label");
const modelLabel = document.getElementById("model-label");

const supervisorStatusText = document.getElementById("supervisor-status-text");
const supervisorStatusDot = document.getElementById("supervisor-status-dot");
const supervisorFeedback = document.getElementById("supervisor-feedback");
const supervisorModelLabel = document.getElementById("supervisor-model-label");
const supervisorSessionLabel = document.getElementById("supervisor-session-label");
const supervisorPromptInput = document.getElementById("supervisor-prompt-input");
const supervisorStartButton = document.getElementById("supervisor-start-btn");
const supervisorSendLastButton = document.getElementById("supervisor-send-last-btn");
const supervisorObserveButton = document.getElementById("supervisor-observe-btn");
const supervisorInterruptButton = document.getElementById("supervisor-interrupt-btn");
const supervisorUseLastButton = document.getElementById("supervisor-use-last-btn");
const supervisorSendDraftButton = document.getElementById("supervisor-send-draft-btn");
const supervisorClearDraftButton = document.getElementById("supervisor-clear-draft-btn");
const approvalList = document.getElementById("approval-list");
const supervisorActionLog = document.getElementById("supervisor-action-log");
const terminalSnapshot = document.getElementById("terminal-snapshot");

const supportedVoices = new Set([
  "alloy",
  "ash",
  "ballad",
  "cedar",
  "coral",
  "echo",
  "marin",
  "sage",
  "shimmer",
  "verse"
]);
const promptPresetStorageKey = "realtimeVoice.selectedPreset";
const promptCustomStorageKey = "realtimeVoice.customInstructions";
const supervisorSessionStorageKey = "realtimeVoice.supervisorSessionId";

let peerConnection = null;
let dataChannel = null;
let localStream = null;
let localTrack = null;
let remoteAudio = null;
let isMuted = false;
let userDrafts = new Map();
let assistantDrafts = new Map();
let lastUserTurn = "";
let promptConfig = {
  baseInstructions: "",
  presets: []
};

function nowLabel() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function selectedVoice() {
  const voice = voiceSelect.value;
  if (supportedVoices.has(voice)) {
    return voice;
  }

  voiceSelect.value = "marin";
  addEvent("voice_fallback", `Unsupported voice "${voice}" was reset to "marin".`);
  return "marin";
}

function applyStatusTone(targetDot, tone = "idle") {
  targetDot.className = "status-dot";
  if (tone === "live") {
    targetDot.classList.add("live");
  } else if (tone === "busy") {
    targetDot.classList.add("busy");
  } else if (tone === "error") {
    targetDot.classList.add("error");
  }
}

function setStatus(label, tone = "idle") {
  statusText.textContent = label;
  applyStatusTone(statusDot, tone);
}

function setSupervisorStatus(label, tone = "idle") {
  supervisorStatusText.textContent = label;
  applyStatusTone(supervisorStatusDot, tone);
}

function setLiveBanner(text) {
  liveBanner.textContent = text;
}

function setPromptSaveStatus(text, pending = false) {
  promptSaveStatus.textContent = text;
  promptSaveStatus.classList.toggle("pending", pending);
}

function addEvent(type, detail) {
  const wrapper = document.createElement("article");
  wrapper.className = "event";
  wrapper.innerHTML = `<strong>${type}</strong><span>${detail}</span>`;
  eventLog.prepend(wrapper);
}

function addMessage(role, text) {
  if (!text || !text.trim()) {
    return;
  }

  const wrapper = document.createElement("article");
  wrapper.className = "message";
  wrapper.dataset.role = role;
  wrapper.innerHTML = `
    <div class="message-header">
      <span>${role}</span>
      <span>${nowLabel()}</span>
    </div>
    <p class="message-body"></p>
  `;
  wrapper.querySelector(".message-body").textContent = text.trim();
  transcriptList.prepend(wrapper);

  if (role === "user") {
    lastUserTurn = text.trim();
  }
}

function updateDraft(map, key, delta) {
  const current = map.get(key) || "";
  map.set(key, `${current}${delta}`);
}

function commitDraft(map, key, fallbackRole, finalText) {
  const text = finalText || map.get(key) || "";
  map.delete(key);
  addMessage(fallbackRole, text);
}

function currentPreset() {
  return promptConfig.presets.find((preset) => preset.id === presetSelect.value) || null;
}

function renderPresetSummary() {
  const preset = currentPreset();
  if (!preset) {
    presetSummary.textContent =
      "Base coding voice mode only. Add your own instructions below if you want a custom personality.";
    return;
  }

  presetSummary.textContent = preset.content;
}

function savePromptState() {
  localStorage.setItem(promptPresetStorageKey, presetSelect.value);
  localStorage.setItem(promptCustomStorageKey, customInstructionsInput.value);
  setPromptSaveStatus("Saved locally");
}

function restorePromptState() {
  const savedPreset = localStorage.getItem(promptPresetStorageKey);
  const savedCustom = localStorage.getItem(promptCustomStorageKey);

  if (savedPreset) {
    presetSelect.value = savedPreset;
  }
  if (savedCustom) {
    customInstructionsInput.value = savedCustom;
  }
}

function renderPresetOptions() {
  const options = [
    '<option value="">Base coding voice mode</option>',
    ...promptConfig.presets.map(
      (preset) => `<option value="${preset.id}">${preset.title}</option>`
    )
  ];
  presetSelect.innerHTML = options.join("");
  restorePromptState();
  renderPresetSummary();
}

async function loadPromptConfig() {
  const response = await fetch("/api/prompt-config");
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || "Failed to load prompt presets.");
  }

  promptConfig = {
    baseInstructions: data.baseInstructions || "",
    presets: Array.isArray(data.presets) ? data.presets : []
  };
  renderPresetOptions();
}

function buildInstructions() {
  const style = styleSelect.value;
  const styleLine =
    style === "detail"
      ? "Allow slightly longer spoken replies when helpful, but keep technical detail concise."
      : style === "balanced"
        ? "Keep spoken replies short, but allow a bit more context when needed."
        : "Keep spoken replies extra short and action-oriented.";
  const preset = currentPreset();
  const customInstructions = customInstructionsInput.value.trim();

  return [
    promptConfig.baseInstructions ||
      "You are in realtime voice work mode for coding sessions.",
    preset ? preset.content : "",
    `Current spoken style preference: ${styleLine}`,
    customInstructions
      ? `Additional user instructions:\n${customInstructions}`
      : ""
  ]
    .filter(Boolean)
    .join("\n\n");
}

function buildSessionUpdate() {
  const detection = turnSelect.value;
  const turnDetection =
    detection === "manual"
      ? null
      : detection === "server_vad"
        ? {
            type: "server_vad",
            threshold: 0.5,
            prefix_padding_ms: 300,
            silence_duration_ms: 500,
            create_response: true,
            interrupt_response: true
          }
        : {
            type: "semantic_vad",
            eagerness: "medium",
            create_response: true,
            interrupt_response: true
          };

  return {
    type: "session.update",
    session: {
      type: "realtime",
      instructions: buildInstructions(),
      audio: {
        input: {
          transcription: {
            model: "gpt-4o-transcribe"
          },
          turn_detection: turnDetection,
          noise_reduction: {
            type: "near_field"
          }
        },
        output: {
          voice: selectedVoice()
        }
      }
    }
  };
}

function handleRealtimeEvent(event) {
  switch (event.type) {
    case "session.created":
      addEvent("session.created", `Realtime session ready: ${event.session?.id || "unknown id"}`);
      break;
    case "input_audio_buffer.speech_started":
      setStatus("Listening", "busy");
      setLiveBanner("Speech detected. Capturing your turn...");
      break;
    case "input_audio_buffer.speech_stopped":
      setStatus("Processing", "busy");
      setLiveBanner("Speech stopped. Waiting for the model response...");
      break;
    case "conversation.item.input_audio_transcription.delta":
      updateDraft(userDrafts, event.item_id, event.delta || "");
      setLiveBanner(`You: ${userDrafts.get(event.item_id)}`);
      break;
    case "conversation.item.input_audio_transcription.completed":
      commitDraft(userDrafts, event.item_id, "user", event.transcript);
      setLiveBanner("User turn captured.");
      break;
    case "response.output_audio_transcript.delta":
      updateDraft(assistantDrafts, event.item_id || event.response_id, event.delta || "");
      setLiveBanner(`Assistant: ${assistantDrafts.get(event.item_id || event.response_id)}`);
      break;
    case "response.output_audio_transcript.done":
      commitDraft(
        assistantDrafts,
        event.item_id || event.response_id,
        "assistant",
        event.transcript
      );
      setStatus("Connected", "live");
      setLiveBanner("Assistant turn completed.");
      break;
    case "response.done":
      setStatus("Connected", "live");
      break;
    case "error":
      setStatus("Error", "error");
      setLiveBanner(event.error?.message || "The Realtime API reported an error.");
      addEvent("error", JSON.stringify(event.error || event, null, 2));
      break;
    default:
      if (
        event.type === "conversation.item.created" ||
        event.type === "response.created" ||
        event.type === "rate_limits.updated"
      ) {
        return;
      }
      addEvent(event.type, JSON.stringify(event, null, 2));
  }
}

function ensureRealtimeReady() {
  if (!dataChannel || dataChannel.readyState !== "open") {
    throw new Error("Connect to the Realtime session first.");
  }
}

async function requestToken() {
  const response = await fetch("/api/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      voice: selectedVoice(),
      instructions: buildInstructions()
    })
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Token request failed.");
  }

  modelLabel.textContent = data.model || "gpt-realtime-1.5";
  expiryLabel.textContent = data.expires_at
    ? new Date(data.expires_at * 1000).toLocaleTimeString()
    : "Unknown";
  return data.value;
}

async function connect() {
  connectButton.disabled = true;
  setStatus("Connecting", "busy");
  setLiveBanner("Requesting microphone and minting a short-lived Realtime token...");

  try {
    if (!promptConfig.baseInstructions) {
      await loadPromptConfig();
    }

    const token = await requestToken();
    localStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true
      }
    });

    localTrack = localStream.getTracks()[0];
    remoteAudio = document.createElement("audio");
    remoteAudio.autoplay = true;

    peerConnection = new RTCPeerConnection();
    peerConnection.ontrack = (event) => {
      remoteAudio.srcObject = event.streams[0];
    };
    peerConnection.onconnectionstatechange = () => {
      addEvent("connection", peerConnection.connectionState);
      if (peerConnection.connectionState === "connected") {
        setStatus("Connected", "live");
        setLiveBanner("Realtime voice session is live.");
      }
      if (
        peerConnection.connectionState === "failed" ||
        peerConnection.connectionState === "disconnected" ||
        peerConnection.connectionState === "closed"
      ) {
        setStatus("Disconnected", "idle");
      }
    };

    peerConnection.addTrack(localTrack, localStream);

    dataChannel = peerConnection.createDataChannel("oai-events");
    dataChannel.addEventListener("open", () => {
      const configEvent = buildSessionUpdate();
      dataChannel.send(JSON.stringify(configEvent));
      addEvent("session.update", "Applied browser-side Realtime session preferences.");
    });
    dataChannel.addEventListener("message", (event) => {
      const parsed = JSON.parse(event.data);
      handleRealtimeEvent(parsed);
    });

    const offer = await peerConnection.createOffer();
    await peerConnection.setLocalDescription(offer);

    const response = await fetch("https://api.openai.com/v1/realtime/calls", {
      method: "POST",
      body: offer.sdp,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/sdp"
      }
    });

    if (!response.ok) {
      throw new Error(await response.text());
    }

    const answer = {
      type: "answer",
      sdp: await response.text()
    };

    await peerConnection.setRemoteDescription(answer);
    disconnectButton.disabled = false;
    muteButton.disabled = false;
  } catch (error) {
    setStatus("Error", "error");
    setLiveBanner(error instanceof Error ? error.message : String(error));
    connectButton.disabled = false;
    addEvent("connect_error", error instanceof Error ? error.message : String(error));
    disconnect();
  }
}

function disconnect() {
  if (dataChannel) {
    dataChannel.close();
    dataChannel = null;
  }

  if (peerConnection) {
    peerConnection.close();
    peerConnection = null;
  }

  if (localStream) {
    localStream.getTracks().forEach((track) => track.stop());
    localStream = null;
  }

  localTrack = null;
  remoteAudio = null;
  isMuted = false;
  muteButton.textContent = "Mute mic";
  connectButton.disabled = false;
  disconnectButton.disabled = true;
  muteButton.disabled = true;
  setStatus("Idle");
  setLiveBanner("Session disconnected.");
}

function toggleMute() {
  if (!localTrack) {
    return;
  }

  isMuted = !isMuted;
  localTrack.enabled = !isMuted;
  muteButton.textContent = isMuted ? "Unmute mic" : "Mute mic";
  setLiveBanner(isMuted ? "Microphone muted." : "Microphone live.");
}

function markPromptDirty() {
  setPromptSaveStatus("Unsaved local changes", true);
}

function getSupervisorSessionId() {
  const existing = localStorage.getItem(supervisorSessionStorageKey);
  if (existing) {
    return existing;
  }

  const generated = typeof crypto?.randomUUID === "function"
    ? crypto.randomUUID()
    : `supervisor-${Date.now()}`;
  localStorage.setItem(supervisorSessionStorageKey, generated);
  return generated;
}

function setSupervisorFeedback(text) {
  supervisorFeedback.textContent = text && text.trim()
    ? text
    : "The Python supervisor is ready when you are.";
}

function setTerminalSnapshot(text) {
  terminalSnapshot.textContent = text && text.trim()
    ? text
    : "The latest visible Claude terminal output will appear here.";
}

function renderSupervisorActionLog(items) {
  supervisorActionLog.innerHTML = "";
  if (!items || !items.length) {
    const empty = document.createElement("article");
    empty.className = "event";
    empty.innerHTML = "<strong>idle</strong><span>No supervisor actions yet.</span>";
    supervisorActionLog.append(empty);
    return;
  }

  items.forEach((item) => {
    const entry = document.createElement("article");
    entry.className = "event";
    entry.innerHTML = `<strong>${item.type || "action"}</strong><span>${item.detail || ""}</span>`;
    supervisorActionLog.append(entry);
  });
}

function renderApprovals(items) {
  approvalList.innerHTML = "";
  if (!items || !items.length) {
    approvalList.textContent = "No approvals pending.";
    return;
  }

  items.forEach((item) => {
    const wrapper = document.createElement("article");
    wrapper.className = "approval-card";
    wrapper.dataset.callId = item.callId;
    const argumentsText = typeof item.arguments === "string"
      ? item.arguments
      : JSON.stringify(item.arguments || {}, null, 2);
    wrapper.innerHTML = `
      <strong>${item.toolName || "approval required"}</strong>
      <p>${argumentsText}</p>
      <div class="button-row">
        <button class="button primary" type="button" data-approval="approve">Approve</button>
        <button class="button" type="button" data-approval="reject">Reject</button>
      </div>
    `;
    approvalList.append(wrapper);
  });
}

function speakText(text) {
  if (!text || !("speechSynthesis" in window)) {
    return;
  }

  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
}

async function callSupervisor(path, payload = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      sessionId: getSupervisorSessionId(),
      ...payload
    })
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Supervisor request failed.");
  }
  return data;
}

function applySupervisorResponse(data, { speak = true, addTranscriptMessage = true } = {}) {
  supervisorModelLabel.textContent = data.supervisorModel || supervisorModelLabel.textContent;
  supervisorSessionLabel.textContent = data.sessionId || getSupervisorSessionId();
  setSupervisorFeedback(data.spokenResponse || "The Python supervisor finished without a spoken summary.");
  setTerminalSnapshot(data.terminalSnapshot || "");
  renderSupervisorActionLog(Array.isArray(data.actionLog) ? data.actionLog : []);
  renderApprovals(Array.isArray(data.pendingApprovals) ? data.pendingApprovals : []);

  if (data.pendingApprovals?.length) {
    setSupervisorStatus("Awaiting approval", "busy");
  } else if (data.claudeSessionExists) {
    setSupervisorStatus(data.terminalReady ? "Claude ready" : "Claude busy", data.terminalReady ? "live" : "busy");
  } else {
    setSupervisorStatus("Claude not attached", "idle");
  }

  if (data.spokenResponse && addTranscriptMessage) {
    addMessage("assistant", data.spokenResponse);
  }
  if (data.spokenResponse && speak) {
    speakText(data.spokenResponse);
  }
}

async function refreshSupervisorHealth() {
  try {
    const response = await fetch("/api/supervisor/health");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Supervisor health failed.");
    }

    supervisorModelLabel.textContent = data.supervisorModel || "gpt-5.4";
    supervisorSessionLabel.textContent = getSupervisorSessionId();
    setTerminalSnapshot(data.terminal?.output || "");
    renderSupervisorActionLog([]);
    renderApprovals([]);
    setSupervisorFeedback("Supervisor loaded. Start or verify Claude when you want the backend to take over.");
    if (data.terminal?.session_exists) {
      setSupervisorStatus(data.terminal.ready ? "Claude ready" : "Claude busy", data.terminal.ready ? "live" : "busy");
    } else {
      setSupervisorStatus("Claude not attached", "idle");
    }
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_health_error", error instanceof Error ? error.message : String(error));
  }
}

async function startSupervisorClaude() {
  setSupervisorStatus("Starting", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/session");
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_start_error", error instanceof Error ? error.message : String(error));
  }
}

async function observeClaudeState() {
  setSupervisorStatus("Observing", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/observe");
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_observe_error", error instanceof Error ? error.message : String(error));
  }
}

async function sendLastHeardTurn() {
  if (!lastUserTurn) {
    setSupervisorFeedback("No spoken turn is available yet. Speak first, or send a manual draft.");
    return;
  }

  setSupervisorStatus("Sending", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/turn", {
      userText: lastUserTurn
    });
    applySupervisorResponse(data, {
      addTranscriptMessage: true
    });
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_turn_error", error instanceof Error ? error.message : String(error));
  }
}

function useLastHeardTurn() {
  if (!lastUserTurn) {
    setSupervisorFeedback("No spoken turn is available yet. Speak first to seed the draft box.");
    return;
  }

  supervisorPromptInput.value = lastUserTurn;
  setSupervisorFeedback("Moved the last heard turn into the manual prompt draft box.");
}

async function sendManualDraft() {
  const prompt = supervisorPromptInput.value.trim();
  if (!prompt) {
    setSupervisorFeedback("Type a manual prompt first, or use the last heard turn.");
    return;
  }

  setSupervisorStatus("Sending", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/manual-prompt", {
      prompt
    });
    applySupervisorResponse(data, {
      addTranscriptMessage: true
    });
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_manual_prompt_error", error instanceof Error ? error.message : String(error));
  }
}

async function interruptClaude() {
  setSupervisorStatus("Interrupting", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/interrupt");
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_interrupt_error", error instanceof Error ? error.message : String(error));
  }
}

async function handleApprovalDecision(callId, approve) {
  setSupervisorStatus("Resolving approval", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/decision", {
      callId,
      approve,
      rejectionMessage: approve ? undefined : "The user rejected this terminal action."
    });
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("supervisor_approval_error", error instanceof Error ? error.message : String(error));
  }
}

presetSelect.addEventListener("change", () => {
  renderPresetSummary();
  markPromptDirty();
});
customInstructionsInput.addEventListener("input", markPromptDirty);
savePromptButton.addEventListener("click", savePromptState);
clearPromptButton.addEventListener("click", () => {
  customInstructionsInput.value = "";
  savePromptState();
});
connectButton.addEventListener("click", connect);
disconnectButton.addEventListener("click", disconnect);
muteButton.addEventListener("click", toggleMute);

supervisorStartButton.addEventListener("click", startSupervisorClaude);
supervisorSendLastButton.addEventListener("click", sendLastHeardTurn);
supervisorObserveButton.addEventListener("click", observeClaudeState);
supervisorInterruptButton.addEventListener("click", interruptClaude);
supervisorUseLastButton.addEventListener("click", useLastHeardTurn);
supervisorSendDraftButton.addEventListener("click", sendManualDraft);
supervisorClearDraftButton.addEventListener("click", () => {
  supervisorPromptInput.value = "";
  setSupervisorFeedback("Cleared the manual Claude prompt draft.");
});
approvalList.addEventListener("click", (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) {
    return;
  }

  const action = target.dataset.approval;
  if (!action) {
    return;
  }

  const card = target.closest(".approval-card");
  const callId = card?.dataset.callId;
  if (!callId) {
    return;
  }

  void handleApprovalDecision(callId, action === "approve");
});

addEvent("ready", "UI loaded. Choose your voice settings and connect when ready.");
loadPromptConfig()
  .then(() => {
    addEvent("prompt_config", `Loaded ${promptConfig.presets.length} preset personalities.`);
  })
  .catch((error) => {
    addEvent("prompt_config_error", error instanceof Error ? error.message : String(error));
    setPromptSaveStatus("Prompt presets unavailable");
  });
renderSupervisorActionLog([]);
renderApprovals([]);
refreshSupervisorHealth();
