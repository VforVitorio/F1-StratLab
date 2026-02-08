# F1 Strategy Manager - API Documentation

**Version:** 0.1.0
**Last Updated:** February 8, 2025
**Base URL:** `http://localhost:8000`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Telemetry Endpoints](#telemetry-endpoints)
4. [Circuit Analysis](#circuit-analysis)
5. [Driver Comparison](#driver-comparison)
6. [AI Chat & Voice](#ai-chat--voice)
7. [ML Predictions (Future)](#ml-predictions-future)
8. [Agent System (Future)](#agent-system-future)
9. [WebSocket Streaming (Future)](#websocket-streaming-future)
10. [Error Handling](#error-handling)

---

## Overview

The F1 Strategy Manager API provides REST endpoints for accessing Formula 1 telemetry data, AI-powered analysis, and strategic recommendations. Built with FastAPI, it offers automatic interactive documentation.

**Interactive Documentation:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

**Technical Stack:**
- Framework: FastAPI
- Authentication: Supabase JWT
- AI Backend: LM Studio (local LLM inference)
- Data Source: FastF1 library + Custom datasets

---

## Authentication

All authentication endpoints use Supabase for user management and JWT token generation.

### POST /api/v1/auth/signup

Register a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secure_password",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "message": "User created",
  "user_id": "uuid-here"
}
```

### POST /api/v1/auth/signin

Authenticate and receive JWT token.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "secure_password"
}
```

**Response:**
```json
{
  "access_token": "jwt_token_here",
  "token_type": "bearer"
}
```

### GET /api/v1/auth/me

Get current user profile. Requires authentication.

**Headers:**
```
Authorization: Bearer <jwt_token>
```

**Response:**
```json
{
  "id": "uuid",
  "email": "user@example.com",
  "full_name": "John Doe"
}
```

### POST /api/v1/auth/signout

Logout and invalidate session.

---

## Telemetry Endpoints

### GET /api/v1/telemetry/gps

List available Grand Prix events for a season.

**Parameters:**
- `year` (required): Season year (e.g., 2024)

**Example:**
```bash
curl "http://localhost:8000/api/v1/telemetry/gps?year=2024"
```

**Response:**
```json
{
  "gps": ["Bahrain", "Saudi Arabia", "Australia", "Japan", ...]
}
```

### GET /api/v1/telemetry/sessions

List available sessions for a Grand Prix.

**Parameters:**
- `year` (required): Season year
- `gp` (required): Grand Prix name

**Example:**
```bash
curl "http://localhost:8000/api/v1/telemetry/sessions?year=2024&gp=Spain"
```

**Response:**
```json
{
  "sessions": ["FP1", "FP2", "FP3", "Q", "R"]
}
```

### GET /api/v1/telemetry/drivers

List drivers in a specific session.

**Parameters:**
- `year` (required): Season year
- `gp` (required): Grand Prix name
- `session` (required): Session type (FP1, FP2, FP3, SQ, Q, S, R)

**Example:**
```bash
curl "http://localhost:8000/api/v1/telemetry/drivers?year=2024&gp=Spain&session=Q"
```

**Response:**
```json
{
  "drivers": ["VER", "HAM", "LEC", "NOR", ...]
}
```

### GET /api/v1/telemetry/lap-times

Get lap times for specified drivers.

**Parameters:**
- `year` (required): Season year
- `gp` (required): Grand Prix name
- `session` (required): Session type
- `drivers` (required): Comma-separated driver codes (e.g., "VER,HAM,LEC")

**Example:**
```bash
curl "http://localhost:8000/api/v1/telemetry/lap-times?year=2024&gp=Spain&session=Q&drivers=VER,HAM"
```

**Response:**
```json
{
  "lap_times": [
    {
      "driver": "VER",
      "lap_number": 1,
      "lap_time": "1:18.456",
      "sector1": "23.123",
      "sector2": "31.234",
      "sector3": "24.099"
    },
    ...
  ]
}
```

### GET /api/v1/telemetry/lap-telemetry

Get detailed telemetry for a specific lap.

**Parameters:**
- `year` (required): Season year
- `gp` (required): Grand Prix name
- `session` (required): Session type
- `driver` (required): Driver code
- `lap_number` (required): Lap number

**Example:**
```bash
curl "http://localhost:8000/api/v1/telemetry/lap-telemetry?year=2024&gp=Spain&session=Q&driver=VER&lap_number=5"
```

**Response:**
```json
{
  "distance": [0, 10, 20, ...],
  "speed": [0, 50, 120, 250, ...],
  "throttle": [0, 50, 100, ...],
  "brake": [0, 0, 80, ...],
  "rpm": [8000, 10000, 12000, ...],
  "gear": [1, 2, 3, 4, ...],
  "drs": [0, 0, 1, ...]
}
```

---

## Circuit Analysis

### GET /api/v1/circuit-domination

Get circuit domination visualization data showing which driver was fastest in each microsector.

**Parameters:**
- `year` (required): Season year (2018-2030)
- `gp` (required): Grand Prix name
- `session` (required): Session type
- `drivers` (required): Comma-separated driver codes (max 3)

**Example:**
```bash
curl "http://localhost:8000/api/v1/circuit-domination?year=2024&gp=Spain&session=Q&drivers=VER,LEC"
```

**Response:**
```json
{
  "x": [100.5, 101.2, 102.8, ...],
  "y": [50.3, 51.1, 52.0, ...],
  "colors": ["#A259F7", "#A259F7", "#00B4D8", ...],
  "drivers": [
    {"driver": "VER", "color": "#A259F7"},
    {"driver": "LEC", "color": "#00B4D8"}
  ]
}
```

---

## Driver Comparison

### GET /api/v1/comparison/compare

Compare telemetry between two drivers using their fastest laps.

**Parameters:**
- `year` (required): Season year
- `gp` (required): Grand Prix name
- `session` (required): Session type
- `driver1` (required): First driver code
- `driver2` (required): Second driver code

**Example:**
```bash
curl "http://localhost:8000/api/v1/comparison/compare?year=2024&gp=Monaco&session=Q&driver1=VER&driver2=LEC"
```

**Response:**
```json
{
  "circuit": {
    "x": [100, 101, ...],
    "y": [50, 51, ...],
    "colors": ["#A259F7", "#00B4D8", ...]
  },
  "pilot1": {
    "driver": "VER",
    "color": "#A259F7",
    "speed": [120, 250, ...],
    "throttle": [100, 80, ...],
    "brake": [0, 50, ...]
  },
  "pilot2": {
    "driver": "LEC",
    "color": "#00B4D8",
    "speed": [118, 248, ...],
    "throttle": [100, 75, ...],
    "brake": [0, 55, ...]
  },
  "delta": [-0.1, -0.2, 0.05, ...],
  "metadata": {
    "rotation_angle": 45.2,
    "aspect_ratio": 1.5,
    "qualifying_phase": "Q3",
    "warning": null
  }
}
```

**Notes:**
- For Qualifying sessions, the API automatically uses the highest common phase (Q1/Q2/Q3) both drivers reached
- Delta values: negative means driver1 was faster, positive means driver2 was faster
- Microsector colors indicate which driver dominated each track segment

---

## AI Chat & Voice

### GET /api/v1/chat/health

Check LM Studio connection status.

**Response:**
```json
{
  "status": "healthy",
  "lm_studio_running": true,
  "available_models": 3
}
```

### GET /api/v1/chat/models

Get list of available LLM models.

**Response:**
```json
{
  "models": [
    "qwen-2.5-vl-4b-instruct",
    "llama-3.3-70b-instruct",
    "mistral-7b-instruct"
  ]
}
```

### POST /api/v1/chat/message

Send a message to the AI assistant. Returns complete response (non-streaming).

**Request Body:**
```json
{
  "text": "Why is VER faster in sector 2?",
  "image": "base64_encoded_chart_image",
  "chat_history": [
    {"role": "user", "content": "Previous message"},
    {"role": "assistant", "content": "Previous response"}
  ],
  "context": {
    "year": 2024,
    "gp": "Spain",
    "session": "Q",
    "drivers": ["VER", "LEC"]
  },
  "model": "qwen-2.5-vl-4b-instruct",
  "temperature": 0.7,
  "max_tokens": 2000
}
```

**Response:**
```json
{
  "response": "VER gains time in sector 2 due to...",
  "llm_model": "qwen-2.5-vl-4b-instruct",
  "tokens_used": 450
}
```

### POST /api/v1/chat/stream

Send a message with streaming response using Server-Sent Events.

**Request:** Same schema as `/chat/message`

**Response:** Server-Sent Events stream with text chunks

### POST /api/v1/chat/query

Intelligent query routing with specialized handlers based on query type classification.

**Request:** Same schema as `/chat/message`

**Response:**
```json
{
  "type": "technical_analysis",
  "handler": "TechnicalQueryHandler",
  "response": "Detailed technical analysis...",
  "metadata": {
    "telemetry_fetched": true,
    "charts_generated": 2
  }
}
```

**Query Types:**
- `basic` - Simple informational questions
- `technical` - In-depth telemetry analysis
- `comparison` - Driver or lap comparisons
- `report` - Conversation summaries
- `download` - Data export requests

### POST /api/v1/voice/...

Voice interaction endpoints supporting speech-to-text, text-to-speech, and full pipeline.

**Note:** Voice endpoints documentation will be added in future updates.

---

## ML Predictions (Future)

These endpoints will be implemented in Phase 3-4 (ML Foundation & Additional Predictors).

### POST /api/v1/ml/predict/laptime

Predict lap time based on telemetry features and circuit clustering.

**Status:** Not yet implemented

**Planned Request:**
```json
{
  "circuit_cluster": "balanced",
  "year": 2024,
  "telemetry_features": {...}
}
```

### POST /api/v1/ml/predict/tiredeg

Predict tire degradation percentage based on compound, stint length, and circuit characteristics.

**Status:** Not yet implemented

### POST /api/v1/ml/predict/sector

Predict sector times (S1, S2, S3) using multi-output XGBoost model.

**Status:** Not yet implemented

### POST /api/v1/ml/predict/overtake

Predict overtake probability for the next 3 laps based on gap, DRS availability, and tire compound delta.

**Status:** Not yet implemented

### POST /api/v1/ml/predict/safetycar

Predict safety car deployment probability for the next 5 laps based on weather, incidents, and field spread.

**Status:** Not yet implemented

---

## Agent System (Future)

These endpoints will be implemented in Phase 5 (Multi-Agent System).

### POST /api/v1/agent/strategy/recommend

Get strategic recommendations from the coordinated multi-agent system.

**Status:** Not yet implemented

**Planned Request:**
```json
{
  "telemetry_context": {...},
  "radio_events": [...],
  "ml_predictions": {...}
}
```

**Planned Response:**
```json
{
  "recommendation": "Pit on lap 35 for Hard tires",
  "confidence": 0.87,
  "reasoning": "Based on current tire degradation...",
  "agent_coordination": {
    "telemetry_agent": "Normal operation",
    "radio_agent": "Team suggests early pit",
    "strategy_agent": "Optimal window: lap 34-36"
  }
}
```

---

## WebSocket Streaming (Future)

These endpoints will be implemented in Phase 7 (User Interfaces). The API will maintain a hybrid architecture with REST endpoints for queries and WebSocket for real-time streaming.

### WS /ws/replay (MVP)

Stream race replay data from CSV/Parquet files at 10Hz for offline analysis.

**Status:** Not yet implemented

**Architecture:** Hybrid REST + WebSocket in the same FastAPI backend

**Connection:**
```javascript
const ws = new WebSocket("ws://localhost:8000/ws/replay");

ws.onmessage = (event) => {
  const frame = JSON.parse(event.data);
  // frame.timestamp, frame.positions, frame.telemetry
};
```

**Data Format:**
```json
{
  "timestamp": "0:01:23.456",
  "lap": 15,
  "positions": [
    {"driver": "VER", "position": 1, "x": 1234.5, "y": 678.9},
    ...
  ],
  "telemetry": {
    "VER": {"speed": 287, "throttle": 100, "gear": 8},
    ...
  }
}
```

### WS /ws/live (Extension - Future)

Stream live telemetry data from Kafka consumer for real-time race monitoring.

**Status:** Planned for future extension

**Note:** The MVP uses `/ws/replay` with offline data. This endpoint will be added later for live streaming integration.

---

## Error Handling

### Standard Error Response

All endpoints return errors in this format:

```json
{
  "detail": "Error message describing what went wrong"
}
```

### HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid parameters)
- `401` - Unauthorized (authentication required)
- `404` - Not Found (session/driver/data not found)
- `500` - Internal Server Error
- `503` - Service Unavailable (LM Studio connection failed)

### Common Error Examples

**Session not found:**
```json
{
  "detail": "No session data found for 2024 Spain Q"
}
```

**Driver not found:**
```json
{
  "detail": "Driver 'ABC' not found in session"
}
```

**LM Studio unavailable:**
```json
{
  "detail": "LM Studio is not running or not accessible"
}
```

**Invalid parameters:**
```json
{
  "detail": "Invalid driver code: AB. Must be 3 letters (e.g., 'VER', 'HAM')"
}
```

---

## Development Notes

### Adding New Endpoints

When implementing new endpoints:

1. Update this documentation with request/response schemas
2. Add curl examples for testing
3. Document query parameters and validation rules
4. Include error scenarios
5. Test using interactive documentation at `/docs`

### Versioning

API endpoints are versioned under `/api/v1/`. Breaking changes will increment the version to `/api/v2/`.

### Architecture

The backend maintains a hybrid architecture:
- **REST endpoints** for historical data queries and ML predictions
- **WebSocket endpoints** for real-time streaming (Phase 7 implementation)
- Both protocols coexist in the same FastAPI application

---

**Maintained by:** Development Team
**Repository:** F1_Strat_Manager
**License:** See LICENSE file
