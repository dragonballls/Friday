# Jarvis

Jarvis is a self-improving AI assistant built around a minimal interface.

## Interface

The desktop application intentionally has **one visible control: a single chat bar**. There is no dashboard, sidebar, settings screen, status panel, coding panel, orb, or other application UI.

Press Enter in the bar to talk to Jarvis. Responses are spoken through the system speech engine when available.

## Self-coding

Jarvis starts its self-coding loop automatically after the local API is healthy. Each improvement run gets a fresh session so conversational context does not grow without bound. Work is performed through the existing agent, coding, verification, and safety layers, while coding output remains non-visual.

## Core API

The local service exposes only the minimal application surface:

- `POST /api/v1/chat` — talk to Jarvis
- `POST /api/v1/autopilot` — run a self-coding task
- `GET /api/v1/health` — health check

All other legacy API routes are disabled in minimal mode.

## Development

The repository keeps its existing Windows packaging and startup architecture while the user-facing product is branded **Jarvis**. The current desktop workspace remains compatible with the existing local development and Windows startup flow.

## Safety and continuity

Self-coding continues to use the repository's existing safe-coding and verification mechanisms. The goal is incremental improvement without sacrificing a working build.
