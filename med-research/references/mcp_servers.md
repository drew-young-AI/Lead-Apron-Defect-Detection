# Medical MCP Servers (Agentic Integration)

To expand your research capabilities, integrate these open-source MCP servers into your Agent (e.g., Claude Desktop or Cline).

## 1. JamesANZ/medical-mcp (All-in-One)
- **Repo**: [JamesANZ/medical-mcp](https://github.com/JamesANZ/medical-mcp)
- **Description**: Access PubMed, ClinicalTrials.gov, FDA, WHO, and Google Scholar.
- **Config (Claude Desktop)**:
```json
"medical-mcp": {
  "command": "npx",
  "args": ["-y", "@jamesanz/medical-mcp"]
}
```

## 2. cyanheads/pubmed-mcp-server (Deep Mining)
- **Repo**: [cyanheads/pubmed-mcp-server](https://github.com/cyanheads/pubmed-mcp-server)
- **Description**: Specialized in full-text fetching (PMC) and MeSH term filtering.
- **Config**:
```json
"pubmed-mcp": {
  "command": "npx",
  "args": ["-y", "@cyanheads/pubmed-mcp-server"]
}
```

## 3. JackKuo666/ClinicalTrials-MCP-Server (Trials)
- **Repo**: [JackKuo666/ClinicalTrials-MCP-Server](https://github.com/JackKuo666/ClinicalTrials-MCP-Server)
- **Description**: Fetch active clinical trials and export to CSV.

## 4. Local Python Bridge (Built-in)
- **Location**: `Med-Research-Skill/scripts/pubmed_client.py`
- **Capability**: Direct PubMed E-Utils integration without external node dependencies.
