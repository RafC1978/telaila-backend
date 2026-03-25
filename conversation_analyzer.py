"""
TelAila Conversation Analyzer (Production Version)
Uses Google Vertex AI to extract insights and updates Firestore directly.
"""

import json
import os
from datetime import datetime
from google.cloud import firestore
import vertexai
from vertexai.generative_models import GenerativeModel

class ConversationAnalyzer:
    """
    The 'Brain' that extracts health data, biography snippets, and dashboard updates.
    """
    
    def __init__(self, project_id="telaila", location="northamerica-northeast1"):
        # Initialize Vertex AI
        vertexai.init(project=project_id, location=location)
        self.model = GenerativeModel("gemini-1.5-pro")
        self.db = firestore.Client()

    def analyze_and_save(self, beta_id, transcript, elder_name):
        """
        The Master Workflow: Analyze the text and distribute results to the vault.
        """
        print(f"🧠 Analyzing session for {elder_name} ({beta_id})...")
        
        # 1. Get the Analysis from Gemini
        analysis = self._run_ai_analysis(transcript, elder_name)
        
        if not analysis:
            return False

        # 2. Update Firestore Collections
        # We store these in sub-collections for the specific user
        user_ref = self.db.collection("testers").document(beta_id)
        
        # Save Full Conversation
        user_ref.collection("conversations").add({
            "timestamp": datetime.now().isoformat(),
            "transcript": transcript,
            "summary": analysis['conversation']['mood'],
            "topics": analysis['conversation']['topics']
        })

        # Save Health Data Point
        user_ref.collection("health_logs").add({
            "timestamp": datetime.now().isoformat(),
            "mood": analysis['health']['mood'],
            "energy": analysis['health']['energy'],
            "red_flags": analysis['health']['red_flags'],
            "summary": analysis['health']['summary']
        })

        # Save Biography Snippets
        for story in analysis['biography']['stories']:
            user_ref.collection("biography").add({
                "type": "story",
                "content": story,
                "extracted_at": datetime.now().isoformat()
            })

        # 3. Update the Main Dashboard Status
        user_ref.update({
            "last_conversation": datetime.now().isoformat(),
            "conversation_count": firestore.Increment(1),
            "current_health_status": analysis['family_dashboard']['health_summary']
        })

        print(f"✅ Vault updated for {beta_id}")
        return analysis

    def _run_ai_analysis(self, transcript, elder_name):
        """
        Internal call to Gemini 1.5 Pro.
        """
        prompt = f"""
        Analyze this conversation between Aila (AI) and {elder_name}.
        TRANSCRIPT: {transcript}
        
        Return a JSON object with:
        1. health: {{pain, sleep, energy, mood, red_flags, summary}}
        2. biography: {{stories, people, places}}
        3. conversation: {{mood, topics, follow_ups}}
        4. family_dashboard: {{health_summary, notable_moments, recommendations}}
        
        Output MUST be pure JSON.
        """
        
        try:
            response = self.model.generate_content(prompt)
            # Clean the response text (remove ```json wrappers)
            clean_json = response.text.replace('```json', '').replace('```', '').strip()
            return json.loads(clean_json)
        except Exception as e:
            print(f"❌ AI Analysis failed: {e}")
            return None
