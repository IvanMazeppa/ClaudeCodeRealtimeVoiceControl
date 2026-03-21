# Companion Integration Guide

## How the pieces connect

```
Browser                          Python companion (port 4174)
  │                                   │
  ├─ WebRTC ←→ OpenAI Realtime API    │
  │    audio + data channel            │
  │                                   │
  └─ WebSocket ←────────────────────→ │
       tool calls + state sync         │
                                      ├── tool execution (terminal, git, repo)
                                      ├── deep analysis (gpt-5.4 agents)
                                      └── memory + approval management
```

Audio never touches the Python server. The browser keeps its existing WebRTC
connection to OpenAI for voice I/O. The companion server only handles tool
execution and state.

## Browser-side integration

### 1. Connect to companion on startup

When the page loads (or when the user connects), open a WebSocket to the
companion server and send `init`:

```javascript
let companionWs = null;
let companionTools = [];
let companionInstructions = "";

function connectCompanion() {
  companionWs = new WebSocket("ws://127.0.0.1:4174");

  companionWs.onopen = () => {
    companionWs.send(JSON.stringify({
      type: "init",
      sessionId: getSupervisorSessionId(),
      profileSessionId: getProfileSessionId(),
    }));
  };

  companionWs.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleCompanionMessage(msg);
  };

  companionWs.onclose = () => {
    // Reconnect after delay
    setTimeout(connectCompanion, 2000);
  };
}

function handleCompanionMessage(msg) {
  switch (msg.type) {
    case "ready":
      companionTools = msg.tools;         // tool definitions for session.update
      companionInstructions = msg.instructions; // dynamic instructions
      break;
    case "memory":
      renderSessionMemory(msg.memory);
      break;
    case "approvals":
      renderApprovals(msg.pending);
      break;
    case "terminal":
      setTerminalSnapshot(msg.state.output);
      break;
    case "tool_result":
      handleToolResult(msg);              // send result back to Realtime API
      break;
  }
}
```

### 2. Register tools in the Realtime session

When building the `session.update` payload, include the companion's tools:

```javascript
function buildSessionUpdate() {
  return {
    type: "session.update",
    session: {
      instructions: companionInstructions || buildInstructions(),
      tools: companionTools,  // ← tool definitions from companion server
      // ... audio config unchanged
    }
  };
}
```

### 3. Intercept function calls from the data channel

The Realtime API sends function call events on the data channel. The browser
catches these and forwards them to Python:

```javascript
function handleRealtimeEvent(event) {
  switch (event.type) {
    // ... existing cases ...

    case "response.function_call_arguments.done":
      // Forward to companion server for execution
      if (companionWs && companionWs.readyState === WebSocket.OPEN) {
        companionWs.send(JSON.stringify({
          type: "tool_call",
          name: event.name,
          callId: event.call_id,
          arguments: event.arguments,
        }));
        addEvent("tool_call", `Calling ${event.name}...`);
      }
      break;
  }
}
```

### 4. Send tool results back to OpenAI

When the companion server returns a tool result, send it back to the Realtime
API via the data channel so the model can incorporate it into its response:

```javascript
function handleToolResult(msg) {
  if (!dataChannel || dataChannel.readyState !== "open") return;

  // Create the tool output conversation item
  dataChannel.send(JSON.stringify({
    type: "conversation.item.create",
    item: {
      type: "function_call_output",
      call_id: msg.callId,
      output: msg.result,
    }
  }));

  // Trigger a new model response that incorporates the tool result
  dataChannel.send(JSON.stringify({
    type: "response.create"
  }));

  addEvent("tool_result", `${msg.name}: ${msg.ok ? "done" : "error"}`);
}
```

### 5. Replace HTTP state sync with WebSocket

Instead of `POST /api/supervisor/context`, send browser state over the
companion WebSocket:

```javascript
async function syncBrowserState() {
  if (!companionWs || companionWs.readyState !== WebSocket.OPEN) return;
  companionWs.send(JSON.stringify({
    type: "browser_state",
    state: buildBrowserState(),
  }));
}
```

### 6. Replace HTTP terminal monitor with WebSocket

Instead of polling `/api/supervisor/observe`, request terminal refreshes:

```javascript
function refreshTerminal() {
  if (!companionWs || companionWs.readyState !== WebSocket.OPEN) return;
  companionWs.send(JSON.stringify({ type: "terminal_refresh" }));
}
```

## What the voice loop looks like

1. User says: "What is Claude doing right now?"
2. Browser sends audio to OpenAI via WebRTC
3. OpenAI model transcribes, decides to call `see_claude_terminal`
4. OpenAI sends `response.function_call_arguments.done` on data channel
5. Browser forwards `{type: "tool_call", name: "see_claude_terminal", ...}` to Python
6. Python executes: captures tmux pane, returns terminal output
7. Python sends `{type: "tool_result", result: "Claude is working on..."}` to browser
8. Browser sends `conversation.item.create` + `response.create` to OpenAI
9. OpenAI model speaks: "Claude is currently adding tests to the auth module."

Total added latency over current voice-only: one localhost WebSocket round trip
for the tool call (~5-20ms).

## Migration notes

- The existing HTTP supervisor routes continue to work unchanged
- The companion WebSocket is additive, not a replacement (yet)
- Once the WebSocket path is validated, HTTP routes can be removed one by one
- The `WebSearchTool` is a hosted OpenAI tool — it runs server-side at OpenAI,
  not in Python. To use it, add it to the session tools with type "web_search"
  instead of "function". This is separate from the function tools.
