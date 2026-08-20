from fastapi import FastAPI, Request
import database
import models
import requests

from routers import menu, orders, reservations

app = FastAPI()

models.Base.metadata.create_all(bind=database.engine)

# Your own API base URL internally.
# Vapi calls /vapi/tools, and this webhook calls your existing endpoints.
BASE_URL = "http://127.0.0.1:8000"


@app.get("/")
def root():
    return {"status": "backend is alive"}


app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(reservations.router)


@app.post("/vapi/tools")
async def vapi_tools(request: Request):
    body = await request.json()

    print("Vapi request:", body)

    # Vapi sends the tool call inside message.toolCalls
    message = body.get("message", {})
    tool_calls = message.get("toolCalls", [])

    results = []

    for tool_call in tool_calls:
        function = tool_call.get("function", {})
        tool_name = function.get("name")
        arguments = function.get("arguments", {})

        # Sometimes arguments can arrive as a JSON string.
        if isinstance(arguments, str):
            import json
            arguments = json.loads(arguments)

        try:

            # -------------------------------------------------
            # GET MENU
            # -------------------------------------------------
            if tool_name == "get_menu":

                response = requests.get(
                    f"{BASE_URL}/menu",
                    timeout=15,
                )

                response.raise_for_status()

                result = response.json()


            # -------------------------------------------------
            # CREATE ORDER
            # -------------------------------------------------
            elif tool_name == "create_order":

                payload = {
                    "customer_name": arguments["customer_name"],
                    "customer_phone": arguments.get("customer_phone", ""),
                    "customer_email": arguments["customer_email"],
                    "delivery_address": arguments["delivery_address"],
                    "items": arguments["items"],
                }

                response = requests.post(
                    f"{BASE_URL}/orders",
                    json=payload,
                    timeout=15,
                )

                response.raise_for_status()

                result = response.json()


            # -------------------------------------------------
            # CHECK ORDER STATUS
            # -------------------------------------------------
            elif tool_name == "check_order_status":

                order_id = arguments["order_id"]

                response = requests.get(
                    f"{BASE_URL}/orders/{order_id}",
                    timeout=15,
                )

                response.raise_for_status()

                result = response.json()


            # -------------------------------------------------
            # CHECK TABLE AVAILABILITY
            # -------------------------------------------------
            elif tool_name == "check_availability":

                table_id = arguments["table_id"]
                reservation_time = arguments["reservation_time"]

                response = requests.get(
                    f"{BASE_URL}/tables/{table_id}/availability",
                    params={
                        "reservation_time": reservation_time,
                    },
                    timeout=15,
                )

                response.raise_for_status()

                result = response.json()


            # -------------------------------------------------
            # CREATE RESERVATION
            # -------------------------------------------------
            elif tool_name == "create_reservation":

                payload = {
                    "customer_name": arguments["customer_name"],
                    "customer_phone": arguments["customer_phone"],
                    "table_id": arguments["table_id"],
                    "reservation_time": arguments["reservation_time"],
                    "party_size": arguments["party_size"],
                }

                response = requests.post(
                    f"{BASE_URL}/reservations",
                    json=payload,
                    timeout=15,
                )

                response.raise_for_status()

                result = response.json()


            # -------------------------------------------------
            # CANCEL RESERVATION
            # -------------------------------------------------
            elif tool_name == "cancel_reservation":

                reservation_id = arguments["reservation_id"]

                response = requests.patch(
                    f"{BASE_URL}/reservations/{reservation_id}/cancel",
                    timeout=15,
                )

                response.raise_for_status()

                result = response.json()


            # -------------------------------------------------
            # UNKNOWN TOOL
            # -------------------------------------------------
            else:

                result = {
                    "error": f"Unknown tool: {tool_name}"
                }


        except requests.RequestException as e:

            print(f"Backend error for {tool_name}: {e}")

            result = {
                "error": f"Backend request failed: {str(e)}"
            }

        except Exception as e:

            print(f"Tool error for {tool_name}: {e}")

            result = {
                "error": str(e)
            }


        results.append({
            "name": tool_name,
            "toolCallId": tool_call.get("id"),
            "result": result,
        })


    return {
        "results": results
    }