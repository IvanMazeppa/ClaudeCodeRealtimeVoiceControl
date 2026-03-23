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
const sessionMemoryProjectSession = document.getElementById("session-memory-project-session");
const sessionMemoryProfileSession = document.getElementById("session-memory-profile-session");
const sessionMemoryProfile = document.getElementById("session-memory-profile");
const sessionMemoryGoal = document.getElementById("session-memory-goal");
const sessionMemoryLatestTurn = document.getElementById("session-memory-latest-turn");
const sessionMemoryUpdated = document.getElementById("session-memory-updated");
const sessionMemorySummary = document.getElementById("session-memory-summary");
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
const supervisorMonitorStatus = document.getElementById("supervisor-monitor-status");
const supervisorMonitorUpdated = document.getElementById("supervisor-monitor-updated");
const supervisorMonitorToggleButton = document.getElementById("supervisor-monitor-toggle-btn");
const mentorGoalInput = document.getElementById("mentor-goal-input");
const mentorExplainButton = document.getElementById("mentor-explain-btn");
const mentorSecondOpinionButton = document.getElementById("mentor-second-opinion-btn");
const mentorDraftPromptButton = document.getElementById("mentor-draft-prompt-btn");
const mentorExplainApprovalButton = document.getElementById("mentor-explain-approval-btn");
const mentorUseDraftButton = document.getElementById("mentor-use-draft-btn");
const mentorSummary = document.getElementById("mentor-summary");
const mentorBullets = document.getElementById("mentor-bullets");
const mentorRisks = document.getElementById("mentor-risks");
const mentorFiles = document.getElementById("mentor-files");
const mentorDraftOutput = document.getElementById("mentor-draft-output");

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
const promptProfileStateStoragePrefix = "realtimeVoice.profileState";
const supervisorSessionStorageKey = "realtimeVoice.supervisorSessionId";
const supervisorMonitorIntervalMs = 1800;
const supervisorMonitorSlowIntervalMs = 4200;
const transcriptPreviewLimit = 6;
const browserStateSyncDebounceMs = 320;

let peerConnection = null;
let dataChannel = null;
let localStream = null;
let localTrack = null;
let remoteAudio = null;
let isMuted = false;
let userDrafts = new Map();
let assistantDrafts = new Map();
let lastUserTurn = "";
let latestPendingApprovals = [];
let latestMentorDraft = "";
let transcriptHistory = [];
let promptConfig = {
  baseInstructions: "",
  presets: []
};
let supervisorMonitorEnabled = true;
let supervisorMonitorTimer = null;
let supervisorMonitorRefreshing = false;
let supervisorRequestCount = 0;
let browserStateSyncTimer = null;
let browserStateSyncInFlight = false;
let browserStateFingerprint = "";
let latestMentorState = emptyMentorState();
let activeProfileStorageKey = "";
let activeProfileHasLocalState = false;

// Companion WebSocket state
let companionWs = null;
let companionTools = [];
let companionInstructions = "";
let companionReady = false;

function nowLabel() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function safeStorageSegment(value) {
  const normalized = String(value || "").trim().toLowerCase();
  const compact = normalized.replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "");
  return compact || "base";
}

function formatSessionHandle(value, fallback) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return fallback;
  }

  if (normalized.length <= 30) {
    return normalized;
  }

  return `${normalized.slice(0, 14)}...${normalized.slice(-10)}`;
}

function emptyMentorState() {
  return {
    screenSummary: "",
    bullets: [],
    risks: [],
    changedFiles: [],
    draftedPrompt: ""
  };
}

function normalizeStringList(raw, { limit = 6, itemLimit = 220 } = {}) {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .slice(0, limit)
    .map((item) => String(item || "").trim())
    .filter(Boolean)
    .map((item) => (item.length > itemLimit ? `${item.slice(0, itemLimit - 3).trimEnd()}...` : item));
}

function normalizeMentorState(raw = {}) {
  return {
    screenSummary: String(raw.screenSummary || "").trim(),
    bullets: normalizeStringList(raw.bullets),
    risks: normalizeStringList(raw.risks),
    changedFiles: normalizeStringList(raw.changedFiles),
    draftedPrompt: String(
      raw.draftedPrompt
      || raw.draftedFollowUpPrompt
      || ""
    ).trim()
  };
}

function normalizeTranscriptHistory(raw) {
  if (!Array.isArray(raw)) {
    return [];
  }

  return raw
    .slice(-transcriptPreviewLimit)
    .map((item) => {
      if (!item || typeof item !== "object") {
        return null;
      }

      const role = String(item.role || "").trim().toLowerCase() || "assistant";
      const text = String(item.text || "").trim();
      const capturedAt = String(item.capturedAt || "").trim();
      if (!text) {
        return null;
      }

      return {
        role,
        text,
        capturedAt
      };
    })
    .filter(Boolean);
}

