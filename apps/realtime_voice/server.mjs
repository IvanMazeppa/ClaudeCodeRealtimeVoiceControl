import "dotenv/config";

import { execFile } from "node:child_process";
import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const execFileAsync = promisify(execFile);

const app = express();
const host = process.env.REALTIME_HOST || "0.0.0.0";
const port = Number(process.env.REALTIME_PORT || 4173);
const model = process.env.REALTIME_MODEL || "gpt-realtime-1.5";
const defaultVoice = process.env.REALTIME_VOICE || "marin";
const apiKey = process.env.OPENAI_API_KEY;
const publicDir = path.join(__dirname, "public");
const promptPath = path.join(__dirname, "prompts", "system_prompt.txt");
const presetDir = path.join(__dirname, "prompts", "presets");
const claudeBridgeConfigPath = path.join(__dirname, "config", "claude-bridge.json");
const claudeBridgeLocalConfigPath = path.join(__dirname, "config", "claude-bridge.local.json");
const supervisorRoot = path.join(__dirname, "python_supervisor");
const supervisorSrc = path.join(supervisorRoot, "src");
const supervisorVenvPython = path.join(supervisorRoot, ".venv", "bin", "python");
const supervisorPython =
  process.env.REALTIME_SUPERVISOR_PYTHON ||
  (fs.existsSync(supervisorVenvPython) ? supervisorVenvPython : "python3");
const supervisorModel = process.env.REALTIME_SUPERVISOR_MODEL || "gpt-5.4";
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

app.use(express.json());
app.use(express.static(publicDir));

