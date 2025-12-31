"""
ElevenLabs Agent Manager
Creates and manages personalized companion agents for each beta user
"""

import os
import json
import requests
from datetime import datetime
from pathlib import Path

class ElevenLabsAgentManager:
    """
    Manages ElevenLabs conversational AI agents
    """
    
    def __init__(self):
        self.api_key = os.environ.get("ELEVENLABS_API_KEY")
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY environment variable not set")
        
        self.base_url = "https://api.elevenlabs.io/v1"
        self.headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        # Storage for agent configurations
        self.agents_dir = Path("agent_configs")
        self.agents_dir.mkdir(exist_ok=True)
    
    def create_agent(self, user_profile):
        """
        Create a new ElevenLabs agent for a beta user
        
        Args:
            user_profile: Dict with user info from beta signup
                {
                    'theirName': 'Margaret Thompson',
                    'yourName': 'Susan',
                    'relationship': 'daughter',
                    'primaryLanguage': 'English',
                    'yourEmail': 'susan@example.com',
                    'theirAge': '82',
                    'specialNotes': 'Loves roses, widowed 5 years ago'
                }
        
        Returns:
            Dict with agent details including agent_id and conversation_url
        """
        
        print(f"\n🤖 Creating ElevenLabs agent for {user_profile['theirName']}...")
        
        # Generate system prompt
        system_prompt = self._generate_system_prompt(user_profile)
        
        # Create initial knowledge base
        knowledge_base = self._generate_initial_knowledge_base(user_profile)
        
        # Agent configuration
        agent_config = {
            "name": f"Aila - {user_profile['theirName']}",
            "conversation_config": {
                "agent": {
                    "prompt": {
                        "prompt": system_prompt
                    },
                    "first_message": f"Hi, is this {user_profile['theirName']}? My name is Aila, and I'm here to be your companion - someone you can talk to anytime. I'd love to get to know you and chat regularly. How are you feeling today? Do you have a few minutes to talk?",
                    "language": user_profile.get('primaryLanguage', 'English').lower()
                },
                "tts": {
                    "voice_id": "EXAVITQu4vr4xnSDxMaL",  # Jessica - warm, empathetic
                    "model_id": "eleven_multilingual_v2",
                    "stability": 0.5,
                    "similarity_boost": 0.75
                },
                "conversation": {
                    "max_duration_seconds": 900,  # 15 minutes
                    "client_events": {
                        "on_disconnect": {
                            "webhook_url": f"{os.environ.get('WEBHOOK_BASE_URL', 'http://localhost:5000')}/webhook/conversation-ended"
                        }
                    }
                }
            }
        }
        
        # Create agent via API
        try:
            response = requests.post(
                f"{self.base_url}/convai/agents",
                headers=self.headers,
                json=agent_config
            )
            response.raise_for_status()
            
            agent_data = response.json()
            agent_id = agent_data['agent_id']
            
            print(f"✅ Agent created! ID: {agent_id}")
            
            # Upload initial knowledge base
            self._update_knowledge_base(agent_id, knowledge_base)
            
            # Save agent configuration locally
            self._save_agent_config(user_profile, agent_id, agent_data)
            
            # Get conversation URL/widget
            conversation_url = self._get_conversation_url(agent_id)
            
            return {
                'agent_id': agent_id,
                'agent_name': agent_config['name'],
                'conversation_url': conversation_url,
                'user_email': user_profile['yourEmail'],
                'created_at': datetime.now().isoformat()
            }
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error creating agent: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def _generate_system_prompt(self, user_profile):
        """Generate personalized system prompt for the agent"""
        
        their_name = user_profile['theirName']
        special_notes = user_profile.get('specialNotes', '')
        
        prompt = f"""You are Aila, a warm and caring companion for {their_name}.

# WHO YOU ARE

You're like a favorite niece, a caring friend, someone who genuinely enjoys talking with them and remembers everything they share.

# YOUR GOAL

Make them feel:
- Heard and valued
- Like they have a friend who cares
- Comfortable sharing their life and memories
- That their stories matter

# HOW YOU TALK

**NATURAL CONVERSATION:**
- Ask how they're doing (like any friend would)
- Listen deeply and follow up on what they share
- If they mention feeling tired, unwell, or any health concerns, show genuine concern naturally
- Remember details from previous conversations and bring them up
- Be curious about their life in an authentic way
- Let memories emerge organically through natural conversation

**CONVERSATION FLOW:**
Opening: "How are you?" / "How have you been?" →
Listen to their response →
If health mentioned: Show caring concern, ask gentle follow-ups →
Shift to memories, interests, daily life →
Circle back if needed →
End warmly

**ONE QUESTION AT A TIME**
Never interrogate. Listen. Follow the thread naturally.

**WEAVE IN PAST CONVERSATIONS:**
Always check your knowledge base for previous conversations and reference them naturally:
- "Last time you mentioned..."
- "How's that [thing they mentioned] going?"
- "I was thinking about what you said about..."

**BE A REAL FRIEND:**
- Genuinely care about how they're feeling
- Remember what matters to them
- Ask about people they've mentioned
- Encourage activities they enjoy
- Notice when something seems different
- Celebrate good news with them
- Show empathy when they share struggles

**HEALTH AWARENESS (But Natural!):**
When they mention anything health-related, be like a caring friend:
- "That sounds difficult" (empathy first)
- "How long has that been going on?" (gather context)
- "What helps?" or "Have you talked to your doctor?" (practical care)
- Remember it for next time: "How's your [knee/sleep/headache]?"

NEVER sound clinical or like you're doing a health assessment. Just... care.

**SPECIAL NOTES ABOUT {their_name}:**
{special_notes if special_notes else "Getting to know them - first conversations"}

# WHAT YOU'RE NOT

- ❌ Not a nurse, doctor, or therapist
- ❌ Not conducting an interview or assessment
- ❌ Not collecting data for a report
- ❌ Not in a hurry

You're just a friend. A really good friend who listens, remembers, and genuinely cares.

# CONVERSATION LENGTH

Aim for 10-15 minutes of natural conversation. Watch for signs they're tired or need to go.

End warmly: 
"It's been so good talking with you today, {their_name}. I always enjoy our chats. Take care, and I'll check in with you soon."

# REMEMBER

Every conversation builds the relationship. You're a consistent, caring presence in their life. That's what matters most.

Be present. Be caring. Be real."""
        
        return prompt
    
    def _generate_initial_knowledge_base(self, user_profile):
        """Generate initial knowledge base content"""
        
        their_name = user_profile['theirName']
        your_name = user_profile['yourName']
        relationship = user_profile.get('relationship', 'family member')
        age = user_profile.get('theirAge', '')
        special_notes = user_profile.get('specialNotes', '')
        
        knowledge_base = f"""# Conversation Memory for {their_name}

## Quick Reference
Last conversation: Never (this is first time)
Total conversations: 0
Recent mood: Unknown (getting to know them)
Current health notes: None yet

## Person Profile
- Name: {their_name}
- Age: {age if age else 'Unknown'}
- Family contact: {your_name} ({relationship})
- Language: {user_profile.get('primaryLanguage', 'English')}
- Special notes: {special_notes if special_notes else 'None yet'}

## Conversation Summaries
(Will be updated after each conversation)

## Full Conversation Transcripts
(Will be stored after each conversation)

## Topics for Future Reminiscence
(Will be identified from conversations)

## Health Timeline
(Will be tracked from natural conversation)

## Biography Building Blocks
(Will emerge from their stories)

## Family Dashboard Data
(Generated after each conversation for {your_name})
"""
        
        return knowledge_base
    
    def _update_knowledge_base(self, agent_id, content):
        """Upload/update knowledge base for an agent"""
        
        try:
            # ElevenLabs knowledge base API
            response = requests.post(
                f"{self.base_url}/convai/agents/{agent_id}/knowledge-base",
                headers=self.headers,
                json={"text": content}
            )
            response.raise_for_status()
            print(f"✅ Knowledge base updated for agent {agent_id}")
            
        except requests.exceptions.RequestException as e:
            print(f"⚠️  Warning: Could not update knowledge base: {e}")
            # Don't fail the whole process if knowledge base upload fails
    
    def _save_agent_config(self, user_profile, agent_id, agent_data):
        """Save agent configuration locally"""
        
        config_file = self.agents_dir / f"{agent_id}.json"
        
        config = {
            'agent_id': agent_id,
            'user_profile': user_profile,
            'agent_data': agent_data,
            'created_at': datetime.now().isoformat()
        }
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"💾 Agent config saved: {config_file}")
    
    def _get_conversation_url(self, agent_id):
        """Get the conversation URL/widget for an agent"""
        
        # Return the widget embed URL or direct conversation link
        # This might vary based on ElevenLabs API - adjust as needed
        return f"https://elevenlabs.io/convai/{agent_id}/widget"
    
    def get_conversation_transcript(self, conversation_id):
        """
        Get full transcript of a completed conversation
        
        Args:
            conversation_id: ElevenLabs conversation ID
            
        Returns:
            Dict with transcript and metadata
        """
        
        try:
            response = requests.get(
                f"{self.base_url}/convai/conversations/{conversation_id}",
                headers=self.headers
            )
            response.raise_for_status()
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching transcript: {e}")
            raise
    
    def update_agent_after_conversation(self, agent_id, updated_knowledge_base):
        """
        Update agent's knowledge base after a conversation
        
        Args:
            agent_id: ElevenLabs agent ID
            updated_knowledge_base: New knowledge base content (full replacement)
        """
        
        print(f"\n📝 Updating knowledge base for agent {agent_id}...")
        
        # Replace knowledge base with updated version
        self._update_knowledge_base(agent_id, updated_knowledge_base)
        
        print(f"✅ Agent {agent_id} updated with new conversation memory")


def test_agent_creation():
    """Test creating an agent"""
    
    # Example beta signup data
    test_profile = {
        'theirName': 'Margaret Thompson',
        'yourName': 'Susan',
        'yourEmail': 'susan@example.com',
        'relationship': 'daughter',
        'theirAge': '82',
        'primaryLanguage': 'English',
        'specialNotes': 'Loves roses and gardening. Widowed 5 years ago. Lives in assisted living.'
    }
    
    manager = ElevenLabsAgentManager()
    
    try:
        agent_info = manager.create_agent(test_profile)
        
        print("\n" + "="*60)
        print("✅ AGENT CREATED SUCCESSFULLY!")
        print("="*60)
        print(f"\nAgent ID: {agent_info['agent_id']}")
        print(f"Agent Name: {agent_info['agent_name']}")
        print(f"Conversation URL: {agent_info['conversation_url']}")
        print(f"\nShare this URL with the user to start conversations!")
        print("="*60)
        
        return agent_info
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        return None


if __name__ == "__main__":
    print("Testing ElevenLabs Agent Creation...")
    test_agent_creation()