function activePresetId() {
  return currentPreset()?.id || presetSelect.value || "";
}

function currentProfileKey() {
  return `preset:${safeStorageSegment(activePresetId() || "base")}`;
}

function buildProfileStorageKey(profileKey = currentProfileKey()) {
  return `${promptProfileStateStoragePrefix}.${safeStorageSegment(getSupervisorSessionId())}.${safeStorageSegment(profileKey)}`;
}

function getProfileSessionId() {
  return `${getSupervisorSessionId()}::${currentProfileKey()}`;
}

function formatTranscriptTime(capturedAt) {
  if (!capturedAt) {
    return nowLabel();
  }

  const parsed = new Date(capturedAt);
  if (Number.isNaN(parsed.getTime())) {
    return nowLabel();
  }

  return parsed.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function compactInstructionText(text, limit = 220) {
  const normalized = String(text || "").trim().replace(/\s+/g, " ");
  if (!normalized) {
    return "";
  }

  if (normalized.length <= limit) {
    return normalized;
  }

  return `${normalized.slice(0, Math.max(0, limit - 3)).trimEnd()}...`;
}

function renderTranscriptHistory() {
  transcriptList.innerHTML = "";
  [...transcriptHistory].reverse().forEach((entry) => {
    const wrapper = document.createElement("article");
    wrapper.className = "message";
    wrapper.dataset.role = entry.role;
    wrapper.innerHTML = `
      <div class="message-header">
        <span>${entry.role}</span>
        <span>${formatTranscriptTime(entry.capturedAt)}</span>
      </div>
      <p class="message-body"></p>
    `;
    wrapper.querySelector(".message-body").textContent = entry.text;
    transcriptList.append(wrapper);
  });
}

function currentProfileSnapshot() {
  return {
    assistantStyle: styleSelect.value,
    customInstructions: customInstructionsInput.value.trim(),
    mentorGoal: mentorGoalInput.value.trim(),
    manualPromptDraft: supervisorPromptInput.value.trim(),
    lastUserTurn,
    transcriptHistory: transcriptHistory.slice(-transcriptPreviewLimit),
    mentorState: latestMentorState
  };
}

function persistActiveProfileState(targetKey = activeProfileStorageKey) {
  if (!targetKey) {
    return;
  }

  localStorage.setItem(targetKey, JSON.stringify(currentProfileSnapshot()));
  activeProfileHasLocalState = true;
}

function loadStoredProfileState(profileKey = currentProfileKey()) {
  const raw = localStorage.getItem(buildProfileStorageKey(profileKey));
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object") {
        return parsed;
      }
    } catch (error) {
      addEvent("profile_state_error", error instanceof Error ? error.message : String(error));
    }
  }

  const legacyCustomInstructions = localStorage.getItem(promptCustomStorageKey);
  if (legacyCustomInstructions?.trim()) {
    return {
      customInstructions: legacyCustomInstructions
    };
  }

  return null;
}

function applyProfileState(profileState = {}) {
  styleSelect.value = String(profileState.assistantStyle || "brief");
  customInstructionsInput.value = String(profileState.customInstructions || "");
  mentorGoalInput.value = String(profileState.mentorGoal || "");
  supervisorPromptInput.value = String(profileState.manualPromptDraft || "");
  lastUserTurn = String(profileState.lastUserTurn || "").trim();
  transcriptHistory = normalizeTranscriptHistory(profileState.transcriptHistory);
  renderTranscriptHistory();
  renderMentorResponse(profileState.mentorState || emptyMentorState(), {
    persist: false
  });
}

function buildProfileStateFromMemory(memory = {}) {
  return {
    assistantStyle: String(memory.assistantStyle || "brief"),
    customInstructions: String(memory.customInstructions || ""),
    mentorGoal: String(memory.currentGoal || ""),
    manualPromptDraft: String(memory.manualPromptDraft || ""),
    lastUserTurn: String(memory.lastUserTurn || ""),
    transcriptHistory: normalizeTranscriptHistory(memory.transcriptPreview),
    mentorState: normalizeMentorState({
      screenSummary: memory.mentorSummary,
      bullets: memory.mentorBullets,
      risks: memory.mentorRisks,
      changedFiles: memory.mentorFiles,
      draftedPrompt: memory.latestMentorDraft
    })
  };
}

