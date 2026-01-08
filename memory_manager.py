"""
Memory Manager - Tiered Memory System for TelAila
Handles efficient memory storage and retrieval to keep costs low and latency fast
"""

import anthropic
import os
from datetime import datetime

class MemoryManager:
    """
    Manages three-tier memory system:
    1. Core Facts (permanent profile)
    2. Recent Context (last 3 conversations)
    3. Historical Summary (compressed old conversations)
    """
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        self.max_kb_chars = 15000  # Trigger summarization at 15k chars
        self.sessions_to_keep_full = 3  # Keep last 3 sessions in full detail
    
    def should_compress(self, knowledge_base):
        """Check if knowledge base needs compression"""
        return len(knowledge_base) > self.max_kb_chars
    
    def compress_knowledge_base(self, knowledge_base, user_name):
        """
        Compress old sessions while keeping recent ones and core facts
        
        This is the KEY cost optimization:
        - Keeps last 3 sessions in full detail
        - Compresses older sessions into bullet points
        - Extracts and preserves core facts
        """
        
        print(f"\n🗜️  Compressing knowledge base for {user_name}...")
        print(f"   Current size: {len(knowledge_base)} chars")
        
        prompt = f"""You are compressing a conversation memory database to save tokens while preserving important information.

CURRENT KNOWLEDGE BASE (too large, needs compression):
{knowledge_base}

YOUR TASK:
Create a compressed version that:

1. CORE FACTS SECTION (Always preserve):
   - Name, age, family relationships
   - Location, interests, hobbies
   - Health conditions (chronic or important)
   - Deceased loved ones
   - Career/life background
   - Key personality traits

2. RECENT SESSIONS (Keep last 3 in full detail):
   - Keep the most recent 3 sessions word-for-word
   - These provide immediate context

3. HISTORICAL SUMMARY (Compress older sessions):
   - Compress sessions 4+ into bullet points
   - Group by theme: health timeline, family events, interests discussed
   - Keep memorable quotes
   - Track mood patterns

TARGET SIZE: ~8,000-10,000 characters
PRESERVE: All important facts, just remove redundancy and verbosity

Return the compressed knowledge base in the same markdown format."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=8000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            compressed_kb = response.content[0].text
            
            print(f"   ✅ Compressed to: {len(compressed_kb)} chars")
            print(f"   💰 Savings: {len(knowledge_base) - len(compressed_kb)} chars per conversation")
            
            return compressed_kb
            
        except Exception as e:
            print(f"   ❌ Compression failed: {e}")
            print(f"   ⚠️  Keeping original (will retry next time)")
            return knowledge_base
    
    def extract_core_facts(self, knowledge_base, user_name):
        """
        Extract permanent core facts for Tier 1 memory
        This creates a compact "profile" that's always loaded
        """
        
        prompt = f"""Extract the CORE PERMANENT FACTS about this person from their conversation history.

KNOWLEDGE BASE:
{knowledge_base}

Extract ONLY facts that are:
- Permanent (won't change conversation-to-conversation)
- Essential for context (who they are, family, interests)
- Important health conditions (chronic, not temporary)

Return in this EXACT format:

# Core Profile - {user_name}
- Name: [name], age [age]
- Family: [key family members and relationships]
- Location: [where they live]
- Interests: [main hobbies/passions]
- Health: [chronic conditions only]
- Important people: [deceased loved ones, close relationships]
- Personality: [2-3 key traits]
- Career/Background: [brief summary if known]

Keep it under 500 characters. Be concise."""

        try:
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=1000,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            core_facts = response.content[0].text
            return core_facts
            
        except Exception as e:
            print(f"❌ Core facts extraction failed: {e}")
            return f"# Core Profile - {user_name}\n- Name: {user_name}\n"
    
    def get_recent_sessions(self, knowledge_base, count=3):
        """
        Extract the most recent N sessions from knowledge base
        Used for Tier 2 (recent context)
        """
        
        # Split by session markers
        sessions = knowledge_base.split('### Session')
        
        # Get last N sessions (they'll have 'Session N' prefix)
        recent = []
        for session in sessions[-count:]:
            if session.strip():
                recent.append('### Session' + session)
        
        return '\n\n'.join(recent)
    
    def build_optimized_context(self, knowledge_base, user_name):
        """
        Build optimized context for agent (Tier 1 + Tier 2 only)
        This is what gets sent to ElevenLabs agent
        
        COST OPTIMIZATION: Instead of sending 20k tokens, send 2-3k tokens
        """
        
        # Extract core facts (Tier 1)
        core_facts = self.extract_core_facts(knowledge_base, user_name)
        
        # Get recent sessions (Tier 2)
        recent_sessions = self.get_recent_sessions(knowledge_base, count=self.sessions_to_keep_full)
        
        # Combine into optimized context
        optimized_context = f"""{core_facts}

---

## Recent Conversations
{recent_sessions}

---

_Note: Additional historical context available if needed. Ask about specific topics._
"""
        
        return optimized_context
    
    def manage_knowledge_base(self, knowledge_base, user_name):
        """
        Main entry point: manage knowledge base efficiently
        
        Returns:
            - updated_kb: Compressed if needed
            - should_update: Whether to save changes
        """
        
        # Check if compression needed
        if self.should_compress(knowledge_base):
            print(f"📊 Knowledge base is {len(knowledge_base)} chars (threshold: {self.max_kb_chars})")
            compressed_kb = self.compress_knowledge_base(knowledge_base, user_name)
            return compressed_kb, True
        else:
            print(f"✅ Knowledge base size OK ({len(knowledge_base)} chars)")
            return knowledge_base, False
