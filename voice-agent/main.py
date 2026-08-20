import os
import asyncio
from pathlib import Path

import requests
from dotenv import load_dotenv
from loguru import logger

# ============================================================
# ENVIRONMENT
# ============================================================

# restaurant-backend/.env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_path)

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(f"OPENAI_API_KEY not found in {env_path}")

BASE_URL = "http://127.0.0.1:8000"


# ============================================================
# PIPECAT IMPORTS
# ============================================================

from pipecat.audio.vad.silero import SileroVADAnalyzer

from pipecat.frames.frames import (
    LLMRunFrame,
    TextFrame,
)

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask

from pipecat.processors.aggregators.llm_context import LLMContext

from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)

from pipecat.processors.frame_processor import (
    FrameDirection,
    FrameProcessor,
)

from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport

from pipecat.services.llm_service import FunctionCallParams

from pipecat.services.openai.llm import OpenAILLMService
from pipecat.services.openai.stt import OpenAISTTService
from pipecat.services.openai.tts import OpenAITTSService

from pipecat.transports.base_transport import TransportParams


# ============================================================
# WEBRTC TRANSPORT
# ============================================================

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
    ),
}


# ============================================================
# BACKEND HELPERS
# ============================================================

def backend_get_menu():
    response = requests.get(
        f"{BASE_URL}/menu",
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def backend_create_order(
    customer_name,
    customer_email,
    items,
    customer_phone="",
    delivery_address="",
):
    payload = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "customer_email": customer_email,
        "delivery_address": delivery_address,
        "items": items,
    }

    response = requests.post(
        f"{BASE_URL}/orders",
        json=payload,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def backend_check_order_status(order_id):
    response = requests.get(
        f"{BASE_URL}/orders/{order_id}",
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def backend_check_availability(
    table_id,
    reservation_time,
):
    response = requests.get(
        f"{BASE_URL}/tables/{table_id}/availability",
        params={
            "reservation_time": reservation_time,
        },
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def backend_create_reservation(
    customer_name,
    table_id,
    reservation_time,
    party_size,
    customer_phone="",
):
    payload = {
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "table_id": table_id,
        "reservation_time": reservation_time,
        "party_size": party_size,
    }

    response = requests.post(
        f"{BASE_URL}/reservations",
        json=payload,
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


def backend_cancel_reservation(reservation_id):
    response = requests.patch(
        f"{BASE_URL}/reservations/{reservation_id}/cancel",
        timeout=10,
    )

    response.raise_for_status()

    return response.json()


# ============================================================
# PIPECAT TOOLS
# ============================================================

async def get_menu(params: FunctionCallParams):
    try:
        result = await asyncio.to_thread(
            backend_get_menu
        )

        await params.result_callback(result)

    except Exception as e:
        logger.exception("get_menu failed")

        await params.result_callback(
            {
                "success": False,
                "error": str(e),
            }
        )


async def create_order(
    params: FunctionCallParams,
    customer_name: str,
    customer_email: str,
    items: list,
    customer_phone: str = "",
    delivery_address: str = "",
):
    try:
        result = await asyncio.to_thread(
            backend_create_order,
            customer_name,
            customer_email,
            items,
            customer_phone,
            delivery_address,
        )

        await params.result_callback(result)

    except Exception as e:
        logger.exception("create_order failed")

        await params.result_callback(
            {
                "success": False,
                "error": str(e),
            }
        )


async def check_order_status(
    params: FunctionCallParams,
    order_id: str,
):
    try:
        result = await asyncio.to_thread(
            backend_check_order_status,
            order_id,
        )

        await params.result_callback(result)

    except Exception as e:
        logger.exception("check_order_status failed")

        await params.result_callback(
            {
                "success": False,
                "error": str(e),
            }
        )


async def check_availability(
    params: FunctionCallParams,
    table_id: int,
    reservation_time: str,
):
    try:
        result = await asyncio.to_thread(
            backend_check_availability,
            table_id,
            reservation_time,
        )

        await params.result_callback(result)

    except Exception as e:
        logger.exception("check_availability failed")

        await params.result_callback(
            {
                "success": False,
                "error": str(e),
            }
        )


async def create_reservation(
    params: FunctionCallParams,
    customer_name: str,
    table_id: int,
    reservation_time: str,
    party_size: int,
    customer_phone: str = "",
):
    try:
        result = await asyncio.to_thread(
            backend_create_reservation,
            customer_name,
            table_id,
            reservation_time,
            party_size,
            customer_phone,
        )

        await params.result_callback(result)

    except Exception as e:
        logger.exception("create_reservation failed")

        await params.result_callback(
            {
                "success": False,
                "error": str(e),
            }
        )


async def cancel_reservation(
    params: FunctionCallParams,
    reservation_id: int,
):
    try:
        result = await asyncio.to_thread(
            backend_cancel_reservation,
            reservation_id,
        )

        await params.result_callback(result)

    except Exception as e:
        logger.exception("cancel_reservation failed")

        await params.result_callback(
            {
                "success": False,
                "error": str(e),
            }
        )


# ============================================================
# GOODBYE DETECTOR
# ============================================================

class GoodbyeDetector(FrameProcessor):
    """
    Watches the assistant's generated text.

    When the final goodbye is generated, we wait a few seconds
    so TTS can finish speaking, then stop the pipeline.
    """

    def __init__(self):
        super().__init__()

        self.task = None
        self.goodbye_detected = False

    def set_task(self, task):
        self.task = task

    async def process_frame(
        self,
        frame,
        direction,
    ):
        await super().process_frame(
            frame,
            direction,
        )

        if (
            isinstance(frame, TextFrame)
            and direction == FrameDirection.DOWNSTREAM
        ):
            text = frame.text.strip()

            if (
                not self.goodbye_detected
                and "Thank you for calling Mirch & Co." in text
                and "Allah Hafiz" in text
            ):
                self.goodbye_detected = True

                logger.info(
                    "Final goodbye detected."
                )

                if self.task:
                    asyncio.create_task(
                        self.end_call()
                    )

        await self.push_frame(
            frame,
            direction,
        )

    async def end_call(self):
        """
        Wait for TTS to finish the goodbye, then
        stop the Pipecat pipeline.
        """

        # Give TTS time to finish speaking.
        await asyncio.sleep(4)

        logger.info(
            "Goodbye finished. Ending call."
        )

        if self.task:
            await self.task.cancel()


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are the voice assistant for Mirch & Co., a Pakistani restaurant in Lahore.

You are having a real-time voice conversation with a customer.

Speak naturally, clearly, and conversationally in English with a subtle
Pakistani English style. Do not exaggerate the accent.

Use English by default.

If the customer speaks Urdu or Roman Urdu, you may naturally respond in
Urdu or a mix of Urdu and English.

Your personality is warm, friendly, confident, and helpful, like a real
Pakistani restaurant employee answering the phone.

Do not sound like a formal customer-service chatbot.

VOICE STYLE:

Keep most replies to one short sentence.

Use two short sentences only when necessary.

Do not give long explanations unless the customer specifically asks.

Do not repeat information.

Do not repeatedly say "Jee". Use it occasionally and naturally.

Do not use bullet points, numbered lists, headings, markdown, emojis,
parentheses, or unnecessary formatting.

MENU:

Always use get_menu when you need real menu information.

Never invent menu items, prices, ingredients, or availability.

Prices must always come from the backend.

PRICE:

Never say "Rs", "Rs.", or "PKR".

Always say "rupees".

For example:

"The BBQ Burger is 850 rupees."

Never pronounce R and S separately.

ORDERS:

You can actually place orders using create_order.

Never tell the customer that an order was placed unless create_order
successfully returned a result confirming the order.

Before creating an order, collect:

customer name
customer email
phone number if the customer wants to provide it
delivery address when delivery is requested
exact menu items
quantities

The customer email is required for order confirmation.

Use get_menu to identify the correct menu_item_id and current price.

Before calling create_order, briefly confirm the order details with
the customer.

For example:

"Just to confirm, that's one BBQ Burger for 850 rupees. Shall I place it?"

Only call create_order after the customer confirms.

After create_order succeeds, use the actual response from the backend
when telling the customer the order ID, status, or total.

Never invent an order ID or total.

ORDER STATUS:

Use check_order_status when the customer asks about an existing order.

Do not guess an order's status.

RESERVATIONS:

Use check_availability to check whether a table is available.

Use create_reservation to create a real reservation.

Never claim that a reservation was booked unless the backend confirms it.

Before creating a reservation, confirm the customer's:

name
table
date/time
party size
phone number if provided

CANCELLATIONS:

Use cancel_reservation when the customer wants to cancel a reservation.

Never claim that a reservation was cancelled unless the backend confirms it.

CONVERSATION:

Pay attention to what the customer has already provided.

Do not ask for information that the customer already gave you.

If the customer says goodbye, says they are finished, or clearly wants
to end the conversation, politely end the call.

The final goodbye MUST be exactly:

"Thank you for calling Mirch & Co. Take care, Allah Hafiz."

Do not add anything after that sentence.
"""


# ============================================================
# RUN BOT
# ============================================================

async def run_bot(
    transport,
    runner_args,
):
    logger.info(
        "Starting Mirch & Co. voice agent"
    )

    # --------------------------------------------------------
    # SPEECH → TEXT
    # --------------------------------------------------------

    stt = OpenAISTTService(
        api_key=os.environ["OPENAI_API_KEY"],
    )

    # --------------------------------------------------------
    # TEXT → AI
    # --------------------------------------------------------

    llm = OpenAILLMService(
        api_key=os.environ["OPENAI_API_KEY"],
        settings=OpenAILLMService.Settings(
            system_instruction=SYSTEM_PROMPT,
        ),
    )

    # --------------------------------------------------------
    # AI → SPEECH
    # --------------------------------------------------------

    tts = OpenAITTSService(
        api_key=os.environ["OPENAI_API_KEY"],
    )

    # --------------------------------------------------------
    # CONTEXT + TOOLS
    # --------------------------------------------------------

    context = LLMContext(
        tools=[
            get_menu,
            create_order,
            check_order_status,
            check_availability,
            create_reservation,
            cancel_reservation,
        ]
    )

    user_aggregator, assistant_aggregator = (
        LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                vad_analyzer=SileroVADAnalyzer()
            ),
        )
    )

    # --------------------------------------------------------
    # GOODBYE DETECTOR
    # --------------------------------------------------------

    goodbye_detector = GoodbyeDetector()

    # --------------------------------------------------------
    # PIPELINE
    # --------------------------------------------------------

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            goodbye_detector,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    # --------------------------------------------------------
    # TASK
    # --------------------------------------------------------

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
    )

    # Give detector access to the task AFTER task exists.
    goodbye_detector.set_task(task)

    # --------------------------------------------------------
    # CLIENT CONNECTED
    # --------------------------------------------------------

    @transport.event_handler(
        "on_client_connected"
    )
    async def on_client_connected(
        transport,
        client,
    ):
        logger.info(
            "Client connected"
        )

        context.add_message(
            {
                "role": "user",
                "content": (
                    "Please introduce yourself "
                    "to the customer."
                ),
            }
        )

        await task.queue_frames(
            [LLMRunFrame()]
        )

    # --------------------------------------------------------
    # CLIENT DISCONNECTED
    # --------------------------------------------------------

    @transport.event_handler(
        "on_client_disconnected"
    )
    async def on_client_disconnected(
        transport,
        client,
    ):
        logger.info(
            "Client disconnected"
        )

        await task.cancel()

    # --------------------------------------------------------
    # RUN
    # --------------------------------------------------------

    from pipecat.pipeline.runner import PipelineRunner

    runner = PipelineRunner()

    await runner.run(task)


# ============================================================
# BOT ENTRY POINT
# ============================================================

async def bot(
    runner_args: RunnerArguments,
):
    transport = await create_transport(
        runner_args,
        transport_params,
    )

    await run_bot(
        transport,
        runner_args,
    )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":
    from pipecat.runner.run import main

    main()