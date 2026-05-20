# AI-Driven Research Workflows (Consensus & Elicit Logic)

For high-level medical synthesis, simulate the following logic patterns within the Med Deep Research project.

## 1. Consensus-Driven Claim Extraction (Consensus.ai Logic)
- **Goal**: Find a "Yes/No" or "Quantitative" answer to a research question based on multiple papers.
- **Workflow**:
    1. Extract the "Conclusion" or "Result" sentence from each paper in the matrix.
    2. Group papers by their findings (e.g., "Supports AI", "Opposes AI", "Inconclusive").
    3. Calculate the **Consensus Score** based on JCR IF and sample sizes.

## 2. Evidence-Based Task Automation (Elicit.org Logic)
- **Goal**: Automatically fill a comparative table for specific parameters.
- **Workflow**:
    1. Define specific extraction targets (e.g., "Population", "Sensitivity", "Loss Function").
    2. Perform targeted `web_fetch` on the "Materials & Methods" sections.
    3. Flag discrepancies between papers for human decision-making.

## 3. Medical Professional Skills (Clinical Decision Support)
- **Guideline Alignment**: Always check findings against **WHO**, **ACOG** (for FHR), and **ICRP** (for Radiation) guidelines.
- **ICD-11 / MeSH Integration**: Tag research results with standard medical codes to ensure hospital system compatibility.
- **Differential Diagnosis (DDx) Assistance**: When analyzing FHR, use AI to propose DDx for deceleration patterns (e.g., cord compression vs. placental insufficiency).
