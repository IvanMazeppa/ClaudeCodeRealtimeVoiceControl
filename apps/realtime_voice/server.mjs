import "dotenv/config";

import express from "express";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const host = process.env.REALTIME_HOST || "127.0.0.1";
const port = Number(process.env.REALTIME_PORT || 4173);
const model = process.env.REALTIME_MODEL || "gpt-realtime";
const defaultVoice = process.env.REALTIME_VOICE || "marin";
const apiKey = process.env.OPENAI_API_KEY;
const publicDir = path.join(__dirname, "public");
const promptPath = path.join(__dirname, "prompts", "system_prompt.txt");

app.use(express.json());
app.use(express.static(publicDir));

function readInstructions() {
  try {
    return fs.readFileSync(promptPath, "utf8").trim();
  } catch {
    return "Speak briefly, stay practical, and keep detailed technical output on screen.";
  }
}

function buildSession(voice = defaultVoice) {
  return {
    type: "realtime",
    model,
    instructions: readInstructions(),
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
        voice
      }
    }
  };
}

app.get("/health", (_req, res) => {
  res.json({
    ok: true,
    model,
    defaultVoice,
    hasApiKey: Boolean(apiKey)
  });
});

app.post("/api/token", async (req, res) => {
  if (!apiKey) {
    res.status(500).json({
      error: "OPENAI_API_KEY is not set for the realtime voice server."
    });
    return;
  }

  const requestedVoice = typeof req.body?.voice === "string" && req.body.voice
    ? req.body.voice
    : defaultVoice;

  const payload = {
    expires_after: {
      anchor: "created_at",
      seconds: 600
    },
    session: buildSession(requestedVoice)
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
  console.log(`Realtime voice server ready at http://${host}:${port}`);
});
