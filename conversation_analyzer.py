"""
Conversation Analyzer
Processes completed conversations to extract health data, 
build biography content, and generate family updates
"""

import json
import re
from datetime import datetime
from anthropic import Anthropic
import os

class ConversationAnalyzer:
    """
    Analyzes conversation transcripts to extract:
    - Health indicators
    - Biography content
    - Topics for reminiscence
    - Family dashboard data
    """
    
    def __init__(self):
        self.client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    
    def analyze_conversation(self, transcript, user_name, existing_knowledge_base=""):
        """
        Analyze a complete conversation transcript
        
        Args:
            transcript: Full conversation text or structured transcript
            user_name: Name of the person
            existing_knowledge_base: Previous knowledge base content
            
        Returns:
            Dict with analysis results
        """
        
        print(f"\n🔍 Analyzing conversation for {user_name}...")
        
        # Use Claude to analyze the conversation
        analysis_prompt = f"""Analyze this conversation between Aila (AI companion) and {user_name}.

CONVERSATION TRANSCRIPT:
{transcript}

Extract the following information:

1. HEALTH INDICATORS:
   - Any mentions of pain, discomfort, illness (with location, severity 1-5 if mentioned)
   - Sleep patterns (bedtime, wake time, quality, issues)
   - Appetite and eating (meals eaten, appetite level, digestive issues)
   - Energy levels (1-5 scale or descriptive)
   - Mood indicators (positive, negative, neutral with context)
   - Medications mentioned
   - Doctor visits or medical appointments
   - Mobility or fall concerns
   - Bathroom/urinary issues if mentioned
   - Any RED FLAG concerns (chest pain, severe symptoms, suicidal thoughts, falls)
   - IMPORTANT: DO NOT flag technical issues as health concerns (AI repetition, glitches, connectivity problems, system errors are NOT health red flags)

2. BIOGRAPHY CONTENT:
   - Life stories shared (with full details and quotes)
   - Sensory details (colors, smells, sounds, sights)
   - Important people mentioned (names, relationships)
   - Places lived or visited
   - Career/work history
   - Hobbies and interests
   - Significant life events

3. CONVERSATION QUALITY:
   - Overall mood during conversation
   - Engagement level (high/moderate/low)
   - Topics discussed
   - Memorable quotes (exact wording)
   - Follow-up items for next conversation

4. FAMILY INSIGHTS:
   - Anything family should know
   - Concerns or needs identified (ONLY real health/wellbeing concerns, NOT technical issues)
   - Positive moments to share
   - Recommended actions
   - NOTE: Do not flag AI/technical issues (repetition, glitches, errors) as concerns

Return your analysis as VALID JSON ONLY. No markdown, no code blocks, no comments.

Use this exact structure:
{{
  "health": {{
    "pain": [],
    "sleep": {{}},
    "appetite": {{}},
    "energy": "",
    "mood": "",
    "medications": [],
    "red_flags": [],
    "summary": ""
  }},
  "biography": {{
    "stories": [],
    "sensory_details": [],
    "people": [],
    "timeline_events": []
  }},
  "conversation": {{
    "mood": "",
    "engagement": "",
    "topics": [],
    "memorable_quotes": [],
    "follow_ups": []
  }},
  "family_dashboard": {{
    "health_summary": "",
    "notable_moments": [],
    "concerns": [],
    "recommendations": []
  }}
}}

CRITICAL: Return ONLY the JSON object above. No explanation, no code blocks, no comments.
Be thorough but accurate. Only include what was actually mentioned in the conversation."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": analysis_prompt
                }]
            )
            
            # Extract JSON from response
            analysis_text = response.content[0].text.strip()
            
            # Remove markdown code blocks if present
            if analysis_text.startswith("```json"):
                analysis_text = analysis_text[7:]
            elif analysis_text.startswith("```"):
                analysis_text = analysis_text[3:]
            
            if analysis_text.endswith("```"):
                analysis_text = analysis_text[:-3]
            
            # Remove any trailing/leading whitespace
            analysis_text = analysis_text.strip()
            
            # Try to parse JSON
            try:
                analysis = json.loads(analysis_text)
            except json.JSONDecodeError as je:
                print(f"⚠️  JSON parsing error: {je}")
                print(f"   First 200 chars of response: {analysis_text[:200]}")
                # Try to extract JSON if it's embedded in text
                json_match = re.search(r'\{.*\}', analysis_text, re.DOTALL)
                if json_match:
                    analysis = json.loads(json_match.group(0))
                else:
                    raise je
            
            print("✅ Conversation analyzed")
            
            return analysis
            
        except Exception as e:
            print(f"⚠️  Error analyzing conversation: {e}")
            # Return minimal analysis if Claude fails
            return self._create_minimal_analysis(transcript, user_name)
    
    def _create_minimal_analysis(self, transcript, user_name):
        """Create basic analysis if AI analysis fails"""
        return {
            "health": {
                "summary": "Unable to analyze - review transcript manually",
                "red_flags": []
            },
            "biography": {
                "stories": [],
                "people": []
            },
            "conversation": {
                "mood": "neutral",
                "engagement": "moderate",
                "topics": [],
                "memorable_quotes": [],
                "follow_ups": []
            },
            "family_dashboard": {
                "health_summary": "Conversation completed - manual review needed",
                "notable_moments": [],
                "concerns": [],
                "recommendations": ["Review full transcript"]
            }
        }
    
    def update_knowledge_base(self, existing_kb, transcript, analysis, user_name):
        """
        Update knowledge base with new conversation data
        
        Args:
            existing_kb: Current knowledge base content
            transcript: Full conversation transcript
            analysis: Analysis results from analyze_conversation()
            user_name: Person's name
            
        Returns:
            Updated knowledge base content
        """
        
        print(f"\n📝 Updating knowledge base for {user_name}...")
        
        # Parse existing KB to get conversation count
        conversation_number = self._get_conversation_count(existing_kb) + 1
        
        # Build new session entry
        session_date = datetime.now().strftime("%B %d, %Y")
        session_time = datetime.now().strftime("%I:%M %p")
        
        # Create comprehensive session summary
        session_summary = f"""
