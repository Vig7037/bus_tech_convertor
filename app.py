"""
app.py — BizArch ADK Agent with Draw.io Architecture Output
─────────────────────────────────────────────────────────────
3-agent ADK SequentialAgent pipeline:
  1. RequirementsAnalystAgent  → structured requirements
  2. TechSpecsAgent            → JSON technical specifications
  3. DrawioArchitectAgent      → native Draw.io XML diagram

Then converts the .drawio XML to a PNG image for display in Streamlit.
Inspired by Ruban Siva's article on automating Draw.io with MCP and AI.
"""

import asyncio
import json
import os
import re
import tempfile
from pathlib import Path

import streamlit as st

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="BizArch ADK + Draw.io",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@400;500;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

html, body, [class*="css"] { font-family: 'Syne', sans-serif; }
[data-testid="stSidebar"] { background: #0d0d14 !important; border-right: 1px solid rgba(255,255,255,0.07) !important; }
[data-testid="stSidebar"] * { color: #cccae0 !important; }
.main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1280px; }
h1,h2,h3 { font-family: 'Syne', sans-serif !important; }
h1 { font-weight: 800 !important; }

/* Pipeline steps */
.pipe-step { display:flex; align-items:center; gap:10px; padding:10px 14px; border-radius:8px; font-size:13px; font-weight:600; margin-bottom:6px; }
.pipe-idle   { background:rgba(255,255,255,0.03); color:#55536a; border:1px solid rgba(255,255,255,0.06); }
.pipe-active { background:rgba(245,158,11,0.12);  color:#f59e0b;  border:1px solid rgba(245,158,11,0.25); }
.pipe-done   { background:rgba(61,220,132,0.10);  color:#3ddc84;  border:1px solid rgba(61,220,132,0.22); }
.pipe-error  { background:rgba(248,113,113,0.10); color:#f87171;  border:1px solid rgba(248,113,113,0.22); }
.dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
.dot-idle   { background:#3a384d; }
.dot-active { background:#f59e0b; box-shadow:0 0 7px #f59e0b; animation:pulse 1s infinite; }
.dot-done   { background:#3ddc84; }
.dot-error  { background:#f87171; }
@keyframes pulse { 0%,100%{opacity:1;transform:scale(1)} 50%{opacity:.6;transform:scale(1.4)} }

/* Cards */
.tcard { background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.08); border-radius:10px; padding:14px 16px; margin-bottom:8px; }
.tcard-label { font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#4e4c63; font-family:'JetBrains Mono',monospace; margin-bottom:6px; }
.sec-title { font-size:10px; font-weight:700; letter-spacing:1.4px; text-transform:uppercase; color:#7c6af7; font-family:'JetBrains Mono',monospace; border-bottom:1px solid rgba(124,106,247,0.2); padding-bottom:8px; margin:18px 0 12px; }
.badge { display:inline-block; padding:3px 9px; border-radius:20px; font-size:11px; font-weight:600; margin:2px; font-family:'JetBrains Mono',monospace; }
.b-blue  { background:rgba(96,165,250,0.14); color:#60a5fa; border:1px solid rgba(96,165,250,0.28); }
.b-green { background:rgba(61,220,132,0.14); color:#3ddc84; border:1px solid rgba(61,220,132,0.28); }
.b-amber { background:rgba(245,158,11,0.14); color:#f59e0b; border:1px solid rgba(245,158,11,0.28); }
.b-red   { background:rgba(248,113,113,0.14); color:#f87171; border:1px solid rgba(248,113,113,0.28); }
.b-purple{ background:rgba(124,106,247,0.14); color:#9d8ff5; border:1px solid rgba(124,106,247,0.28); }
.b-teal  { background:rgba(45,212,191,0.14); color:#2dd4bf; border:1px solid rgba(45,212,191,0.28); }
.li-item { padding:8px 12px; background:rgba(255,255,255,0.03); border-radius:8px; border-left:2px solid #7c6af7; margin-bottom:5px; font-size:13px; line-height:1.5; }
.req-block { background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07); border-radius:10px; padding:16px; margin-bottom:10px; }
.req-key { font-size:10px; font-weight:700; letter-spacing:1px; text-transform:uppercase; color:#7c6af7; font-family:'JetBrains Mono',monospace; margin-bottom:8px; }
.req-val { font-size:13px; line-height:1.7; color:#b0aec8; }

/* Diagram viewer */
.diagram-frame { background:#f8f9fa; border:1px solid #e0e0e0; border-radius:12px; padding:16px; text-align:center; }
.drawio-badge { display:inline-flex; align-items:center; gap:6px; background:#FF6D00; color:#fff; padding:5px 12px; border-radius:6px; font-size:12px; font-weight:700; font-family:'JetBrains Mono',monospace; }

.stButton > button { font-family:'Syne',sans-serif !important; font-weight:700 !important; border-radius:10px !important; }
[data-testid="stMetric"] { background:rgba(120,100,250,0.08); border:1px solid rgba(120,100,250,0.22); border-radius:10px; padding:12px 16px !important; }
</style>
""", unsafe_allow_html=True)

# ── Examples ──────────────────────────────────────────────────────────────────
EXAMPLES = {
    "🛒 E-commerce": "We run an online marketplace where sellers list products and buyers purchase them. We need a product catalog, shopping cart, checkout with credit card/UPI/wallet payments, order management, real-time inventory, email/SMS notifications, a seller dashboard with analytics, customer reviews, and a recommendation engine.",
    "💳 Fintech App": "We're building a personal finance app that syncs with bank accounts via open banking APIs, auto-categorizes transactions using AI, tracks budgets and savings goals, sends overspend alerts, and generates monthly financial reports. We need bank-grade security, real-time balance sync, and multi-bank support.",
    "☁️ SaaS Platform": "We're building a B2B project management SaaS for software teams with kanban boards, sprint planning, bug tracking, threaded comments, file attachments, time tracking, GitHub integration, role-based access, and a billing system with free/pro/enterprise subscription tiers.",
    "🚗 Delivery App": "On-demand food delivery: customers browse restaurants, order food, pay online, and track delivery on a live map. Drivers accept requests, navigate to restaurants, and deliver. Restaurants manage menus and orders via a web portal. We need real-time GPS, push notifications, dynamic pricing, and in-app support chat.",
    "🏥 Telemedicine": "Patients book video consultations with doctors, upload medical records securely, receive e-prescriptions, track medications, and book lab tests. We need HIPAA-compliant storage, encrypted video calling, insurance claim integration, and a doctor scheduling system.",
}


# ── ADK pipeline runner ───────────────────────────────────────────────────────
async def run_adk_pipeline(api_key: str, business_input: str) -> dict:
    os.environ["GOOGLE_API_KEY"] = api_key
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"

    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types as genai_types
    from agent import root_agent

    APP_NAME, USER_ID, SESSION_ID = "bizarch_app", "user", "session_001"
    session_service = InMemorySessionService()
    await session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)

    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    async for _ in runner.run_async(
        user_id=USER_ID,
        session_id=SESSION_ID,
        new_message=genai_types.Content(
            role="user",
            parts=[genai_types.Part(text=business_input)],
        ),
    ):
        pass  # consume all events; state is populated in session

    session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
    return dict(session.state) if session and session.state else {}


def run_pipeline_sync(api_key: str, business_input: str) -> dict:
    return asyncio.run(run_adk_pipeline(api_key, business_input))


# ── Parsers ───────────────────────────────────────────────────────────────────
def parse_requirements(raw: str) -> dict:
    fields = ["BUSINESS_GOAL","ACTORS","CORE_FLOWS","FUNCTIONAL_REQUIREMENTS","DATA_ENTITIES","INTEGRATIONS","CONSTRAINTS"]
    result = {}
    for i, field in enumerate(fields):
        nxt = fields[i+1] if i+1 < len(fields) else None
        pattern = (rf"{field}:\s*(.*?)(?={nxt}:|$)" if nxt else rf"{field}:\s*(.*?)$")
        m = re.search(pattern, raw, re.DOTALL | re.IGNORECASE)
        result[field] = m.group(1).strip() if m else ""
    return result


def parse_tech_specs(raw: str) -> dict:
    clean = re.sub(r"```json|```", "", raw).strip()
    s, e = clean.find("{"), clean.rfind("}") + 1
    return json.loads(clean[s:e] if s != -1 and e > s else clean)


def extract_drawio_xml(raw: str) -> str:
    """Strip any markdown fences and extract the mxGraphModel XML."""
    raw = re.sub(r"```xml|```drawio|```", "", raw).strip()
    # Find <mxGraphModel ... </mxGraphModel>
    m = re.search(r"(<mxGraphModel[\s\S]*?</mxGraphModel>)", raw, re.DOTALL)
    return m.group(1).strip() if m else raw.strip()


# ── Render helpers ────────────────────────────────────────────────────────────
def badges(items, cls):
    return "".join(f'<span class="badge {cls}">{i}</span>' for i in items)

def list_items(items):
    return "".join(f'<div class="li-item">{i}</div>' for i in items)

def render_requirements(reqs):
    labels = {"BUSINESS_GOAL":"🎯 Business Goal","ACTORS":"👥 Actors","CORE_FLOWS":"🔄 Core Flows",
              "FUNCTIONAL_REQUIREMENTS":"✅ Features","DATA_ENTITIES":"🗃️ Data Entities",
              "INTEGRATIONS":"🔌 Integrations","CONSTRAINTS":"⚠️ Constraints"}
    for k, label in labels.items():
        val = reqs.get(k, "").strip()
        if val:
            st.markdown(f'<div class="req-block"><div class="req-key">{label}</div><div class="req-val">{val}</div></div>', unsafe_allow_html=True)

def render_tech_specs(specs):
    m1,m2,m3,m4 = st.columns(4)
    m1.metric("System Type",  specs.get("system_type","—"))
    m2.metric("Complexity",   specs.get("estimated_complexity","—"))
    m3.metric("Scale",        specs.get("scale_tier","—"))
    m4.metric("Timeline",     specs.get("mvp_timeline","—"))
    st.markdown("")
    st.markdown(f'<div class="tcard"><div class="tcard-label">Summary</div><div>{specs.get("summary","")}</div></div>', unsafe_allow_html=True)

    layers = specs.get("layers", {})
    if layers:
        st.markdown('<div class="sec-title">System Layers</div>', unsafe_allow_html=True)
        layer_cols = st.columns(3)
        layer_items = list(layers.items())
        for i, (layer, items) in enumerate(layer_items):
            with layer_cols[i % 3]:
                color_map = {"client":"b-blue","gateway":"b-purple","services":"b-green","data":"b-amber","infrastructure":"b-teal","external":"b-red"}
                cls = color_map.get(layer, "b-blue")
                items_html = "".join(f'<div style="font-size:12px;color:#9997b0;padding:2px 0">{it}</div>' for it in (items or []))
                st.markdown(
                    f'<div class="tcard"><div class="tcard-label">{layer.title()}</div>{items_html}</div>',
                    unsafe_allow_html=True,
                )

    stack = specs.get("tech_stack", {})
    if stack:
        st.markdown('<div class="sec-title">Technology Stack</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            for label, key, cls in [("Frontend","frontend","b-blue"),("Backend","backend","b-green"),("Message Queue","message_queue","b-red")]:
                items = stack.get(key,[])
                if items:
                    st.markdown(f'<div class="tcard"><div class="tcard-label">{label}</div>{badges(items,cls)}</div>', unsafe_allow_html=True)
        with c2:
            for label, key, cls in [("Database","database","b-amber"),("Cache","cache","b-purple"),("Infrastructure","infrastructure","b-teal")]:
                items = stack.get(key,[])
                if items:
                    st.markdown(f'<div class="tcard"><div class="tcard-label">{label}</div>{badges(items,cls)}</div>', unsafe_allow_html=True)

    flows = specs.get("key_data_flows", [])
    if flows:
        st.markdown('<div class="sec-title">Key Data Flows</div>', unsafe_allow_html=True)
        st.markdown(list_items(flows), unsafe_allow_html=True)

    with st.expander("🔧 Raw JSON"):
        st.code(json.dumps(specs, indent=2), language="json")


# ── Pipeline status ───────────────────────────────────────────────────────────
STEPS = [
    ("RequirementsAnalystAgent", "📋 Analyzing business requirements"),
    ("TechSpecsAgent",           "⚙️  Generating technical specifications"),
    ("DrawioArchitectAgent",     "🎨 Designing Draw.io architecture diagram"),
]

def render_status(states):
    icons = {"idle":"○","active":"⏳","done":"✅","error":"❌"}
    html = ""
    for (_, label), state in zip(STEPS, states):
        html += (f'<div class="pipe-step pipe-{state}">'
                 f'<div class="dot dot-{state}"></div>'
                 f'{icons[state]} {label}</div>')
    return html


# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏗️ BizArch ADK + Draw.io")
    st.markdown("<small style='color:#6b6880'>3-agent ADK pipeline → Draw.io architecture image</small>", unsafe_allow_html=True)
    st.divider()

    api_key = st.text_input("Gemini API Key", type="password", placeholder="AIza...",
                             help="https://aistudio.google.com/app/apikey")

    st.divider()
    st.markdown("#### 📋 Examples")
    for label in EXAMPLES:
        if st.button(label, use_container_width=True, key=f"ex_{label}"):
            st.session_state["biz_input"] = EXAMPLES[label]
            st.rerun()

    st.divider()
    st.markdown("""
    <div style='font-size:11px;color:#4e4c63;line-height:1.9;font-family:monospace'>
    <b>ADK Pipeline</b><br>
    1. RequirementsAnalystAgent<br>
    2. TechSpecsAgent<br>
    3. DrawioArchitectAgent<br>
    ↓ SequentialAgent<br><br>
    <b>Image Export</b><br>
    1. draw.io Desktop CLI<br>
    2. drawio-batch (npm)<br>
    3. draw.io Export API<br>
    4. Python SVG renderer
    </div>
    """, unsafe_allow_html=True)


# ── Main ──────────────────────────────────────────────────────────────────────
st.markdown("# 🏗️ BizArch ADK + Draw.io")
st.markdown("Describe your business → **ADK pipeline** → professional **Draw.io architecture diagram** as an image")
st.divider()

business_input = st.text_area(
    "Business Description",
    value=st.session_state.get("biz_input", ""),
    height=150,
    placeholder="e.g. We run an on-demand food delivery platform. Customers browse restaurants, order food, pay online, and track delivery in real-time...",
    key="biz_input",
)

col_run, col_reset = st.columns([3, 1])
with col_run:
    run_btn = st.button("⚡ Run Pipeline → Generate Diagram", type="primary", use_container_width=True)
with col_reset:
    if st.button("🔄 Reset", use_container_width=True):
        for k in ["pipeline_result","biz_input"]:
            st.session_state.pop(k, None)
        st.rerun()

st.divider()

status_ph = st.empty()
status_ph.markdown(render_status(["idle","idle","idle"]), unsafe_allow_html=True)


# ── Run ───────────────────────────────────────────────────────────────────────
if run_btn:
    if not api_key:
        st.error("⚠️ Enter your Gemini API Key in the sidebar.")
        st.stop()
    if not business_input.strip():
        st.error("⚠️ Please describe your business.")
        st.stop()

    states = ["idle", "idle", "idle"]
    try:
        for i in range(3):
            states[i] = "active"
            status_ph.markdown(render_status(states), unsafe_allow_html=True)

        with st.spinner("🤖 Running 3-agent ADK pipeline..."):
            result = run_pipeline_sync(api_key, business_input)
            st.session_state["pipeline_result"] = result

        for i in range(3):
            states[i] = "done"
        status_ph.markdown(render_status(states), unsafe_allow_html=True)
        st.success("✅ Pipeline complete! Generating architecture image...")
        st.rerun()

    except Exception as e:
        states[0] = "error"
        status_ph.markdown(render_status(states), unsafe_allow_html=True)
        st.error(f"❌ Pipeline error: {e}")
        with st.expander("Debug"):
            import traceback; st.code(traceback.format_exc())


# ── Output ────────────────────────────────────────────────────────────────────
if "pipeline_result" in st.session_state:
    result = st.session_state["pipeline_result"]
    status_ph.markdown(render_status(["done","done","done"]), unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["🎨 Architecture Diagram", "⚙️ Tech Specs", "📋 Requirements"])

    # ── TAB 1: Draw.io Architecture Image ────────────────────────────────────
    with tab1:
        raw_xml = result.get("drawio_xml", "")
        if raw_xml:
            xml = extract_drawio_xml(raw_xml)

            st.markdown("#### Architecture Diagram")
            st.markdown(
                "Generated by **DrawioArchitectAgent** using native Draw.io XML · "
                "Following Ruban Siva's Draw.io + AI best practices"
            )

            # Save .drawio file
            output_dir = Path(tempfile.gettempdir()) / "bizarch_output"
            output_dir.mkdir(exist_ok=True)

            from drawio_exporter import drawio_xml_to_image, save_drawio_file
            drawio_path = save_drawio_file(xml, output_dir)

            # Convert to image
            with st.spinner("🖼️ Exporting diagram to image..."):
                try:
                    img_bytes, mime_type, method = drawio_xml_to_image(xml, output_dir)
                    export_success = True
                except Exception as ex:
                    export_success = False
                    export_error = str(ex)

            if export_success:
                st.markdown(
                    f'<div style="margin-bottom:12px">'
                    f'<span class="drawio-badge">draw.io</span> '
                    f'<span style="font-size:12px;color:#888;margin-left:8px">Exported via: {method}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

                if mime_type == "image/png":
                    st.image(img_bytes, use_container_width=True, caption="System Architecture")
                    # Download PNG
                    st.download_button(
                        "⬇️ Download PNG",
                        data=img_bytes,
                        file_name="architecture.png",
                        mime="image/png",
                    )
                else:
                    # SVG — display as HTML
                    svg_str = img_bytes.decode("utf-8")
                    st.markdown(
                        f'<div style="background:#f8f9fa;border-radius:12px;padding:16px;overflow:auto">'
                        f'{svg_str}</div>',
                        unsafe_allow_html=True,
                    )
                    st.download_button(
                        "⬇️ Download SVG",
                        data=img_bytes,
                        file_name="architecture.svg",
                        mime="image/svg+xml",
                    )
            else:
                st.warning(f"Image export encountered an issue: {export_error}")
                st.info("The Draw.io XML has been generated. Download it below to open in draw.io.")

            # Always offer .drawio download
            st.download_button(
                "⬇️ Download .drawio (editable)",
                data=drawio_path.read_bytes(),
                file_name="architecture.drawio",
                mime="application/xml",
                help="Open in draw.io desktop or diagrams.net to edit",
            )

            # Draw.io XML viewer
            with st.expander("🔍 View Draw.io XML source"):
                st.code(xml, language="xml")

            # Instructions for installing CLI
            with st.expander("💡 For highest-quality PNG export — install draw.io Desktop"):
                st.markdown("""
**Install draw.io Desktop CLI** for pixel-perfect PNG export:

```bash
# macOS
brew install --cask drawio

# Linux (Debian/Ubuntu)
wget https://github.com/jgraph/drawio-desktop/releases/latest/download/drawio-amd64.deb
sudo dpkg -i drawio-amd64.deb

# Windows
# Download from https://github.com/jgraph/drawio-desktop/releases
```

Then re-run the app — it will automatically detect and use the CLI.

**Or install cairosvg** for the Python SVG → PNG renderer:
```bash
pip install cairosvg
```

**Or open the .drawio file** directly at **https://app.diagrams.net** and export manually.
                """)
        else:
            st.info("No diagram XML found. Re-run the pipeline.")

    # ── TAB 2: Tech Specs ──────────────────────────────────────────────────
    with tab2:
        raw_tech = result.get("tech_specs", "")
        if raw_tech:
            st.markdown("#### Technical Specifications")
            st.caption("Produced by **TechSpecsAgent**")
            st.divider()
            try:
                render_tech_specs(parse_tech_specs(raw_tech))
            except Exception as e:
                st.warning(f"Could not parse JSON: {e}")
                st.code(raw_tech, language="json")
        else:
            st.info("No tech specs found.")

    # ── TAB 3: Requirements ────────────────────────────────────────────────
    with tab3:
        raw_req = result.get("requirements", "")
        if raw_req:
            st.markdown("#### Requirements Analysis")
            st.caption("Produced by **RequirementsAnalystAgent**")
            st.divider()
            render_requirements(parse_requirements(raw_req))
            with st.expander("Raw output"):
                st.code(raw_req, language="text")
        else:
            st.info("No requirements found.")

else:
    # Welcome
    st.markdown("")
    c1, c2, c3 = st.columns(3)
    for col, icon, title, desc in [
        (c1, "📋", "Requirements Analyst Agent", "Extracts actors, flows, data entities, integrations and constraints"),
        (c2, "⚙️", "Tech Specs Agent",           "Designs full system layers, tech stack, data flows and NFRs"),
        (c3, "🎨", "Draw.io Architect Agent",    "Generates native Draw.io XML with animated edges, proper shapes & layers"),
    ]:
        col.markdown(
            f'<div style="background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.07);'
            f'border-radius:12px;padding:20px;text-align:center;height:170px;">'
            f'<div style="font-size:28px;margin-bottom:12px">{icon}</div>'
            f'<div style="font-weight:700;font-size:13px;margin-bottom:8px">{title}</div>'
            f'<div style="font-size:12px;color:#6b6880;line-height:1.5">{desc}</div></div>',
            unsafe_allow_html=True,
        )
    st.markdown("")
    st.markdown(
        '<div style="text-align:center;font-size:13px;color:#4e4c63;padding:12px">'
        'Inspired by <a href="https://medium.com/google-cloud/automating-mastering-infrastructure-diagrams-with-draw-io-mcp-and-antigravity-2839b78df143" '
        'style="color:#7c6af7">Ruban Siva\'s article</a> on automating Draw.io with AI</div>',
        unsafe_allow_html=True,
    )
