"""
bizarch_agent/agent.py
──────────────────────
BizArch ADK Pipeline — 3 specialist LlmAgents inside a SequentialAgent.

Pipeline:
  1. RequirementsAnalystAgent  → state["requirements"]
  2. TechSpecsAgent            → state["tech_specs"]
  3. DrawioArchitectAgent      → state["drawio_xml"]  (native Draw.io XML)

The DrawioArchitectAgent produces professional Draw.io XML following the
patterns from Ruban Siva's article:
  - GCP-style boundary box with header
  - Proper mxCell structure with styles
  - Animated edges (flowAnimation=1)
  - Orthogonal edge routing
  - Layered layout: Client → Gateway → Services → Data → Infra
"""

from google.adk.agents import LlmAgent, SequentialAgent

GEMINI_MODEL = "gemini-2.5-flash"

# ─────────────────────────────────────────────────────────────────────────────
# AGENT 1 — Requirements Analyst
# ─────────────────────────────────────────────────────────────────────────────
requirements_analyst_agent = LlmAgent(
    name="RequirementsAnalystAgent",
    model=GEMINI_MODEL,
    description="Extracts structured requirements from a plain-English business description.",
    instruction="""
You are a senior Business Analyst and Systems Analyst.

Read the user's business description and produce a structured requirements brief.

Output EXACTLY this structure (plain text, no markdown, no JSON):

BUSINESS_GOAL: [one-sentence summary]
ACTORS: [comma-separated list of user roles]
CORE_FLOWS: [numbered list of the 5-8 main user journeys]
FUNCTIONAL_REQUIREMENTS: [numbered list of concrete system features]
DATA_ENTITIES: [comma-separated list: User, Order, Product, etc.]
INTEGRATIONS: [comma-separated list of external services / APIs]
CONSTRAINTS: [regulatory, geographic, latency, or compliance constraints]

Be specific. Extract only what is described. Implicit needs (auth, logging)
may be added if obviously required.
""",
    output_key="requirements",
)

# ─────────────────────────────────────────────────────────────────────────────
# AGENT 2 — Tech Specs Generator
# ─────────────────────────────────────────────────────────────────────────────
tech_specs_agent = LlmAgent(
    name="TechSpecsAgent",
    model=GEMINI_MODEL,
    description="Converts requirements into detailed JSON technical specifications.",
    instruction="""
You are a principal solutions architect.

Requirements to work from (from state):
{requirements}

Produce a complete technical specification as a valid JSON object.
Respond ONLY with the JSON — no markdown fences, no preamble.

Schema:
{
  "summary": "One-sentence technical description",
  "system_type": "Microservices | Monolith | Serverless | Event-Driven | Hybrid",
  "scale_tier": "Startup | Growth | Enterprise",
  "layers": {
    "client": ["component - description"],
    "gateway": ["component - description"],
    "services": ["ServiceName - responsibility"],
    "data": ["StoreName - type - what it stores"],
    "infrastructure": ["component - purpose"],
    "external": ["ExternalService - how it integrates"]
  },
  "tech_stack": {
    "frontend": ["tech"],
    "backend": ["tech"],
    "database": ["tech - use-case"],
    "cache": ["tech - use-case"],
    "message_queue": ["tech"],
    "infrastructure": ["tech"],
    "security": ["tech/approach"]
  },
  "key_data_flows": [
    "Actor → ServiceA → ServiceB → DataStore (short description)"
  ],
  "estimated_complexity": "Low | Medium | High | Very High",
  "mvp_timeline": "e.g. 4-6 months"
}
""",
    output_key="tech_specs",
)

