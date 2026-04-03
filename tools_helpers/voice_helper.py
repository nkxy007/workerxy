import os
import logging
from google import genai

logger = logging.getLogger(__name__)

class VoiceHelper:
    """Manages Gemini API audio processing for browser-based push-to-talk."""
    def __init__(self, mode="transcription", model="gemini-2.5-flash"):
        """
        mode: 'transcription' (Option B) or 'agent_tool' (Option A - not applicable for simple push-to-talk, but kept for compatibility)
        """
        self.mode = mode
        # Live models aren't supported for static generate_content audio, use standard flash models
        self.model = "gemini-2.5-flash" if "live" in model else model
        
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set")
            
        self.client = genai.Client(
            http_options={"api_version": "v1beta"},
            api_key=api_key
        )

    async def process_audio(self, audio_bytes: bytes) -> str:
        """Transcribes the provided audio bytes using Gemini."""
        try:
            logger.info("Sending audio to Gemini for transcription...")
            # Google GenAI SDK requires types.Part for byte data
            from google.genai import types
            audio_part = types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav")
            
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    audio_part, 
                    "Transcribe exactly what the user is saying. Do not add any conversational filler. Only return the transcribed text."
                ]
            )
            transcription = response.text
            if transcription:
                return transcription.strip()
            return ""
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}", exc_info=True)
            return f"Error transcribing audio: {e}"
