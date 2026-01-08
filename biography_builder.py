"""
Biography Builder - TelAila
Builds rich life stories from FULL conversation archives (not compressed KB)

This ensures all the "color" and detail is preserved for biography generation
"""

import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

class BiographyBuilder:
    """
    Builds comprehensive biographies from full conversation archives
    
    Key principle: NEVER use compressed knowledge base for biography
    Always read from original conversation JSON files
    """
    
    def __init__(self, beta_manager):
        self.beta_manager = beta_manager
    
    def build_biography(self, beta_id):
        """
        Build full biography from complete conversation archive
        
        Returns rich biography with:
        - All stories (with full context and sensory details)
        - Character map (people mentioned across all conversations)
        - Timeline of life events
        - Themes and patterns
        - Full quotes in context
        """
        
        conversations_path = self.beta_manager.get_tester_data_path(beta_id, "conversations")
        
        if not conversations_path.exists():
            return self._empty_biography()
        
        # Load ALL conversations (full data)
        all_conversations = []
        for conv_file in sorted(conversations_path.glob("*.json")):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conv_data = json.load(f)
                all_conversations.append(conv_data)
            except Exception as e:
                print(f"⚠️ Could not load {conv_file.name}: {e}")
        
        if not all_conversations:
            return self._empty_biography()
        
        # Extract biography data from FULL conversations
        stories = self._extract_all_stories(all_conversations)
        people = self._build_character_map(all_conversations)
        timeline = self._build_timeline(all_conversations)
        themes = self._identify_themes(all_conversations)
        quotes = self._extract_contextual_quotes(all_conversations)
        
        return {
            'total_stories': len(stories),
            'stories': stories,
            'people': people,
            'timeline': timeline,
            'themes': themes,
            'quotes_in_context': quotes,
            'total_conversations': len(all_conversations),
            'data_source': 'full_conversation_archive',
            'word_count': self._count_biography_words(stories)
        }
    
    def _extract_all_stories(self, conversations):
        """
        Extract all stories with FULL detail and color
        
        Returns stories with:
        - Full narrative
        - Sensory details (sights, sounds, smells)
        - Emotional context
        - People involved
        - Time period indicators
        """
        
        all_stories = []
        
        for i, conv in enumerate(conversations, 1):
            analysis = conv.get('analysis', {})
            bio = analysis.get('biography', {})
            
            stories = bio.get('stories', [])
            sensory_details = bio.get('sensory_details', [])
            
            for story in stories:
                # Enrich story with session context
                enriched_story = {
                    'session_number': i,
                    'date': conv.get('timestamp', ''),
                    'topic': story.get('topic', 'untitled'),
                    'full_details': story.get('details', ''),
                    'people_involved': story.get('people_involved', []),
                    'sensory_details': sensory_details,  # Preserve the color!
                    'emotional_tone': analysis.get('conversation', {}).get('mood', 'neutral'),
                    'context': story.get('context', ''),
                    'significance': story.get('significance', '')
                }
                all_stories.append(enriched_story)
        
        return all_stories
    
    def _build_character_map(self, conversations):
        """
        Build detailed map of all people mentioned
        
        Returns character profiles with:
        - Relationship to elder
        - All mentions across conversations
        - Contexts in which they appear
        - Emotional associations
        """
        
        character_map = defaultdict(lambda: {
            'mentions': [],
            'relationships': set(),
            'contexts': [],
            'first_mentioned': None
        })
        
        for conv in conversations:
            timestamp = conv.get('timestamp', '')
            analysis = conv.get('analysis', {})
            bio = analysis.get('biography', {})
            
            people = bio.get('people', [])
            
            for person in people:
                name = person if isinstance(person, str) else person.get('name', 'Unknown')
                
                if not character_map[name]['first_mentioned']:
                    character_map[name]['first_mentioned'] = timestamp
                
                character_map[name]['mentions'].append({
                    'date': timestamp,
                    'context': analysis.get('conversation', {}).get('topics', [])
                })
        
        # Convert sets to lists for JSON serialization
        for name in character_map:
            character_map[name]['relationships'] = list(character_map[name]['relationships'])
        
        return dict(character_map)
    
    def _build_timeline(self, conversations):
        """
        Build chronological timeline of life events mentioned
        
        Returns timeline with:
        - Events in chronological order (when determinable)
        - Era markers (childhood, career, retirement, etc.)
        - Major life transitions
        """
        
        timeline = []
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            bio = analysis.get('biography', {})
            
            events = bio.get('timeline_events', [])
            
            for event in events:
                timeline.append({
                    'mentioned_on': conv.get('timestamp', ''),
                    'event': event,
                    'context': analysis.get('conversation', {}).get('topics', [])
                })
        
        return timeline
    
    def _identify_themes(self, conversations):
        """
        Identify recurring themes across all conversations
        
        Returns themes like:
        - Family (frequency, sentiment, key stories)
        - Career (main jobs, achievements)
        - Hobbies (what they loved doing)
        - Places (where they lived, traveled)
        - Loss (people they've lost, grief patterns)
        """
        
        themes = defaultdict(lambda: {
            'frequency': 0,
            'stories': [],
            'sentiment': [],
            'key_moments': []
        })
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            topics = analysis.get('conversation', {}).get('topics', [])
            mood = analysis.get('conversation', {}).get('mood', 'neutral')
            
            # Track topic frequency and sentiment
            for topic in topics:
                themes[topic]['frequency'] += 1
                themes[topic]['sentiment'].append(mood)
        
        return dict(themes)
    
    def _extract_contextual_quotes(self, conversations):
        """
        Extract quotes with FULL context
        
        Returns quotes with:
        - Full quote text
        - What prompted it (conversation context)
        - Who was being discussed
        - Emotional state when said
        """
        
        contextual_quotes = []
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            quotes = analysis.get('conversation', {}).get('memorable_quotes', [])
            topics = analysis.get('conversation', {}).get('topics', [])
            mood = analysis.get('conversation', {}).get('mood', '')
            
            for quote in quotes:
                contextual_quotes.append({
                    'quote': quote,
                    'date': conv.get('timestamp', ''),
                    'conversation_topics': topics,
                    'emotional_state': mood,
                    'session_summary': analysis.get('conversation', {}).get('summary', '')
                })
        
        return contextual_quotes
    
    def _count_biography_words(self, stories):
        """Count total words across all story details"""
        total = 0
        for story in stories:
            total += len(story.get('full_details', '').split())
        return total
    
    def _empty_biography(self):
        """Return empty biography structure"""
        return {
            'total_stories': 0,
            'stories': [],
            'people': {},
            'timeline': [],
            'themes': {},
            'quotes_in_context': [],
            'total_conversations': 0,
            'data_source': 'full_conversation_archive',
            'word_count': 0
        }
    
    def export_biography_document(self, beta_id, format='markdown'):
        """
        Export full biography as a readable document
        
        Formats:
        - markdown: Rich markdown document
        - json: Structured data
        - pdf: Formatted PDF (future)
        """
        
        biography = self.build_biography(beta_id)
        
        if format == 'markdown':
            return self._format_as_markdown(biography, beta_id)
        elif format == 'json':
            return json.dumps(biography, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def _format_as_markdown(self, biography, beta_id):
        """Format biography as beautiful markdown document"""
        
        tester = self.beta_manager.registry['testers'].get(beta_id)
        elder_name = tester['signup_data']['theirName'] if tester else 'Unknown'
        
        md = f"""# The Life Story of {elder_name}
*Captured through {biography['total_conversations']} conversations*

---

## Their Stories ({biography['total_stories']} captured)

"""
        
        # Add all stories with full detail
        for story in biography['stories']:
            md += f"### {story['topic'].title()}\n"
            md += f"*Shared on {story['date'][:10]}*\n\n"
            md += f"{story['full_details']}\n\n"
            
            if story['sensory_details']:
                md += f"**Sensory memories:** {', '.join(story['sensory_details'])}\n\n"
            
            if story['people_involved']:
                md += f"**People:** {', '.join(story['people_involved'])}\n\n"
            
            md += "---\n\n"
        
        # Add character map
        md += "## People in Their Life\n\n"
        for name, data in biography['people'].items():
            md += f"### {name}\n"
            md += f"- First mentioned: {data['first_mentioned'][:10]}\n"
            md += f"- Total mentions: {len(data['mentions'])}\n\n"
        
        # Add themes
        md += "## Life Themes\n\n"
        for theme, data in biography['themes'].items():
            md += f"### {theme.title()}\n"
            md += f"- Discussed {data['frequency']} times\n\n"
        
        # Add memorable quotes
        md += "## In Their Own Words\n\n"
        for quote_data in biography['quotes_in_context']:
            md += f"> \"{quote_data['quote']}\"\n\n"
            md += f"*Said on {quote_data['date'][:10]} while discussing {', '.join(quote_data['conversation_topics'][:2])}*\n\n"
        
        md += f"\n---\n\n*Generated on {datetime.now().strftime('%B %d, %Y')}*\n"
        md += f"*Based on {biography['total_conversations']} conversations with {elder_name}*\n"
        
        return md
