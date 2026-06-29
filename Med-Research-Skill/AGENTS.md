# Agents & AI Shell Integration Guide (v11.0 Master)

## 🤖 Overview
This document outlines how different AI Agents and CLI Shells can extend and utilize the **Med-Research Skill** with zero-hallucination guarantees.

## 1. Extension Logic & System Anchors
Med-Research is a **Constitutional Skill** enforced via two main specification files:
- **GEMINI.md** (Project Constitution): Defines the highest decision weighting hierarchy.
- **med-research/SKILL.md**: Defines the execution rules, 9-column matrix structure, and validation protocol.

## 2. Agentic Workflow (GARP v11.0)
When an agent is tasked with research, it must behave as a **Senior Clinical Research Lead**:

1. **Step 1: Environment Check**: Verify if target directories exist (`Med Deep Research/reports/` and `Med Deep Research/papers/`).
2. **Step 2: Deep Mining**: Query PubMed, IEEE, or Google Scholar via local APIs or MCP.
3. **Step 3: Verification (1:1 Integrity)**: 
   - Parse DOI and resolve using `scripts/verify_integrity.py`.
   - Ensure DOI matches paper title exactly. If mismatch occurs, flag it as `REF recovery pending`.
4. **Step 4: Local PDF Physical Validation**:
   - Verify if PDF exists on disk.
   - If missing, flag as `[PENDING]` or `[Web Link]`, do not fabricate path.
5. **Step 5: Matrix Rendering**: Output the standard 9-column matrix.

## 3. Toolchain Reference
The skill contains the following automated modules:
- **Verification Engine**: `med-research/scripts/verify_integrity.py`
  - Validates markdown tables, checks URL/DOI consistency, and updates PDF local file links.
- **Knowledge Aggregator**: `med-research/scripts/knowledge_aggregator.py`
  - Local RAG builder to scan physical papers on disk and extract equations/parameters.

## 4. IP & Ethics Mandate for Agents
- **No False Claims**: Agents must not claim authorship of the synthesized clinical data.
- **Traceability First**: Every technical claim must have a `Trace-Note` pointing to a specific Section/Figure in the original paper.

## 5. v11.0 品質門控觸發條件
- 任何包含「深度研究」「literature review」「文獻」「鉛衣」「DICOM」「CTG」「medical AI」的任務，Agent 必須強制套用 `med-research/SKILL.md` v11.0 協議。
- 禁止在未完成 JCR 驗證前輸出矩陣。
- 每輪輸出前，Agent 必須回溯 `PROGRESS.md` 確認版本連續性。
