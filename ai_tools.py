tools = [
    {
        "type": "function",
        "function": {
            "name": "get_menu",
            "description": "Get the full restaurant menu, including item names, descriptions, prices, and categories.",
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
            "name": "create_order",
            "description": "Place a new food order for a customer, with one or more menu items.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name."
                    },
                    "customer_email": {
                        "type": "string",
                        "description": "The customer's email address, required for sending order confirmation."
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "The customer's phone number, used to identify returning customers."
                    },
                    "delivery_address": {
                        "type": "string",
                        "description": "Where the order should be delivered."
                    },
                    "items": {
                        "type": "array",
                        "description": "The list of menu items and quantities being ordered.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "menu_item_id": {
                                    "type": "integer",
                                    "description": "The ID of the menu item, from get_menu."
                                },
                                "quantity": {
                                    "type": "integer",
                                    "description": "How many of this item to order."
                                }
                            },
                            "required": ["menu_item_id", "quantity"]
                        }
                    }
                },
                "required": ["customer_name", "customer_email", "items"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_order_status",
            "description": "Check the current status of an existing order using its order ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "order_id": {
                        "type": "integer",
                        "description": "The ID of the order to check."
                    }
                },
                "required": ["order_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check whether a specific table is available at a specific date and time, before attempting to book it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "table_id": {
                        "type": "integer",
                        "description": "The ID of the table to check."
                    },
                    "reservation_time": {
                        "type": "string",
                        "description": "The requested date and time, in ISO 8601 format, e.g. 2026-08-20T19:00:00."
                    }
                },
                "required": ["table_id", "reservation_time"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_reservation",
            "description": "Book a table reservation for a customer, after confirming availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "customer_name": {
                        "type": "string",
                        "description": "The customer's name."
                    },
                    "customer_phone": {
                        "type": "string",
                        "description": "The customer's phone number."
                    },
                    "table_id": {
                        "type": "integer",
                        "description": "The ID of the table to reserve."
                    },
                    "reservation_time": {
                        "type": "string",
                        "description": "The requested date and time, in ISO 8601 format."
                    },
                    "party_size": {
                        "type": "integer",
                        "description": "Number of people in the party."
                    }
                },
                "required": ["customer_name", "table_id", "reservation_time", "party_size"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_reservation",
            "description": "Cancel an existing reservation using its reservation ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reservation_id": {
                        "type": "integer",
                        "description": "The ID of the reservation to cancel."
                    }
                },
                "required": ["reservation_id"]
            }
        }
    }
]