function hydrateProfileFromSessionMemory(memory = {}) {
  const restored = buildProfileStateFromMemory(memory);
  const hasVisibleState = Boolean(
    restored.customInstructions
    || restored.mentorGoal
    || restored.manualPromptDraft
    || restored.lastUserTurn
    || restored.transcriptHistory.length
    || restored.mentorState.screenSummary
    || restored.mentorState.draftedPrompt
  );
  if (!hasVisibleState) {
    return;
  }

  applyProfileState(restored);
  persistActiveProfileState();
  setPromptSaveStatus("Restored this character from supervisor memory");
}

function activateCurrentProfile({ announce = false, forceSync = false } = {}) {
  if (activeProfileStorageKey) {
    persistActiveProfileState(activeProfileStorageKey);
  }

  activeProfileStorageKey = buildProfileStorageKey();
  const storedState = loadStoredProfileState();
  activeProfileHasLocalState = Boolean(storedState);
  applyProfileState(storedState || {});
  renderPresetSummary();
  renderSessionMemory({
    projectSessionId: getSupervisorSessionId(),
    profileSessionId: getProfileSessionId(),
    profileLabel: profileLabel(),
    currentGoal: mentorGoalInput.value.trim(),
    lastUserTurn,
    updatedAt: activeProfileHasLocalState ? "Local restore ready" : "Waiting for first sync",
    interfaceSummary:
      "Claude and project work stay shared across presets. The selected character keeps its own memory, drafts, and mentor thread."
  });

  if (announce) {
    setSupervisorFeedback(
      `Switched to ${profileLabel()}. Claude stays on the shared project lane while this character keeps its own conversation memory.`
    );
  }

  browserStateFingerprint = "";
  if (forceSync) {
    void syncBrowserState({ force: true });
  }
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

function setSupervisorMonitorState(label) {
  supervisorMonitorStatus.textContent = label;
}

function setSupervisorMonitorUpdated(label) {
  supervisorMonitorUpdated.textContent = label;
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

  const normalized = text.trim();
  rememberTranscriptEntry(role, normalized);

  if (role === "user") {
    lastUserTurn = normalized;
  }

  renderTranscriptHistory();
  persistActiveProfileState();
  scheduleBrowserStateSync();
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

function rememberTranscriptEntry(role, text) {
  transcriptHistory.push({
    role,
    text,
    capturedAt: new Date().toISOString()
  });
  if (transcriptHistory.length > transcriptPreviewLimit) {
    transcriptHistory = transcriptHistory.slice(-transcriptPreviewLimit);
  }
}

function profileLabel() {
  const preset = currentPreset();
  const presetTitle = preset?.title || "Base coding voice mode";
  return `${presetTitle} / ${styleSelect.value}`;
}

function buildBrowserState() {
  return {
    realtimeConnected: Boolean(peerConnection && peerConnection.connectionState === "connected"),
    realtimeStatus: statusText.textContent.trim(),
    supervisorStatus: supervisorStatusText.textContent.trim(),
    profileSessionId: getProfileSessionId(),
    voice: selectedVoice(),
    turnDetection: turnSelect.value,
    assistantStyle: styleSelect.value,
    selectedPresetId: currentPreset()?.id || "",
    selectedPresetTitle: currentPreset()?.title || "",
    customInstructions: customInstructionsInput.value.trim(),
    profileLabel: profileLabel(),
    liveTerminalEnabled: supervisorMonitorEnabled,
    pendingApprovalCount: latestPendingApprovals.length,
    lastUserTurn,
    manualPromptDraft: supervisorPromptInput.value.trim(),
    mentorGoal: mentorGoalInput.value.trim(),
    latestMentorDraft,
    mentorSummary: latestMentorState.screenSummary,
    mentorBullets: latestMentorState.bullets,
    mentorRisks: latestMentorState.risks,
    mentorFiles: latestMentorState.changedFiles,
    transcriptPreview: transcriptHistory.slice(-4)
  };
}

function renderSessionMemory(memory = {}) {
  sessionMemoryProjectSession.textContent = formatSessionHandle(
    memory.projectSessionId,
    "Shared lane not created yet"
  );
  sessionMemoryProjectSession.title = String(memory.projectSessionId || "");
  sessionMemoryProfileSession.textContent = formatSessionHandle(
    memory.profileSessionId,
    "Character lane not created yet"
  );
  sessionMemoryProfileSession.title = String(memory.profileSessionId || "");
  sessionMemoryProfile.textContent = memory.profileLabel?.trim()
    || "Awaiting browser sync";
  sessionMemoryGoal.textContent = memory.currentGoal?.trim()
    || "No goal captured yet";
  sessionMemoryLatestTurn.textContent = memory.lastUserTurn?.trim()
    || "No recent turn captured yet";
  sessionMemoryUpdated.textContent = memory.updatedAt?.trim()
    || "Not yet";
  sessionMemorySummary.textContent = memory.interfaceSummary?.trim()
    || "The supervisor has not received browser context yet.";
}

function scheduleBrowserStateSync(delay = browserStateSyncDebounceMs) {
  if (browserStateSyncTimer) {
    window.clearTimeout(browserStateSyncTimer);
  }

  browserStateSyncTimer = window.setTimeout(() => {
    void syncBrowserState();
  }, delay);
}

async function syncBrowserState({ force = false } = {}) {
  const browserState = buildBrowserState();
  const fingerprint = JSON.stringify(browserState);
  if (!force && fingerprint === browserStateFingerprint) {
    return;
  }

  if (browserStateSyncInFlight) {
    return;
  }

  browserStateSyncInFlight = true;

  // Also push state over the companion WebSocket (parallel, non-blocking)
  syncCompanionBrowserState();

  try {
    const response = await fetch("/api/supervisor/context", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        sessionId: getSupervisorSessionId(),
        profileSessionId: getProfileSessionId(),
        browserState
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Browser-state sync failed.");
    }

    browserStateFingerprint = fingerprint;
    renderSessionMemory(data.sessionMemory || {});
  } catch (error) {
    addEvent("supervisor_context_error", error instanceof Error ? error.message : String(error));
  } finally {
    browserStateSyncInFlight = false;
  }
}

function savePromptState() {
  localStorage.setItem(promptPresetStorageKey, presetSelect.value);
  persistActiveProfileState();
  localStorage.removeItem(promptCustomStorageKey);
  setPromptSaveStatus("Saved to this character");
  scheduleBrowserStateSync();
  applyLiveSessionUpdate("Saved character instructions into the live Realtime session.");
}

function restorePromptState() {
  const savedPreset = localStorage.getItem(promptPresetStorageKey);
  if (savedPreset) {
    presetSelect.value = savedPreset;
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
  restorePromptState();
  activateCurrentProfile();
}

function buildPersistentPresetMemory() {
  const memoryLines = [];
  const currentGoal = compactInstructionText(mentorGoalInput.value, 220);
  const rememberedTurn = compactInstructionText(lastUserTurn, 240);
  const rememberedDraft = compactInstructionText(latestMentorDraft, 260);
  const transcriptLines = transcriptHistory
    .slice(-4)
    .map((entry) => {
      if (!entry || typeof entry !== "object") {
        return "";
      }

      const role = compactInstructionText(entry.role, 24).toLowerCase() || "assistant";
      const text = compactInstructionText(entry.text, 180);
      return text ? `${role}: ${text}` : "";
    })
    .filter(Boolean);

  if (currentGoal) {
    memoryLines.push(`Current standing goal for this preset: ${currentGoal}`);
  }
  if (rememberedTurn) {
    memoryLines.push(`Most recent remembered user turn before this session: ${rememberedTurn}`);
  }
  if (rememberedDraft) {
    memoryLines.push(`Last drafted follow-up for this preset: ${rememberedDraft}`);
  }
  if (transcriptLines.length) {
    memoryLines.push(
      "Recent remembered conversation for this preset:\n"
      + transcriptLines.join("\n")
    );
  }

  if (!memoryLines.length) {
    return "";
  }

  return [
    "Persistent preset memory carried over after reconnect or refresh.",
    "Use it as remembered context for this character, not as a new live user turn.",
    memoryLines.join("\n")
  ].join("\n");
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
  const persistentPresetMemory = buildPersistentPresetMemory();

  return [
    promptConfig.baseInstructions ||
      "You are in realtime voice work mode for coding sessions.",
    preset ? preset.content : "",
    `Current spoken style preference: ${styleLine}`,
    persistentPresetMemory,
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

  // Use companion instructions if available, otherwise fall back to local
  const instructions = companionInstructions || buildInstructions();

  const sessionPayload = {
    type: "session.update",
    session: {
      type: "realtime",
      instructions,
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

  // Register companion function tools so the Realtime model can call them
  if (companionTools.length > 0) {
    sessionPayload.session.tools = companionTools;
  }

  return sessionPayload;
}

function applyLiveSessionUpdate(detail) {
  if (!dataChannel || dataChannel.readyState !== "open") {
    return false;
  }

  dataChannel.send(JSON.stringify(buildSessionUpdate()));
  addEvent("session.update", detail);
  return true;
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
    case "response.function_call_arguments.done":
      // Forward tool calls to the companion server for execution
      if (companionWs && companionWs.readyState === WebSocket.OPEN) {
        companionWs.send(JSON.stringify({
          type: "tool_call",
          name: event.name,
          callId: event.call_id,
          arguments: event.arguments,
        }));
        addEvent("tool_call", `Calling ${event.name}...`);
      } else {
        addEvent("tool_call_error", `Companion not connected; cannot execute ${event.name}`);
      }
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
      applyLiveSessionUpdate("Applied browser-side Realtime session preferences and restored preset memory.");
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
    scheduleBrowserStateSync();
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
  disconnectCompanion();
  scheduleBrowserStateSync();
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

// ── Companion WebSocket ────────────────────────────────────────────

function connectCompanion() {
  if (companionWs && companionWs.readyState <= WebSocket.OPEN) {
    return;
  }

  // Connect through the Node server's /companion proxy (same origin, same port)
  // so we don't need a second port forwarded through WSL2
  const wsProto = window.location.protocol === "https:" ? "wss:" : "ws:";
  companionWs = new WebSocket(`${wsProto}//${window.location.host}/companion`);

  companionWs.onopen = () => {
    companionWs.send(JSON.stringify({
      type: "init",
      sessionId: getSupervisorSessionId(),
      profileSessionId: getProfileSessionId(),
    }));
    addEvent("companion", "WebSocket connected to companion server.");
  };

  companionWs.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data);
      handleCompanionMessage(msg);
    } catch (err) {
      addEvent("companion_error", "Failed to parse companion message.");
    }
  };

  companionWs.onclose = () => {
    companionReady = false;
    addEvent("companion", "WebSocket disconnected. Reconnecting in 3s...");
    setTimeout(connectCompanion, 3000);
  };

  companionWs.onerror = () => {
    // onclose will fire after this; no need to double-log
  };
}

function handleCompanionMessage(msg) {
  switch (msg.type) {
    case "ready":
      companionTools = msg.tools || [];
      companionInstructions = msg.instructions || "";
      companionReady = true;
      addEvent("companion", `Ready with ${companionTools.length} tools.`);
      // Re-send session.update so the Realtime model picks up tools + instructions
      applyLiveSessionUpdate("Companion tools registered in Realtime session.");
      break;
    case "memory":
      renderSessionMemory(msg.memory || {});
      break;
    case "approvals":
      renderApprovals(msg.pending || []);
      break;
    case "terminal":
      if (msg.state) {
        setTerminalSnapshot(msg.state.output || "");
        // Update status indicator with interactive menu awareness
        if (msg.state.session_exists) {
          if (msg.state.interactive_menu) {
            setSupervisorStatus("Interactive menu", "busy");
          } else if (msg.state.ready) {
            setSupervisorStatus("Claude ready", "live");
          } else {
            setSupervisorStatus("Claude busy", "busy");
          }
        }
      }
      break;
    case "tool_result":
      handleToolResult(msg);
      break;
    case "error":
      addEvent("companion_error", msg.message || "Unknown companion error");
      break;
    case "pong":
      break;
  }
}

function handleToolResult(msg) {
  if (!dataChannel || dataChannel.readyState !== "open") {
    addEvent("companion_error", "Data channel not open; cannot relay tool result.");
    return;
  }

  // Send the function call output back to OpenAI Realtime API
  dataChannel.send(JSON.stringify({
    type: "conversation.item.create",
    item: {
      type: "function_call_output",
      call_id: msg.callId,
      output: msg.result || "",
    }
  }));

  // Trigger a new model response that incorporates the tool result
  dataChannel.send(JSON.stringify({
    type: "response.create"
  }));

  addEvent("tool_result", `${msg.name}: ${msg.ok ? "done" : "error"}`);
}

function syncCompanionBrowserState() {
  if (!companionWs || companionWs.readyState !== WebSocket.OPEN) {
    return;
  }
  companionWs.send(JSON.stringify({
    type: "browser_state",
    state: buildBrowserState(),
  }));
}

function disconnectCompanion() {
  if (companionWs) {
    // Prevent auto-reconnect by removing onclose before closing
    companionWs.onclose = null;
    companionWs.close();
    companionWs = null;
  }
  companionTools = [];
  companionInstructions = "";
  companionReady = false;
}

// ── End Companion WebSocket ────────────────────────────────────────

function markPromptDirty() {
  persistActiveProfileState();
  setPromptSaveStatus("Profile draft updated locally", true);
  scheduleBrowserStateSync();
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
  latestPendingApprovals = Array.isArray(items) ? items : [];
  approvalList.innerHTML = "";
  if (!items || !items.length) {
    approvalList.textContent = "No approvals pending.";
    scheduleBrowserStateSync();
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

  scheduleBrowserStateSync();
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

function updateSupervisorMonitorButton() {
  supervisorMonitorToggleButton.textContent = supervisorMonitorEnabled
    ? "Pause live view"
    : "Resume live view";
}

function syncSupervisorMonitorState(data) {
  if (!supervisorMonitorEnabled) {
    setSupervisorMonitorState("Live view paused");
    return;
  }

  if (data.pendingApprovals?.length) {
    setSupervisorMonitorState("Watching approvals");
  } else if (!data.claudeSessionExists) {
    setSupervisorMonitorState("Waiting for Claude");
  } else if (data.terminalInteractiveMenu) {
    setSupervisorMonitorState("Interactive menu active");
  } else if (data.terminalReady) {
    setSupervisorMonitorState("Live view active");
  } else {
    setSupervisorMonitorState("Watching Claude work");
  }

  setSupervisorMonitorUpdated(nowLabel());
}

function nextSupervisorMonitorDelay() {
  return document.hidden ? supervisorMonitorSlowIntervalMs : supervisorMonitorIntervalMs;
}

function scheduleSupervisorMonitor(delay = nextSupervisorMonitorDelay()) {
  if (supervisorMonitorTimer) {
    window.clearTimeout(supervisorMonitorTimer);
    supervisorMonitorTimer = null;
  }

  if (!supervisorMonitorEnabled) {
    return;
  }

  supervisorMonitorTimer = window.setTimeout(() => {
    void refreshSupervisorMonitor();
  }, delay);
}

function renderMentorList(target, items, emptyText) {
  target.innerHTML = "";
  if (!items || !items.length) {
    const item = document.createElement("li");
    item.textContent = emptyText;
    target.append(item);
    return;
  }

  items.forEach((entry) => {
    const item = document.createElement("li");
    item.textContent = entry;
    target.append(item);
  });
}

function renderMentorResponse(data = {}, { persist = true } = {}) {
  const mentorState = normalizeMentorState(data);
  const screenSummary = mentorState.screenSummary;
  const draft = mentorState.draftedPrompt;
  latestMentorDraft = draft;
  latestMentorState = mentorState;

  mentorSummary.textContent = screenSummary
    || "Mentor results will appear here once you run one of the mentor actions.";
  renderMentorList(mentorBullets, mentorState.bullets, "No mentor detail yet.");
  renderMentorList(mentorRisks, mentorState.risks, "No risks highlighted yet.");
  renderMentorList(mentorFiles, mentorState.changedFiles, "No files highlighted yet.");
  mentorDraftOutput.textContent = draft || "No drafted Claude prompt yet.";
  mentorUseDraftButton.disabled = !draft;

  if (persist) {
    persistActiveProfileState();
  }
}

async function callSupervisor(path, payload = {}) {
  supervisorRequestCount += 1;
  const browserState = buildBrowserState();
  try {
    const response = await fetch(path, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        sessionId: getSupervisorSessionId(),
        profileSessionId: getProfileSessionId(),
        browserState,
        ...payload
      })
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Supervisor request failed.");
    }
    browserStateFingerprint = JSON.stringify(browserState);
    renderSessionMemory(data.sessionMemory || {});
    return data;
  } finally {
    supervisorRequestCount = Math.max(0, supervisorRequestCount - 1);
  }
}

function applySupervisorResponse(
  data,
  {
    speak = true,
    addTranscriptMessage = true,
    passive = false
  } = {}
) {
  supervisorModelLabel.textContent = data.supervisorModel || supervisorModelLabel.textContent;
  supervisorSessionLabel.textContent = data.sessionId || getSupervisorSessionId();
  renderSessionMemory(data.sessionMemory || {});

  if (!passive) {
    setSupervisorFeedback(data.spokenResponse || "The Python supervisor finished without a spoken summary.");
  }
  setTerminalSnapshot(data.terminalSnapshot || "");
  if (!passive) {
    renderSupervisorActionLog(Array.isArray(data.actionLog) ? data.actionLog : []);
  }
  renderApprovals(Array.isArray(data.pendingApprovals) ? data.pendingApprovals : []);
  if (!passive) {
    renderMentorResponse(data.mentor || {}, {
      persist: true
    });
  }

  if (data.pendingApprovals?.length) {
    setSupervisorStatus("Awaiting approval", "busy");
  } else if (data.claudeSessionExists) {
    if (data.terminalInteractiveMenu) {
      setSupervisorStatus("Interactive menu", "busy");
    } else {
      setSupervisorStatus(data.terminalReady ? "Claude ready" : "Claude busy", data.terminalReady ? "live" : "busy");
    }
  } else {
    setSupervisorStatus("Claude not attached", "idle");
  }
  syncSupervisorMonitorState(data);

  if (!passive && data.spokenResponse && addTranscriptMessage) {
    addMessage("assistant", data.spokenResponse);
  }
  if (!passive && data.spokenResponse && speak) {
    speakText(data.spokenResponse);
  }

  if (!passive) {
    scheduleSupervisorMonitor(900);
  }

  scheduleBrowserStateSync(180);
}

async function refreshSupervisorHealth() {
  try {
    const response = await fetch(
      `/api/supervisor/health?sessionId=${encodeURIComponent(getSupervisorSessionId())}&profileSessionId=${encodeURIComponent(getProfileSessionId())}`
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || data.error || "Supervisor health failed.");
    }

    if (!activeProfileHasLocalState) {
      hydrateProfileFromSessionMemory(data.sessionMemory || {});
    }

    supervisorModelLabel.textContent = data.supervisorModel || "gpt-5.4";
    supervisorSessionLabel.textContent = getSupervisorSessionId();
    renderSessionMemory(data.sessionMemory || {});
    setTerminalSnapshot(data.terminal?.output || "");
    renderSupervisorActionLog([]);
    renderApprovals(Array.isArray(data.pendingApprovals) ? data.pendingApprovals : []);
    renderMentorResponse(latestMentorState, {
      persist: false
    });
    setSupervisorFeedback("Supervisor loaded. Start or verify Claude when you want the backend to take over.");
    updateSupervisorMonitorButton();
    setSupervisorMonitorUpdated("Not yet");
    if (data.terminal?.session_exists) {
      if (data.terminal.interactive_menu) {
        setSupervisorStatus("Interactive menu", "busy");
      } else {
        setSupervisorStatus(data.terminal.ready ? "Claude ready" : "Claude busy", data.terminal.ready ? "live" : "busy");
      }
    } else {
      setSupervisorStatus("Claude not attached", "idle");
    }
    syncSupervisorMonitorState({
      claudeSessionExists: Boolean(data.terminal?.session_exists),
      terminalReady: Boolean(data.terminal?.ready),
      terminalInteractiveMenu: Boolean(data.terminal?.interactive_menu),
      pendingApprovals: Array.isArray(data.pendingApprovals) ? data.pendingApprovals : []
    });
    scheduleBrowserStateSync(180);
    scheduleSupervisorMonitor(1200);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    setSupervisorMonitorState("Live view retrying");
    addEvent("supervisor_health_error", error instanceof Error ? error.message : String(error));
    scheduleSupervisorMonitor(2500);
  }
}

async function refreshSupervisorMonitor() {
  if (!supervisorMonitorEnabled) {
    return;
  }

  if (supervisorMonitorRefreshing || supervisorRequestCount > 0) {
    scheduleSupervisorMonitor(900);
    return;
  }

  supervisorMonitorRefreshing = true;
  try {
    const data = await callSupervisor("/api/supervisor/observe");
    applySupervisorResponse(data, {
      speak: false,
      addTranscriptMessage: false,
      passive: true
    });
  } catch (error) {
    setSupervisorMonitorState("Live view retrying");
    addEvent("supervisor_monitor_error", error instanceof Error ? error.message : String(error));
    scheduleSupervisorMonitor(2500);
  } finally {
    supervisorMonitorRefreshing = false;
    if (supervisorMonitorEnabled) {
      scheduleSupervisorMonitor();
    }
  }
}

function toggleSupervisorMonitor() {
  supervisorMonitorEnabled = !supervisorMonitorEnabled;
  updateSupervisorMonitorButton();
  scheduleBrowserStateSync();
  if (!supervisorMonitorEnabled) {
    if (supervisorMonitorTimer) {
      window.clearTimeout(supervisorMonitorTimer);
      supervisorMonitorTimer = null;
    }
    setSupervisorMonitorState("Live view paused");
    return;
  }

  setSupervisorMonitorState("Resuming live view");
  void refreshSupervisorMonitor();
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
  persistActiveProfileState();
  setSupervisorFeedback("Moved the last heard turn into the manual prompt draft box.");
  scheduleBrowserStateSync();
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

function mentorGoal() {
  return mentorGoalInput.value.trim();
}

async function explainLatestChanges() {
  setSupervisorStatus("Mentor working", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/explain-latest");
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("mentor_explain_error", error instanceof Error ? error.message : String(error));
  }
}

async function requestSecondOpinion() {
  const goal = mentorGoal();
  if (!goal) {
    setSupervisorFeedback("Add a short goal or concern first so the mentor knows what to evaluate.");
    return;
  }

  setSupervisorStatus("Mentor reviewing", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/second-opinion", {
      goal
    });
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("mentor_second_opinion_error", error instanceof Error ? error.message : String(error));
  }
}

async function draftClaudePrompt() {
  const goal = mentorGoal();
  if (!goal) {
    setSupervisorFeedback("Add a short goal first so the mentor can draft a useful Claude prompt.");
    return;
  }

  setSupervisorStatus("Mentor drafting", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/draft-claude-prompt", {
      goal
    });
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("mentor_draft_error", error instanceof Error ? error.message : String(error));
  }
}