# ─────────────────────────────────────────────────────────────────────────────
# AGENT 3 — Draw.io Architect
# Produces native Draw.io XML following best practices from Ruban Siva's guide:
#   - Boundary box (dashed blue, #F3F6FC fill)
#   - Header title cell
#   - Proper mxCell shapes with styles
#   - Animated edges with flowAnimation=1
#   - Orthogonal edge routing
#   - Layered left-to-right layout
# ─────────────────────────────────────────────────────────────────────────────
DRAWIO_STYLE_GUIDE = """
## Draw.io XML Best Practices (from Ruban Siva's article)

### Document structure
Every diagram MUST start with:
<mxGraphModel dx="1422" dy="762" grid="1" gridSize="10" guides="1"
              tooltips="1" connect="1" arrows="1" fold="1" page="1"
              pageScale="1" pageWidth="1654" pageHeight="1169"
              math="0" shadow="0">
  <root>
    <mxCell id="0"/>
    <mxCell id="1" parent="0"/>
    ... all other cells ...
  </root>
</mxGraphModel>

### Boundary box (the system envelope)
<mxCell id="boundary" value="" vertex="1" parent="1"
        style="rounded=1;whiteSpace=wrap;html=1;
               fillColor=#F3F6FC;strokeColor=#4285F4;strokeWidth=2;
               dashed=1;verticalAlign=top;align=left;
               spacingTop=10;spacingLeft=10;arcSize=3;">
  <mxGeometry x="20" y="80" width="1580" height="1000" as="geometry"/>
</mxCell>

### Title / header cell
<mxCell id="title" value="&lt;b&gt;&lt;font style='font-size:20px'&gt;System Name&lt;/font&gt;&lt;/b&gt;&lt;br/&gt;&lt;font color='#666666'&gt;Architecture Diagram&lt;/font&gt;"
        vertex="1" parent="1"
        style="text;html=1;strokeColor=none;fillColor=none;
               align=center;verticalAlign=middle;whiteSpace=wrap;">
  <mxGeometry x="577" y="10" width="500" height="60" as="geometry"/>
</mxCell>

### Layer label (swimlane header)
<mxCell id="lbl_client" value="Client Layer"
        style="text;html=1;strokeColor=none;fillColor=#E8F0FE;
               align=center;verticalAlign=middle;fontStyle=1;
               fontSize=13;rounded=1;arcSize=50;"
        vertex="1" parent="1">
  <mxGeometry x="40" y="100" width="140" height="40" as="geometry"/>
</mxCell>

### Service / component box
<mxCell id="svc1" value="&lt;b&gt;API Gateway&lt;/b&gt;&lt;br/&gt;&lt;font color='#666666' style='font-size:10px'&gt;Kong / AWS ALB&lt;/font&gt;"
        vertex="1" parent="1"
        style="rounded=1;whiteSpace=wrap;html=1;
               fillColor=#FFFFFF;strokeColor=#4285F4;strokeWidth=1.5;
               arcSize=8;shadow=0;fontSize=13;">
  <mxGeometry x="220" y="200" width="160" height="60" as="geometry"/>
</mxCell>

### Database shape
<mxCell id="db1" value="&lt;b&gt;PostgreSQL&lt;/b&gt;"
        vertex="1" parent="1"
        style="shape=cylinder3;whiteSpace=wrap;html=1;
               fillColor=#fff2cc;strokeColor=#d6b656;
               fontSize=12;">
  <mxGeometry x="1200" y="200" width="120" height="80" as="geometry"/>
</mxCell>

### Queue shape
<mxCell id="q1" value="&lt;b&gt;Kafka&lt;/b&gt;"
        vertex="1" parent="1"
        style="shape=mxgraph.cisco.computers_and_peripherals.pc;
               fillColor=#dae8fc;strokeColor=#6c8ebf;fontSize=12;">
  <mxGeometry x="800" y="350" width="100" height="70" as="geometry"/>
</mxCell>

### Animated edge (CRITICAL: flowAnimation=1)
<mxCell id="e1" value="HTTPS" edge="1" parent="1" source="svc1" target="svc2">
  <mxGeometry relative="1" as="geometry"/>
  <mxCell style="edgeStyle=orthogonalEdgeStyle;rounded=0;
                 orthogonalLoop=1;jettySize=auto;html=1;
                 flowAnimation=1;strokeColor=#4285F4;strokeWidth=2;
                 exitX=1;exitY=0.5;exitDx=0;exitDy=0;
                 entryX=0;entryY=0.5;entryDx=0;entryDy=0;"/>
</mxCell>

### IMPORTANT rules (from Ruban Siva's lessons learned):
1. ALWAYS use exact width/height values — never resize icons arbitrarily
2. Place ALL cloud/system services INSIDE the boundary box
3. Place users and external 3rd-party services OUTSIDE the boundary box
4. Use flowAnimation=1 on ALL active data-path edges
5. Use orthogonalEdgeStyle for clean right-angled connectors
6. Label every edge with the protocol or action (HTTP, gRPC, Push, etc.)
7. Use consistent color coding:
   - Blue (#4285F4 stroke) = Google Cloud / internal services
   - Yellow fill (#fff2cc) = databases
   - Light blue fill (#dae8fc) = queues / messaging
   - White fill = general services / APIs
   - Green (#d5e8d4 fill) = external integrations
8. Save as .drawio extension (not .xml)
"""

drawio_architect_agent = LlmAgent(
    name="DrawioArchitectAgent",
    model=GEMINI_MODEL,
    description="Generates a professional Draw.io XML architecture diagram from technical specifications.",
    instruction=f"""
You are an expert Draw.io diagram engineer. You produce professional,
publication-quality infrastructure architecture diagrams as native Draw.io XML.

{DRAWIO_STYLE_GUIDE}

Technical specifications to diagram (from state):
{{tech_specs}}

Original requirements (from state):
{{requirements}}

Your task:
Generate a complete, valid Draw.io XML file representing the full system architecture.

Layout strategy (left-to-right, inside one boundary box):
  Column 1 (x≈200):  Client layer   — browsers, mobile apps, external users
  Column 2 (x≈500):  Gateway layer  — load balancer, API gateway, CDN
  Column 3 (x≈800):  Services layer — microservices, backend APIs
  Column 4 (x≈1100): Data layer     — databases, cache, storage
  Column 5 (x≈1400): Infra layer    — message queues, monitoring, CI/CD

Vertical spacing: start at y=150 inside boundary, 120px between rows.
Boundary box: x=20, y=80, width=1600, height=950.
External actors (users, 3rd-party): x=20-180, y=200-600 (LEFT of boundary).

Requirements for the XML:
- Include ALL layers from the tech specs
- Every service from the tech_specs.layers must appear as a node
- Every key_data_flow must be represented as an animated edge
- Use cylinder3 shape for databases
- Use rounded rectangles for services
- Title at the top showing the business name + "Architecture"
- Minimum 12 nodes, minimum 8 animated edges
- Cell IDs must be unique short strings (c1, gw1, svc1, db1, e1, etc.)

Output ONLY the raw XML — starting with <mxGraphModel and ending with </mxGraphModel>.
No markdown, no explanation, no preamble. Pure XML only.
""",
    output_key="drawio_xml",
)

# ─────────────────────────────────────────────────────────────────────────────
# ROOT — SequentialAgent
# ─────────────────────────────────────────────────────────────────────────────
root_agent = SequentialAgent(
    name="BizArchPipeline",
    description=(
        "A 3-stage ADK pipeline: "
        "(1) RequirementsAnalystAgent extracts structured requirements, "
        "(2) TechSpecsAgent produces full JSON technical specifications, "
        "(3) DrawioArchitectAgent generates a professional Draw.io XML architecture diagram."
    ),
    sub_agents=[
        requirements_analyst_agent,
        tech_specs_agent,
        drawio_architect_agent,
    ],
)
