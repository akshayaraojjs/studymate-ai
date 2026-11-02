import os
import json

from groq import Groq
from dotenv import load_dotenv

from tools import (
    add_expense,
    list_expenses,
    get_total_expenses,
    get_expenses_by_category
)

load_dotenv()

api_key = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL")

if not api_key:
    raise ValueError("GROQ_API_KEY is missing from .env")

if not MODEL:
    raise ValueError("GROQ_MODEL is missing from .env")

client = Groq(api_key=api_key)

tools = [
    {
        "type": "function",
        "function": {
            "name": "add_expense",
            "description": "Add a new expense.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {
                        "type": "number",
                        "description": "Expense amount in INR."
                    },
                    "category": {
                        "type": "string",
                        "description": "Expense category."
                    }
                },
                "required": ["amount", "category"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_expenses",
            "description": "Retrieve all saved expenses.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_total_expenses",
            "description": "Calculate the total of all saved expenses.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_expenses_by_category",
            "description": "Calculate expenses for a specified category.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {
                        "type": "string",
                        "description": "Expense category to filter."
                    }
                },
                "required": ["category"]
            }
        }
    }
]

available_functions = {
    "add_expense": add_expense,
    "list_expenses": list_expenses,
    "get_total_expenses": get_total_expenses,
    "get_expenses_by_category": get_expenses_by_category
}

def execute_tool_call(tool_call):
    function_name = tool_call.function.name

    if function_name not in available_functions:
        return {
            "success": False,
            "error": "Unknown tool requested."
        }

    try:
        arguments = json.loads(tool_call.function.arguments)

        function = available_functions[function_name]

        result = function(**arguments)

        return result

    except (json.JSONDecodeError, TypeError, ValueError) as error:
        return {
            "success": False,
            "error": str(error)
        }

    except Exception:
        return {
            "success": False,
            "error": "The requested operation could not be completed."
        }

SYSTEM_PROMPT = """
You are a Smart Expense Assistant.

Your job is to help users manage their daily expenses.

Rules:
1. Use add_expense when the user wants to record an expense.
2. Use list_expenses when the user asks to see all expenses.
3. Use get_total_expenses when the user asks for total spending.
4. Use get_expenses_by_category when the user asks about a category.
5. Never invent expense records or totals.
6. Use tool results when answering questions about saved expenses.
7. If a required amount or category is missing, ask the user.
8. Currency is Indian Rupees (INR).
9. Do not claim an operation succeeded unless the tool result confirms it.
"""


def run_agent(user_input):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": user_input
        }
    ]

    max_iterations = 5

    for iteration in range(max_iterations):

        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2
        )

        assistant_message = response.choices[0].message

        # Add the model response to conversation history
        messages.append(assistant_message)

        # Check whether the model requested any tools
        tool_calls = assistant_message.tool_calls

        # If there are no tool calls, the model has produced its final answer
        if not tool_calls:
            return assistant_message.content or "I could not generate a response."

        # Execute every requested tool
        for tool_call in tool_calls:

            print(
                f"\n[Agent selected tool: "
                f"{tool_call.function.name}]"
            )

            result = execute_tool_call(tool_call)

            # Send the tool result back to the model
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })

    return "The agent reached its maximum number of steps. Please try again."

def main():

    print("=" * 50)
    print("       SMART EXPENSE ASSISTANT")
    print("=" * 50)

    print("Type 'exit' to close the application.")

    while True:

        user_input = input("\nYou: ").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("Assistant: Goodbye!")
            break

        if not user_input:
            continue

        try:
            answer = run_agent(user_input)
            print(f"\nAssistant: {answer}")

        except Exception as error:
            print(f"\nError: {error}")


if __name__ == "__main__":
    main()
