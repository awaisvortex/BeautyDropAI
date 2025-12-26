# Voice Agent - Frontend Integration Guide (Next.js)

## Overview

The BeautyDrop Voice Agent allows users to speak with an AI assistant to find salons, get service information, and learn about pricing. This guide explains how to integrate the voice agent into the Next.js frontend.

---

## Backend Endpoint

| Environment | WebSocket URL                       |
| ----------- | ----------------------------------- |
| Local Dev   | `ws://localhost:8004/ws/voice/`     |
| Production  | `wss://api.beautydrop.ai/ws/voice/` |

---

## WebSocket Protocol

### Messages FROM Client → Server

```typescript
// Send audio data (PCM16, 24kHz, mono, base64 encoded)
{ type: "audio", data: "<base64 string>" }

// Send text message (for testing or accessibility fallback)
{ type: "text", text: "What salons offer haircuts?" }

// End the session
{ type: "end" }

// Cancel current response (user interrupted)
{ type: "cancel" }
```

### Messages FROM Server → Client

```typescript
// Connection status
{ type: "status", status: "connecting" | "connected", message?: string, session_id?: string }

// Audio response (PCM16, 24kHz, mono, base64 encoded)
{ type: "audio", data: "<base64 string>" }

// Transcript (for displaying conversation)
{ type: "transcript", role: "user" | "assistant", text: string }

// Error
{ type: "error", message: string }
```

---

## Audio Format Requirements

| Property    | Value                              |
| ----------- | ---------------------------------- |
| Format      | PCM16 (raw 16-bit signed integers) |
| Sample Rate | 24000 Hz                           |
| Channels    | 1 (mono)                           |
| Encoding    | Base64                             |

> **Important**: Browser microphones typically capture at 44100Hz or 48000Hz. You MUST resample to 24000Hz before sending.

---

## React Hook Example

```typescript
// hooks/useVoiceAgent.ts
import { useCallback, useRef, useState } from "react";

interface VoiceAgentOptions {
  wsUrl?: string;
  onTranscript?: (role: "user" | "assistant", text: string) => void;
  onStatusChange?: (status: string) => void;
  onError?: (error: string) => void;
}

export function useVoiceAgent(options: VoiceAgentOptions = {}) {
  const {
    wsUrl = process.env.NEXT_PUBLIC_VOICE_WS_URL ||
      "ws://localhost:8004/ws/voice/",
    onTranscript,
    onStatusChange,
    onError,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const audioQueueRef = useRef<Float32Array[]>([]);

  // Connect to voice agent
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    onStatusChange?.("connecting");
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setIsConnected(true);
      onStatusChange?.("connected");
    };

    ws.onclose = () => {
      setIsConnected(false);
      onStatusChange?.("disconnected");
    };

    ws.onerror = () => {
      onError?.("Connection failed");
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case "transcript":
          onTranscript?.(data.role, data.text);
          break;
        case "audio":
          playAudio(data.data);
          break;
        case "error":
          onError?.(data.message);
          break;
      }
    };

    wsRef.current = ws;
  }, [wsUrl, onTranscript, onStatusChange, onError]);

  // Start recording
  const startRecording = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      connect();
      return;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      });

      streamRef.current = stream;
      const audioContext = new AudioContext();
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      const nativeSampleRate = audioContext.sampleRate;

      processor.onaudioprocess = (e) => {
        if (!isRecording) return;

        const inputData = e.inputBuffer.getChannelData(0);

        // Resample to 24000Hz
        const ratio = nativeSampleRate / 24000;
        const resampledLength = Math.floor(inputData.length / ratio);
        const resampled = new Float32Array(resampledLength);

        for (let i = 0; i < resampledLength; i++) {
          resampled[i] = inputData[Math.floor(i * ratio)];
        }

        // Convert to PCM16
        const pcm16 = new Int16Array(resampled.length);
        for (let i = 0; i < resampled.length; i++) {
          pcm16[i] = Math.max(-32768, Math.min(32767, resampled[i] * 32768));
        }

        // Send as base64
        const uint8 = new Uint8Array(pcm16.buffer);
        let binary = "";
        for (let i = 0; i < uint8.length; i++) {
          binary += String.fromCharCode(uint8[i]);
        }

        wsRef.current?.send(
          JSON.stringify({ type: "audio", data: btoa(binary) })
        );
      };

      source.connect(processor);
      processor.connect(audioContext.destination);
      setIsRecording(true);
    } catch (error) {
      onError?.("Microphone access denied");
    }
  }, [connect, isRecording, onError]);

  // Stop recording
  const stopRecording = useCallback(() => {
    setIsRecording(false);
    streamRef.current?.getTracks().forEach((track) => track.stop());
    audioContextRef.current?.close();
  }, []);

  // Play audio response
  const playAudio = useCallback(
    (base64: string) => {
      if (!audioContextRef.current) {
        audioContextRef.current = new AudioContext({ sampleRate: 24000 });
      }

      const binary = atob(base64);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
      }

      const pcm16 = new Int16Array(bytes.buffer);
      const float32 = new Float32Array(pcm16.length);
      for (let i = 0; i < pcm16.length; i++) {
        float32[i] = pcm16[i] / 32768;
      }

      audioQueueRef.current.push(float32);
      if (!isPlaying) playNextChunk();
    },
    [isPlaying]
  );

  const playNextChunk = useCallback(() => {
    if (audioQueueRef.current.length === 0) {
      setIsPlaying(false);
      return;
    }

    setIsPlaying(true);
    const float32 = audioQueueRef.current.shift()!;
    const ctx = audioContextRef.current!;

    const buffer = ctx.createBuffer(1, float32.length, 24000);
    buffer.getChannelData(0).set(float32);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);
    source.onended = playNextChunk;
    source.start();
  }, []);

  // Send text message
  const sendText = useCallback((text: string) => {
    wsRef.current?.send(JSON.stringify({ type: "text", text }));
  }, []);

  // Disconnect
  const disconnect = useCallback(() => {
    wsRef.current?.close();
    stopRecording();
  }, [stopRecording]);

  return {
    isConnected,
    isRecording,
    isPlaying,
    connect,
    disconnect,
    startRecording,
    stopRecording,
    sendText,
  };
}
```

