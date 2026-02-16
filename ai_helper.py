from openai import OpenAI
import os
import base64
from typing import ByteString
from anthropic import Anthropic
import google.generativeai as genai
from google.generativeai import types
import requests

class AIHelper:
    def __init__(self, key: str, model="openai", intelligence=False) -> None:
        self.key = key
        self.model = model
        if self.model == "openai":
            self.client = OpenAI(
            api_key = self.key
          )
            self.model = "gpt-5-mini"
        elif self.model == "openai-big":
            self.client = OpenAI(
            api_key = self.key
          )
            self.model = "gpt-5"
        elif "gpt" in self.model:
            self.client = OpenAI(
                api_key=self.key
            )
        elif self.model == "claude":
            os.environ["ANTHROPIC_API_KEY"] = self.key
            self.client = Anthropic()
        elif self.model == "gemini":
            os.environ["GEMINI_API_KEY"] = self.key
            #self.client = genai.Client(api_key=self.key)
        elif self.model == "grok":
            self.client = OpenAI(
            api_key = self.key,
            base_url="https://api.xai.com/v1"
            )
        if intelligence:
            self.model = "o4-mini"
        #TODO: add model exact_name key to replace the hard coded claude and gemini models

    def encode_image(self, image_path):
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def gemini_wrapper(self, image_data:str, context:str, image_type="png"):
        """This function takes an image path and generates interpretation using Google Gemini"""
        response = self.client.models.generate_content(
            model="gemini-2.0-flash",
            contents=[context, 
            types.Part.from_bytes(data=image_data, mime_type=f"image/{image_type}")])
        return response
        
    def anthropic_wrapper(self, image_data:ByteString, context:str, image_type="png"):
        message = self.client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=8192,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": f"image/{image_type}",
                            "data": image_data,
                        },
                    },
                    {
                    "type": "text",
                    "text": context
                    }
                ],
            }
        ],
        )
        return message
    

    def get_xai_response(self, context, image_type, image_encoded, api_key, temperature=0.7):
        url = "https://api.x.ai/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "messages": [
                {
                  "role": "user",
                  "content": [
        
                    {
                      "type": "image_url",
                      "image_url": {
                        "url": f"data:image/{image_type};base64,{image_encoded}",
                        "detail": "high"
                      },
                    },
                    {"type": "text", "text": context}
                  ],
                }
              ],
            "model": "grok-4-fast-reasoning",
            "stream": False,
            "temperature": temperature
        }
        try:
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()  
            result = response.json()
            print(f"AI Response: {result}")
            return result['choices'][0]['message']['content']
            
        except requests.exceptions.RequestException as e:
            print(f"An error occurred: {e}")
        except KeyError as e:
            print(f"Missing environment variable: {e}")

    def get_image_analysis(self, image_encoded:ByteString, context: str, temperature=1, image_type="png") -> str:
        if self.model == "claude":
            print("Using Claude model for image analysis")
            response = self.anthropic_wrapper(image_encoded, context, image_type)
            print(response)
            return response.content[0].text
        elif self.model == "gemini":
            print("Using Gemini model for image analysis")
            response = self.gemini_wrapper(image_encoded, context, image_type)
            print(response)
            return response
        elif self.model == "grok":
            return self.get_xai_response(context, image_type, image_encoded, self.key, temperature)
        else:
            print(f"Using model {self.model} for image analysis")
            response = self.client.chat.completions.create(
              model= self.model,
              messages=[
                {
                  "role": "user",
                  "content": [
                    {"type": "text", "text": context},
                    {
                      "type": "image_url",
                      "image_url": {
                        "url": f"data:image/{image_type};base64,{image_encoded}",
                        "detail": "high"
                      },
                    },
                  ],
                }
              ],
              max_completion_tokens=15000,
              temperature=temperature if not "gpt-5" in self.model else 1
            )
            response_to_use = response.choices[0]
            print(f"AI Response: {response_to_use}")
            print(f"Entire AI response: {response}")
            return response_to_use.message.content
