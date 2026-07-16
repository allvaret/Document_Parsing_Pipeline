# Document Parsing Pipeline


![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)  ![Static Badge](https://img.shields.io/badge/LICENSE-MIT-GREEN?style=for-the-badge) ![Static Badge](https://img.shields.io/badge/Stable%20V1-green?style=for-the-badge)

PDF → Structured Sections → JSON → Executive Summary

A document parsing pipeline that extracts the structural hierarchy of financial PDF reports, identifies semantic sections through layout heuristics and NLP scoring, and produces structured data for high-quality LLM summarization.  

## Overview

Financial reports are among the most valuable sources of information for investors, analysts, and businesses. However, they are often lengthy, highly structured documents that require significant time to read, interpret, and analyze.

Although Large Language Models (LLMs) can assist in summarizing these reports, directly processing raw PDF text frequently leads to the loss of structural context. Headings, tables, page layouts, and document hierarchy are essential for understanding the information correctly, yet they are often discarded during text extraction.

This project addresses that challenge by introducing a document parsing pipeline that reconstructs the logical structure of financial reports before any interaction with an LLM. Using layout heuristics, typographic analysis, and NLP-based title scoring, the parser identifies document sections and generates a structured JSON representation of the report.

Instead of asking the LLM to understand an unstructured document, the parser provides a clean, hierarchical representation, allowing the language model to focus solely on generating accurate and context-aware executive summaries. The result is a pipeline that reduces information loss while helping transform lengthy financial documents into insights that can be consumed more efficiently.  

## Architecture

The parser separates document understanding from language generation.

Instead of relying on an LLM to infer the structure of a raw PDF, the pipeline first reconstructs the document hierarchy and organizes its content into structured sections. Only then is the resulting JSON passed to the language model for summarization.

## Architecture

The parser separates **document understanding** from **language generation**. Rather than relying on an LLM to infer document structure, the pipeline first reconstructs the logical hierarchy of the PDF and produces a structured JSON representation. Only then is the content passed to the language model for summarization.

```mermaid
flowchart TD

    %% ---------- INPUT ----------
    A["📄 Financial PDF Report"]

    %% ---------- PARSING ----------  
    subgraph Parsing  
        B["Extract Text<br/>(PyMuPDF)"]
        C["Clean Document<br/>Remove headers, footers and noise"]
        D["Group Words into Lines"]
    end

    %% ---------- TITLE DETECTION ----------
    subgraph Document Understanding
        E["Detect Title Candidates"]
        F["Layout Heuristics"]
        G["Semantic NLP Scoring"]
        H["Select Valid Titles"]
        I["Detect Content Regions"]
        J["Build Document Sections"]
    end

    %% ---------- OUTPUT ----------
    K["Structured JSON"]

    %% ---------- LLM ----------
    subgraph Language Generation
        L["Local LLM (Ollama)"]
        M["Executive Summary"]
    end

    A --> B
    B --> C
    C --> D

    D --> E

    E --> F
    E --> G

    F --> H
    G --> H

    H --> I
    I --> J
    J --> K

    K --> L
    L --> M
```

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/allvaret/Document_Parsing_Pipeline.git
cd Document_Parsing_Pipeline
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Download the spaCy language model

```bash
python -m spacy download pt_core_news_md
```

### 5. Install Ollama

Download and install Ollama from the official website:

[https://ollama.com
](https://ollama.com/search)  
### 6. Download a language model

The project uses **Qwen2.5:3B** by default.

```bash
ollama pull qwen2.5:3b
```

You may use another compatible model by changing the model name in:

```text
src/LLM/client.py
```

## Quick Start

Place a financial PDF report inside the `assets/` directory.

By default, the project expects an input file defined in `src/main.py`:

```python
INPUT_FILE = "assets/example_report.pdf"
```

Run the application:

```bash
python src/main.py
```

The pipeline will:

1. Extract the document text.
2. Reconstruct its logical structure.
3. Generate a structured JSON representation.
4. Produce an executive summary using a local LLM.

Generated files are saved alongside the original document:

```text
example_report.pdf
example_report_sections.json
example_report_summary.json
```
## Project Structure

```text
financial-report-parsing-pipeline/
│
├── assets/                # Sample PDF reports and results
├── src/
│   ├── extractor/         # Parsing pipeline and section reconstruction
│   ├── llm/               # Local LLM client and prompt templates
│   ├── utils/             # Shared utilities and helper functions
│   └── main.py            # Application entry point
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

The project is organized into three main components:

* **Extractor** — Responsible for document understanding, including text extraction, title detection, region detection, and section building.
* **LLM** — Handles communication with the local language model and prompt management.
* **Utils** — Provides reusable utilities shared across the parsing pipeline.

## Example Output

### Input

[assets/Earnings Release 3T25.pdf](assets/Earnings%20Release%203T25.pdf)


### Generated Section

#### Table example: DRE Gerencial Trimestral 
* **Confiança da Extração:** Alta (`high`)

| R$ milhões | 3T25 | 2T25 | 3T24 | 3T25 x 2T25 | 3T25 x 3T24 |
| --- | --- | --- | --- | --- | --- |
| **Receita Total** | 133,3 | 139,3 | 157,7 | -4,3% | -15,5% |
| Receita com Clientes | 100,0 | 101,6 | 125,8 | -1,6% | -20,5% |
| Investment Banking (fees) + CM (fees) | 67,2 | 73,9 | 101,4 | -9,1% | -33,7% |
| Treasury Sales & Structuring (capital) | 28,7 | 23,9 | 21,3 | 20,3% | 34,9% |
| Gestão de Patrimônio (fees) | 4,0 | 3,8 | 3,1 | 5,3% | 29,9% |
| Remuneração do Capital (capital) | 33,3 | 37,7 | 31,9 | -11,5% | 4,3% |
| **Despesas** | (68,9) | (75,4) | (92,3) | -8,6% | -25,3% |
| Pessoal | (26,2) | (34,7) | (32,1) | -24,5% | -18,1% |
| Administrativas | (31,4) | (20,0) | (43,9) | 56,8% | -28,4% |
| Impostos sobre a receita | (10,2) | (10,9) | (14,7) | -5,9% | -30,6% |
| Outras | (1,1) | (9,8) | (1,7) | -89,1% | -35,5% |
| **Resultado Operacional** | 64,4 | 63,9 | 65,4 | 0,8% | -1,6% |
| IR & CSLL | (22,1) | (18,7) | (15,3) | 18,6% | 44,7% |
| **Lucro Líquido** | 42,2 | 45,2 | 50,1 | -6,6% | -15,8% |

<details>
<summary> Visualizar JSON de Origem</summary>

```json
{
  "title": "DRE Gerencial Trimestral",
  "page": 9,
  "confidence": "high",
  "content": [
    {
      "type": "table",
      "confidence": "high",
      "markdown": "| R$ milhões | 3T25 | 2T25 | 3T24 | 3T25 x 2T25 | 3T25 x 3T24 |\n| --- | --- | --- | --- | --- | --- |\n| Receita Total | 133,3 | 139,3 | 157,7 | -4,3% | -15,5% |\n| Receita com Clientes | 100,0 | 101,6 | 125,8 | -1,6% | -20,5% |\n| Investment Banking (fees) + CM (fees) | 67,2 | 73,9 | 101,4 | -9,1% | -33,7% |\n| Treasury Sales & Structuring (capital) | 28,7 | 23,9 | 21,3 | 20,3% | 34,9% |\n| Gestão de Patrimônio (fees) | 4,0 | 3,8 | 3,1 | 5,3% | 29,9% |\n| Remuneração do Capital (capital) | 33,3 | 37,7 | 31,9 | -11,5% | 4,3% |\n| Despesas | (68,9) | (75,4) | (92,3) | -8,6% | -25,3% |\n| Pessoal | (26,2) | (34,7) | (32,1) | -24,5% | -18,1% |\n| Administrativas | (31,4) | (20,0) | (43,9) | 56,8% | -28,4% |\n| Impostos sobre a receita | (10,2) | (10,9) | (14,7) | -5,9% | -30,6% |\n| Outras | (1,1) | (9,8) | (1,7) | -89,1% | -35,5% |\n| Resultado Operacional | 64,4 | 63,9 | 65,4 | 0,8% | -1,6% |\n| IR & CSLL | (22,1) | (18,7) | (15,3) | 18,6% | 44,7% |\n| Lucro Líquido | 42,2 | 45,2 | 50,1 | -6,6% | -15,8% |"
    }
  ]
}
```
</details>
    
### Executive Summary

```text
#### Período Principal: 9M25 vs 9M24

**Resultado do Período:** O resultado financeiro da empresa mostrou uma receita total de R$ 400,1 milhões (-8,5% em relação ao 9M24), lucro líquido de R$ 130,5 milhões (-13,9% em relação ao 9M24) e margem líquida de 32,6% (-2,0 pontos percentuais ou p.p. em relação ao 9M24). A receita com clientes teve uma queda significativa de -10,1%, enquanto a margem líquida apresentou um leve aumento de -2,0 p.p.

**Pontos de Atenção:** A principal preocupação é a redução da atividade de M&A no período, que afetou negativamente as receitas e lucros. Além disso, o crescimento do volume de emissões de renda fixa no mercado de capitais foi de 11%, apesar da queda na receita com clientes.

**Destaque Positivo:** A evolução positiva do índice de eficiência (45,8% vs. 47,7%) e o aumento do índice de remuneração (23,8% vs. 24,9%) indicam uma melhoria na gestão operacional.

**Contexto de Mercado:** O cenário econômico mostrou um crescimento moderado no mercado de capitais, com volume de emissões aumentando em 11%, embora a taxa Selic tenha diminuído significativamente. No entanto, o mercado de capitais ainda enfrenta desafios relacionados à volatilidade e ao aumento da incerteza macroeconômica.

---

Este resumo sintetiza os principais pontos do relatório financeiro, destacando as variações relevantes em receita total, lucro líquido e margem, assim como os riscos e tendências preocupantes no mercado de capitais.

```

## Technical Challenges

| Challenge                         | Solution                                                                                                           |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Recovering document structure** | Combined layout heuristics and typographic analysis to reconstruct the logical hierarchy of PDF reports.           |
| **Reliable title detection**      | Introduced a hybrid scoring approach that combines layout-based heuristics with NLP semantic scoring.              |
| **Repeated section titles**       | Implemented structural deduplication to remove recurring headers while preserving legitimate section titles.       |
| **Mixed document content**        | Distinguished narrative text from tabular regions before section reconstruction.                                   |
| **LLM context quality**           | Generated a structured JSON representation instead of sending raw PDF text, reducing noise and preserving context. |


## Roadmap

The current release focuses on building a robust document parsing pipeline capable of reconstructing the logical structure of financial reports before LLM summarization.

Future improvements include:

### Version 1.x

* Command-line interface (CLI)
* Improved logging and configuration
* Additional prompt templates
* Performance optimizations

### Version 2

* OCR support for scanned PDFs
* Enhanced table extraction
* Improved multi-column document parsing
* More robust section reconstruction

### Version 3

* Structured financial fact extraction
* Relevance ranking pipeline
* Knowledge-oriented JSON generation
* Multi-document analysis

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
