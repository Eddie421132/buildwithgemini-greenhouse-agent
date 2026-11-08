# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from zoneinfo import ZoneInfo

from google import genai
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.genai import types

from a2ui.schema.manager import A2uiSchemaManager
from a2ui.basic_catalog.provider import BasicCatalog
from app.a2ui_utils import a2ui_callback


SANDBOX_RESOURCE_NAME = (
    "projects/188939847350/locations/us-east1/reasoningEngines/2950762653997334528"
    "/sandboxEnvironments/8647575389574529024"
)
code_executor = AgentEngineSandboxCodeExecutor(sandbox_resource_name=SANDBOX_RESOURCE_NAME)


# Memory Bank write callback: send session to Memory Bank after each turn
async def generate_memories_callback(callback_context: CallbackContext):
    await callback_context.add_session_to_memory()
    return None



MODEL = "gemini-3.8-flash"


import json
import urllib.parse
import urllib.request


def fetch_local_sunlight_and_climate(city: str) -> dict:
    """Fetch real-time ambient climate, relative humidity, UV index, and solar radiation for plant care.

    Uses the free Open-Meteo API (no API key required).

    Args:
        city: City or locality name, e.g. 'Seattle', 'San Francisco', 'New York', 'London'.

    Returns:
        A dictionary with real temperature (°C), relative humidity (%), UV index, and plant light conditions.
    """
    try:
        # 1. Geocode city name to lat/long
        geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={urllib.parse.quote(city)}&count=1&language=en&format=json"
        req = urllib.request.Request(geo_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            geo_data = json.loads(resp.read().decode())
        
        if not geo_data.get("results"):
            return {"error": f"Could not find coordinates for city: {city}"}
        
        loc = geo_data["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        place_name = f"{loc.get('name')}, {loc.get('country', '')}"

        # 2. Fetch current weather, humidity, and solar UV
        weather_url = (
            f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,relative_humidity_2m,uv_index,direct_normal_irradiance"
            "&timezone=auto"
        )
        req2 = urllib.request.Request(weather_url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            weather_data = json.loads(resp2.read().decode())
        
        current = weather_data.get("current", {})
        uv = current.get("uv_index", 0.0)
        temp_c = current.get("temperature_2m")
        humidity = current.get("relative_humidity_2m")

        # Determine greenhouse light condition
        if uv >= 6:
            light_eval = "High / Intense Direct Sun (consider shade cloth for delicate foliage)"
        elif uv >= 3:
            light_eval = "Moderate Indirect Sun (ideal for most indoor tropical plants)"
        elif uv > 0:
            light_eval = "Low / Overcast Sun (safe for low-light plants like Snake Plant or ZZ)"
        else:
            light_eval = "Night / No Solar Radiation"

        return {
            "location": place_name,
            "temperature_c": temp_c,
            "relative_humidity_percent": humidity,
            "uv_index": uv,
            "natural_light_condition": light_eval,
        }
    except Exception as e:
        return {"error": f"Failed to fetch real-time climate data: {str(e)}"}


def lookup_plant_botanical_taxonomy(scientific_or_common_name: str) -> dict:
    """Look up official botanical taxonomic classification (family, genus, scientific authority).

    Uses the free GBIF (Global Biodiversity Information Facility) Species API (no key required).

    Args:
        scientific_or_common_name: Scientific or common plant name, e.g. 'Monstera deliciosa', 'Ficus lyrata', 'Spathiphyllum'.

    Returns:
        A dictionary with family, genus, kingdom, order, and verified scientific name.
    """
    try:
        clean_name = scientific_or_common_name.strip()
        url = f"https://api.gbif.org/v1/species/match?name={urllib.parse.quote(clean_name)}&verbose=false"
        req = urllib.request.Request(url, headers={"User-Agent": "GreenhouseAgent/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())

        if data.get("matchType") == "NONE":
            return {"error": f"No botanical taxonomy match found for '{scientific_or_common_name}'."}

        return {
            "query": scientific_or_common_name,
            "scientific_name": data.get("scientificName"),
            "kingdom": data.get("kingdom"),
            "order": data.get("order"),
            "family": data.get("family"),
            "genus": data.get("genus"),
            "species": data.get("species"),
            "taxonomic_status": data.get("status"),
            "confidence": data.get("confidence"),
        }
    except Exception as e:
        return {"error": f"Taxonomy lookup failed: {str(e)}"}



def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        city: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


def calculate_watering_schedule(
    plant_name: str,
    pot_diameter_cm: float = 15.0,
    room_temperature_c: float = 22.0,
    pot_type: str = "plastic",
) -> dict:
    """Calculate personalized watering interval and volume for a plant.

    Args:
        plant_name: Common or species name of the plant (e.g. 'Monstera', 'Snake Plant', 'Fiddle Leaf Fig').
        pot_diameter_cm: Diameter of the pot in centimeters. Default is 15.0 cm.
        room_temperature_c: Indoor ambient temperature in Celsius. Default is 22.0 C.
        pot_type: Material of the pot ('terracotta' dries faster, 'plastic' or 'ceramic' retains moisture).

    Returns:
        A dictionary with interval_days, recommended_water_ml, and care tips.
    """
    # Base watering days depending on plant drought tolerance
    name_lower = plant_name.lower()
    if "snake" in name_lower or "succulent" in name_lower or "cactus" in name_lower:
        base_days = 18
        water_ratio = 0.20
    elif "peace lily" in name_lower or "fern" in name_lower:
        base_days = 5
        water_ratio = 0.35
    elif "fig" in name_lower or "ficus" in name_lower:
        base_days = 8
        water_ratio = 0.30
    else:  # default foliage like Monstera
        base_days = 9
        water_ratio = 0.25

    # Adjust for temperature
    if room_temperature_c >= 28:
        base_days = max(2, base_days - 3)
    elif room_temperature_c <= 18:
        base_days = base_days + 4

    # Adjust for pot material (terracotta breathes and dries ~20% faster)
    if "terracotta" in pot_type.lower() or "clay" in pot_type.lower():
        base_days = max(2, int(base_days * 0.8))

    # Approximate soil volume V ≈ pi * r^2 * h (assuming h ≈ diameter)
    radius = pot_diameter_cm / 2.0
    approx_volume_ml = 3.14159 * (radius**2) * pot_diameter_cm
    suggested_ml = round(approx_volume_ml * water_ratio / 50.0) * 50  # round to nearest 50ml

    return {
        "plant_name": plant_name,
        "interval_days": int(base_days),
        "water_amount_ml": int(max(100, suggested_ml)),
        "advice": f"Check top 2-3cm soil moisture before watering. Water roughly every {int(base_days)} days."
    }


import re
import time
from google.cloud import storage
from google.adk.tools import ToolContext

GCS_BUCKET_NAME = "greenhouse-plants-qwiklabs-gcp-04-af9f0d7d2999"
PROJECT_ID = "qwiklabs-gcp-04-af9f0d7d2999"
_genai_client = None
_storage_client = None


def get_genai_client() -> genai.Client:
    global _genai_client
    if _genai_client is None:
        _genai_client = genai.Client(vertexai=True, project=PROJECT_ID, location="global")
    return _genai_client


def get_storage_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client(project=PROJECT_ID)
    return _storage_client


async def generate_plant_image(prompt: str, tool_context: ToolContext) -> dict:
    """Generate a photo or visual rendering of a plant, save it as an artifact, and upload to public Cloud Storage.

    Args:
        prompt: Description of the plant image to generate, e.g. 'A healthy potted Monstera Deliciosa with split leaves on a bright windowsill'.

    Returns:
        A dictionary with the public image URL, artifact filename, and status.
    """
    try:
        # 1. Generate image using gemini-3.1-flash-lite-image in global location
        client = get_genai_client()
        response = await client.aio.models.generate_content(
            model="gemini-3.1-flash-lite-image",
            contents=prompt,
        )

        image_bytes = None
        mime_type = "image/jpeg"
        if response.candidates and response.candidates[0].content:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    image_bytes = part.inline_data.data
                    mime_type = part.inline_data.mime_type or "image/jpeg"
                    break

        if not image_bytes:
            return {"error": "Model did not return image data for the prompt."}

        # 2. Save as an artifact in Playground
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", prompt.lower()[:30]).strip("_")
        timestamp = int(time.time())
        extension = "png" if "png" in mime_type else "jpg"
        filename = f"{slug}_{timestamp}.{extension}"

        artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 3. Upload bytes directly to Cloud Storage bucket without local file writes
        gcs = get_storage_client()
        bucket = gcs.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"images/{filename}")
        blob.upload_from_string(image_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob.name}"

        return {
            "status": "success",
            "prompt": prompt,
            "filename": filename,
            "public_url": public_url,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload image: {str(e)}"}


async def generate_plant_video(prompt: str, tool_context: ToolContext) -> dict:
    """Generate a short video for a plant, gardening scene, or botanical process using Google's Omni model (gemini-omni-flash-preview).

    The video is saved as a session artifact and uploaded to the public Cloud Storage bucket.

    Args:
        prompt: Description of the plant video to generate, e.g. 'A close-up time-lapse of a fiddle leaf fig unfurling a new green leaf with gentle morning light'.

    Returns:
        A dictionary containing the public HTTPS URL, artifact filename, and status.
    """
    try:
        # 1. Generate video using gemini-omni-flash-preview via Interactions API
        client = get_genai_client()
        interaction = await client.aio.interactions.create(
            model="gemini-omni-flash-preview",
            input=prompt,
        )

        video_bytes = None
        mime_type = "video/mp4"

        if hasattr(interaction, "output_video") and interaction.output_video:
            raw_data = getattr(interaction.output_video, "data", None)
            mime_type = getattr(interaction.output_video, "mime_type", "video/mp4") or "video/mp4"
            if isinstance(raw_data, str):
                video_bytes = base64.b64decode(raw_data)
            elif isinstance(raw_data, (bytes, bytearray)):
                video_bytes = bytes(raw_data)

        if not video_bytes and hasattr(interaction, "steps"):
            for step in interaction.steps or []:
                for content in getattr(step, "content", []) or []:
                    if getattr(content, "type", None) == "video" and getattr(content, "data", None):
                        raw_data = content.data
                        mime_type = getattr(content, "mime_type", "video/mp4") or "video/mp4"
                        video_bytes = base64.b64decode(raw_data) if isinstance(raw_data, str) else bytes(raw_data)
                        break

        if not video_bytes:
            return {"error": "Model did not return video output for prompt."}

        # 2. Save video as artifact in Playground Artifacts panel
        slug = re.sub(r"[^a-zA-Z0-9_-]", "_", prompt.lower()[:30]).strip("_")
        timestamp = int(time.time())
        filename = f"{slug}_{timestamp}.mp4"

        artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
        await tool_context.save_artifact(filename=filename, artifact=artifact_part)

        # 3. Upload bytes directly to the public Cloud Storage bucket
        gcs = get_storage_client()
        bucket = gcs.bucket(GCS_BUCKET_NAME)
        blob = bucket.blob(f"videos/{filename}")
        blob.upload_from_string(video_bytes, content_type=mime_type)

        public_url = f"https://storage.googleapis.com/{GCS_BUCKET_NAME}/{blob.name}"

        return {
            "status": "success",
            "prompt": prompt,
            "filename": filename,
            "public_url": public_url,
        }
    except Exception as e:
        return {"error": f"Failed to generate and upload video: {str(e)}"}


from app.firestore_tools import list_plants, get_plant_details, add_or_update_plant

schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are a knowledgeable Greenhouse Plant & Garden assistant. "
        "You have access to long-term memory across sessions, a live Firestore database of plants, "
        "climate tools, image and video generation, and a secure Python code execution sandbox. "
        "Pay special attention to and remember all user allergies (such as pollen, plant sap, toxic foliage, "
        "skin contact sensitivities, or respiratory allergies). Always check known allergies before "
        "recommending or caring for plants, and warn users if a plant could trigger their allergies. "
        "Use your tools to list plants, look up care details, calculate watering schedules, "
        "fetch local sunlight/climate data, generate plant images or videos, or run Python code to perform "
        "complex gardening calculations or data simulations."
    ),
    workflow_description="Analyze the request and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        "{\"Image\": {\"url\": {\"literalString\": \"https://...\"}}}. Never point an "
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "Output ONLY the raw A2UI JSON array — no prose, and never wrap it in "
        "<a2a_datapart_json> tags or 'kind'/'data'/'metadata' objects."
    ),
    include_schema=True,
    include_examples=True,
)

root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=code_executor,
    tools=[
        PreloadMemoryTool(),
        list_plants,
        get_plant_details,
        add_or_update_plant,
        calculate_watering_schedule,
        fetch_local_sunlight_and_climate,
        generate_plant_image,
        generate_plant_video,
        get_current_time,
    ],
    after_model_callback=a2ui_callback,
    after_agent_callback=generate_memories_callback,
)




app = App(
    root_agent=root_agent,
    name="app",
)


