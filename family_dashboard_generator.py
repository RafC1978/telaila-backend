"""
Family Dashboard Generator
Creates comprehensive family reports from conversation data
Phase 1: Health Event Tracking + Enhanced Theme-Based "In Their Words"
"""

import json
import re
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import pytz

class FamilyDashboardGenerator:
    """
    Generates family dashboard data by analyzing all conversations
    for a specific beta tester
    """
    
    def __init__(self, beta_manager):
        self.beta_manager = beta_manager
        self.local_tz = pytz.timezone('America/Vancouver')
        
        # Keywords for health event detection
        self.injury_keywords = [
            'fell', 'fall', 'fallen', 'hurt', 'injured', 'injury', 'accident',
            'broke', 'broken', 'sprain', 'strain', 'cut', 'bruise', 'hit',
            'twisted', 'pulled', 'torn', 'fracture', 'bump', 'crash', 'ladder'
        ]
        
        self.illness_keywords = [
            'sick', 'ill', 'fever', 'cold', 'flu', 'infection', 'virus',
            'nausea', 'vomit', 'diarrhea', 'cough', 'congestion', 'covid',
            'pneumonia', 'bronchitis', 'diagnosis', 'diagnosed'
        ]
        
        self.symptom_keywords = [
            'pain', 'ache', 'sore', 'stiff', 'tired', 'fatigue', 'weak',
            'dizzy', 'numb', 'swollen', 'inflammation', 'discomfort',
            'trouble sleeping', 'can\'t sleep', 'insomnia', 'headache',
            'sleeping sitting', 'not sleeping'
        ]
        
        self.body_parts = [
            'back', 'knee', 'hip', 'shoulder', 'neck', 'arm', 'leg',
            'ankle', 'wrist', 'hand', 'foot', 'head', 'chest', 'stomach'
        ]
        
        # Theme definitions for "In Their Words"
        self.theme_definitions = {
            'snowbird_lifestyle': {
                'name': 'Snowbird Lifestyle',
                'keywords': ['snowbird', 'arizona', 'winter', 'rv', 'park', 'trailer', 
                            'south', 'warm', 'sun', 'migrate', 'seasonal'],
                'priority': 1
            },
            'health_recovery': {
                'name': 'Health & Recovery',
                'keywords': ['pain', 'injury', 'back', 'sleep', 'doctor', 'recovery',
                            'hurt', 'fell', 'hospital', 'healing', 'better', 'worse'],
                'priority': 2
            },
            'family': {
                'name': 'Family',
                'keywords': ['daughter', 'son', 'wife', 'husband', 'grandkid', 'grandson',
                            'granddaughter', 'child', 'family', 'kids', 'mother', 'father',
                            'sister', 'brother', 'grandchild'],
                'priority': 3
            },
            'social_life': {
                'name': 'Social Life & Friends',
                'keywords': ['friend', 'poker', 'dinner', 'lunch', 'community', 'neighbor',
                            'people', 'social', 'party', 'gathering', 'club', 'group'],
                'priority': 4
            },
            'hobbies': {
                'name': 'Hobbies & Interests',
                'keywords': ['poker', 'golf', 'fishing', 'woodworking', 'reading', 'garden',
                            'hobby', 'enjoy', 'love doing', 'passion', 'craft'],
                'priority': 5
            },
            'travel': {
                'name': 'Travel & Adventures',
                'keywords': ['travel', 'trip', 'vacation', 'visit', 'flew', 'drive',
                            'adventure', 'explore', 'country', 'cruise'],
                'priority': 6
            },
            'home_living': {
                'name': 'Home & Daily Life',
                'keywords': ['home', 'house', 'trailer', 'storage', 'errands', 'routine',
                            'morning', 'day', 'living', 'chores'],
                'priority': 7
            },
            'memories': {
                'name': 'Memories & Life Story',
                'keywords': ['remember', 'years ago', 'used to', 'when i was', 'childhood',
                            'grew up', 'younger', 'back then', 'history', 'past'],
                'priority': 8
            },
            'work_career': {
                'name': 'Work & Career',
                'keywords': ['work', 'job', 'career', 'retired', 'business', 'company',
                            'profession', 'boss', 'employee', 'office'],
                'priority': 9
            }
        }
        
        # Meta-quote patterns to filter OUT (regex)
        self.meta_patterns = [
            # AI/Robot references
            r"don'?t you (ever )?sleep",
            r"do you sleep",
            r"you'?re (an? )?(ai|robot|machine|computer)",
            r"as (an? )?(ai|artificial)",
            r"see me (as|purely as) fiction",
            r"speaking with me",
            r"talking to (me|you)",
            r"you (don'?t |can'?t )?(have|feel|experience|understand)",
            r"what do you think",
            r"how do you feel",
            r"are you real",
            r"you'?re not (real|human)",
            r"artificial intelligence",
            r"you'?re programmed",
            r"your programming",
            
            # Meta-conversation
            r"this conversation",
            r"we'?re (just )?talking",
            r"you asked",
            r"i asked you",
            r"let me ask",
            r"that'?s a good question",
            
            # Too vague/short
            r"^(yes|no|okay|ok|sure|right|yeah|yep|nope|maybe|hmm|huh|well)[\.\?!,]?$",
            r"^i (think|guess|suppose) so[\.\?!]?$",
            r"^that'?s (right|true|correct)[\.\?!]?$",
            r"^i don'?t know[\.\?!]?$",
            r"^not really[\.\?!]?$",
        ]
        
        # Compile patterns for efficiency
        self.compiled_meta_patterns = [re.compile(p, re.IGNORECASE) for p in self.meta_patterns]
    
    def _to_local_time(self, timestamp_str):
        """Convert UTC timestamp to Vancouver local time"""
        try:
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            return dt.astimezone(self.local_tz)
        except:
            try:
                return datetime.fromisoformat(timestamp_str)
            except:
                return datetime.now(self.local_tz)
    
    def _format_date(self, timestamp_str):
        """Format timestamp as readable date string"""
        if not timestamp_str:
            return 'Unknown'
        try:
            local_time = self._to_local_time(timestamp_str)
            return local_time.strftime('%b %d, %Y')
        except:
            return 'Unknown'
    
    def _calculate_duration(self, transcript):
        """Estimate conversation duration from transcript"""
        if not transcript:
            return "Unknown"
        turns = transcript.count('\nAila:') + transcript.count('\nUser:')
        minutes = (turns * 30) // 60
        if minutes < 1:
            return "< 1 minute"
        elif minutes == 1:
            return "1 minute"
        else:
            return f"{minutes} minutes"
    
    def _is_meta_quote(self, quote):
        """Check if quote is meta/AI-related and should be filtered"""
        if not quote:
            return True
        
        quote_lower = quote.lower().strip()
        
        # Check against compiled patterns
        for pattern in self.compiled_meta_patterns:
            if pattern.search(quote_lower):
                return True
        
        # Additional keyword checks
        meta_keywords = ['aila', 'ai ', ' ai', 'robot', 'artificial', 'programmed', 
                        'machine', 'computer', 'algorithm']
        if any(kw in quote_lower for kw in meta_keywords):
            return True
        
        return False
    
    def _detect_theme(self, text, topics=None, stories=None):
        """Detect the most relevant theme for a piece of text"""
        if not text:
            return 'general', 'Life Story'
        
        text_lower = text.lower()
        
        # Also check topics and stories
        all_text = text_lower
        if topics:
            all_text += ' ' + ' '.join(t.lower() for t in topics if t)
        if stories:
            for story in stories:
                if isinstance(story, dict):
                    all_text += ' ' + story.get('topic', '').lower()
                    all_text += ' ' + story.get('details', '').lower()
                elif isinstance(story, str):
                    all_text += ' ' + story.lower()
        
        # Score each theme
        theme_scores = {}
        for theme_id, theme_def in self.theme_definitions.items():
            score = 0
            for keyword in theme_def['keywords']:
                if keyword in all_text:
                    score += 1
            if score > 0:
                theme_scores[theme_id] = score
        
        if not theme_scores:
            return 'general', 'Life Story'
        
        # Return highest scoring theme
        best_theme = max(theme_scores, key=theme_scores.get)
        return best_theme, self.theme_definitions[best_theme]['name']
    
    def generate_dashboard(self, beta_id):
        """Generate complete family dashboard for a beta tester"""
        self.beta_manager._load_registry()
        tester = self.beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            return {'success': False, 'error': 'Beta tester not found'}
        
        conversations_path = self.beta_manager.get_tester_data_path(beta_id, "conversations")
        kb_path = self.beta_manager.get_tester_data_path(beta_id, "knowledge_base.md")
        
        conversations = self._load_conversations(conversations_path)
        
        knowledge_base = ""
        if kb_path.exists():
            with open(kb_path, 'r', encoding='utf-8') as f:
                knowledge_base = f.read()
        
        # Get elder name for context building
        elder_name = tester['signup_data'].get('theirName', 'They')
        
        # Detect health events FIRST (needed by other sections)
        health_events = self._detect_health_events(conversations, knowledge_base)
        
        dashboard = {
            'success': True,
            'beta_id': beta_id,
            'elder': {
                'name': elder_name,
                'age': tester['signup_data'].get('theirAge', 'Unknown'),
            },
            'family': {
                'name': tester['signup_data'].get('yourName', 'Unknown'),
                'email': tester['signup_data'].get('yourEmail', ''),
                'relationship': tester['signup_data'].get('relationship', 'family member'),
            },
            'generated_at': datetime.now().isoformat(),
            'summary': self._generate_summary(conversations, tester, health_events),
            'health_events': health_events,
            'in_their_words': self._build_in_their_words(conversations, elder_name),  # NEW
            'biography_progress': self._analyze_biography_progress(knowledge_base, conversations),
            'life_story_quotes': self._extract_biographical_quotes(conversations),  # KEEP for backward compat
            'recent_conversations': self._generate_recent_conversations(conversations),
            'health_insights': self._generate_health_insights(conversations, health_events),
            'alerts': self._identify_alerts(conversations, health_events),
            'trends': self._generate_trends(conversations),
            'recommendations': self._generate_recommendations(conversations, tester, health_events),
        }
        
        return dashboard
    
    def _load_conversations(self, conversations_path):
        """Load all conversation JSON files"""
        conversations = []
        if not conversations_path.exists():
            return conversations
        
        for conv_file in sorted(conversations_path.glob("*.json")):
            try:
                with open(conv_file, 'r', encoding='utf-8') as f:
                    conversations.append(json.load(f))
            except Exception as e:
                print(f"⚠️ Could not load {conv_file.name}: {e}")
        
        return conversations
    
    def _build_in_their_words(self, conversations, elder_name):
        """
        Build theme-based "In Their Words" section with context narratives
        
        Returns:
        {
            "themes": [
                {
                    "theme_id": "snowbird_lifestyle",
                    "theme_name": "Snowbird Lifestyle",
                    "context": "Gerry and his wife have been snowbirds for 13 years...",
                    "quotes": [...],
                    "first_mentioned": "Jan 08, 2026",
                    "last_updated": "Jan 09, 2026"
                }
            ],
            "meta_filtered_count": 3
        }
        """
        theme_data = defaultdict(lambda: {
            'quotes': [],
            'context_pieces': [],
            'first_mentioned': None,
            'last_mentioned': None,
            'stories': []
        })
        
        meta_filtered_count = 0
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            conv_quotes = analysis.get('conversation', {}).get('memorable_quotes', [])
            topics = analysis.get('conversation', {}).get('topics', [])
            mood = analysis.get('conversation', {}).get('mood', 'neutral')
            bio = analysis.get('biography', {})
            stories = bio.get('stories', [])
            
            timestamp = conv.get('timestamp', '')
            date_fmt = self._format_date(timestamp)
            
            # Get mood info
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good', 'cheerful']):
                mood_emoji, mood_label = '😊', 'Happy'
            elif any(w in mood_lower for w in ['negative', 'sad', 'upset', 'worried']):
                mood_emoji, mood_label = '😔', 'Reflective'
            else:
                mood_emoji, mood_label = '😌', 'Relaxed'
            
            # Process stories for context building
            for story in stories:
                if isinstance(story, dict):
                    story_topic = story.get('topic', '')
                    story_details = story.get('details', '')
                elif isinstance(story, str):
                    story_topic = ''
                    story_details = story
                else:
                    continue
                
                if story_details and len(story_details.strip()) > 10:
                    theme_id, _ = self._detect_theme(story_details, topics, stories)
                    theme_data[theme_id]['stories'].append({
                        'topic': story_topic,
                        'details': story_details,
                        'timestamp': timestamp
                    })
                    theme_data[theme_id]['context_pieces'].append(story_details)
                    
                    # Update timestamps
                    if not theme_data[theme_id]['first_mentioned'] or timestamp < theme_data[theme_id]['first_mentioned']:
                        theme_data[theme_id]['first_mentioned'] = timestamp
                    if not theme_data[theme_id]['last_mentioned'] or timestamp > theme_data[theme_id]['last_mentioned']:
                        theme_data[theme_id]['last_mentioned'] = timestamp
            
            # Process quotes
            for quote in conv_quotes:
                if not quote or not isinstance(quote, str):
                    continue
                
                quote_stripped = quote.strip()
                
                # Filter meta quotes
                if self._is_meta_quote(quote_stripped):
                    meta_filtered_count += 1
                    continue
                
                # Skip too short
                if len(quote_stripped.split()) < 5:
                    continue
                
                # Detect theme for this quote
                theme_id, _ = self._detect_theme(quote_stripped, topics, stories)
                
                theme_data[theme_id]['quotes'].append({
                    'quote': quote_stripped,
                    'date': date_fmt,
                    'timestamp': timestamp,
                    'mood': mood_label,
                    'mood_emoji': mood_emoji
                })
                
                # Update timestamps
                if not theme_data[theme_id]['first_mentioned'] or timestamp < theme_data[theme_id]['first_mentioned']:
                    theme_data[theme_id]['first_mentioned'] = timestamp
                if not theme_data[theme_id]['last_mentioned'] or timestamp > theme_data[theme_id]['last_mentioned']:
                    theme_data[theme_id]['last_mentioned'] = timestamp
        
        # Build final themes with context narratives
        themes = []
        for theme_id, data in theme_data.items():
            if not data['quotes']:
                continue
            
            # Get theme name
            if theme_id in self.theme_definitions:
                theme_name = self.theme_definitions[theme_id]['name']
                priority = self.theme_definitions[theme_id]['priority']
            else:
                theme_name = 'Life Story'
                priority = 99
            
            # Build context narrative from stories
            context = self._build_theme_context(theme_id, data, elder_name)
            
            # Deduplicate quotes
            seen_quotes = set()
            unique_quotes = []
            for q in data['quotes']:
                q_lower = q['quote'].lower().strip()
                if q_lower not in seen_quotes:
                    seen_quotes.add(q_lower)
                    unique_quotes.append(q)
            
            # Sort quotes by date (newest first)
            unique_quotes.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            themes.append({
                'theme_id': theme_id,
                'theme_name': theme_name,
                'priority': priority,
                'context': context,
                'quotes': unique_quotes[:5],  # Top 5 quotes per theme
                'total_quotes': len(unique_quotes),
                'first_mentioned': self._format_date(data['first_mentioned']),
                'last_updated': self._format_date(data['last_mentioned'])
            })
        
        # Sort themes by priority
        themes.sort(key=lambda x: x.get('priority', 99))
        
        return {
            'themes': themes,
            'meta_filtered_count': meta_filtered_count,
            'total_themes': len(themes)
        }
    
    def _build_theme_context(self, theme_id, data, elder_name):
        """Build a narrative context for a theme from accumulated stories"""
        context_pieces = data.get('context_pieces', [])
        stories = data.get('stories', [])
        
        if not context_pieces and not stories:
            return f"Stories and memories shared about {self.theme_definitions.get(theme_id, {}).get('name', 'this topic')}."
        
        # Extract key facts from context pieces
        facts = []
        
        # Theme-specific context building
        if theme_id == 'snowbird_lifestyle':
            # Look for duration, location, community size
            for piece in context_pieces:
                piece_lower = piece.lower()
                
                # Duration
                years_match = re.search(r'(\d+)\s*years?\s*(as\s+)?snowbird', piece_lower)
                if years_match:
                    facts.append(f"has been a snowbird for {years_match.group(1)} years")
                
                # Location
                if 'arizona' in piece_lower:
                    facts.append("winters in Arizona")
                if 'canada' in piece_lower or 'canadian' in piece_lower:
                    facts.append("summers in Canada")
                
                # Community
                people_match = re.search(r'(\d+,?\d*)\s*people', piece_lower)
                if people_match:
                    facts.append(f"is part of a community of {people_match.group(1)} people")
                
                # New park
                if 'new park' in piece_lower or 'new area' in piece_lower or 'november' in piece_lower:
                    facts.append("recently moved to a new park")
        
        elif theme_id == 'health_recovery':
            for piece in context_pieces:
                piece_lower = piece.lower()
                
                if 'fell' in piece_lower or 'fall' in piece_lower:
                    if 'ladder' in piece_lower:
                        facts.append("fell off a ladder")
                    else:
                        facts.append("had a fall")
                
                if 'back' in piece_lower:
                    facts.append("is dealing with back pain")
                
                if 'sleep' in piece_lower:
                    facts.append("has been having trouble sleeping")
                
                if 'better' in piece_lower or 'improving' in piece_lower:
                    facts.append("is slowly recovering")
        
        elif theme_id == 'social_life':
            for piece in context_pieces:
                piece_lower = piece.lower()
                
                if 'poker' in piece_lower:
                    # Try to find frequency
                    freq_match = re.search(r'(\d+)\s*times?\s*(a|per)\s*week', piece_lower)
                    if freq_match:
                        facts.append(f"plays poker {freq_match.group(1)} times a week")
                    else:
                        facts.append("enjoys playing poker")
                
                people_match = re.search(r'(\d+)\s*(friends?|people)', piece_lower)
                if people_match:
                    facts.append(f"has a social circle of about {people_match.group(1)} friends")
        
        elif theme_id == 'family':
            for piece in context_pieces:
                piece_lower = piece.lower()
                
                # Look for family members
                if 'daughter' in piece_lower:
                    # Try to find name
                    name_match = re.search(r'daughter\s+(\w+)|(\w+)\s+.*daughter', piece_lower)
                    if name_match:
                        name = name_match.group(1) or name_match.group(2)
                        if name and name.lower() not in ['my', 'his', 'her', 'the', 'a']:
                            facts.append(f"has a daughter named {name.title()}")
                    else:
                        facts.append("has a daughter")
                
                if 'wife' in piece_lower:
                    facts.append("is married")
                
                if 'grandkid' in piece_lower or 'grandchild' in piece_lower:
                    facts.append("has grandchildren")
        
        # Deduplicate facts
        unique_facts = list(dict.fromkeys(facts))
        
        # Build narrative
        if unique_facts:
            # Capitalize first letter of first fact
            if unique_facts[0] and unique_facts[0][0].islower():
                unique_facts[0] = unique_facts[0][0].upper() + unique_facts[0][1:]
            
            context = f"{elder_name} {', '.join(unique_facts[:4])}."
        else:
            # Fallback to generic context
            theme_name = self.theme_definitions.get(theme_id, {}).get('name', 'various topics')
            context = f"{elder_name} has shared stories about {theme_name.lower()}."
        
        return context
    
    def _detect_health_events(self, conversations, knowledge_base):
        """Detect significant health events and link related symptoms"""
        event_mentions = defaultdict(list)
        
        for conv in conversations:
            timestamp = conv.get('timestamp', '')
            analysis = conv.get('analysis', {})
            health = analysis.get('health', {})
            summary = health.get('summary', '')
            red_flags = health.get('red_flags', [])
            transcript = conv.get('transcript', '')
            
            if summary:
                self._extract_health_mentions(event_mentions, summary, timestamp, 'health_summary')
            
            for flag in red_flags:
                flag_text = flag if isinstance(flag, str) else str(flag)
                self._extract_health_mentions(event_mentions, flag_text, timestamp, 'red_flag')
            
            if transcript:
                self._extract_health_mentions(event_mentions, transcript, timestamp, 'transcript')
        
        if knowledge_base:
            self._extract_health_mentions(event_mentions, knowledge_base, '', 'knowledge_base')
        
        events = self._consolidate_health_events(event_mentions)
        return self._link_symptoms_to_causes(events)
    
    def _extract_health_mentions(self, event_mentions, text, timestamp, source):
        """Extract health-related mentions from text"""
        if not text:
            return
        
        text_lower = text.lower()
        
        for keyword in self.injury_keywords:
            if keyword in text_lower:
                body_part = self._extract_body_part(text_lower)
                
                if keyword in ['fell', 'fall', 'fallen', 'ladder']:
                    event_key = f"injury_fall_{body_part or 'general'}"
                    severity = 'high'
                else:
                    event_key = f"injury_{keyword}_{body_part or 'general'}"
                    severity = 'high'
                
                context = self._extract_context(text, keyword)
                
                event_mentions[event_key].append({
                    'timestamp': timestamp,
                    'source': source,
                    'text': context or text[:200],
                    'keyword': keyword,
                    'body_part': body_part,
                    'type': 'injury',
                    'severity': severity
                })
        
        for keyword in self.symptom_keywords:
            if keyword in text_lower:
                body_part = self._extract_body_part(text_lower)
                event_key = f"symptom_{keyword.replace(' ', '_')}_{body_part or 'general'}"
                
                context = self._extract_context(text, keyword)
                
                event_mentions[event_key].append({
                    'timestamp': timestamp,
                    'source': source,
                    'text': context or text[:200],
                    'keyword': keyword,
                    'body_part': body_part,
                    'type': 'symptom',
                    'severity': 'moderate'
                })
    
    def _extract_context(self, text, keyword):
        """Extract surrounding context for a keyword"""
        text_lower = text.lower()
        idx = text_lower.find(keyword)
        if idx == -1:
            return None
        
        start = max(0, idx - 50)
        end = min(len(text), idx + len(keyword) + 100)
        
        context = text[start:end].strip()
        if start > 0:
            context = "..." + context
        if end < len(text):
            context = context + "..."
        
        return context
    
    def _extract_body_part(self, text):
        """Extract body part mentioned in text"""
        for part in self.body_parts:
            if part in text:
                return part
        return None
    
    def _consolidate_health_events(self, event_mentions):
        """Consolidate mentions into distinct health events"""
        events = []
        
        for event_key, mentions in event_mentions.items():
            if not mentions:
                continue
            
            dated_mentions = [m for m in mentions if m.get('timestamp')]
            if dated_mentions:
                sorted_mentions = sorted(dated_mentions, key=lambda x: x.get('timestamp', ''))
            else:
                sorted_mentions = mentions
            
            if not sorted_mentions:
                continue
            
            first = sorted_mentions[0]
            last = sorted_mentions[-1]
            
            event_type = first.get('type', 'symptom')
            keyword = first.get('keyword', '')
            body_part = first.get('body_part')
            
            if keyword in ['fell', 'fall', 'fallen', 'ladder'] or event_type == 'injury':
                severity = 'high'
            elif len(sorted_mentions) >= 3:
                severity = 'moderate'
            else:
                severity = 'low'
            
            if keyword in ['fell', 'fall', 'fallen', 'ladder']:
                title = "Fall Incident"
                if body_part:
                    title = f"Fall Incident - {body_part.title()} Injury"
            elif body_part:
                title = f"{body_part.title()} {keyword.title()}"
            else:
                title = keyword.replace('_', ' ').title()
            
            event_id = hashlib.md5(f"{event_key}_{first.get('timestamp', 'unknown')}".encode()).hexdigest()[:8]
            
            descriptions = [m.get('text', '') for m in sorted_mentions if m.get('text')]
            description = descriptions[0] if descriptions else title
            
            events.append({
                'event_id': f"HE_{event_id}",
                'type': event_type,
                'severity': severity,
                'title': title,
                'description': description[:300],
                'detected_on': first.get('timestamp', ''),
                'detected_on_formatted': self._format_date(first.get('timestamp', '')),
                'last_mentioned': last.get('timestamp', ''),
                'last_mentioned_formatted': self._format_date(last.get('timestamp', '')),
                'body_part': body_part,
                'keyword': keyword,
                'related_symptoms': [],
                'status': 'active',
                'needs_family_followup': severity == 'high',
                'mentions_count': len(sorted_mentions),
                'family_actions': [],
            })
        
        return events
    
    def _link_symptoms_to_causes(self, events):
        """Link symptoms to their root causes"""
        causes = [e for e in events if e['type'] == 'injury']
        symptoms = [e for e in events if e['type'] == 'symptom']
        
        for symptom in symptoms:
            symptom_body = symptom.get('body_part')
            symptom_date = symptom.get('detected_on', '')
            
            for cause in causes:
                cause_date = cause.get('detected_on', '')
                cause_body = cause.get('body_part')
                
                if cause_date <= symptom_date or not cause_date:
                    if cause_body == symptom_body or not cause_body or not symptom_body:
                        cause['related_symptoms'].append({
                            'symptom': symptom['title'],
                            'status': 'ongoing',
                            'event_id': symptom['event_id']
                        })
                        symptom['linked_to'] = cause['event_id']
                        symptom['linked_to_title'] = cause['title']
                        break
        
        events.sort(key=lambda x: (
            {'high': 0, 'moderate': 1, 'low': 2}.get(x['severity'], 2),
            x.get('detected_on', '') or 'zzz'
        ))
        
        return events
    
    def _generate_summary(self, conversations, tester, health_events=None):
        """Generate overall summary with health context"""
        if not conversations:
            return {
                'total_conversations': 0,
                'first_conversation_date': None,
                'last_conversation_date': None,
                'days_since_last_conversation': None,
                'overall_engagement': 'No data',
                'mood_trend': 'No data',
                'mood_context': None,
                'status': 'no_conversations'
            }
        
        total = len(conversations)
        first_ts = conversations[0].get('timestamp')
        last_ts = conversations[-1].get('timestamp')
        
        first_conv = self._to_local_time(first_ts) if first_ts else None
        last_conv = self._to_local_time(last_ts) if last_ts else None
        
        days_since = None
        if last_conv:
            now = datetime.now(self.local_tz)
            days_since = (now - last_conv).days
        
        scores = []
        for conv in conversations:
            eng = conv.get('analysis', {}).get('conversation', {}).get('engagement', 'moderate')
            scores.append({'high': 3, 'moderate': 2, 'low': 1}.get(str(eng).lower(), 2))
        
        avg_eng = sum(scores) / len(scores) if scores else 2
        engagement = 'High' if avg_eng >= 2.5 else 'Moderate' if avg_eng >= 1.5 else 'Low'
        
        mood_scores = []
        for conv in conversations[-5:]:
            mood = conv.get('analysis', {}).get('conversation', {}).get('mood', 'neutral')
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good']):
                mood_scores.append(3)
            elif any(w in mood_lower for w in ['negative', 'sad', 'upset', 'anxious']):
                mood_scores.append(1)
            else:
                mood_scores.append(2)
        
        avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else 2
        mood = 'Positive' if avg_mood >= 2.5 else 'Neutral' if avg_mood >= 1.5 else 'Low'
        
        mood_context = None
        if health_events:
            high_events = [e for e in health_events if e.get('severity') == 'high' and e.get('status') == 'active']
            if high_events:
                e = high_events[0]
                mood_context = f"Recent {e['title'].lower()} may be affecting mood ({e['detected_on_formatted']})"
        
        return {
            'total_conversations': total,
            'first_conversation_date': first_conv.strftime('%B %d, %Y') if first_conv else None,
            'last_conversation_date': last_conv.strftime('%B %d, %Y') if last_conv else None,
            'days_since_last_conversation': days_since,
            'overall_engagement': engagement,
            'mood_trend': mood,
            'mood_context': mood_context,
            'status': 'active' if days_since and days_since < 7 else 'inactive'
        }
    
    def _generate_health_insights(self, conversations, health_events=None):
        """Analyze health patterns with event context"""
        health_mentions = []
        concerns = []
        patterns = defaultdict(int)
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            health = analysis.get('health', {})
            
            if health.get('summary'):
                health_mentions.append({
                    'date': conv.get('timestamp', ''),
                    'date_formatted': self._format_date(conv.get('timestamp', '')),
                    'summary': health.get('summary', ''),
                    'mood': analysis.get('conversation', {}).get('mood', 'neutral')
                })
            
            for flag in health.get('red_flags', []):
                flag_text = flag if isinstance(flag, str) else str(flag)
                concerns.append({
                    'date': conv.get('timestamp', ''),
                    'date_formatted': self._format_date(conv.get('timestamp', '')),
                    'concern': flag_text,
                    'severity': 'high'
                })
            
            if health.get('pain'):
                patterns['pain_mentions'] += 1
            if health.get('sleep'):
                patterns['sleep_discussions'] += 1
        
        latest_health = None
        if conversations:
            latest_health = conversations[-1].get('analysis', {}).get('health', {}).get('summary')
        
        active_summary = None
        if health_events:
            active_high = [e for e in health_events if e.get('severity') == 'high']
            if active_high:
                titles = [e['title'] for e in active_high[:3]]
                active_summary = f"Active concerns: {', '.join(titles)}"
        
        return {
            'current_status': latest_health or 'No recent health information',
            'active_events_summary': active_summary,
            'total_health_mentions': len(health_mentions),
            'active_concerns': concerns[-3:] if concerns else [],
            'patterns': dict(patterns),
            'trend': self._determine_health_trend(health_mentions),
            'recent_mentions': health_mentions[-5:] if health_mentions else []
        }
    
    def _determine_health_trend(self, health_mentions):
        """Determine if health is improving, declining, or stable"""
        if len(health_mentions) < 2:
            return 'insufficient_data'
        
        recent = [m['mood'] for m in health_mentions[-3:]]
        pos = sum(1 for m in recent if 'positive' in str(m).lower())
        neg = sum(1 for m in recent if any(w in str(m).lower() for w in ['negative', 'pain', 'bad']))
        
        if pos > neg:
            return 'improving'
        elif neg > pos:
            return 'declining'
        return 'stable'
    
    def _generate_recent_conversations(self, conversations):
        """Get summaries of recent conversations"""
        recent = conversations[-3:] if len(conversations) >= 3 else conversations
        
        summaries = []
        for conv in reversed(recent):
            analysis = conv.get('analysis', {})
            conv_data = analysis.get('conversation', {})
            
            if 'timestamp' in conv:
                local = self._to_local_time(conv['timestamp'])
                date_str = local.strftime('%B %d, %Y at %I:%M %p')
            else:
                date_str = 'Unknown'
            
            summaries.append({
                'date': date_str,
                'topics': conv_data.get('topics', []),
                'mood': conv_data.get('mood', 'neutral'),
                'engagement': conv_data.get('engagement', 'moderate'),
                'duration_estimate': self._calculate_duration(conv.get('transcript', '')),
                'highlights': conv_data.get('follow_ups', [])[:2]
            })
        
        return summaries
    
    def _extract_biographical_quotes(self, conversations):
        """
        Extract quotes - KEPT FOR BACKWARD COMPATIBILITY
        New code should use in_their_words instead
        """
        quotes = []
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            conv_quotes = analysis.get('conversation', {}).get('memorable_quotes', [])
            topics = analysis.get('conversation', {}).get('topics', [])
            mood = analysis.get('conversation', {}).get('mood', 'neutral')
            stories = analysis.get('biography', {}).get('stories', [])
            
            timestamp = conv.get('timestamp', '')
            date_fmt = self._format_date(timestamp)
            
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good']):
                mood_emoji, mood_label = '😊', 'Happy'
            elif any(w in mood_lower for w in ['negative', 'sad', 'upset']):
                mood_emoji, mood_label = '😔', 'Reflective'
            else:
                mood_emoji, mood_label = '😌', 'Relaxed'
            
            for quote in conv_quotes:
                if not quote or not isinstance(quote, str):
                    continue
                
                quote_stripped = quote.strip()
                
                # Use improved meta filtering
                if self._is_meta_quote(quote_stripped):
                    continue
                
                if len(quote_stripped.split()) < 5:
                    continue
                
                # Detect theme for category
                theme_id, theme_name = self._detect_theme(quote_stripped, topics, stories)
                
                quotes.append({
                    'quote': quote_stripped,
                    'date': date_fmt,
                    'timestamp': timestamp,
                    'category': theme_name,
                    'topics': topics,
                    'mood': mood_label,
                    'mood_emoji': mood_emoji
                })
        
        # Deduplicate
        seen = set()
        unique = []
        for q in quotes:
            text = q['quote'].lower().strip()
            if text not in seen:
                seen.add(text)
                unique.append(q)
        
        return unique[-8:]
    
    def _build_life_story_profile(self, conversations):
        """Build life story profile"""
        profile = {
            'places': [], 'people': [], 'work_career': [],
            'interests_hobbies': [], 'life_events': [], 'stories': [],
            'chapters_captured': set()
        }
        
        for conv in conversations:
            bio = conv.get('analysis', {}).get('biography', {})
            timestamp = conv.get('timestamp', '')
            
            for story in bio.get('stories', []):
                if isinstance(story, dict):
                    topic = story.get('topic', '')
                    details = story.get('details', '')
                    people = story.get('people_involved', [])
                elif isinstance(story, str):
                    topic, details, people = 'story', story, []
                else:
                    continue
                
                topic_lower = topic.lower()
                
                if any(w in topic_lower for w in ['live', 'home', 'city', 'place']):
                    if details and details.strip():
                        profile['places'].append({'detail': details.strip(), 'mentioned_on': timestamp})
                        profile['chapters_captured'].add('Places & Locations')
                
                if any(w in topic_lower for w in ['work', 'job', 'career']):
                    if details and details.strip():
                        profile['work_career'].append({'detail': details.strip(), 'mentioned_on': timestamp})
                        profile['chapters_captured'].add('Work & Career')
                
                if any(w in topic_lower for w in ['hobby', 'interest', 'love', 'enjoy']):
                    if details and details.strip():
                        profile['interests_hobbies'].append({'detail': details.strip(), 'mentioned_on': timestamp})
                        profile['chapters_captured'].add('Interests & Hobbies')
                
                profile['stories'].append({'topic': topic, 'details': details, 'people': people, 'mentioned_on': timestamp})
            
            for person in bio.get('people', []):
                if isinstance(person, dict):
                    name = person.get('name', '')
                    rel = person.get('relationship', 'mentioned')
                elif isinstance(person, str):
                    name, rel = person, 'mentioned'
                else:
                    continue
                
                if name and name.strip():
                    profile['people'].append({'name': name.strip(), 'relationship': rel, 'mentioned_on': timestamp})
                    profile['chapters_captured'].add('Important People')
            
            for event in bio.get('timeline_events', []):
                if isinstance(event, dict):
                    text = event.get('event', '') or event.get('description', '')
                elif isinstance(event, str):
                    text = event
                else:
                    continue
                
                if text and len(text.strip()) >= 5:
                    profile['life_events'].append({'event': text.strip(), 'mentioned_on': timestamp})
                    profile['chapters_captured'].add('Life Events')
        
        # Deduplicate all sections
        for key in ['people', 'places', 'work_career', 'interests_hobbies', 'life_events']:
            seen = set()
            unique = []
            field = 'name' if key == 'people' else 'detail' if key != 'life_events' else 'event'
            for item in profile[key]:
                val = item.get(field, '').lower().strip()
                if val and val not in seen:
                    seen.add(val)
                    unique.append(item)
            profile[key] = unique
        
        profile['chapters_captured'] = sorted(list(profile['chapters_captured']))
        
        chapters_count = len(profile['chapters_captured'])
        profile['progress'] = {
            'chapters_captured': chapters_count,
            'total_chapters': 8,
            'percentage': int((chapters_count / 8) * 100),
            'next_areas': self._suggest_biography_areas_v2(profile)
        }
        
        return profile
    
    def _suggest_biography_areas_v2(self, profile):
        """Suggest chapters to explore"""
        all_chapters = {
            'Places & Locations': 'Where have you lived? Where have you traveled?',
            'Important People': 'Family, friends, mentors who shaped your life',
            'Work & Career': 'What did you do for work?',
            'Interests & Hobbies': 'What do you love doing?',
            'Childhood': 'Growing up, early memories',
            'Family': 'Parents, siblings, children',
            'Travel & Adventures': 'Favorite trips, adventures',
            'Life Events': 'Marriages, moves, achievements'
        }
        
        captured = set(profile['chapters_captured'])
        missing = [{'chapter': c, 'description': d} for c, d in all_chapters.items() if c not in captured]
        return missing[:3]
    
    def _analyze_biography_progress(self, knowledge_base, conversations):
        """Analyze biography progress"""
        profile = self._build_life_story_profile(conversations)
        
        return {
            'total_stories_captured': len(profile['stories']),
            'life_story_profile': profile,
            'knowledge_base_sections': knowledge_base.count('###') if knowledge_base else 0,
            'knowledge_base_words': len(knowledge_base.split()) if knowledge_base else 0,
            'completeness_estimate': profile['progress']['percentage'],
            'next_areas_to_explore': profile['progress']['next_areas']
        }
    
    def _identify_alerts(self, conversations, health_events=None):
        """Identify alerts with health events"""
        alerts = []
        
        false_alarm_keywords = ['technical', 'ai', 'glitch', 'error', 'system', 'connectivity']
        
        def is_false_alarm(msg):
            if not msg:
                return True
            text = msg.get('concern', str(msg)) if isinstance(msg, dict) else str(msg)
            return any(kw in text.lower() for kw in false_alarm_keywords)
        
        if health_events:
            for event in health_events:
                if event.get('severity') == 'high' and event.get('needs_family_followup'):
                    alerts.append({
                        'type': 'health_event',
                        'severity': 'high',
                        'message': f"{event['title']}: {event['description'][:100]}",
                        'event_id': event['event_id'],
                        'date': event.get('detected_on', ''),
                        'date_formatted': event.get('detected_on_formatted', ''),
                        'action_needed': True,
                        'suggested_action': 'Follow up about this health event'
                    })
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            
            for flag in analysis.get('health', {}).get('red_flags', []):
                if not is_false_alarm(flag):
                    text = flag if isinstance(flag, str) else str(flag)
                    if health_events and any(e.get('severity') == 'high' for e in health_events):
                        continue
                    alerts.append({
                        'type': 'health_concern',
                        'severity': 'high',
                        'message': text,
                        'date': conv.get('timestamp', ''),
                        'date_formatted': self._format_date(conv.get('timestamp', '')),
                        'action_needed': True
                    })
        
        seen = set()
        unique = []
        for a in alerts:
            msg = a.get('message', '').lower()[:50]
            if msg not in seen:
                seen.add(msg)
                unique.append(a)
        
        return sorted(unique, key=lambda x: ({'high': 0, 'medium': 1}.get(x.get('severity'), 2)))[:5]
    
    def _generate_trends(self, conversations):
        """Generate trend data"""
        mood_timeline = []
        engagement_timeline = []
        frequency = defaultdict(int)
        
        for conv in conversations:
            date = conv.get('timestamp', '')
            mood = conv.get('analysis', {}).get('conversation', {}).get('mood', 'neutral')
            eng = conv.get('analysis', {}).get('conversation', {}).get('engagement', 'moderate')
            
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good']):
                mood_score, mood_cat = 3, 'positive'
            elif any(w in mood_lower for w in ['negative', 'sad', 'anxious']):
                mood_score, mood_cat = 1, 'negative'
            else:
                mood_score, mood_cat = 2, 'neutral'
            
            mood_timeline.append({
                'date': date,
                'date_formatted': self._format_date(date),
                'mood': mood_cat,
                'mood_score': mood_score
            })
            
            engagement_timeline.append({
                'date': date,
                'date_formatted': self._format_date(date),
                'engagement': eng,
                'engagement_score': {'high': 3, 'moderate': 2, 'low': 1}.get(str(eng).lower(), 2)
            })
            
            if date:
                try:
                    dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
                    frequency[dt.strftime('%Y-W%W')] += 1
                except:
                    pass
        
        return {
            'mood_timeline': mood_timeline,
            'engagement_timeline': engagement_timeline,
            'conversation_frequency': dict(frequency),
            'total_data_points': len(conversations)
        }
    
    def _generate_recommendations(self, conversations, tester, health_events=None):
        """Generate recommendations with health context"""
        recs = []
        
        if not conversations:
            recs.append({
                'priority': 'high',
                'category': 'getting_started',
                'message': f"Schedule first conversation with {tester['signup_data'].get('theirName', 'your loved one')}",
                'action': 'Share conversation link'
            })
            return recs
        
        if health_events:
            for event in health_events:
                if event.get('severity') == 'high' and event.get('needs_family_followup'):
                    recs.append({
                        'priority': 'high',
                        'category': 'health_followup',
                        'message': f"Follow up on: {event['title']}",
                        'action': f"Check in about the {event['title'].lower()} from {event['detected_on_formatted']}",
                        'event_id': event['event_id']
                    })
                    break
        
        if len(conversations) < 2:
            recs.append({
                'priority': 'medium',
                'category': 'engagement',
                'message': 'Encourage regular conversations',
                'action': 'Suggest 2-3 conversations per week'
            })
        
        total_stories = sum(len(c.get('analysis', {}).get('biography', {}).get('stories', [])) for c in conversations)
        if total_stories > 0:
            recs.append({
                'priority': 'low',
                'category': 'connection',
                'message': f"{total_stories} stories shared",
                'action': 'Read highlights to stay connected'
            })
        
        return recs
