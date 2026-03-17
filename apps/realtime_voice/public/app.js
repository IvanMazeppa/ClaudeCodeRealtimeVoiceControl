const connectButton = document.getElementById("connect-btn");
const disconnectButton = document.getElementById("disconnect-btn");
const muteButton = document.getElementById("mute-btn");
const voiceSelect = document.getElementById("voice-select");
const turnSelect = document.getElementById("turn-select");
const styleSelect = document.getElementById("style-select");
const transcriptList = document.getElementById("transcript-list");
const eventLog = document.getElementById("event-log");
const liveBanner = document.getElementById("live-banner");
const statusText = document.getElementById("status-text");
const statusDot = document.getElementById("status-dot");
const expiryLabel = document.getElementById("expiry-label");
const modelLabel = document.getElementById("model-label");

let peerConnection = null;
let dataChannel = null;
let localStream = null;
let localTrack = null;
let remoteAudio = null;
let isMuted = false;
let userDrafts = new Map();
let assistantDrafts = new Map();

function nowLabel() {
  return new Date().toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
}

function setStatus(label, tone = "idle") {
  statusText.textContent = label;
  statusDot.className = "status-dot";
  if (tone === "live") {
    statusDot.classList.add("live");
  } else if (tone === "busy") {
    statusDot.classList.add("busy");
  } else if (tone === "error") {
    statusDot.classList.add("error");
  }
}

function setLiveBanner(text) {
  liveBanner.textContent = text;
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

function buildInstructions() {
  const style = styleSelect.value;
  const styleLine =
    style === "detail"
      ? "You may speak slightly longer when helpful, but still keep technical detail concise."
      : style === "balanced"
        ? "Keep spoken replies short, but allow a bit more context when needed."
        : "Keep spoken replies extra short and action-oriented.";

  return [
    "You are in realtime voice work mode for coding sessions.",
    "Speak clearly and briefly.",
    styleLine,
    "Do not read code blocks, long file paths, diffs, or logs aloud unless explicitly asked.",
    "If more detail exists, summarize it and indicate that the details belong on screen.",
    "Ask one short follow-up question at a time."
  ].join(" ");
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
          voice: voiceSelect.value
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

async function requestToken() {
  const response = await fetch("/api/token", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      voice: voiceSelect.value
    })
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || data.error || "Token request failed.");
  }

  modelLabel.textContent = data.model || "gpt-realtime";
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

connectButton.addEventListener("click", connect);
disconnectButton.addEventListener("click", disconnect);
muteButton.addEventListener("click", toggleMute);

addEvent("ready", "UI loaded. Choose your voice settings and connect when ready.");