function stripAnsi(text) {
  return text.replace(
    // eslint-disable-next-line no-control-regex
    /\u001b\[[0-9;?]*[ -/]*[@-~]|\u001b[@-_]/g,
    ""
  );
}

function wait(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

function readJsonFile(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

function loadClaudeBridgeConfig() {
  const baseConfig = readJsonFile(claudeBridgeConfigPath) || {};
  const localConfig = readJsonFile(claudeBridgeLocalConfigPath) || {};
  const merged = {
    ...baseConfig,
    ...localConfig,
    modePhrases: {
      ...(baseConfig.modePhrases || {}),
      ...(localConfig.modePhrases || {})
    }
  };

  return {
    ...merged,
    sessionName: merged.sessionName || "voice-coding-claude",
    workingDirectory: path.resolve(repoRoot, merged.workingDirectory || "."),
    command: merged.command || "claude",
    captureLines: Number(merged.captureLines || 160),
    startupPromptFile: path.resolve(
      repoRoot,
      merged.startupPromptFile || "apps/claude_code_voice/prompts/session_start.md"
    ),
    startupSettleMs: Number(merged.startupSettleMs || 1200),
    modePhrases: merged.modePhrases || {}
  };
}

async function runTool(command, args, options = {}) {
  return execFileAsync(command, args, {
    cwd: options.cwd || repoRoot,
    env: {
      ...process.env,
      ...(options.env || {})
    },
    maxBuffer: 1024 * 1024 * 4
  });
}

async function runTmux(args, options = {}) {
  return runTool("tmux", args, options);
}

function claudeTarget(config) {
  return `${config.sessionName}:0.0`;
}

async function claudeSessionExists(config) {
  try {
    await runTmux(["has-session", "-t", config.sessionName]);
    return true;
  } catch {
    return false;
  }
}

async function ensureClaudeSession(config) {
  const exists = await claudeSessionExists(config);
  if (exists) {
    return false;
  }

  await runTmux([
    "new-session",
    "-d",
    "-s",
    config.sessionName,
    "-c",
    config.workingDirectory,
    config.command
  ]);
  await wait(1200);
  return true;
}

async function setTmuxBuffer(bufferName, text) {
  await runTmux(["set-buffer", "-b", bufferName, text]);
}

async function clearTmuxBuffer(bufferName) {
  try {
    await runTmux(["delete-buffer", "-b", bufferName]);
  } catch {
    // ignore missing buffer cleanup
  }
}

async function sendTextToClaude(config, text, { submit = true } = {}) {
  const bufferName = `voice-bridge-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  await setTmuxBuffer(bufferName, text);
  try {
    await runTmux(["paste-buffer", "-b", bufferName, "-t", claudeTarget(config)]);
    if (submit) {
      await runTmux(["send-keys", "-t", claudeTarget(config), "C-m"]);
    }
  } finally {
    await clearTmuxBuffer(bufferName);
  }
}

async function captureClaudeOutput(config) {
  const { stdout } = await runTmux([
    "capture-pane",
    "-p",
    "-t",
    claudeTarget(config),
    "-S",
    `-${config.captureLines}`
  ]);

  return stripAnsi(stdout).trim();
}

async function sendClaudeInterrupt(config) {
  await runTmux(["send-keys", "-t", claudeTarget(config), "C-c"]);
}

function readStartupPrompt(config) {
  try {
    const contents = fs.readFileSync(config.startupPromptFile, "utf8").trim();
    const fencedMatch = contents.match(/```(?:text)?\n([\s\S]*?)```/);
    return fencedMatch ? fencedMatch[1].trim() : contents;
  } catch {
    return "";
  }
}

function readInstructions() {
  try {
    return fs.readFileSync(promptPath, "utf8").trim();
  } catch {
    return "Speak briefly, stay practical, and keep detailed technical output on screen.";
  }
}

function titleizePreset(id) {
  return id
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function loadPresetPrompts() {
  try {
    const entries = fs.readdirSync(presetDir, { withFileTypes: true });
    return entries
      .filter((entry) => entry.isFile() && entry.name.endsWith(".txt"))
      .map((entry) => {
        const id = entry.name.replace(/\.txt$/, "");
        const content = fs
          .readFileSync(path.join(presetDir, entry.name), "utf8")
          .trim();

        return {
          id,
          title: titleizePreset(id),
          content
        };
      })
      .sort((a, b) => a.title.localeCompare(b.title));
  } catch {
    return [];
  }
}

function normalizeInstructions(value) {
  if (typeof value !== "string") {
    return readInstructions();
  }

  const trimmed = value.trim();
  return trimmed || readInstructions();
}

function normalizeVoice(voice) {
  if (typeof voice === "string" && supportedVoices.has(voice)) {
    return voice;
  }

  return supportedVoices.has(defaultVoice) ? defaultVoice : "marin";
}

function normalizeClaudeMode(config, mode) {
  if (typeof mode !== "string") {
    return null;
  }

  const value = config.modePhrases?.[mode];
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function commandErrorDetail(error) {
  if (error && typeof error === "object") {
    const stderr = "stderr" in error ? String(error.stderr || "") : "";
    const stdout = "stdout" in error ? String(error.stdout || "") : "";
    const message = "message" in error ? String(error.message || "") : "";
    return (stderr || stdout || message || String(error)).trim();
  }

  return String(error);
}

async function runPythonSupervisor(command, payload = {}) {
  try {
    const { stdout } = await runTool(
      supervisorPython,
      [
        "-m",
        "realtime_voice_supervisor.cli",
        command,
        "--app-root",
        __dirname,
        "--repo-root",
        repoRoot,
        "--payload-json",
        JSON.stringify(payload)
      ],
      {
        cwd: supervisorRoot,
        env: {
          PYTHONPATH: supervisorSrc,
          REALTIME_SUPERVISOR_MODEL: supervisorModel
        }
      }
    );
    const trimmed = stdout.trim();
    return trimmed ? JSON.parse(trimmed) : {};
  } catch (error) {
    throw new Error(commandErrorDetail(error));
  }
}

function buildSession({
  voice = defaultVoice,
  instructions = readInstructions()
} = {}) {
  return {
    type: "realtime",
    model,
    instructions: normalizeInstructions(instructions),
    output_modalities: ["audio"],
    audio: {
      input: {
        format: {
          type: "audio/pcm",
          rate: 24000
        },
        noise_reduction: {
          type: "near_field"
        },
        transcription: {
          model: "gpt-4o-transcribe"
        },
        turn_detection: {
          type: "semantic_vad",
          eagerness: "medium",
          create_response: true,
          interrupt_response: true
        }
      },
      output: {
        format: {
          type: "audio/pcm",
          rate: 24000
        },
        voice: normalizeVoice(voice)
      }
    }
  };
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    model,
    defaultVoice: normalizeVoice(defaultVoice),
    supportedVoices: [...supportedVoices],
    hasApiKey: Boolean(apiKey)
  });
});

app.get("/api/prompt-config", (_req, res) => {
  res.json({
    baseInstructions: readInstructions(),
    presets: loadPresetPrompts()
  });
});

app.get("/api/supervisor/health", async (_req, res) => {
  try {
    const data = await runPythonSupervisor("health");
    res.json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Python supervisor health check failed.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/supervisor/session", async (req, res) => {
  try {
    const data = await runPythonSupervisor("ensure-session", {
      sessionId: req.body?.sessionId
    });
    res.json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to verify the Claude session through the Python supervisor.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/supervisor/observe", async (req, res) => {
  try {
    const data = await runPythonSupervisor("observe", {
      sessionId: req.body?.sessionId
    });
    res.json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to observe the Claude terminal through the Python supervisor.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/supervisor/turn", async (req, res) => {
  try {
    const data = await runPythonSupervisor("handle-turn", {
      sessionId: req.body?.sessionId,
      userText: req.body?.userText
    });
    res.json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to process the spoken turn through the Python supervisor.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/supervisor/manual-prompt", async (req, res) => {
  try {
    const data = await runPythonSupervisor("manual-prompt", {
      sessionId: req.body?.sessionId,
      prompt: req.body?.prompt
    });
    res.json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to send the manual Claude prompt through the Python supervisor.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/supervisor/interrupt", async (req, res) => {
  try {
    const data = await runPythonSupervisor("interrupt", {
      sessionId: req.body?.sessionId
    });
    res.json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to interrupt Claude through the Python supervisor.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/supervisor/decision", async (req, res) => {
  try {
    const data = await runPythonSupervisor("decision", {
      sessionId: req.body?.sessionId,
      callId: req.body?.callId,
      approve: req.body?.approve,
      always: req.body?.always,
      rejectionMessage: req.body?.rejectionMessage
    });
    res.status(data.ok ? 200 : 400).json(data);
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to apply the approval decision through the Python supervisor.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.get("/api/claude/health", async (_req, res) => {
  const config = loadClaudeBridgeConfig();

  try {
    const sessionExists = await claudeSessionExists(config);
    const output = sessionExists ? await captureClaudeOutput(config) : "";

    res.json({
      ok: true,
      sessionName: config.sessionName,
      sessionExists,
      workingDirectory: config.workingDirectory,
      command: config.command,
      startupPromptFile: config.startupPromptFile,
      modePhrases: config.modePhrases,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to inspect Claude bridge state.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/claude/start", async (req, res) => {
  const config = loadClaudeBridgeConfig();
  const sendStartupPrompt = Boolean(req.body?.sendStartupPrompt);

  try {
    const created = await ensureClaudeSession(config);
    let startupPromptSent = false;

    if (sendStartupPrompt) {
      const promptText = readStartupPrompt(config);
      if (promptText) {
        await sendTextToClaude(config, promptText);
        startupPromptSent = true;
        await wait(config.startupSettleMs);
      }
    }

    const output = await captureClaudeOutput(config);
    res.json({
      ok: true,
      created,
      startupPromptSent,
      sessionName: config.sessionName,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to start or attach the Claude bridge session.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/claude/startup-prompt", async (_req, res) => {
  const config = loadClaudeBridgeConfig();

  try {
    await ensureClaudeSession(config);
    const promptText = readStartupPrompt(config);
    if (!promptText) {
      res.status(500).json({
        ok: false,
        error: "The configured startup prompt file could not be read."
      });
      return;
    }

    await sendTextToClaude(config, promptText);
    await wait(config.startupSettleMs);
    const output = await captureClaudeOutput(config);
    res.json({
      ok: true,
      sessionName: config.sessionName,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to send the Claude startup prompt.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/claude/prompt", async (req, res) => {
  const config = loadClaudeBridgeConfig();
  const text = typeof req.body?.text === "string" ? req.body.text.trim() : "";
  const settleMs = Number(req.body?.settleMs || 1200);

  if (!text) {
    res.status(400).json({
      ok: false,
      error: "Prompt text is required."
    });
    return;
  }

  try {
    await ensureClaudeSession(config);
    await sendTextToClaude(config, text);
    await wait(settleMs);
    const output = await captureClaudeOutput(config);
    res.json({
      ok: true,
      sessionName: config.sessionName,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to send a prompt to Claude.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/claude/mode", async (req, res) => {
  const config = loadClaudeBridgeConfig();
  const phrase = normalizeClaudeMode(config, req.body?.mode);

  if (!phrase) {
    res.status(400).json({
      ok: false,
      error: "Unknown Claude mode."
    });
    return;
  }

  try {
    await ensureClaudeSession(config);
    await sendTextToClaude(config, phrase);
    await wait(800);
    const output = await captureClaudeOutput(config);
    res.json({
      ok: true,
      mode: req.body?.mode,
      phrase,
      sessionName: config.sessionName,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to switch Claude bridge mode.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/claude/interrupt", async (_req, res) => {
  const config = loadClaudeBridgeConfig();

  try {
    const exists = await claudeSessionExists(config);
    if (!exists) {
      res.status(404).json({
        ok: false,
        error: "Claude bridge session is not running."
      });
      return;
    }

    await sendClaudeInterrupt(config);
    await wait(500);
    const output = await captureClaudeOutput(config);
    res.json({
      ok: true,
      sessionName: config.sessionName,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to interrupt Claude.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.get("/api/claude/output", async (_req, res) => {
  const config = loadClaudeBridgeConfig();

  try {
    const exists = await claudeSessionExists(config);
    if (!exists) {
      res.status(404).json({
        ok: false,
        error: "Claude bridge session is not running."
      });
      return;
    }

    const output = await captureClaudeOutput(config);
    res.json({
      ok: true,
      sessionName: config.sessionName,
      output
    });
  } catch (error) {
    res.status(500).json({
      ok: false,
      error: "Failed to capture Claude output.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.post("/api/token", async (req, res) => {
  if (!apiKey) {
    res.status(500).json({
      error: "OPENAI_API_KEY is not set for the realtime voice server."
    });
    return;
  }

  const requestedVoice = normalizeVoice(req.body?.voice || defaultVoice);
  const requestedInstructions = normalizeInstructions(req.body?.instructions);

  const payload = {
    expires_after: {
      anchor: "created_at",
      seconds: 600
    },
    session: buildSession({
      voice: requestedVoice,
      instructions: requestedInstructions
    })
  };

  try {
    const response = await fetch("https://api.openai.com/v1/realtime/client_secrets", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      const errorText = await response.text();
      res.status(response.status).json({
        error: "Failed to mint a Realtime client secret.",
        detail: errorText
      });
      return;
    }

    const data = await response.json();
    res.json({
      value: data.value,
      expires_at: data.expires_at,
      session: data.session,
      model,
      voice: requestedVoice,
      instructions: payload.session.instructions
    });
  } catch (error) {
    res.status(500).json({
      error: "Realtime token request failed.",
      detail: error instanceof Error ? error.message : String(error)
    });
  }
});

app.use((_req, res) => {
  res.sendFile(path.join(publicDir, "index.html"));
});

app.listen(port, host, () => {
  const localhostUrl = `http://127.0.0.1:${port}`;
  const bindLabel = host === "0.0.0.0" ? "all interfaces" : host;
  console.log(`Realtime voice server ready on ${bindLabel}:${port}`);
  console.log(`Try ${localhostUrl} from the same machine or your WSL IP if localhost forwarding is unavailable.`);
});
