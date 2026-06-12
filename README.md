# ⚕️ MeshMed - Healthcare Coordination Intelligence

![MeshMed Architecture](https://img.shields.io/badge/AgentOS-Day_04-blue)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![HIPAA Aligned](https://img.shields.io/badge/compliance-HIPAA%20%7C%20DISHA-brightgreen)

**MeshMed** is the healthcare coordination intelligence module for AgentOS. 

*The core insight: Healthcare coordination failure is an information sequencing problem.* 
The solution is not a universal health record—it is an autonomous agent that sits at every handoff point and ensures the right information arrives *before* the patient does.

## 🛡️ Critical Safety Constraints

MeshMed is built with uncompromising clinical guardrails:
1. **Never Diagnoses:** MeshMed extracts and surfaces information; it never creates new clinical conclusions.
2. **Never Alters Treatment:** It never recommends stopping or starting medications.
3. **Always Consult a Doctor:** Every interaction alert and lab trend analysis strictly ends with: *"Please discuss this with your prescribing doctor."*
4. **PHI Isolation:** Protected Health Information (PHI) is encrypted at rest using per-patient symmetric Fernet keys. PHI never enters the Vector DB (ChromaDB); only anonymous UUIDs are embedded.

## ✨ Core Capabilities

- 📄 **Medical Document Parsing**: Extracts structured data from chaotic Indian handwritten prescriptions, lab reports, and discharge summaries using OCR and Claude Opus.
- 💊 **Drug Interaction Detection**: An $O(N^2)$ combinatorial safety checker running across active medications, translating technical OpenFDA mechanisms into 8th-grade plain language alerts.
- 🤝 **Handoff Packet Generation**: Before appointments, MeshMed generates a filtered, specialty-aware `ProviderBrief` (PDF) for the doctor, and a 10-bullet `PatientBrief` checklist for the patient via WhatsApp.
- 🏛️ **ABHA & IRDAI Integration**: Connects with India's Ayushman Bharat Health Account (ABHA) via FHIR R4 parsers, and automatically compiles medical evidence into IRDAI-compliant Insurance Claim packages.
- 💬 **WhatsApp Multi-Turn UI**: A complete Redis-backed conversational interface designed for 2G-friendly WhatsApp interactions, supporting image uploads and voice notes (via VaakShastra).

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- PostgreSQL
- Redis
- ChromaDB

### Installation

1. **Clone and setup virtual environment:**
   ```bash
   git clone <repository_url>
   cd Day04_MeshMed
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
   *CRITICAL: You must generate and set a valid `PHI_ENCRYPTION_KEY` (32-byte url-safe base64 string) in your `.env` file before running the application.*

4. **Run the API Server:**
   ```bash
   uvicorn meshmed.server.api:app --reload --port 8003
   ```

## 🏗️ Architecture

MeshMed is deeply integrated into the AgentOS ecosystem:
- **VaakShastra (Day 01)**: MeshMed routes WhatsApp audio notes to VaakShastra for transcription and synthesizes voice reminders for elderly patients.
- **GhostCFO (Day 02)**: Hospital bills and pharmacy receipts are intercepted by MeshMed and synced to the financial tracking layer.
- **RiteOfWay (Day 06)**: If an insurance claim compiled by MeshMed is rejected, the complete evidence package is automatically forwarded to the legal agent for grievance filing.
- **SoulMap (Day 22)**: MeshMed shares non-PHI contextual flags (e.g., "chronic condition detected") to trigger emotional support workflows.

## 🧪 Evaluation

MeshMed includes a rigorous, zero-tolerance evaluation harness covering 40 synthetic test cases across Document Parsing, Drug Interactions, Handoff Hallucinations, and Safety Guardrails.

```bash
# Run the evaluation harness
python -m meshmed.eval.run
```

## 📜 License

Internal AgentOS Module. All rights reserved.
