# 🏗️ BizArch ADK + Draw.io Agent

> Inspired by [Ruban Siva's article](https://medium.com/google-cloud/automating-mastering-infrastructure-diagrams-with-draw-io-mcp-and-antigravity-2839b78df143) — *"Automating & Mastering Infrastructure Diagrams with Draw.io, MCP, and Antigravity"*

Convert any business description into a **professional Draw.io architecture diagram** using Google's Agent Development Kit (ADK) and Gemini 2.0 Flash.

---

## How It Works

```
Business Description (plain English)
         │
         ▼
┌────────────────────────────────────────────────────────┐
│           BizArchPipeline  (SequentialAgent)           │
│                                                        │
│  1. RequirementsAnalystAgent                           │
│     └─► state["requirements"]  (structured plain text) │
│                  │                                     │
│  2. TechSpecsAgent                                     │
│     reads: {requirements}                              │
│     └─► state["tech_specs"]  (JSON: layers, stack, ...) │
│                  │                                     │
│  3. DrawioArchitectAgent                               │
│     reads: {tech_specs} + {requirements}               │
│     └─► state["drawio_xml"]  (native Draw.io XML)      │
└────────────────────────────────────────────────────────┘
         │
         ▼
   drawio_exporter.py  →  PNG image
   (tries 4 strategies in order)
         │
         ▼
   Streamlit renders image + download buttons
```

---

## ADK Concepts Used

| Concept | Usage |
|---|---|
| `LlmAgent` | Each of the 3 specialist agents |
| `SequentialAgent` | Orchestrates the 3 agents in strict order |
| `output_key` | Each agent saves its output to session state |
| `{state_key}` template | Agents read previous agents' outputs from state |
| `InMemorySessionService` | Manages session state locally |
| `Runner` | Executes the pipeline asynchronously |

---

## Draw.io XML Best Practices (from Ruban Siva's article)

The `DrawioArchitectAgent` follows these patterns:

- **Boundary box** — dashed blue border (`#4285F4`), light fill (`#F3F6FC`) wrapping all cloud services
- **Animated edges** — `flowAnimation=1` on all active data-path connectors
- **Orthogonal routing** — `edgeStyle=orthogonalEdgeStyle` for clean right-angle lines
- **Consistent shapes** — `cylinder3` for databases, `rounded=1` for services
- **Color coding** — Yellow for DBs, light-blue for queues, white for services, green for external
- **Layered layout** — Client → Gateway → Services → Data → Infrastructure (left to right)
- **Proper IDs** — Short unique cell IDs (no spaces) for reliable edge connections
- **`.drawio` extension** — Always saved as `.drawio` not `.xml`

---

## Image Export — 4 Strategies (automatic fallback)

The app tries these in order:

| Priority | Strategy | Requires |
|---|---|---|
| 1 | **draw.io Desktop CLI** | draw.io desktop app installed |
| 2 | **drawio-batch** (npm) | `npm install -g draw.io-export` |
| 3 | **draw.io Export Service** | Internet access |
| 4 | **Python SVG renderer** | `pip install cairosvg` (optional) |

---

## Project Structure

```
bizarch_adk_drawio/
├── app.py                    # Streamlit UI
├── drawio_exporter.py        # XML → PNG conversion (4 strategies)
├── requirements.txt
├── README.md
└── bizarch_agent/
    ├── __init__.py
    └── agent.py              # ADK agents (root_agent = SequentialAgent)
```

---

## Setup & Run

```bash
# 1. Install Python dependencies
pip install -r requirements.txt

# 2. (Recommended) Install draw.io desktop for best PNG quality
#    macOS:
brew install --cask drawio
#    Linux:
wget https://github.com/jgraph/drawio-desktop/releases/latest/download/drawio-amd64.deb
sudo dpkg -i drawio-amd64.deb

# 3. Run
streamlit run app.py

# Alternative: use ADK's built-in dev UI (great for debugging agent events)
adk web

# Alternative: run from CLI
adk run bizarch_agent
```

---

## Output Tabs

| Tab | Content |
|---|---|
| 🎨 Architecture Diagram | PNG/SVG image of the Draw.io diagram + `.drawio` download |
| ⚙️ Tech Specs | Parsed JSON dashboard: layers, stack, data flows, timeline |
| 📋 Requirements | Structured requirements: actors, flows, features, constraints |
