"""
TelAila ElevenLabs Agent Manager (Production Version)
Handles automated agent creation, personalization, and memory injection.
"""

import os
import requests
import json
from google.cloud import firestore

class ElevenLabsAgentManager:
    """
    Automates the lifecycle of ElevenLabs Conversational Agents.
    """
    
    def __init__(self):
        # Retrieve the API key from the environment (Secret Manager)
        self.api_key = os.environ.get('ELEVENLABS_API_KEY')
        self.base_url = "https://api.elevenlabs.io/v1/convai"
        self.headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        if not self.api_key:
            print("⚠️ ELEVENLABS_API_KEY is missing. Check Secret Manager/Cloud Run env vars.")

    def create_personalized_agent(self, tester_data):
        """
        Creates a new, unique ElevenLabs agent for a specific elder.
        """
        if not self.api_key:
            return None

        signup = tester_data['signup_data']
        elder_name = signup.get('theirName', 'Friend')
        
        # This is the "Soul" of the agent. We build it dynamically.
        system_prompt = f"""
        You are Aila, a caring and patient companion for {elder_name}. 
        Your goal is to reduce loneliness and help build a life biography.
        
        Context about {elder_name}:
        - Relationship to family: {signup.get('relationship')}
        - Primary Language: {signup.get('primaryLanguage')}
        - Interests/Notes: {signup.get('specialNotes')}
        
        Style: Warm, curious, and professional. 
        Ask open-ended questions about their past to help build their biography.
        """

        payload = {
            "name": f"Aila for {elder_name}",
            "conversation_config": {
                "agent": {
                    "prompt": {"prompt": system_prompt},
                    "first_message": f"Hi {elder_name}, it's Aila. I was just thinking about you and wanted to see how your day is going.",
                    "language": "en"
                },
                "asr": {"quality": "high"},
                "tts": {
                    "voice_id": "21m00Tcm4TlvDq8ikWAM" # Example: 'Rachel' voice. Swap for your preferred ID.
                }
            }
        }

        try:
            response = requests.post(f"{self.base_url}/agents/create", headers=self.headers, json=payload)
            response.raise_for_status()
            agent_info = response.json()
            
            print(f"✅ Created ElevenLabs Agent: {agent_info['agent_id']} for {elder_name}")
            return agent_info['agent_id']
            
        except Exception as e:
            print(f"❌ Failed to create ElevenLabs agent: {e}")
            return None

    def update_agent_memory(self, agent_id, latest_insights):
        """
        Injects new biography snippets or health notes into the agent's prompt
        before the next scheduled call.
        """
        # 1. Fetch the current agent config
        # 2. Append 'latest_insights' to the system prompt
        # 3. PATCH the agent back to ElevenLabs
        # This ensures Aila "remembers" things from the last call.
        pass

    def initiate_outbound_call(self, agent_id, phone_number):
        """
        Triggers the ElevenLabs outbound dialer.
        """
        payload = {
            "agent_id": agent_id,
            "to_number": phone_number
        }
        # Note: This requires ElevenLabs Outbound API access
        # response = requests.post(f"{self.base_url}/outbound", headers=self.headers, json=payload)
        pass
