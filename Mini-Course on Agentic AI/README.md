# 🤖 Mini-Course on Agentic AI

Welcome to the **Mini-Course on Agentic AI** repository. This course provides a comprehensive curriculum and hands-on practical project designed to teach the fundamentals, design patterns, and implementation strategies of autonomous AI Agents using modern LLM APIs, function calling, and tool use.

---

## 📁 Repository Overview & Contents

This folder contains all course curriculum documents, lecture presentation materials, assessment rubrics, and a full-fledged hands-on code project:

```text
Mini-Course on Agentic AI/
├── Assessment Plan.pdf          # Detailed course assessment methodology & grading rubrics
├── Curriculum Plan.pdf          # Step-by-step course syllabus, modules, and learning objectives
├── Building AI Agents.pptx     # Lecture presentation slides covering Agentic AI concepts
├── smart-expense-agent/         # Capstone Python project demonstrating function-calling AI agent
│   ├── main.py                  # Agent loop, system prompt, and Groq API tool execution
│   ├── tools.py                 # Core business logic functions (add, list, total, filter)
│   ├── expenses.json            # Local JSON data store for expense records
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example             # Template for required environment variables
│   └── README.md                # Project-specific README
└── .gitignore                   # Git ignore rule configuration for the folder
```

---

## 📚 Course Curriculum Summary

### 1. **Curriculum Plan (`Curriculum Plan.pdf`)**
The course is structured to take learners from core conceptual foundations to building production-ready AI agents. Key learning modules include:
- **Module 1: Introduction to Agentic AI** – Understanding LLMs vs. AI Agents, the Agent Loop (Perception $\rightarrow$ Reasoning $\rightarrow$ Action $\rightarrow$ Observation), and single-agent vs. multi-agent paradigms.
- **Module 2: Tool Use & Function Calling** – How LLMs output structured tool calls (JSON schemas), argument parsing, error handling, and runtime execution.
- **Module 3: Memory, State, and Persistence** – Short-term vs. long-term memory, context window management, and local/database persistence.
- **Module 4: Guardrails & Prompt Engineering** – Designing robust system prompts, input validation, and preventing hallucinated results.
- **Module 5: Capstone Implementation** – Building, testing, and debugging an agentic application in Python.

### 2. **Presentation Slides (`Building AI Agents.pptx`)**
Comprehensive slide deck covering:
- Evolution of AI: Static prompts vs. Dynamic Tool-using Agents.
- The ReAct (Reason + Act) loop pattern.
- Schema definitions for Function Calling.
- Real-world agent system architectures and design considerations.

### 3. **Assessment Plan (`Assessment Plan.pdf`)**
Defines evaluation standards for students/learners:
- **Practical Assignments**: Tool design, JSON schema accuracy, system prompt validation.
- **Capstone Project Evaluation**: Functionality, error handling, schema adherence, code cleanliness, and user interaction design.

---

## 💻 Capstone Hands-On Project: Smart Expense Assistant (`smart-expense-agent`)

The `smart-expense-agent` is an interactive CLI application demonstrating function calling and autonomous agent loops using Python and the **Groq API** (`openai/gpt-oss-120b` or compatible models).

### 🌟 Features
- 🗣️ **Natural Language Expense Tracking**: Add, view, summarize, or query expenses using plain English queries.
- 🛠️ **Autonomous Tool Selection**: The agent dynamically decides which backend tool function to invoke based on user intent.
- 📊 **Local Data Persistence**: Saves and retrieves records from `expenses.json`.
- 🛡️ **Built-in Guardrails**: Input validation prevents zero/negative amounts, oversized transactions, and unconfirmed operations.

---

### 🔧 Tools Provided to the Agent

The agent has access to four core Python functions defined in `tools.py`:

| Function Name | Description | Parameters |
| :--- | :--- | :--- |
| `add_expense` | Records a new expense in INR | `amount` (float), `category` (string) |
| `list_expenses` | Retrieves all recorded expense entries | None |
| `get_total_expenses` | Calculates the total sum of all saved expenses | None |
| `get_expenses_by_category` | Calculates and lists expenses for a specified category | `category` (string) |

---

### 🚀 Getting Started with `smart-expense-agent`

#### 1. Prerequisites
- Python 3.10 or higher installed on your system.
- A valid **Groq API Key** (obtainable from [Groq Console](https://console.groq.com/)).

#### 2. Setup Environment

Navigate to the project directory:
```bash
cd "Mini-Course on Agentic AI/smart-expense-agent"
```

Create and activate a Python virtual environment:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

#### 3. Configure Environment Variables
Copy the `.env.example` file to `.env`:
```bash
cp .env.example .env
```

Edit `.env` and set your API key and preferred model:
```env
GROQ_API_KEY=your_actual_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-120b
```

#### 4. Run the Agent Application
Launch the assistant CLI:
```bash
python main.py
```

---

### 💬 Usage Examples

When running `main.py`, interact with the agent naturally:

```text
==================================================
       SMART EXPENSE ASSISTANT
==================================================
Type 'exit' to close the application.

You: Spent 250 Rupees on lunch today

[Agent selected tool: add_expense]

Assistant: I have successfully recorded your expense of ₹250.0 under the category "lunch".

You: How much have I spent in total?

[Agent selected tool: get_total_expenses]

Assistant: You have spent a total of ₹250.0 across 1 expense record.

You: exit
Assistant: Goodbye!
```

---

## 🛠️ Key Agent Design Patterns Demonstrated

1. **ReAct Loop (Reasoning + Acting)**: The agent runs in an iterative loop (`max_iterations = 5`), passing tool output back into the context window until a final answer is generated.
2. **Schema-Driven Function Calling**: Tools are declared using OpenAI-compatible JSON Function Schemas.
3. **Structured System Prompt**: Imposes strict boundaries (e.g., currency default in INR, no fabricated totals, requesting missing parameters).
4. **Resilient Error Execution**: Catches invalid arguments and unknown functions safely without crashing the execution loop.

---

## 📄 License & Attribution

Created as part of the **Agentic AI Course Curriculum**. All resources are intended for educational and instructional purposes.
