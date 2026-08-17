# This is the AI agent -- it takes a customer's message, sends it to
# GPT-4o-mini along with our tool definitions, and if GPT decides to call
# a tool, we actually execute the real request against our own FastAPI
# backend (running locally right now), then feed the result back to GPT
# so it can respond to the customer in natural language.
import os
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv
from ai_tools import tools
 
load_dotenv()
 
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
 
BASE_URL = "http://127.0.0.1:8000"
 
 
# ---- These functions actually call our own FastAPI backend ----
 
def get_menu():
    response = requests.get(f"{BASE_URL}/menu")
    return response.json()
 
 
def create_order(customer_name, items, customer_phone="", delivery_address=""):
    payload = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "delivery_address": delivery_address,
        "items": items
    }
    response = requests.post(f"{BASE_URL}/orders", json=payload)
    return response.json()
 
 
def check_order_status(order_id):
    response = requests.get(f"{BASE_URL}/orders/{order_id}")
    return response.json()
 
 
def check_availability(table_id, reservation_time):
    response = requests.get(
        f"{BASE_URL}/tables/{table_id}/availability",
        params={"reservation_time": reservation_time}
    )
    return response.json()
 
 
def create_reservation(customer_name, table_id, reservation_time, party_size, customer_phone=""):
    payload = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "table_id": table_id,
        "reservation_time": reservation_time,
        "party_size": party_size
    }
    response = requests.post(f"{BASE_URL}/reservations", json=payload)
    return response.json()
 
 
def cancel_reservation(reservation_id):
    response = requests.patch(f"{BASE_URL}/reservations/{reservation_id}/cancel")
    return response.json()
 
 
# Maps tool names (as GPT sees them) to our actual Python functions
AVAILABLE_FUNCTIONS = {
    "get_menu": get_menu,
    "create_order": create_order,
    "check_order_status": check_order_status,
    "check_availability": check_availability,
    "create_reservation": create_reservation,
    "cancel_reservation": cancel_reservation,
}
 
 
def chat_with_agent(user_message, conversation_history=None):
    if conversation_history is None:
        conversation_history = [
            {
                "role": "system",
                "content": (
                    "You are a friendly restaurant assistant. You can help customers "
                    "browse the menu, place orders, check order status, check table "
                    "availability, and make or cancel reservations. Always confirm "
                    "details with the customer before placing an order or reservation. "
                    "Be concise and natural in your responses."
                )
            }
        ]
 
    conversation_history.append({"role": "user", "content": user_message})
 
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=conversation_history,
        tools=tools
    )
 
    message = response.choices[0].message
 
    # If GPT wants to call a tool, execute it and feed the result back
    if message.tool_calls:
        conversation_history.append(message)
 
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            function_args = json.loads(tool_call.function.arguments)
 
            function_to_call = AVAILABLE_FUNCTIONS[function_name]
            function_result = function_to_call(**function_args)
 
            conversation_history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(function_result)
            })
 
        # Ask GPT to respond to the customer now that it has the tool result
        second_response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history
        )
        final_message = second_response.choices[0].message
        conversation_history.append(final_message)
        return final_message.content, conversation_history
 
    else:
        conversation_history.append(message)
        return message.content, conversation_history
 
 
# ---- Simple terminal chat loop for testing ----
if __name__ == "__main__":
    print("Restaurant AI Agent (type 'quit' to exit)\n")
    history = None
 
    while True:
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break
 
        reply, history = chat_with_agent(user_input, history)
        print(f"Agent: {reply}\n")