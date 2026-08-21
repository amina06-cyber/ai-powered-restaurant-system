import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv
from ai_tools import tools

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

BASE_URL = "https://ai-powered-restaurant-system-production.up.railway.app"


# ============================================================
# BACKEND FUNCTIONS
# ============================================================

def get_menu():
    response = requests.get(
        f"{BASE_URL}/menu",
        timeout=15
    )
    response.raise_for_status()
    return response.json()


def create_order(
    customer_name,
    customer_email,
    items,
    customer_phone="",
    delivery_address=""
):
    payload = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "delivery_address": delivery_address,
        "items": items
    }

    response = requests.post(
        f"{BASE_URL}/orders",
        json=payload,
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def check_order_status(order_id):
    response = requests.get(
        f"{BASE_URL}/orders/{order_id}",
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def check_availability(
    table_id,
    reservation_time
):
    response = requests.get(
        f"{BASE_URL}/tables/{table_id}/availability",
        params={
            "reservation_time": reservation_time
        },
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def create_reservation(
    customer_name,
    customer_email,
    table_id,
    reservation_time,
    party_size,
    customer_phone=""
):
    """
    Creates the reservation through the FastAPI backend.

    customer_email is now explicitly passed through so the
    backend can use it for the reservation confirmation email.
    """

    payload = {
        "customer_name": customer_name,
        "customer_email": customer_email,
        "customer_phone": customer_phone,
        "table_id": table_id,
        "reservation_time": reservation_time,
        "party_size": party_size
    }

    response = requests.post(
        f"{BASE_URL}/reservations",
        json=payload,
        timeout=15
    )

    response.raise_for_status()

    return response.json()


def cancel_reservation(reservation_id):
    response = requests.patch(
        f"{BASE_URL}/reservations/{reservation_id}/cancel",
        timeout=15
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# TOOL → PYTHON FUNCTION MAP
# ============================================================

AVAILABLE_FUNCTIONS = {
    "get_menu": get_menu,
    "create_order": create_order,
    "check_order_status": check_order_status,
    "check_availability": check_availability,
    "create_reservation": create_reservation,
    "cancel_reservation": cancel_reservation,
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are Mirch, the friendly AI dining assistant for Mirch & Co.

You can:
- answer questions about the menu
- place food orders
- check order status
- check table availability
- make reservations
- cancel reservations

GENERAL RULES
============================================================

- Be friendly, concise, and natural.
- Respond in the same language the customer is using.
- If the customer is speaking English, respond in English.
- Do not randomly switch to Urdu, Hindi, or another language.
- Never claim that you cannot make reservations or orders when the appropriate tools are available.
- Never invent information.
- Never invent prices, dates, times, table numbers, availability, reservation IDs, or order IDs.
- Never say an action succeeded unless the corresponding tool actually succeeded.
- Remember information the customer already provided.
- Do not ask the customer for information they already gave you.


============================================================
RESERVATIONS
============================================================

You CAN make reservations.

When a customer wants to reserve a table, collect:

1. Customer name
2. Customer email
3. Customer phone number
4. Reservation date
5. Reservation time
6. Party size

Remember all information the customer has already provided.

Do not ask for the same information again.

For example:

"I want a table for 2 on August 30 under Faizan,
my email is faizan@gmail.com."

You already know:

name = Faizan
email = faizan@gmail.com
party_size = 2
date = August 30

Only ask for missing information.


============================================================
NEVER INVENT A TIME
============================================================

This is extremely important.

NEVER assume or invent a reservation time.

If the customer says:

"I want a table for 2 tomorrow."

Ask:

"What time would you like the reservation for?"

Do NOT assume 7:00 PM.

Do NOT suggest a time unless appropriate.

Use the exact time provided by the customer.


============================================================
DATE HANDLING
============================================================

Use the exact date provided by the customer.

If the customer says:

"August 30, 2026"

use:

2026-08-30

Do not change the year.

If the customer says "tomorrow", determine the correct date from the current date available to you.

Never invent a date.


============================================================
TIME HANDLING
============================================================

Convert the customer's requested date and time into ISO 8601 format.

Example:

August 30, 2026 at 6:00 PM

becomes:

2026-08-30T18:00:00

Example:

August 30, 2026 at 7:30 PM

becomes:

2026-08-30T19:30:00

Do not invent a time.


============================================================
CHECK AVAILABILITY
============================================================

Once you have:

- reservation date
- reservation time
- party size

you MUST check availability BEFORE telling the customer that a table is available.

Call:

check_availability

The tool requires:

- table_id
- reservation_time

Use an appropriate table_id.

If the result says:

available = false

tell the customer that the requested time is unavailable.

Do NOT create a reservation.

Offer to check another time.

If the result says:

available = true

use the table_id returned by the availability result.

Tell the customer that a table is available.

Ask:

"Would you like me to confirm the reservation?"

Do NOT call create_reservation yet.


============================================================
TABLE ID
============================================================

When check_availability returns an available table:

IMPORTANT:

Use the EXACT table_id returned by check_availability.

Do not invent a table ID.

Do not choose a different table.

Do not call create_reservation using a table ID that was not returned by availability.


============================================================
CONFIRMATION
============================================================

Only call create_reservation after the customer explicitly confirms.

Examples:

"yes"
"yes please"
"confirm it"
"book it"
"go ahead"
"please reserve it"

Before calling create_reservation, make sure you have:

- customer name
- customer email
- customer phone
- table_id
- reservation date
- reservation time
- party size

Never invent missing values.


============================================================
EMAIL FOR RESERVATIONS
============================================================

Email is REQUIRED for reservations.

The email is used to send the reservation confirmation.

If the customer already provided an email:

REMEMBER IT.

Do NOT ask for it again.

When calling create_reservation, ALWAYS pass the customer's email as:

customer_email

Example:

customer_email = "faizan@gmail.com"

Do not omit customer_email.

Do not invent an email.

If the customer has not provided an email, ask for it before creating the reservation.


============================================================
PHONE FOR RESERVATIONS
============================================================

Phone number is REQUIRED for completing a reservation.

If the customer has not provided a phone number, ask for it.

Do not invent a phone number.

If the customer already provided a phone number, remember it.

Do not ask for it again.


============================================================
CREATE RESERVATION
============================================================

When calling create_reservation:

Use the exact information provided by the customer.

Use:

- customer_name
- customer_email
- customer_phone
- table_id from check_availability
- reservation_time
- party_size

Do not change the customer's information.

Do not invent missing values.

Do not call create_reservation before availability has been checked.

Do not call create_reservation before the customer confirms.


============================================================
AFTER SUCCESSFUL RESERVATION
============================================================

Only after create_reservation successfully returns:

Tell the customer the reservation is confirmed.

Include:

- customer name
- date
- time
- party size
- table number if returned

Then say:

"You'll receive a confirmation email shortly."

Then ask:

"Is there anything else I can help you with?"

Do not immediately end the conversation.


============================================================
RESERVATION FAILURE
============================================================

If create_reservation returns:

success = false

DO NOT tell the customer the reservation was confirmed.

Explain the actual problem.

For example:

- table no longer available
- table not found
- missing information
- backend error

Never fabricate a successful reservation.


============================================================
ORDERS
============================================================

For orders collect:

- customer name
- customer email
- customer phone when needed
- delivery address when delivery is requested
- items
- quantities

Before calling create_order:

Confirm the order details with the customer.

Never invent an item.

Never invent a price.


============================================================
CANCELLATIONS
============================================================

For cancellation:

- obtain the reservation ID
- call cancel_reservation
- only tell the customer it was cancelled if the tool succeeds

Never claim cancellation succeeded if the tool failed.


============================================================
TOOL RESULTS
============================================================

Trust the actual tool results.

If a tool returns an error:

- do not pretend it succeeded
- explain the issue clearly
- ask for whatever information is needed

Never fabricate:

- reservation IDs
- order IDs
- table numbers
- availability
- prices
- dates
- times
- successful actions
"""


# ============================================================
# CHAT FUNCTION
# ============================================================

def chat_with_agent(
    user_message,
    conversation_history=None
):

    if conversation_history is None:

        conversation_history = [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        ]

    elif not any(
        message.get("role") == "system"
        for message in conversation_history
    ):

        conversation_history.insert(
            0,
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            }
        )

    conversation_history.append(
        {
            "role": "user",
            "content": user_message
        }
    )

    # ========================================================
    # FIRST GPT REQUEST
    # ========================================================

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history,
        tools=tools
    )

    message = response.choices[0].message

    # ========================================================
    # TOOL CALLS
    # ========================================================

    if message.tool_calls:

        conversation_history.append(message)

        for tool_call in message.tool_calls:

            function_name = tool_call.function.name

            print(
                f"\nAI TOOL CALL: {function_name}"
            )

            try:

                function_args = json.loads(
                    tool_call.function.arguments
                )

            except json.JSONDecodeError:

                function_args = {}

            print(
                f"TOOL ARGUMENTS: {function_args}"
            )

            # ------------------------------------------------
            # Unknown tool
            # ------------------------------------------------

            if function_name not in AVAILABLE_FUNCTIONS:

                function_result = {
                    "success": False,
                    "error": (
                        f"Unknown tool: {function_name}"
                    )
                }

            # ------------------------------------------------
            # Execute tool
            # ------------------------------------------------

            else:

                try:

                    function_to_call = (
                        AVAILABLE_FUNCTIONS[
                            function_name
                        ]
                    )

                    function_result = (
                        function_to_call(
                            **function_args
                        )
                    )

                    print(
                        f"TOOL RESULT: {function_result}"
                    )

                except Exception as e:

                    print(
                        f"TOOL ERROR: {e}"
                    )

                    function_result = {
                        "success": False,
                        "error": str(e)
                    }

            # ------------------------------------------------
            # Give result back to GPT
            # ------------------------------------------------

            conversation_history.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(
                        function_result,
                        default=str
                    )
                }
            )

        # ====================================================
        # SECOND GPT REQUEST
        # ====================================================

        second_response = (
            client.chat.completions.create(
                model="gpt-4o-mini",
                messages=conversation_history,
                tools=tools
            )
        )

        final_message = (
            second_response.choices[0].message
        )

        conversation_history.append(
            final_message
        )

        return (
            final_message.content,
            conversation_history
        )

    # ========================================================
    # NORMAL RESPONSE
    # ========================================================

    conversation_history.append(
        message
    )

    return (
        message.content,
        conversation_history
    )


# ============================================================
# TERMINAL TEST
# ============================================================

if __name__ == "__main__":

    print(
        "Restaurant AI Agent"
    )

    print(
        "Type 'quit' to exit.\n"
    )

    history = None

    while True:

        user_input = input(
            "You: "
        )

        if user_input.lower() == "quit":
            break

        reply, history = chat_with_agent(
            user_input,
            history
        )

        print(
            f"Agent: {reply}\n"
        )