async function explainPendingApproval() {
  const pending = latestPendingApprovals[0];
  if (!pending?.callId) {
    setSupervisorFeedback("There is no pending approval to explain right now.");
    return;
  }

  setSupervisorStatus("Mentor explaining", "busy");
  try {
    const data = await callSupervisor("/api/supervisor/explain-approval", {
      callId: pending.callId
    });
    applySupervisorResponse(data);
  } catch (error) {
    setSupervisorStatus("Supervisor error", "error");
    setSupervisorFeedback(error instanceof Error ? error.message : String(error));
    addEvent("mentor_approval_explain_error", error instanceof Error ? error.message : String(error));
  }
}

function useMentorDraft() {
  if (!latestMentorDraft) {
    setSupervisorFeedback("There is no drafted Claude prompt to use yet.");
    return;
  }

  supervisorPromptInput.value = latestMentorDraft;
  persistActiveProfileState();
  setSupervisorFeedback("Moved the drafted mentor prompt into the Claude draft box.");
  scheduleBrowserStateSync();
}

presetSelect.addEventListener("change", () => {
  localStorage.setItem(promptPresetStorageKey, presetSelect.value);
  activateCurrentProfile({
    announce: true,
    forceSync: true
  });
  applyLiveSessionUpdate("Switched the live Realtime session to the selected character preset.");
  setPromptSaveStatus("Loaded this character");
});
voiceSelect.addEventListener("change", () => {
  scheduleBrowserStateSync();
  applyLiveSessionUpdate("Updated the live Realtime voice preference.");
});
turnSelect.addEventListener("change", () => {
  scheduleBrowserStateSync();
  applyLiveSessionUpdate("Updated live turn detection for the current preset.");
});
styleSelect.addEventListener("change", () => {
  persistActiveProfileState();
  renderSessionMemory({
    projectSessionId: getSupervisorSessionId(),
    profileSessionId: getProfileSessionId(),
    profileLabel: profileLabel(),
    currentGoal: mentorGoalInput.value.trim(),
    lastUserTurn,
    updatedAt: "Local draft updated",
    interfaceSummary:
      "Claude work stays on the shared project lane. This character lane now has updated style and local memory."
  });
  scheduleBrowserStateSync();
  applyLiveSessionUpdate("Updated the live Realtime style and remembered preset context.");
});
customInstructionsInput.addEventListener("input", markPromptDirty);
supervisorPromptInput.addEventListener("input", () => {
  persistActiveProfileState();
  scheduleBrowserStateSync();
});
mentorGoalInput.addEventListener("input", () => {
  persistActiveProfileState();
  scheduleBrowserStateSync();
});
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
  persistActiveProfileState();
  setSupervisorFeedback("Cleared the manual Claude prompt draft.");
  scheduleBrowserStateSync();
});
supervisorMonitorToggleButton.addEventListener("click", toggleSupervisorMonitor);
mentorExplainButton.addEventListener("click", explainLatestChanges);
mentorSecondOpinionButton.addEventListener("click", requestSecondOpinion);
mentorDraftPromptButton.addEventListener("click", draftClaudePrompt);
mentorExplainApprovalButton.addEventListener("click", explainPendingApproval);
mentorUseDraftButton.addEventListener("click", useMentorDraft);
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

document.addEventListener("visibilitychange", () => {
  if (!supervisorMonitorEnabled) {
    return;
  }

  if (document.hidden) {
    scheduleSupervisorMonitor();
    return;
  }

  void refreshSupervisorMonitor();
});

async function initializeApp() {
  addEvent("ready", "UI loaded. Choose your voice settings and connect when ready.");
  renderSupervisorActionLog([]);
  renderApprovals([]);
  renderMentorResponse(emptyMentorState());
  renderSessionMemory({});

  try {
    await loadPromptConfig();
    addEvent("prompt_config", `Loaded ${promptConfig.presets.length} preset personalities.`);
  } catch (error) {
    addEvent("prompt_config_error", error instanceof Error ? error.message : String(error));
    setPromptSaveStatus("Prompt presets unavailable");
    activateCurrentProfile();
  }

  await refreshSupervisorHealth();
  scheduleBrowserStateSync(120);

  // Connect to companion WebSocket server (additive — does not break legacy HTTP path)
  connectCompanion();
}

void initializeApp();
