# BeautyDropAI Agent - Complete Documentation

## Overview

The BeautyDropAI Agent is an intelligent conversational assistant that helps users manage salon bookings, discover shops, and handle appointments. It uses **OpenAI GPT-4** for natural language understanding and **Pinecone** for semantic search over shop/service knowledge.

---

## System Architecture

```mermaid
flowchart TB
    subgraph Users
        C["Customer"]
        O["Shop Owner"]
        S["Staff"]
    end

    subgraph API_Layer["API Layer"]
        API["AgentViewSet"]
        AUTH["Clerk Auth"]
    end

    subgraph Agent_Core["Agent Core"]
        AC["AgentController"]
        CB["ContextBuilder"]
        TE["ToolExecutor"]
    end

    subgraph Knowledge_Layer["Knowledge Layer"]
        ES["EmbeddingService"]
        PS["PineconeService"]
        PC[("Pinecone DB")]
    end

    subgraph External["External Services"]
        OAI["OpenAI GPT-4"]
        EMB["OpenAI Embeddings"]
    end

    subgraph Data_Layer["Data Layer"]
        DB[("PostgreSQL")]
    end

    C --> API
    O --> API
    S --> API
    API --> AUTH
    AUTH --> AC
    AC --> CB
    AC --> TE
    CB --> ES
    ES --> EMB
    CB --> PS
    PS --> PC
    AC <--> OAI
    TE --> DB
```

---

## Request Flow

```mermaid
sequenceDiagram
    participant U as User
    participant API as AgentViewSet
    participant CB as ContextBuilder
    participant PC as Pinecone
    participant AC as AgentController
    participant TE as ToolExecutor
    participant OAI as OpenAI
    participant DB as Database

    U->>API: POST /chat/ message
    API->>DB: Get/Create ChatSession
    DB-->>API: Session + history

    API->>CB: Build context
    CB->>PC: Query knowledge
    PC-->>CB: Similar docs

    API->>AC: process_message
    AC->>OAI: Chat + tools

    loop Tool Loop
        OAI-->>AC: tool_call
        AC->>TE: execute
        TE->>DB: Query data
        DB-->>TE: Result
        TE-->>AC: JSON
        AC->>OAI: Continue
    end

    OAI-->>AC: Response
    AC->>DB: Save message
    AC-->>API: Result
    API-->>U: JSON response
```

---

## Database Models

```mermaid
erDiagram
    User ||--o{ ChatSession : owns
    ChatSession ||--|{ ChatMessage : contains
    ChatMessage ||--o{ AgentAction : triggers
    Shop ||--o{ KnowledgeDocument : indexed

    ChatSession {
        uuid id
        string session_id
        string user_role
        boolean is_active
        int message_count
        int total_tokens_used
    }

    ChatMessage {
        uuid id
        string role
        text content
        json tool_calls
        string tool_name
        int prompt_tokens
        int completion_tokens
        boolean is_error
    }

    AgentAction {
        uuid id
        string action_type
        json input_params
        json output_result
        boolean success
        int execution_time_ms
    }

    KnowledgeDocument {
        uuid id
        string doc_type
        string pinecone_id
        text content_text
        datetime last_synced_at
    }
```

---

## Role-Based Context

```mermaid
flowchart LR
    subgraph Customer_Context["Customer Context"]
        CC["User Info"]
        CB1["Upcoming Bookings"]
        CB2["Booking History"]
        CB3["Favorite Shops"]
    end

    subgraph Owner_Context["Owner Context"]
        OC["User Info"]
        OS["Shop Details"]
        OST["Staff List"]
        OB["Today Bookings"]
        OP["Pending Count"]
    end

    subgraph Staff_Context["Staff Context"]
        SC["User Info"]
        SS["Shop Info"]
        SSV["My Services"]
        STB["Today Appointments"]
    end

    Customer_Context --> CP["Customer Prompt"]
    Owner_Context --> OP2["Owner Prompt"]
    Staff_Context --> SP["Staff Prompt"]
```

---

## Tool System

```mermaid
classDiagram
    class BaseTool {
        +name: str
        +description: str
        +allowed_roles: list
        +parameters()
        +execute()
        +to_openai_function()
    }

    class GetMyBookingsTool {
        +name: get_my_bookings
    }

    class CreateBookingTool {
        +name: create_booking
    }

    class CancelBookingTool {
        +name: cancel_booking
    }

    class SearchShopsTool {
        +name: search_shops
    }

    class GetAvailableSlotsTool {
        +name: get_available_slots
    }

    BaseTool <|-- GetMyBookingsTool
    BaseTool <|-- CreateBookingTool
    BaseTool <|-- CancelBookingTool
    BaseTool <|-- SearchShopsTool
    BaseTool <|-- GetAvailableSlotsTool
```

### Available Tools by Role

