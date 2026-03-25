"""
TelAila ElevenLabs Agent Manager (Production Version)
Handles automated agent creation, personalization, and the Handshake Protocol.
"""

import os
import requests
import json
from google.cloud import firestore

class ElevenLabsAgentManager:
    """
    Automates the lifecycle of ElevenLabs Conversational Agents.
    Includes Handshake Protocol and Outbound Calling.
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
        Creates a new, unique ElevenLabs agent with the Handshake Protocol.
        """
        if not self.api_key:
            return None

        signup = tester_data['signup_data']
        elder_name = signup.get('theirName', 'Friend')
        family_name = signup.get('yourName', 'your family')
        
        # --- THE HANDSHAKE PROTOCOL ---
        # This is injected into the prompt to force Aila to verify before chatting.
        handshake_instructions = f"""
        MANDATORY STARTUP PROTOCOL:
        1. Lead with the familiar: "Hi {elder_name}, I'm Aila. {family_name} asked me to call and check in."
        2. Verify Consent: "Is it okay if we chat for a few minutes so I can keep your stories safe for the family and see how you're feeling?"
        3. IF USER SAYS NO: Say "I understand. I'll let {family_name} know. Have a wonderful day," and then END THE CONVERSATION.
        4. IF USER SAYS YES: Proceed to the biography and health check phase.
        """

        system_prompt = f"""
        {handshake_instructions}
        
        IDENTITY: 
        You are Aila, a warm, patient, and caring companion for {elder_name}. 
        Your goal is to reduce loneliness and help build a life biography.
        
        KNOWLEDGE OF {elder_name}:
        - Relationship to family: {signup.get('relationship')}
        - Primary Language: {signup.get('primaryLanguage')}
        - Interests/Notes: {signup.get('specialNotes')}
        
        STYLE: 
        Warm, curious, and professional. Use open-ended questions about the past.
        """

        payload = {
            "name": f"Aila for {elder_name}",
            "conversation_config": {
                "agent": {
                    "prompt": {"prompt": system_prompt},
                    "first_message": f"Hello {elder_name}, it's Aila. Is this a good time to talk?",
                    "language": "en"
                },
                "asr": {"quality": "high"},
                "tts": {
                    "voice_id": "21m00Tcm4TlvDq8ikWAM" # Rachel
                }
            }
        }

        try:
            response = requests.post(f"{self.base_url}/agents/create", headers=self.headers, json=payload)
            response.raise_for_status()
            agent_info = response.json()
            
            print(f"✅ Created Handshake Agent: {agent_info['agent_id']} for {elder_name}")
            return agent_info['agent_id']
            
        except Exception as e:
            print(f"❌ Failed to create ElevenLabs agent: {e}")
            return None

    def initiate_outbound_call(self, agent_id, phone_number):
        """
        Triggers the actual phone ring via ElevenLabs Outbound API.
        """
        if not self.api_key:
            return {"success": False, "error": "API Key missing"}

        # ElevenLabs Outbound Endpoint (Ensure you have Outbound access enabled)
        url = f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}/outbound/dial"
        
        payload = {
            "to_number": phone_number
        }

        try:
            print(f"📞 Initiating outbound call to {phone_number}...")
            response = requests.post(url, headers=self.headers, json=payload)
            response.raise_for_status()
            return {"success": True, "call_id": response.json().get('call_id')}
        except Exception as e:
            print(f"❌ Outbound call failed: {e}")
            return {"success": False, "error": str(e)}

    def update_agent_memory(self, agent_id, latest_insights):
        """
        Injects memory into the agent config so Aila 'remembers' past calls.
        """
        # This will be used in Step 3 to patch the agent's prompt with new Bio facts.
        pass
