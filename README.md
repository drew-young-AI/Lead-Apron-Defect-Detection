# Med-Research Skill (v5.3) 🚀
### High-Fidelity Medical AI Research & Consensus Engine

## 🌟 Project Overview
**Med-Research Skill** is a specialized extension for AI agents (specifically Gemini CLI) designed to perform high-rigor, autonomous medical literature reviews. It bridges the gap between raw data mining and expert-level clinical decision intelligence.

Born in a clinical environment, this skill ensures that every research step adheres to the highest academic standards (JCR Q1/Q2) and follows a systematic protocol for evidence triangulation.

## 🛠️ Key Features
- **Multi-Source Discovery**: Integrated Python clients for **PubMed (NCBI E-Utils)** and **Google Scholar** to ensure both clinical precision and academic breadth.
- **AI-Consensus Synthesis**: Simulates **Consensus.ai** and **Elicit.org** logic to categorize scientific claims (Support/Oppose/Neutral) and extract critical data variables (N, Design, Outcome).
- **Academic Rigor (JCR Verified)**: Mandatory verification of Journal Impact Factors (IF) and Quartiles. No more "gray literature" bias.
- **Physician-Grade Reporting**: Generates "Decision Intelligence" reports featuring **Dual-Term Analysis** (Engineering Specs + Clinical Value) and **Clinical Decision Support (CDSS)** pathways.
- **Full-Title Traceability**: Enforces 1:1 mapping between report citations and local `/papers` archives with standardized naming conventions.
- **Agentic Workflow**: Evaluates every technical paper for its potential to be implemented as an **Autonomous AI Agent** (e.g., Obstetric Navigation Agents).

## 📂 Directory Structure
```text
med-research/
├── SKILL.md            # Core instruction set for the AI Agent
├── requirements.txt    # Python dependencies (scholarly, playwright, etc.)
├── scripts/
│   ├── pubmed_client.py   # API bridge for PubMed/PMC
│   └── scholar_client.py  # Automated Google Scholar scaper
├── references/
│   ├── medical_journals.md   # JCR Q1/Q2 target list
│   ├── mcp_servers.md        # Integration guide for external medical servers
│   └── ai_research_workflows.md # Consensus & Elicit logic templates
└── assets/             # Report templates and icons
```

## 🚀 Getting Started

### Prerequisites
- [Gemini CLI](https://github.com/google/gemini-cli) installed.
- Python 3.10+ with `pip`.

### Installation
1. **Clone the repo**:
   ```bash
   git clone https://github.com/your-repo/med-research-skill.git
   ```
2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. **Package & Install Skill**:
   ```bash
   # Use Gemini CLI builtin packaging tool
   gemini skills install ./med-research.skill --scope user
   ```

## 📋 Research Protocol (GARP v5.2)
All research sessions follow the **General Autonomous Research Protocol**:
1. **Initialize**: Check system state and define the clinical problem.
2. **Mine**: Dual-track search on PubMed & Scholar.
3. **Scrutinize**: Verify metrics and distinguish performance from validity.
4. **Synthesize**: Generate Executive Matrix + Technical Deep Dives.
5. **Reflect**: Apply the 'Recursive Mirror' to find 'Blue Ocean' publication niches.

## 📄 License
MIT License. Created for medical researchers and AI developers.
