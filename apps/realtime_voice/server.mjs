import "dotenv/config";

import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const host = process.env.REALTIME_HOST || "0.0.0.0";
const port = Number(process.env.REALTIME_PORT || 4173);
const model = process.env.REALTIME_MODEL || "gpt-realtime";
const defaultVoice = process.env.REALTIME_VOICE || "marin";
const apiKey = process.env.OPENAI_API_KEY;
const publicDir = path.join(__dirname, "public");
const promptPath = path.join(__dirname, "prompts", "system_prompt.txt");
const presetDir = path.join(__dirname, "prompts", "presets");
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