---

## Component Example

```tsx
// components/VoiceAgent.tsx
"use client";

import { useState } from "react";
import { useVoiceAgent } from "@/hooks/useVoiceAgent";

interface Message {
  role: "user" | "assistant" | "system";
  text: string;
}

export function VoiceAgent() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState("Click to start");

  const {
    isConnected,
    isRecording,
    connect,
    startRecording,
    stopRecording,
    sendText,
  } = useVoiceAgent({
    onTranscript: (role, text) => {
      setMessages((prev) => [...prev, { role, text }]);
    },
    onStatusChange: setStatus,
    onError: (error) => {
      setMessages((prev) => [
        ...prev,
        { role: "system", text: `Error: ${error}` },
      ]);
    },
  });

  const handleMicClick = () => {
    if (!isConnected) {
      connect();
    } else if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  return (
    <div className="voice-agent">
      <div className="status">{status}</div>

      <button
        onClick={handleMicClick}
        className={`mic-button ${isRecording ? "recording" : ""}`}
      >
        {isRecording ? "🔴 Stop" : "🎤 Speak"}
      </button>

      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <strong>{msg.role}:</strong> {msg.text}
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

## Environment Variables

Add to `.env.local`:

```env
NEXT_PUBLIC_VOICE_WS_URL=ws://localhost:8004/ws/voice/
```

For production:

```env
NEXT_PUBLIC_VOICE_WS_URL=wss://api.beautydrop.ai/ws/voice/
```

---

## Capabilities

The voice agent can answer questions about:

| Query Type      | Example                        |
| --------------- | ------------------------------ |
| Find shops      | "What salons do you have?"     |
| Shop by service | "Which shops offer haircuts?"  |
| Shop details    | "Tell me about Andy & Wendi"   |
| Services        | "What services do they offer?" |
| Pricing         | "How much is a haircut?"       |
| Hours           | "When are they open?"          |
| Contact         | "What's their phone number?"   |

**Note**: The agent cannot book appointments, cancel bookings, or access user accounts. It will direct users to the app/website for those actions.

---

## Testing

1. Start the backend: `poetry run daphne -b 0.0.0.0 -p 8004 config.asgi:application`
2. Open `apps/voice/test_voice.html` in a browser for a standalone test
3. Use the React component in your Next.js app

---

## Troubleshooting

| Issue                  | Solution                                                                          |
| ---------------------- | --------------------------------------------------------------------------------- |
| No audio playing       | Check browser console for AudioContext errors, user must interact with page first |
| Microphone not working | Ensure HTTPS in production, check browser permissions                             |
| Connection fails       | Verify WebSocket URL, check CORS settings on backend                              |
| Audio distorted        | Ensure proper resampling to 24000Hz                                               |