### Session {conversation_number} - {session_date}

**Time:** {session_time}
**Duration:** Approx 10-15 minutes
**Overall mood:** {analysis['conversation']['mood']}
**Engagement:** {analysis['conversation']['engagement']}

**Topics discussed:**
{chr(10).join(f"- {topic}" for topic in analysis['conversation']['topics'])}

**Health notes:**
{analysis['health']['summary']}

**Memorable quotes:**
{chr(10).join(f'- "{quote}"' for quote in analysis['conversation']['memorable_quotes'][:3])}

**Follow-up items for next conversation:**
{chr(10).join(f"- {item}" for item in analysis['conversation']['follow_ups'])}

---

"""
        
        # Full transcript section
        full_transcript = f"""
### Session {conversation_number} - {session_date} (Full Transcript)

{transcript}

---

"""
        
        # Add to appropriate sections
        updated_kb = existing_kb
        
        # Update Quick Reference
        updated_kb = re.sub(
            r"Last conversation:.*?\n",
            f"Last conversation: {session_date}\n",
            updated_kb
        )
        updated_kb = re.sub(
            r"Total conversations:.*?\n",
            f"Total conversations: {conversation_number}\n",
            updated_kb
        )
        updated_kb = re.sub(
            r"Recent mood:.*?\n",
            f"Recent mood: {analysis['conversation']['mood']}\n",
            updated_kb
        )
        updated_kb = re.sub(
            r"Current health notes:.*?\n",
            f"Current health notes: {analysis['health']['summary']}\n",
            updated_kb
        )
        
        # Add session summary
        summary_section_marker = "## Conversation Summaries"
        
        if summary_section_marker in updated_kb:
            # Find the position of the next section
            summary_section_start = updated_kb.find(summary_section_marker)
            
            # Look for the next ## section after Conversation Summaries
            next_section_start = updated_kb.find("\n## ", summary_section_start + len(summary_section_marker))
            
            if next_section_start == -1:
                # No next section, append to end
                updated_kb = updated_kb.rstrip() + "\n\n" + session_summary
            else:
                # Insert before the next section
                # Remove any placeholder text first
                section_content = updated_kb[summary_section_start:next_section_start]
                if "(Will be updated after each conversation)" in section_content:
                    # Remove placeholder
                    updated_kb = updated_kb.replace(
                        "## Conversation Summaries\n(Will be updated after each conversation)\n",
                        "## Conversation Summaries\n"
                    )
                    # Re-find next section position
                    summary_section_start = updated_kb.find(summary_section_marker)
                    next_section_start = updated_kb.find("\n## ", summary_section_start + len(summary_section_marker))
                
                # Insert new summary
                updated_kb = (
                    updated_kb[:next_section_start] + 
                    "\n" + session_summary + 
                    updated_kb[next_section_start:]
                )
        else:
            # Section doesn't exist, add it
            updated_kb += f"\n\n{summary_section_marker}\n\n{session_summary}"
        
        # Add full transcript
        # Find where to insert the new transcript
        transcript_section_marker = "## Full Conversation Transcripts"
        
        if transcript_section_marker in updated_kb:
            # Find the position of the next section (or end of file)
            transcript_section_start = updated_kb.find(transcript_section_marker)
            
            # Look for the next ## section after Full Conversation Transcripts
            next_section_start = updated_kb.find("\n## ", transcript_section_start + len(transcript_section_marker))
            
            if next_section_start == -1:
                # No next section, append to end
                updated_kb = updated_kb.rstrip() + "\n\n" + full_transcript
            else:
                # Insert before the next section
                updated_kb = (
                    updated_kb[:next_section_start] + 
                    "\n" + full_transcript + 
                    updated_kb[next_section_start:]
                )
        else:
            # Section doesn't exist, add it
            updated_kb += f"\n\n{transcript_section_marker}\n\n{full_transcript}"
        
        # Add biography content
        if analysis['biography']['stories']:
            biography_section = f"\n**Session {conversation_number} Stories:**\n"
            for story in analysis['biography']['stories'][:3]:
                biography_section += f"- {story}\n"
            
            biography_marker = "## Biography Building Blocks"
            
            if biography_marker in updated_kb:
                # Find position of next section
                bio_section_start = updated_kb.find(biography_marker)
                next_section_start = updated_kb.find("\n## ", bio_section_start + len(biography_marker))
                
                # Remove placeholder if it exists
                if "(Will emerge from their stories)" in updated_kb:
                    updated_kb = updated_kb.replace(
                        "## Biography Building Blocks\n(Will emerge from their stories)\n",
                        "## Biography Building Blocks\n"
                    )
                    # Re-find positions
                    bio_section_start = updated_kb.find(biography_marker)
                    next_section_start = updated_kb.find("\n## ", bio_section_start + len(biography_marker))
                
                if next_section_start == -1:
                    # Append to end
                    updated_kb = updated_kb.rstrip() + "\n" + biography_section
                else:
                    # Insert before next section
                    updated_kb = (
                        updated_kb[:next_section_start] + 
                        "\n" + biography_section + 
                        updated_kb[next_section_start:]
                    )
            else:
                updated_kb += f"\n\n{biography_marker}\n{biography_section}"
        
        # Add topics for reminiscence
        if analysis['conversation']['follow_ups']:
            topics_section = f"\n**Session {conversation_number} Topics:**\n"
            for item in analysis['conversation']['follow_ups']:
                topics_section += f"- {item}\n"
            
            topics_marker = "## Topics for Future Reminiscence"
            
            if topics_marker in updated_kb:
                # Find position of next section
                topics_section_start = updated_kb.find(topics_marker)
                next_section_start = updated_kb.find("\n## ", topics_section_start + len(topics_marker))
                
                # Remove placeholder if exists
                if "(Will be identified from conversations)" in updated_kb:
                    updated_kb = updated_kb.replace(
                        "## Topics for Future Reminiscence\n(Will be identified from conversations)\n",
                        "## Topics for Future Reminiscence\n"
                    )
                    # Re-find positions
                    topics_section_start = updated_kb.find(topics_marker)
                    next_section_start = updated_kb.find("\n## ", topics_section_start + len(topics_marker))
                
                if next_section_start == -1:
                    # Append to end
                    updated_kb = updated_kb.rstrip() + "\n" + topics_section
                else:
                    # Insert before next section
                    updated_kb = (
                        updated_kb[:next_section_start] + 
                        "\n" + topics_section + 
                        updated_kb[next_section_start:]
                    )
            else:
                updated_kb += f"\n\n{topics_marker}\n{topics_section}"
        
        # Add health timeline
        if analysis['health']['summary'] != "Unable to analyze":
            health_entry = f"\n**{session_date}:**\n"
            health_entry += f"- {analysis['health']['summary']}\n"
            
            health_marker = "## Health Timeline"
            
            if health_marker in updated_kb:
                # Find position of next section
                health_section_start = updated_kb.find(health_marker)
                next_section_start = updated_kb.find("\n## ", health_section_start + len(health_marker))
                
                # Remove placeholder if exists
                if "(Will be tracked from natural conversation)" in updated_kb:
                    updated_kb = updated_kb.replace(
                        "## Health Timeline\n(Will be tracked from natural conversation)\n",
                        "## Health Timeline\n"
                    )
                    # Re-find positions
                    health_section_start = updated_kb.find(health_marker)
                    next_section_start = updated_kb.find("\n## ", health_section_start + len(health_marker))
                
                if next_section_start == -1:
                    # Append to end
                    updated_kb = updated_kb.rstrip() + "\n" + health_entry
                else:
                    # Insert before next section
                    updated_kb = (
                        updated_kb[:next_section_start] + 
                        "\n" + health_entry + 
                        updated_kb[next_section_start:]
                    )
            else:
                updated_kb += f"\n\n{health_marker}\n{health_entry}"
        
        print(f"✅ Knowledge base updated (Session {conversation_number} added)")
        
        return updated_kb
    
    def generate_family_update(self, analysis, user_name, family_name):
        """
        Generate family dashboard update
        
        Args:
            analysis: Analysis results
            user_name: Person's name
            family_name: Family member's name
            
        Returns:
            Dict with family update
        """
        
        print(f"\n📊 Generating family update...")
        
        # Determine alert level
        alert_level = "🟢 Low"
        if analysis['health'].get('red_flags'):
            alert_level = "🔴 HIGH - URGENT"
        elif "concern" in analysis['health']['summary'].lower():
            alert_level = "🟡 Moderate"
        
        update = {
            "date": datetime.now().strftime("%B %d, %Y"),
            "user_name": user_name,
            "family_name": family_name,
            "alert_level": alert_level,
            "health_summary": analysis['health']['summary'],
            "mood": analysis['conversation']['mood'],
            "engagement": analysis['conversation']['engagement'],
            "notable_moments": analysis['family_dashboard']['notable_moments'],
            "concerns": analysis['family_dashboard']['concerns'],
            "recommendations": analysis['family_dashboard']['recommendations'],
            "red_flags": analysis['health'].get('red_flags', [])
        }
        
        print(f"✅ Family update generated - Alert level: {alert_level}")
        
        return update
    
    def _get_conversation_count(self, knowledge_base):
        """Extract conversation count from knowledge base"""
        match = re.search(r"Total conversations:\s*(\d+)", knowledge_base)
        if match:
            return int(match.group(1))
        return 0


if __name__ == "__main__":
    # Test the analyzer
    print("Testing Conversation Analyzer...")
    
    sample_transcript = """
Aila: Hi Margaret! How have you been since we last talked?

Margaret: Pretty good, though I've been tired the last few days.

Aila: I'm sorry to hear you're tired. Has that been ongoing, or just started recently?

Margaret: About three days now. I think I'm just not sleeping well.

Aila: That's frustrating. What time have you been going to bed?

Margaret: Around 9:30, but I keep waking up around 2 AM and can't fall back asleep.

Aila: That sounds difficult. You know, last time you mentioned your rose garden. Have you been thinking about that indoor garden idea?

Margaret: Actually yes! Susan brought me a small rose plant yesterday. It's on my windowsill.

Aila: Oh how wonderful! What color is it?

Margaret: It's pink - reminds me of the ones Robert and I used to grow. The sunset was crimson that night we met at the dance in 1952.
"""
    
    analyzer = ConversationAnalyzer()
    
    # Analyze
    analysis = analyzer.analyze_conversation(sample_transcript, "Margaret")
    
    print("\n" + "="*60)
    print("ANALYSIS RESULTS:")
    print("="*60)
    print(json.dumps(analysis, indent=2))
