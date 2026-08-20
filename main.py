from fastapi import FastAPI, Request
import database
import models
import requests
import json

from routers import menu, orders, reservations


app = FastAPI()


# Create database tables if they do not already exist
models.Base.metadata.create_all(bind=database.engine)


# Public Railway backend URL
BASE_URL = "https://ai-powered-restaurant-system-production.up.railway.app"


# ============================================================
# ROOT
# ============================================================

@app.get("/")
def root():
    return {
        "status": "backend is alive"
    }


# ============================================================
# EXISTING ROUTERS
# ============================================================

app.include_router(menu.router)
app.include_router(orders.router)
app.include_router(reservations.router)


# ============================================================
# VAPI TOOL BRIDGE
# ============================================================

@app.post("/vapi/tools")
async def vapi_tools(request: Request):

    body = await request.json()

    print("========== VAPI TOOL REQUEST ==========")
    print(json.dumps(body, indent=2))
    print("=======================================")

    message = body.get("message", {})

    # Normal Vapi format
    tool_calls = message.get("toolCalls", [])

    # Compatibility with alternate format
    if not tool_calls:
        tool_calls = message.get("toolCallList", [])

    results = []

    # ========================================================
    # PROCESS EACH TOOL CALL
    # ========================================================

    for tool_call in tool_calls:

        tool_name = None
        arguments = {}

        # ----------------------------------------------------
        # Get function information
        # ----------------------------------------------------

        function = tool_call.get("function", {})

        if function:
            tool_name = function.get("name")
            arguments = function.get("arguments", {})

        # ----------------------------------------------------
        # Alternate Vapi format
        # ----------------------------------------------------

        if not tool_name:
            tool_name = tool_call.get("name")

        if not arguments:
            arguments = tool_call.get("arguments", {})

        # ----------------------------------------------------
        # Arguments may arrive as a JSON string
        # ----------------------------------------------------

        if isinstance(arguments, str):

            try:
                arguments = json.loads(arguments)

            except json.JSONDecodeError:

                arguments = {}

        print(f"TOOL: {tool_name}")
        print(f"ARGUMENTS: {arguments}")

        try:

            # =================================================
            # GET MENU
            # =================================================

            if tool_name == "get_menu":

                response = requests.get(
                    f"{BASE_URL}/menu",
                    timeout=15,
                )

                print("MENU STATUS:", response.status_code)
                print("MENU RESPONSE:", response.text)

                response.raise_for_status()

                result = response.json()


            # =================================================
            # CREATE ORDER
            # =================================================

            elif tool_name == "create_order":

                payload = {
                    "customer_name": arguments["customer_name"],
                    "customer_phone": arguments.get(
                        "customer_phone",
                        "",
                    ),
                    "customer_email": arguments["customer_email"],
                    "delivery_address": arguments.get(
                        "delivery_address",
                        "",
                    ),
                    "items": arguments["items"],
                }

                print("CREATE ORDER PAYLOAD:")
                print(
                    json.dumps(
                        payload,
                        indent=2,
                    )
                )

                response = requests.post(
                    f"{BASE_URL}/orders",
                    json=payload,
                    timeout=15,
                )

                print(
                    "ORDER STATUS:",
                    response.status_code,
                )

                print(
                    "ORDER RESPONSE:",
                    response.text,
                )

                response.raise_for_status()

                result = response.json()


            # =================================================
            # CHECK ORDER STATUS
            # =================================================

            elif tool_name == "check_order_status":

                order_id = arguments["order_id"]

                response = requests.get(
                    f"{BASE_URL}/orders/{order_id}",
                    timeout=15,
                )

                print(
                    "ORDER STATUS CHECK:",
                    response.status_code,
                )

                response.raise_for_status()

                result = response.json()


            # =================================================
            # CHECK TABLE AVAILABILITY
            # =================================================
            #
            # Vapi sends:
            #
            # {
            #     "party_size": 3,
            #     "reservation_time": "2026-08-23T20:00:00"
            # }
            #
            # The backend automatically finds a suitable table.
            #
            # =================================================

            elif tool_name == "check_availability":

                party_size = int(
                    arguments["party_size"]
                )

                reservation_time = arguments[
                    "reservation_time"
                ]

                print(
                    "CHECKING TABLE AVAILABILITY:"
                )

                print(
                    f"Party size: {party_size}"
                )

                print(
                    f"Reservation time: "
                    f"{reservation_time}"
                )

                response = requests.get(
                    f"{BASE_URL}/tables/availability",
                    params={
                        "reservation_time": reservation_time,
                        "party_size": party_size,
                    },
                    timeout=15,
                )

                print(
                    "AVAILABILITY STATUS:",
                    response.status_code,
                )

                print(
                    "AVAILABILITY RESPONSE:",
                    response.text,
                )

                response.raise_for_status()

                result = response.json()


            # =================================================
            # CREATE RESERVATION
            # =================================================

            elif tool_name == "create_reservation":

                payload = {
                    "customer_name": arguments[
                        "customer_name"
                    ],
                    "customer_phone": arguments.get(
                        "customer_phone",
                        "",
                    ),
                    "table_id": arguments[
                        "table_id"
                    ],
                    "reservation_time": arguments[
                        "reservation_time"
                    ],
                    "party_size": arguments[
                        "party_size"
                    ],
                }

                print(
                    "CREATE RESERVATION PAYLOAD:"
                )

                print(
                    json.dumps(
                        payload,
                        indent=2,
                    )
                )

                response = requests.post(
                    f"{BASE_URL}/reservations",
                    json=payload,
                    timeout=15,
                )

                print(
                    "RESERVATION STATUS:",
                    response.status_code,
                )

                print(
                    "RESERVATION RESPONSE:",
                    response.text,
                )

                response.raise_for_status()

                result = response.json()


            # =================================================
            # CANCEL RESERVATION
            # =================================================

            elif tool_name == "cancel_reservation":

                reservation_id = arguments[
                    "reservation_id"
                ]

                response = requests.patch(
                    f"{BASE_URL}/reservations/"
                    f"{reservation_id}/cancel",
                    timeout=15,
                )

                print(
                    "CANCEL RESERVATION STATUS:",
                    response.status_code,
                )

                print(
                    "CANCEL RESERVATION RESPONSE:",
                    response.text,
                )

                response.raise_for_status()

                result = response.json()


            # =================================================
            # UNKNOWN TOOL
            # =================================================

            else:

                result = {
                    "success": False,
                    "error": (
                        f"Unknown tool: {tool_name}"
                    ),
                }


        # ====================================================
        # HTTP REQUEST ERROR
        # ====================================================

        except requests.RequestException as e:

            print(
                f"BACKEND ERROR FOR "
                f"{tool_name}: {e}"
            )

            result = {
                "success": False,
                "error": str(e),
            }


        # ====================================================
        # OTHER ERROR
        # ====================================================

        except Exception as e:

            print(
                f"TOOL ERROR FOR "
                f"{tool_name}: {e}"
            )

            result = {
                "success": False,
                "error": str(e),
            }


        # ====================================================
        # ADD TOOL RESULT
        # ====================================================

        results.append(
            {
                "name": tool_name,
                "toolCallId": tool_call.get(
                    "id"
                ),
                "result": result,
            }
        )


    # ========================================================
    # LOG FINAL VAPI RESPONSE
    # ========================================================

    print("VAPI TOOL RESPONSE:")

    print(
        json.dumps(
            {
                "results": results
            },
            indent=2,
            default=str,
        )
    )


    # ========================================================
    # RETURN TO VAPI
    # ========================================================

    return {
        "results": results
    }