| Tool                  | Customer | Owner | Staff | Description                       |
| --------------------- | :------: | :---: | :---: | --------------------------------- |
| `search_shops`        |    ✅    |       |       | Search shops by name/city/service |
| `get_shop_info`       |    ✅    |  ✅   |  ✅   | Get detailed shop information     |
| `get_shop_services`   |    ✅    |  ✅   |  ✅   | List services with prices         |
| `get_shop_staff`      |    ✅    |  ✅   |       | List staff members                |
| `get_available_slots` |    ✅    |  ✅   |  ✅   | Check booking availability        |
| `get_shop_hours`      |    ✅    |  ✅   |  ✅   | Get weekly operating hours        |
| `get_shop_holidays`   |    ✅    |  ✅   |  ✅   | Get upcoming closures             |
| `get_my_bookings`     |    ✅    |       |  ✅   | View own bookings                 |
| `create_booking`      |    ✅    |       |       | Book an appointment               |
| `cancel_booking`      |    ✅    |  ✅   |       | Cancel a booking                  |
| `get_shop_bookings`   |          |  ✅   |       | View all shop bookings            |
| `confirm_booking`     |          |  ✅   |       | Confirm pending booking           |

---

## Pinecone Integration

```mermaid
flowchart LR
    subgraph Sources["Data Sources"]
        SHOP["Shop Model"]
        SVC["Service Model"]
    end

    subgraph Sync["Sync Process"]
        CMD["sync_knowledge_base"]
        BUILD["Build Text"]
        EMBED["Generate Embedding"]
    end

    subgraph Pinecone["Pinecone"]
        UP["Upsert"]
        IDX[("Vector Index")]
    end

    SHOP --> CMD
    SVC --> CMD
    CMD --> BUILD
    BUILD --> EMBED
    EMBED --> UP
    UP --> IDX
```

---

## API Reference

### Chat Endpoint

```
POST /api/v1/agent/chat/
```

**Request:**

```json
{
  "message": "I want to book a haircut tomorrow",
  "session_id": "optional-uuid"
}
```

**Response:**

```json
{
  "response": "I found available slots for haircuts tomorrow...",
  "session_id": "abc123-uuid",
  "message_id": "msg-uuid",
  "actions_taken": [
    {
      "action_type": "get_available_slots",
      "success": true,
      "details": { "slot_count": 8 }
    }
  ],
  "tokens_used": {
    "prompt": 450,
    "completion": 120
  }
}
```

### Session Endpoints

| Method | Endpoint                           | Description               |
| ------ | ---------------------------------- | ------------------------- |
| GET    | `/api/v1/agent/sessions/`          | List all user sessions    |
| GET    | `/api/v1/agent/sessions/{id}/`     | Get session with messages |
| POST   | `/api/v1/agent/sessions/{id}/end/` | End a session             |
| DELETE | `/api/v1/agent/sessions/{id}/`     | Delete session            |

---

## Conversation Examples

### Customer Booking Flow

```mermaid
sequenceDiagram
    participant C as Customer
    participant A as AI Agent

    C->>A: Find salons near downtown
    Note right of A: Tool: search_shops
    A-->>C: Found 3 salons...

    C->>A: Available times tomorrow?
    Note right of A: Tool: get_available_slots
    A-->>C: Slots at 10am, 2pm, 3pm...

    C->>A: Book me for 2pm
    Note right of A: Tool: create_booking
    A-->>C: Booked! ID 12345
```

### Owner Management Flow

```mermaid
sequenceDiagram
    participant O as Shop Owner
    participant A as AI Agent

    O->>A: Show today schedule
    Note right of A: Tool: get_shop_bookings
    A-->>O: 8 bookings today...

    O->>A: Any pending confirmations?
    A-->>O: 2 pending bookings

    O->>A: Confirm them
    Note right of A: Tool: confirm_booking x2
    A-->>O: Both confirmed!
```

---

## File Structure

```
apps/agent/
├── models.py                    # Database models
├── admin.py                     # Admin interface
├── serializers.py               # API serializers
├── views.py                     # API views
├── urls.py                      # URL routing
├── services/
│   ├── agent_controller.py      # Main orchestration
│   ├── context_builder.py       # Role context + RAG
│   ├── embedding_service.py     # OpenAI embeddings
│   ├── pinecone_service.py      # Vector DB
│   └── tool_executor.py         # Tool management
├── tools/
│   ├── base.py                  # BaseTool class
│   ├── booking_tools.py         # Booking operations
│   ├── shop_tools.py            # Shop queries
│   └── schedule_tools.py        # Availability checks
├── prompts/
│   └── system_prompts.py        # Role prompts
└── management/commands/
    └── sync_knowledge_base.py
```

---

## Environment Variables

```bash
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# Pinecone
PINECONE_API_KEY=pc-...
PINECONE_INDEX_NAME=beautydrop-knowledge
```

---

## Admin Debugging

Access `/admin/` to view:

- **Chat Sessions**: View all conversations, user roles, token usage
- **Chat Messages**: See every message with role, tokens, processing time
- **Agent Actions**: Audit log with input/output, success status, timing
- **Knowledge Documents**: Track Pinecone sync status per shop/service
