---
name: med-research
description: High-fidelity medical research and AI consensus engine. Standardized for 100% traceability and peer-review preparation.
---

# Medical Research Skill v6.0 (Final)

## Core Capabilities
1. **Multi-Source Mining**: Simultaneously queries PubMed (clinical precision) and Google Scholar (academic breadth) using `pubmed_client.py` and `scholar_client.py`.
2. **AI Consensus Engine**: Replicates Consensus.ai and Elicit.org logic to categorize claims (Supports/Opposes) and extract rigorous data definitions (N, Design, Outcome).
3. **Smart Traceability**: Merged 'Reference Source (Access Type)' columns for one-click access to local/remote assets.
4. **Academic Rigor (JCR)**: Mandatory verification of Journal Impact Factors (IF) and Quartiles (Q1-Q4).

## Environment Setup
This skill requires Python 3.10+ and the following dependencies:
1. Navigate to the skill's root directory.
2. Run: `pip install -r requirements.txt`
3. Ensure Playwright is installed: `playwright install chromium`

## Reporting Standard
- **Standard Matrix**: 9-column format with full-title enforcement.
- **Relative Pathing**: All local links use `../papers/` for directory portability.
- **Technical Excerpts**: Extensive architectural deep dives below the matrix.

## Standard Research Loop (GARP v6.0)
1. **Initialize**: Check SNAPSHOT.json and set topic in PROGRESS.md.
2. **Mine**: Execute multi-source mining via scripts. Mandatory: 10+ high-impact candidates.
3. **Synthesize**: Generate Executive Matrix with JCR Metrics and Trace-Notes.
4. **Reflect**: Apply 'Recursive Mirror' to evolve research questions towards 'Blue Ocean' niches.
5. **Archive**: Download/Archive full-text (Level 1: PDF, Level 2: HTML, Level 3: Summary).
