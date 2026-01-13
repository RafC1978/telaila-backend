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
        
        # Theme icons for display (will be matched to actual topics)
        self.theme_icons = {
            # Broad categories
            'family': '👨‍👩‍👧‍👦',
            'health': '🏥',
            'travel': '✈️',
            'home': '🏠',
            'work': '💼',
            'hobbies': '🎯',
            'friends': '👥',
            'memories': '💭',
            'daily_life': '☀️',
            'food': '🍽️',
            'nature': '🌿',
            'pets': '🐾',
            'music': '🎵',
            'books': '📚',
            'sports': '⚽',
            'garden': '🌻',
            'crafts': '🎨',
            'faith': '🙏',
            'weather': '🌤️',
            'shopping': '🛍️',
            'general': '💬',
            
            # Specific themes
            'snowbird': '🌴',
            'poker': '🃏',
            'rv_life': '🚐',
            'social_outings': '🍽️',
            'daily_errands': '📋',
            'health_recovery': '💪',
            'friends_social': '👥',
            'visitors': '🏠',
            'conversations': '💬',
        }
        
        # Keywords to help categorize topics into icon groups
        # NOTE: Order matters for overlapping keywords - more specific first!
        self.topic_categories = {
            # Check these FIRST (more specific)
            'shopping': ['bookstore', 'shop', 'shopping', 'store', 'market', 'buy', 'bought'],
            'pets': ['dog', 'cat', 'cats', 'pet', 'animal', 'kitten', 'puppy'],
            'weather': ['weather', 'rain', 'sunny', 'cold', 'warm', 'snow'],
            'books': ['book', 'read', 'reading', 'mystery', 'novel', 'show', 'tv', 'author', 'library'],
            
            # Then broader categories
            'family': ['family', 'daughter', 'son', 'wife', 'husband', 'grandkid', 'grandson', 
                      'granddaughter', 'mother', 'father', 'sister', 'brother', 'parent', 'child', 'kids',
                      'visit with son', 'visit with daughter', 'son\'s visit', 'daughter\'s visit'],
            'health': ['health', 'doctor', 'hospital', 'pain', 'sick', 'medicine', 'injury', 
                      'recovery', 'appointment', 'eye doctor'],
            'travel': ['travel', 'trip', 'vacation', 'journey', 'flight', 'cruise', 'adventure'],
            'home': ['home', 'house', 'apartment', 'moved', 'neighborhood', 'routine', 'morning'],
            'work': ['work', 'job', 'career', 'business', 'office', 'retired', 'profession'],
            'hobbies': ['hobby', 'craft', 'collect', 'build', 'create', 'project', 'knitting', 'sewing', 'woodworking'],
            'friends': ['friend', 'neighbor', 'community', 'club', 'group', 'reconnect'],
            'memories': ['remember', 'childhood', 'grew up', 'years ago', 'used to', 'back then', 'history'],
            'food': ['cook', 'recipe', 'food', 'meal', 'baking', 'kitchen', 'tea'],
            'nature': ['garden', 'flowers', 'plants', 'outdoors', 'birds', 'spring', 
                      'crocus', 'bloom', 'tree'],
            'music': ['music', 'song', 'sing', 'instrument', 'concert'],
            'sports': ['golf', 'fishing', 'sports', 'game', 'exercise', 'walk', 'walking'],
            'faith': ['church', 'faith', 'pray', 'god', 'spiritual', 'religion'],
        }
        
        # Words that should NOT trigger category matching (too ambiguous)
        # Format: category -> list of (blocker_phrase, exception_keywords)
        # If exception keywords are found, the blocker doesn't apply
        self.category_blockers = {
            'nature': {
                'blockers': ['nature of', 'human nature', 'by nature'],
                'exceptions': []
            },
        }
        
        # Keywords that indicate family context (used to override blockers)
        self.family_keywords = ['son', 'daughter', 'wife', 'husband', 'grandkid', 'grandson', 
                               'granddaughter', 'mother', 'father', 'sister', 'brother', 
                               'family', 'parent', 'child', 'kids']
        
        # Meta topics to FILTER OUT (not real topics)
        self.meta_topic_patterns = [
            r'introduction',
            r'purpose of (call|conversation)',
            r'getting to know',
            r'first (call|conversation|chat)',
            r'how (aila|the system) works',
            r'explain(ing)? (the|how)',
        ]
        
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
            
            # Vague/filler responses
            r"^well,? i (do )?(think|guess|suppose)",
            r"i think them through",
            r"^i'?m not sure",
            r"^i (would|could) say",
            r"^it'?s (hard|difficult) to (say|explain)",
            r"^that depends",
            r"^in a way",
            r"^sort of",
            r"^kind of",
            r"^i mean",
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
    
    def _smart_truncate(self, text, max_length=350):
        """Truncate text at sentence boundary if possible, otherwise at word boundary"""
        if not text:
            return ""
        
        # Clean up the text first
        text = str(text).strip()
        
        # Remove leading "..." if present
        while text.startswith('...'):
            text = text[3:].strip()
        
        # Remove trailing artifacts like }' or }}
        while text and text[-1] in "}'\"]}":
            text = text[:-1].strip()
        
        # Remove JSON-like artifacts
        text = text.replace("{'", "").replace("'}", "")
        text = text.replace('{"', "").replace('"}', "")
        text = text.replace("', '", ", ").replace('", "', ", ")
        
        # If already short enough, return as-is
        if len(text) <= max_length:
            # Make sure it ends cleanly
            text = text.rstrip('.,;: ')
            if text and text[-1] not in '.!?':
                text += '.'
            return text
        
        # Try to find a sentence ending within the limit
        truncated = text[:max_length]
        
        # Look for sentence endings (in order of preference)
        best_end = -1
        for ending in ['. ', '! ', '? ', '.\n', '!\n', '?\n', '.', '!', '?']:
            pos = truncated.rfind(ending)
            if pos > max_length * 0.4:  # At least 40% of the length
                # Check if this is actually the end of a sentence (not Mr. or Dr.)
                before = truncated[:pos].split()[-1] if truncated[:pos].split() else ""
                if before.lower() not in ['mr', 'mrs', 'ms', 'dr', 'st', 'vs', 'etc', 'i.e', 'e.g']:
                    best_end = pos + len(ending.rstrip())
                    break
        
        if best_end > 0:
            result = text[:best_end].strip()
            if result and result[-1] not in '.!?':
                result += '.'
            return result
        
        # No good sentence ending - try to find a comma or semicolon
        for sep in [', ', '; ', ' - ', ' – ']:
            last_sep = truncated.rfind(sep)
            if last_sep > max_length * 0.5:
                return text[:last_sep].strip() + '...'
        
        # Cut at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.4:
            return text[:last_space].strip() + '...'
        
        # Just truncate and add ...
        return truncated.strip() + '...'
    
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
    
    def _analyze_quote_sentiment(self, quote, default_emoji, default_label):
        """
        Analyze the quote content and return appropriate mood emoji/label.
        Override conversation mood when quote content suggests different sentiment.
        """
        if not quote:
            return default_emoji, default_label
        
        quote_lower = quote.lower()
        
        # Pain/injury indicators - use 💪 Persevering (they're sharing, being strong)
        pain_words = ['pain', 'hurt', 'sore', 'ache', 'bruise', 'injured', 'injury',
                     'stiff', 'swollen', 'inflammation', 'discomfort']
        if any(word in quote_lower for word in pain_words):
            return '💪', 'Persevering'
        
        # Struggle/difficulty indicators - use 😓 Struggling  
        struggle_words = ['tough', 'difficult', 'hard time', "couldn't", "can't", 
                         'struggle', 'terrible', 'awful', 'worst', 'rough',
                         'trouble sleeping', "couldn't sleep", "can't sleep"]
        if any(word in quote_lower for word in struggle_words):
            return '😓', 'Struggling'
        
        # Recovery/improvement indicators - use 🌱 Recovering
        recovery_words = ['better', 'improving', 'healing', 'recovered', 'getting better',
                         'feeling better', 'bit better', 'little better']
        if any(word in quote_lower for word in recovery_words):
            return '🌱', 'Recovering'
        
        # Worry/concern indicators - use 😟 Concerned
        worry_words = ['worried', 'anxious', 'nervous', 'scared', 'afraid', 'concern']
        if any(word in quote_lower for word in worry_words):
            return '😟', 'Concerned'
        
        # Gratitude/appreciation - use 🙏 Grateful
        gratitude_words = ['grateful', 'thankful', 'blessed', 'appreciate', 'lucky']
        if any(word in quote_lower for word in gratitude_words):
            return '🙏', 'Grateful'
        
        # Joy/excitement - use 😊 Happy
        joy_words = ['love', 'enjoy', 'wonderful', 'amazing', 'fantastic', 'great time',
                    'rewarding', 'beautiful', 'exciting', 'fun']
        if any(word in quote_lower for word in joy_words):
            return '😊', 'Happy'
        
        # Nostalgia/reflection - use 💭 Nostalgic
        nostalgia_words = ['remember', 'years ago', 'used to', 'back then', 'childhood',
                          'grew up', 'when i was', 'memories']
        if any(word in quote_lower for word in nostalgia_words):
            return '💭', 'Nostalgic'
        
        # Wisdom/philosophical - use 🌟 Reflective
        wisdom_words = ['learn', 'realize', 'understand', 'life is', 'important thing',
                       'adventure', 'perspective', 'open-minded']
        if any(word in quote_lower for word in wisdom_words):
            return '🌟', 'Reflective'
        
        # Default to conversation mood
        return default_emoji, default_label
    
    def _detect_theme(self, text, topics=None, stories=None):
        """
        Detect theme based on ACTUAL conversation topics, not hardcoded keywords.
        
        Returns: (theme_id, theme_name, icon)
        
        NEW APPROACH:
        1. If topics are provided, use the FIRST topic as the theme
        2. If no topics, try to categorize based on text content
        3. Generate human-readable theme names from actual topics
        """
        # Priority 1: Use actual topics from conversation analysis
        if topics and len(topics) > 0:
            # Use the first/primary topic
            primary_topic = topics[0] if isinstance(topics[0], str) else str(topics[0])
            theme_name = self._format_theme_name(primary_topic)
            icon = self._get_theme_icon(primary_topic.lower())
            theme_id = self._make_theme_id(primary_topic)
            return theme_id, theme_name, icon
        
        # Priority 2: Check if stories have topics
        if stories:
            for story in stories:
                if isinstance(story, dict) and story.get('topic'):
                    topic = story['topic']
                    theme_name = self._format_theme_name(topic)
                    icon = self._get_theme_icon(topic.lower())
                    theme_id = self._make_theme_id(topic)
                    return theme_id, theme_name, icon
        
        # Priority 3: Try to categorize the text content
        if text:
            text_lower = text.lower()
            for category, keywords in self.topic_categories.items():
                for kw in keywords:
                    if kw in text_lower:
                        theme_name = category.replace('_', ' ').title()
                        icon = self.theme_icons.get(category, '💬')
                        return category, theme_name, icon
        
        # Default
        return 'life_stories', 'Life Stories', '💬'
    
    def _format_theme_name(self, topic):
        """Convert a topic string into a clean, short theme name"""
        if not topic:
            return 'Life Stories'
        
        # Clean up the topic
        name = topic.strip()
        
        # If very long, try to extract the key noun phrase
        if len(name) > 40:
            # Try to get first meaningful phrase before "and", "with", etc.
            for splitter in [' and ', ' with ', ' about ', ' - ', ', ']:
                if splitter in name.lower():
                    parts = name.split(splitter[0].upper() + splitter[1:] if splitter[0].isupper() else splitter)
                    if not parts:
                        parts = name.lower().split(splitter)
                    if parts and len(parts[0]) > 3:
                        name = parts[0].strip()
                        break
        
        # Truncate if still too long
        if len(name) > 35:
            # Cut at last space before limit
            if ' ' in name[:35]:
                name = name[:35].rsplit(' ', 1)[0]
            else:
                name = name[:32] + '...'
        
        # Fix capitalization - title case but preserve apostrophes properly
        words = name.split()
        formatted_words = []
        for word in words:
            if word.upper() == word and len(word) > 2:  # All caps like "TV"
                formatted_words.append(word)
            elif "'" in word:  # Handle apostrophes like "Son's"
                parts = word.split("'")
                formatted_words.append("'".join(p.capitalize() if i == 0 else p.lower() for i, p in enumerate(parts)))
            else:
                formatted_words.append(word.capitalize())
        
        name = ' '.join(formatted_words)
        
        # Handle some common patterns
        name = name.replace('_', ' ')
        
        return name
    
    def _is_meta_topic(self, topic):
        """Check if a topic is a meta-topic (about the conversation itself, not real content)"""
        if not topic:
            return False
        
        topic_lower = topic.lower()
        
        for pattern in self.meta_topic_patterns:
            if re.search(pattern, topic_lower):
                return True
        
        return False
    
    def _normalize_theme_id(self, topic):
        """
        Create a normalized theme ID that groups SIMILAR topics together,
        but preserves distinct meaningful topics.
        
        Strategy:
        1. Check for specific distinct topics (snowbird, poker, etc.)
        2. Check if topic matches a broad category (family, nature, etc.)
        3. Only fall back to raw word extraction if nothing else matches
        """
        if not topic:
            return 'general'
        
        topic_lower = topic.lower().strip()
        
        # PRIORITY 1: Check for SPECIFIC meaningful topics that should stay distinct
        specific_topics = {
            'snowbird': 'snowbird',
            'poker': 'poker',
            'rv life': 'rv_life',
            'rv ': 'rv_life',
            'rv water': 'rv_life',
            'trailer park': 'rv_life', 
            'dinner out': 'social_outings',
            'dinner with': 'social_outings',
            'lunch out': 'social_outings',
            'lunch with': 'social_outings',
            'restaurant': 'social_outings',
            'chinese food': 'social_outings',
            'sushi': 'social_outings',
            'storage facility': 'daily_errands',
            'lockout': 'daily_errands',
            'getting keys': 'daily_errands',
            'visitors to': 'visitors',
            'canadian visitors': 'visitors',
            'nature of ai': 'conversations',
            'nature of consciousness': 'conversations',
            'ai consciousness': 'conversations',
            'human vs ai': 'conversations',
            'problem-solving': 'conversations',
        }
        
        for keyword, theme_id in specific_topics.items():
            if keyword in topic_lower:
                return theme_id
        
        # PRIORITY 2: Check broad categories (with blocker check)
        for category, keywords in self.topic_categories.items():
            # Check if any blocker phrase is present for this category
            blocker_info = self.category_blockers.get(category, {})
            blockers = blocker_info.get('blockers', []) if isinstance(blocker_info, dict) else []
            
            blocked = False
            for blocker in blockers:
                if blocker in topic_lower:
                    blocked = True
                    break
            
            if blocked:
                continue
            
            # Check if any keyword matches
            for kw in keywords:
                if kw in topic_lower:
                    return category
        
        # PRIORITY 3: Extract primary word and check special mappings
        common_words = {
            'the', 'a', 'an', 'and', 'or', 'with', 'about', 'for', 'to', 'of', 
            'in', 'on', 'at', 'by', 'progress', 'challenges', 'conditions',
            'management', 'incident', 'question', 'lifestyle', 'connections',
            'perspectives', 'adventures', 'technical', 'recent', 'new', 'old',
            'outing', 'like', 'living', 'facility'
        }
        
        words = re.findall(r'[a-z]+', topic_lower)
        primary_word = None
        
        for word in words:
            if word not in common_words and len(word) > 2:
                primary_word = word
                break
        
        if primary_word:
            # Map specific words to themes
            word_mappings = {
                # Health
                'back': 'health_recovery',
                'sleep': 'health_recovery', 
                'pain': 'health_recovery',
                'injury': 'health_recovery',
                'recovery': 'health_recovery',
                
                # Social
                'canadian': 'visitors',
                'visitors': 'visitors',
                
                # AI/meta (filter these out or group them)
                'human': 'conversations',
                'consciousness': 'conversations',
                'empathy': 'conversations',
                'problem': 'conversations',
                'solving': 'conversations',
                'capabilities': 'conversations',
                
                # Daily life
                'emergency': 'daily_life',
                'contact': 'daily_life',
                'errands': 'daily_errands',
                'keys': 'daily_errands',
                'storage': 'daily_errands',
                
                # RV/travel
                'water': 'rv_life',
                'tank': 'rv_life',
            }
            
            if primary_word in word_mappings:
                return word_mappings[primary_word]
        
        # FINAL FALLBACK: Return primary word as-is (rare)
        if primary_word:
            return primary_word
        
        return 'general'
    
    def _make_theme_id(self, topic):
        """Create a safe theme ID from a topic"""
        if not topic:
            return 'general'
        
        # Make lowercase, replace spaces with underscores
        theme_id = topic.lower().strip()
        theme_id = re.sub(r'[^a-z0-9\s]', '', theme_id)
        theme_id = re.sub(r'\s+', '_', theme_id)
        
        return theme_id[:50] if theme_id else 'general'
    
    def _get_theme_icon(self, topic_text):
        """Get an appropriate icon for a topic"""
        if not topic_text:
            return '💬'
        
        topic_lower = topic_text.lower()
        
        # Check each category
        for category, keywords in self.topic_categories.items():
            for kw in keywords:
                if kw in topic_lower:
                    return self.theme_icons.get(category, '💬')
        
        return '💬'
    
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
            
            # === THREE MAIN SECTIONS (matching demo tabs) ===
            'weekly_updates': self._generate_weekly_updates(conversations, elder_name),
            'health_insights': self._generate_health_insights_v2(conversations, health_events, elder_name),
            'life_story': self._generate_life_story(conversations, knowledge_base, elder_name),
            
            # === LEGACY (keep for backward compatibility) ===
            'summary': self._generate_summary(conversations, tester, health_events),
            'health_events': health_events,
            'in_their_words': self._build_in_their_words(conversations, elder_name),
            'biography_progress': self._analyze_biography_progress(knowledge_base, conversations),
            'alerts': self._identify_alerts(conversations, health_events),
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
        Build DYNAMIC "In Their Words" section.
        
        KEY FIX: Categorize each quote by its CONTENT, not just the conversation's topic.
        This ensures a snowbird quote isn't labeled "health" just because the conversation
        was primarily about health.
        """
        # Collect quotes organized by theme
        theme_data = defaultdict(lambda: {
            'quotes': [],
            'original_topics': [],
            'icon': '💬',
            'first_mentioned': None,
            'last_mentioned': None
        })
        
        meta_filtered_count = 0
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            conv_quotes = analysis.get('conversation', {}).get('memorable_quotes', [])
            topics = analysis.get('conversation', {}).get('topics', [])
            mood = analysis.get('conversation', {}).get('mood', 'neutral')
            
            timestamp = conv.get('timestamp', '')
            date_fmt = self._format_date(timestamp)
            
            # Get conversation mood
            conv_mood_lower = str(mood).lower()
            if any(w in conv_mood_lower for w in ['positive', 'happy', 'good', 'cheerful']):
                conv_mood_emoji, conv_mood_label = '😊', 'Happy'
            elif any(w in conv_mood_lower for w in ['negative', 'sad', 'upset', 'worried']):
                conv_mood_emoji, conv_mood_label = '😔', 'Reflective'
            else:
                conv_mood_emoji, conv_mood_label = '😌', 'Relaxed'
            
            # Process each quote INDIVIDUALLY
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
                
                # CATEGORIZE BY QUOTE CONTENT (not conversation topic)
                theme_id = self._categorize_quote(quote_stripped, topics)
                
                # Skip meta themes
                if theme_id in ['introduction', 'conversations', 'general']:
                    # Try harder to find a real theme
                    for topic in topics:
                        if topic and not self._is_meta_topic(topic):
                            alt_theme = self._normalize_theme_id(topic)
                            if alt_theme not in ['introduction', 'conversations', 'general']:
                                theme_id = alt_theme
                                break
                
                # Still generic? Skip or use fallback
                if theme_id == 'general':
                    continue
                
                # Get icon for this theme
                icon = self.theme_icons.get(theme_id, '💬')
                
                # Analyze quote-specific sentiment
                quote_mood_emoji, quote_mood_label = self._analyze_quote_sentiment(
                    quote_stripped, conv_mood_emoji, conv_mood_label
                )
                
                # Store with the theme
                theme_data[theme_id]['icon'] = icon
                theme_data[theme_id]['quotes'].append({
                    'quote': quote_stripped,
                    'date': date_fmt,
                    'timestamp': timestamp,
                    'mood': quote_mood_label,
                    'mood_emoji': quote_mood_emoji
                })
                
                # Track original topics
                if topics:
                    theme_data[theme_id]['original_topics'].extend(topics)
                
                # Update timestamps
                if not theme_data[theme_id]['first_mentioned'] or timestamp < theme_data[theme_id]['first_mentioned']:
                    theme_data[theme_id]['first_mentioned'] = timestamp
                if not theme_data[theme_id]['last_mentioned'] or timestamp > theme_data[theme_id]['last_mentioned']:
                    theme_data[theme_id]['last_mentioned'] = timestamp
        
        # Build final themes list
        themes = []
        for theme_id, data in theme_data.items():
            if not data['quotes']:
                continue
            
            # Generate display name
            theme_name = self._generate_theme_display_name(theme_id, data['original_topics'])
            
            # FINAL CHECK: Skip meta themes
            if self._is_meta_topic(theme_name) or self._is_meta_topic(theme_id):
                meta_filtered_count += 1
                continue
            
            icon = data.get('icon', '💬')
            
            # Deduplicate quotes
            seen_quotes = set()
            unique_quotes = []
            for q in data['quotes']:
                q_lower = q['quote'].lower().strip()[:50]
                if q_lower not in seen_quotes:
                    seen_quotes.add(q_lower)
                    unique_quotes.append(q)
            
            # Sort quotes by date (newest first)
            unique_quotes.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
            # Simple context
            context = f"{elder_name} has shared {len(unique_quotes)} memorable moments about {theme_name.lower()}."
            
            themes.append({
                'theme_id': theme_id,
                'theme_name': theme_name,
                'icon': icon,
                'priority': len(unique_quotes),
                'context': context,
                'quotes': unique_quotes[:5],
                'total_quotes': len(unique_quotes),
                'first_mentioned': self._format_date(data['first_mentioned']),
                'last_updated': self._format_date(data['last_mentioned'])
            })
        
        # Sort themes by number of quotes
        themes.sort(key=lambda x: x.get('total_quotes', 0), reverse=True)
        
        return {
            'themes': themes,
            'meta_filtered_count': meta_filtered_count,
            'total_themes': len(themes)
        }
    
    def _categorize_quote(self, quote, conversation_topics=None):
        """
        Categorize a quote based on its CONTENT.
        
        Priority:
        1. Check quote text for specific keywords (snowbird, poker, RV, etc.)
        2. Check quote text against category keywords (family, nature, etc.)
        3. Fall back to conversation topic if quote has no clear category
        4. Return 'general' if nothing matches
        """
        quote_lower = quote.lower()
        
        # PRIORITY 1: Specific meaningful topics from quote content
        specific_keywords = {
            # Snowbird/RV lifestyle
            'snowbird': 'snowbird',
            'snow bird': 'snowbird',
            'rv life': 'rv_life',
            'rv community': 'rv_life',
            'rv park': 'rv_life',
            'trailer park': 'rv_life',
            'arizona': 'snowbird',
            'winter in': 'snowbird',
            
            # Social activities
            'poker': 'poker',
            'card game': 'poker',
            'dinner out': 'social_outings',
            'went to dinner': 'social_outings',
            'restaurant': 'social_outings',
            'chinese food': 'social_outings',
            'sushi': 'social_outings',
            
            # Family
            'my son': 'family',
            'my daughter': 'family',
            'my wife': 'family',
            'my husband': 'family',
            'grandkid': 'family',
            'grandchild': 'family',
            
            # Nature
            'crocus': 'nature',
            'flower': 'nature',
            'garden': 'nature',
            'spring': 'nature',
            'bloom': 'nature',
            
            # Pets
            'my cat': 'pets',
            'my dog': 'pets',
            'the cat': 'pets',
            'the dog': 'pets',
            
            # Health (only if explicitly about health, not just mentions)
            'fell off': 'health_recovery',
            'back injury': 'health_recovery',
            'back pain': 'health_recovery',
            'bruised': 'health_recovery',
            'hurt when': 'health_recovery',
            'getting better': 'health_recovery',
            'little bit better': 'health_recovery',
            'recovery': 'health_recovery',
            'fell and': 'health_recovery',
            'fall and': 'health_recovery',
            'hit the concrete': 'health_recovery',
            'muscles': 'health_recovery',
            'doctor': 'health',
            'hospital': 'health',
            
            # Books/Entertainment
            'book': 'books',
            'reading': 'books',
            'tv show': 'books',
            'watching': 'books',
            
            # Friends
            'my friend': 'friends',
            'old friend': 'friends',
            'friendship': 'friends',
        }
        
        for keyword, theme_id in specific_keywords.items():
            if keyword in quote_lower:
                return theme_id
        
        # PRIORITY 2: Check category keywords
        for category, keywords in self.topic_categories.items():
            # Skip blocked categories for this quote
            blocker_info = self.category_blockers.get(category, {})
            blockers = blocker_info.get('blockers', []) if isinstance(blocker_info, dict) else []
            
            blocked = False
            for blocker in blockers:
                if blocker in quote_lower:
                    blocked = True
                    break
            
            if blocked:
                continue
            
            for kw in keywords:
                if kw in quote_lower:
                    return category
        
        # PRIORITY 3: Fall back to conversation topic
        if conversation_topics:
            for topic in conversation_topics:
                if topic and not self._is_meta_topic(topic):
                    return self._normalize_theme_id(topic)
        
        return 'general'
    def _generate_theme_display_name(self, theme_id, original_topics):
        """Generate a nice display name for a theme based on its ID and original topics"""
        
        # Map theme IDs to nice display names
        display_names = {
            # Broad categories
            'family': 'Family',
            'health': 'Health & Wellness',
            'travel': 'Travel & Outings',
            'home': 'Home & Daily Life',
            'work': 'Work & Career',
            'hobbies': 'Hobbies & Interests',
            'friends': 'Friends & Social',
            'memories': 'Memories',
            'food': 'Food & Cooking',
            'nature': 'Nature & Garden',
            'pets': 'Pets',
            'music': 'Music',
            'books': 'Books & Entertainment',
            'sports': 'Sports & Exercise',
            'faith': 'Faith & Spirituality',
            'weather': 'Weather',
            'shopping': 'Shopping & Errands',
            
            # Specific themes (from _normalize_theme_id)
            'snowbird': 'Snowbird Life',
            'poker': 'Poker & Games',
            'rv_life': 'RV Life',
            'social_outings': 'Dining & Outings',
            'daily_errands': 'Daily Errands',
            'health_recovery': 'Health & Recovery',
            'friends_social': 'Friends & Social',
            'visitors': 'Visitors & Guests',
            'daily_life': 'Daily Life',
            'conversations': 'Conversations',
        }
        
        if theme_id in display_names:
            return display_names[theme_id]
        
        # Otherwise, try to create a nice name from the theme_id
        if theme_id:
            return theme_id.replace('_', ' ').title()
        
        return 'Life Stories'
    def _build_theme_context(self, theme_id, data, elder_name):
        """Build a simple narrative context for a theme"""
        # This method is kept for backward compatibility but simplified
        # The new _build_in_their_words generates its own context
        
        total_quotes = len(data.get('quotes', []))
        theme_name = theme_id.replace('_', ' ').title()
        
        if total_quotes > 0:
            return f"{elder_name} has shared {total_quotes} memorable moments about {theme_name.lower()}."
        else:
            return f"Stories and memories shared about {theme_name.lower()}."
    
    def _detect_health_events(self, conversations, knowledge_base):
        """
        Detect significant health events - SIMPLIFIED VERSION
        
        Creates ONE primary injury event and links all symptoms to it.
        Only extracts from USER content, not agent responses.
        """
        primary_injury = None
        symptoms = []
        
        # Collect all health-related info
        all_health_summaries = []
        has_fall = False
        body_part = None
        first_mention_date = None
        last_mention_date = None
        mention_count = 0
        
        for conv in conversations:
            timestamp = conv.get('timestamp', '')
            analysis = conv.get('analysis', {})
            health = analysis.get('health', {})
            
            # Get health summary (this is the BEST source - already analyzed)
            summary = health.get('summary', '')
            if summary:
                summary_lower = summary.lower()
                all_health_summaries.append({
                    'text': summary,
                    'timestamp': timestamp
                })
                
                # Check for fall
                if any(w in summary_lower for w in ['fell', 'fall', 'fallen', 'ladder']):
                    has_fall = True
                    mention_count += 1
                    
                # Check for body part
                if not body_part:
                    body_part = self._extract_body_part(summary_lower)
                
                # Track dates
                if timestamp:
                    if not first_mention_date or timestamp < first_mention_date:
                        first_mention_date = timestamp
                    if not last_mention_date or timestamp > last_mention_date:
                        last_mention_date = timestamp
            
            # Also check red flags
            for flag in health.get('red_flags', []):
                flag_text = flag if isinstance(flag, str) else str(flag)
                flag_lower = flag_text.lower()
                
                if any(w in flag_lower for w in ['fell', 'fall', 'fallen', 'ladder']):
                    has_fall = True
                
                if not body_part:
                    body_part = self._extract_body_part(flag_lower)
            
            # Check transcript for USER content only
            transcript = conv.get('transcript', '')
            if transcript:
                # Extract only USER lines
                user_content = self._extract_user_content(transcript)
                user_lower = user_content.lower()
                
                if any(w in user_lower for w in ['fell', 'fall', 'fallen', 'ladder']):
                    has_fall = True
                    mention_count += 1
                
                if not body_part:
                    body_part = self._extract_body_part(user_lower)
        
        # Also check knowledge base for USER content
        if knowledge_base:
            kb_lower = knowledge_base.lower()
            if any(w in kb_lower for w in ['fell', 'fall', 'fallen', 'ladder']):
                has_fall = True
            if not body_part:
                body_part = self._extract_body_part(kb_lower)
        
        events = []
        
        # Create ONE primary injury event if we detected a fall/injury
        if has_fall and all_health_summaries:
            # Find the BEST description (longest, most informative)
            best_summary = max(all_health_summaries, key=lambda x: len(x['text']))
            
            # Clean up the description
            description = best_summary['text']
            description = self._smart_truncate(description, 400)
            
            # Generate title
            if body_part:
                title = f"Fall Incident - {body_part.title()} Injury"
            else:
                title = "Fall Incident"
            
            primary_injury = {
                'event_id': 'HE_fall_001',
                'type': 'injury',
                'severity': 'high',
                'title': title,
                'description': description,
                'detected_on': first_mention_date or '',
                'detected_on_formatted': self._format_date(first_mention_date),
                'last_mentioned': last_mention_date or '',
                'last_mentioned_formatted': self._format_date(last_mention_date),
                'body_part': body_part,
                'keyword': 'fall',
                'related_symptoms': [],
                'status': 'active',
                'needs_family_followup': True,
                'mentions_count': max(mention_count, len(all_health_summaries)),
                'family_actions': [],
            }
            events.append(primary_injury)
        
        # Check for symptoms that should be LINKED to the injury (not separate events)
        # We'll just note them in related_symptoms, not create separate events
        if primary_injury and all_health_summaries:
            symptom_keywords = ['pain', 'sleep', 'sore', 'tired', 'stiff']
            found_symptoms = set()
            
            for summary_data in all_health_summaries:
                summary_lower = summary_data['text'].lower()
                
                for symptom in symptom_keywords:
                    if symptom in summary_lower and symptom not in found_symptoms:
                        found_symptoms.add(symptom)
                        
                        # Create readable symptom name
                        if body_part and symptom != 'sleep':
                            symptom_name = f"{body_part.title()} {symptom}"
                        elif symptom == 'sleep':
                            symptom_name = "Sleep difficulties"
                        else:
                            symptom_name = symptom.title()
                        
                        primary_injury['related_symptoms'].append({
                            'symptom': symptom_name,
                            'status': 'ongoing'
                        })
        
        return events
    
    def _extract_user_content(self, transcript):
        """Extract only USER content from transcript, filtering out agent responses"""
        if not transcript:
            return ""
        
        user_lines = []
        lines = transcript.split('\n')
        
        in_user_section = False
        for line in lines:
            line_stripped = line.strip()
            
            # Check for speaker markers
            if line_stripped.startswith('User:'):
                in_user_section = True
                user_lines.append(line_stripped[5:].strip())
            elif line_stripped.startswith('Aila:') or line_stripped.startswith('Assistant:'):
                in_user_section = False
            elif in_user_section and line_stripped:
                user_lines.append(line_stripped)
        
        return ' '.join(user_lines)
    
    def _extract_health_mentions(self, event_mentions, text, timestamp, source):
        """Extract health-related mentions from text"""
        if not text:
            return
        
        text_lower = text.lower()
        
        # Track what we've added from THIS text passage
        fall_added = False
        other_injuries_found = set()
        symptoms_found = set()
        
        # First check: Is this a FALL incident?
        is_fall = any(fw in text_lower for fw in ['fell', 'fall', 'fallen', 'ladder'])
        body_part = self._extract_body_part(text_lower)
        
        if is_fall and not fall_added:
            # ALL fall incidents go to the SAME key - they will be merged
            event_key = "injury_fall_primary"
            
            # Find the best keyword for context extraction
            for kw in ['fell', 'fall', 'ladder']:
                if kw in text_lower:
                    context = self._extract_context(text, kw)
                    break
            else:
                context = text[:200]
            
            event_mentions[event_key].append({
                'timestamp': timestamp,
                'source': source,
                'text': context or text[:200],
                'keyword': 'fall',
                'body_part': body_part,  # Keep body part for title
                'type': 'injury',
                'severity': 'high'
            })
            fall_added = True
        
        # Check for OTHER injuries (not falls)
        if not is_fall:
            for keyword in self.injury_keywords:
                if keyword in text_lower and keyword not in ['fell', 'fall', 'fallen', 'ladder']:
                    injury_key = body_part or 'general'
                    
                    if injury_key in other_injuries_found:
                        continue
                    other_injuries_found.add(injury_key)
                    
                    event_key = f"injury_{keyword}_{injury_key}"
                    context = self._extract_context(text, keyword)
                    
                    event_mentions[event_key].append({
                        'timestamp': timestamp,
                        'source': source,
                        'text': context or text[:200],
                        'keyword': keyword,
                        'body_part': body_part,
                        'type': 'injury',
                        'severity': 'high'
                    })
        
        # Check for symptoms - group by symptom type + body part
        for keyword in self.symptom_keywords:
            if keyword in text_lower:
                bp = self._extract_body_part(text_lower)
                
                # Normalize symptom keywords
                if 'pain' in keyword or 'ache' in keyword:
                    symptom_type = 'pain'
                elif 'sleep' in keyword:
                    symptom_type = 'sleep'
                else:
                    symptom_type = keyword.replace(' ', '_')
                
                symptom_key = f"{symptom_type}_{bp or 'general'}"
                
                if symptom_key in symptoms_found:
                    continue
                symptoms_found.add(symptom_key)
                
                event_key = f"symptom_{symptom_key}"
                context = self._extract_context(text, keyword)
                
                event_mentions[event_key].append({
                    'timestamp': timestamp,
                    'source': source,
                    'text': context or text[:200],
                    'keyword': keyword,
                    'body_part': bp,
                    'type': 'symptom',
                    'severity': 'moderate'
                })
    
    def _extract_context(self, text, keyword):
        """Extract surrounding context for a keyword"""
        if not text:
            return None
            
        text_lower = text.lower()
        idx = text_lower.find(keyword)
        if idx == -1:
            return None
        
        # Get more context - 80 chars before, 150 after
        start = max(0, idx - 80)
        end = min(len(text), idx + len(keyword) + 150)
        
        context = text[start:end].strip()
        
        # Try to start at a sentence or word boundary
        if start > 0:
            # Look for sentence start
            first_period = context.find('. ')
            first_capital_after = -1
            for i, c in enumerate(context):
                if c.isupper() and i > 0:
                    first_capital_after = i
                    break
            
            if first_period != -1 and first_period < 30:
                context = context[first_period + 2:]
            elif first_capital_after != -1 and first_capital_after < 20:
                context = context[first_capital_after:]
        
        # Clean up any JSON artifacts
        context = context.replace("'}", "").replace('"}', "").replace("{'", "").replace('{"', "")
        context = context.replace("', '", ", ").replace('", "', ", ")
        
        return context.strip()
    
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
            
            # Check ALL mentions for body part (some may have it, some may not)
            body_part = None
            for m in sorted_mentions:
                if m.get('body_part'):
                    body_part = m['body_part']
                    break
            
            if keyword in ['fell', 'fall', 'fallen', 'ladder'] or 'fall' in event_key:
                severity = 'high'
            elif event_type == 'injury':
                severity = 'high'
            elif len(sorted_mentions) >= 3:
                severity = 'moderate'
            else:
                severity = 'low'
            
            # Generate title
            if keyword in ['fell', 'fall', 'fallen', 'ladder'] or 'fall' in event_key:
                title = "Fall Incident"
                if body_part:
                    title = f"Fall Incident - {body_part.title()} Injury"
            elif body_part:
                title = f"{body_part.title()} {keyword.title()}"
            else:
                title = keyword.replace('_', ' ').title()
            
            event_id = hashlib.md5(f"{event_key}_{first.get('timestamp', 'unknown')}".encode()).hexdigest()[:8]
            
            # Get the BEST description (longest, most informative)
            descriptions = [m.get('text', '') for m in sorted_mentions if m.get('text')]
            if descriptions:
                # Pick the longest description
                description = max(descriptions, key=len)
            else:
                description = title
            
            # Clean and truncate description
            description = self._smart_truncate(description, 350)
            
            events.append({
                'event_id': f"HE_{event_id}",
                'type': event_type,
                'severity': severity,
                'title': title,
                'description': description,
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
        """Link symptoms to their root causes, after deduplicating injuries"""
        
        # STEP 1: Deduplicate injury events with same body part
        # Keep the "Fall Incident" title if present, merge others into it
        injuries = [e for e in events if e['type'] == 'injury']
        symptoms = [e for e in events if e['type'] == 'symptom']
        other = [e for e in events if e['type'] not in ['injury', 'symptom']]
        
        # STEP 1A: First merge ALL fall incidents together (they're the same event)
        fall_injuries = [i for i in injuries if 'fall' in i.get('title', '').lower() or 'fall' in i.get('keyword', '').lower()]
        non_fall_injuries = [i for i in injuries if i not in fall_injuries]
        
        merged_injuries = []
        
        # Merge all fall incidents into one
        if fall_injuries:
            # Find the one with body part (most specific)
            primary = None
            for inj in fall_injuries:
                if inj.get('body_part'):
                    primary = inj
                    break
            
            if not primary:
                primary = fall_injuries[0]
            
            # Ensure good title
            if primary.get('body_part'):
                primary['title'] = f"Fall Incident - {primary['body_part'].title()} Injury"
            else:
                primary['title'] = "Fall Incident"
            
            # Merge all descriptions and data
            all_descriptions = []
            total_mentions = 0
            earliest_date = primary.get('detected_on', '')
            latest_date = primary.get('last_mentioned', '')
            all_body_parts = set()
            
            for inj in fall_injuries:
                if inj.get('description'):
                    all_descriptions.append(inj['description'])
                total_mentions += inj.get('mentions_count', 1)
                
                if inj.get('body_part'):
                    all_body_parts.add(inj['body_part'])
                
                inj_date = inj.get('detected_on', '')
                if inj_date and (not earliest_date or inj_date < earliest_date):
                    earliest_date = inj_date
                
                inj_last = inj.get('last_mentioned', '')
                if inj_last and (not latest_date or inj_last > latest_date):
                    latest_date = inj_last
            
            # Use the best description
            best_description = max(all_descriptions, key=len) if all_descriptions else primary.get('description', '')
            
            # Update primary with merged data
            primary['description'] = self._smart_truncate(best_description, 300)
            primary['mentions_count'] = total_mentions
            primary['detected_on'] = earliest_date
            primary['detected_on_formatted'] = self._format_date(earliest_date)
            primary['last_mentioned'] = latest_date
            primary['last_mentioned_formatted'] = self._format_date(latest_date)
            
            # If we found body parts, update
            if all_body_parts:
                primary['body_part'] = list(all_body_parts)[0]  # Use first found
                primary['title'] = f"Fall Incident - {primary['body_part'].title()} Injury"
            
            merged_injuries.append(primary)
        
        # STEP 1B: Group remaining (non-fall) injuries by body part
        injuries_by_body = {}
        for injury in non_fall_injuries:
            body = injury.get('body_part') or 'general'
            if body not in injuries_by_body:
                injuries_by_body[body] = []
            injuries_by_body[body].append(injury)
        
        # Merge non-fall injuries with same body part
        for body, body_injuries in injuries_by_body.items():
            if len(body_injuries) == 1:
                merged_injuries.append(body_injuries[0])
            else:
                # Multiple injuries for same body part - merge them
                primary = body_injuries[0]
                
                all_descriptions = []
                total_mentions = 0
                earliest_date = primary.get('detected_on', '')
                latest_date = primary.get('last_mentioned', '')
                
                for inj in body_injuries:
                    if inj.get('description'):
                        all_descriptions.append(inj['description'])
                    total_mentions += inj.get('mentions_count', 1)
                    
                    inj_date = inj.get('detected_on', '')
                    if inj_date and (not earliest_date or inj_date < earliest_date):
                        earliest_date = inj_date
                    
                    inj_last = inj.get('last_mentioned', '')
                    if inj_last and (not latest_date or inj_last > latest_date):
                        latest_date = inj_last
                
                best_description = max(all_descriptions, key=len) if all_descriptions else primary.get('description', '')
                
                primary['description'] = self._smart_truncate(best_description, 300)
                primary['mentions_count'] = total_mentions
                primary['detected_on'] = earliest_date
                primary['detected_on_formatted'] = self._format_date(earliest_date)
                primary['last_mentioned'] = latest_date
                primary['last_mentioned_formatted'] = self._format_date(latest_date)
                
                merged_injuries.append(primary)
        
        # STEP 2: Link symptoms to causes
        for symptom in symptoms:
            symptom_body = symptom.get('body_part')
            symptom_date = symptom.get('detected_on', '')
            
            for cause in merged_injuries:
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
        
        # Combine all events
        all_events = merged_injuries + symptoms + other
        
        # Sort by severity and date
        all_events.sort(key=lambda x: (
            {'high': 0, 'moderate': 1, 'low': 2}.get(x['severity'], 2),
            x.get('detected_on', '') or 'zzz'
        ))
        
        return all_events
    
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
    
    def _generate_weekly_updates(self, conversations, elder_name):
        """
        Generate Weekly Updates section matching the demo format:
        - Conversations This Week (count + days)
        - Overall Mood (with emoji and description)
        - Engagement (level and description)
        - Latest Conversation Summary (narrative + key moments)
        - This Week's Highlights (day-by-day)
        """
        now = datetime.now(self.local_tz)
        week_start = now - timedelta(days=7)
        
        # Filter to this week's conversations
        week_convs = []
        for conv in conversations:
            ts = conv.get('timestamp', '')
            if ts:
                conv_time = self._to_local_time(ts)
                if conv_time and conv_time >= week_start:
                    week_convs.append(conv)
        
        # Handle no conversations this week
        if not week_convs:
            # Use last few conversations instead
            week_convs = conversations[-3:] if len(conversations) >= 3 else conversations
            period_label = "Recent"
        else:
            period_label = "This Week"
        
        if not week_convs:
            return self._empty_weekly_updates(elder_name)
        
        # 1. CONVERSATIONS COUNT & DAYS
        conv_count = len(week_convs)
        conv_days = []
        for conv in week_convs:
            ts = conv.get('timestamp', '')
            if ts:
                conv_time = self._to_local_time(ts)
                if conv_time:
                    day_name = conv_time.strftime('%A')
                    if day_name not in conv_days:
                        conv_days.append(day_name)
        
        conversations_this_week = {
            'count': conv_count,
            'count_label': f"{conv_count} call{'s' if conv_count != 1 else ''}",
            'days': conv_days,
            'days_label': ', '.join(conv_days) if conv_days else 'Various days',
            'period': period_label
        }
        
        # 2. OVERALL MOOD
        mood_scores = []
        mood_labels = []
        for conv in week_convs:
            mood = conv.get('analysis', {}).get('conversation', {}).get('mood', 'neutral')
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good', 'cheerful', 'great']):
                mood_scores.append(3)
                mood_labels.append('positive')
            elif any(w in mood_lower for w in ['negative', 'sad', 'upset', 'anxious', 'worried']):
                mood_scores.append(1)
                mood_labels.append('negative')
            else:
                mood_scores.append(2)
                mood_labels.append('neutral')
        
        avg_mood = sum(mood_scores) / len(mood_scores) if mood_scores else 2
        
        # Determine consistency
        unique_moods = set(mood_labels)
        if len(unique_moods) == 1:
            consistency = "Consistent all week"
        elif len(unique_moods) == 2 and 'negative' not in unique_moods:
            consistency = "Generally positive"
        elif 'negative' in unique_moods and mood_labels[-1] == 'negative':
            consistency = "Declining recently"
        else:
            consistency = "Varies"
        
        if avg_mood >= 2.5:
            overall_mood = {
                'value': 'Positive',
                'emoji': '✨',
                'description': consistency,
                'score': avg_mood
            }
        elif avg_mood >= 1.5:
            overall_mood = {
                'value': 'Neutral',
                'emoji': '😊',
                'description': consistency,
                'score': avg_mood
            }
        else:
            overall_mood = {
                'value': 'Low',
                'emoji': '😔',
                'description': consistency,
                'score': avg_mood
            }
        
        # 3. ENGAGEMENT
        eng_scores = []
        for conv in week_convs:
            eng = conv.get('analysis', {}).get('conversation', {}).get('engagement', 'moderate')
            eng_lower = str(eng).lower()
            if 'high' in eng_lower:
                eng_scores.append(3)
            elif 'low' in eng_lower:
                eng_scores.append(1)
            else:
                eng_scores.append(2)
        
        avg_eng = sum(eng_scores) / len(eng_scores) if eng_scores else 2
        
        # Generate engagement description based on conversation content
        has_stories = any(
            conv.get('analysis', {}).get('biography', {}).get('stories', [])
            for conv in week_convs
        )
        has_quotes = any(
            conv.get('analysis', {}).get('conversation', {}).get('memorable_quotes', [])
            for conv in week_convs
        )
        
        if avg_eng >= 2.5:
            if has_stories:
                eng_desc = "Sharing stories actively"
            elif has_quotes:
                eng_desc = "Opening up in conversations"
            else:
                eng_desc = "Very engaged"
            engagement = {'value': 'High', 'description': eng_desc, 'score': avg_eng}
        elif avg_eng >= 1.5:
            engagement = {'value': 'Moderate', 'description': "Participating regularly", 'score': avg_eng}
        else:
            engagement = {'value': 'Low', 'description': "Brief conversations", 'score': avg_eng}
        
        # 4. LATEST CONVERSATION SUMMARY
        latest_conv = week_convs[-1]
        latest_summary = self._generate_latest_conversation_summary(latest_conv, elder_name)
        
        # 5. THIS WEEK'S HIGHLIGHTS
        highlights = self._generate_weekly_highlights(week_convs, elder_name)
        
        return {
            'conversations_this_week': conversations_this_week,
            'overall_mood': overall_mood,
            'engagement': engagement,
            'latest_conversation': latest_summary,
            'highlights': highlights,
            'period': period_label
        }
    
    def _empty_weekly_updates(self, elder_name):
        """Return empty weekly updates for users with no conversations"""
        return {
            'conversations_this_week': {
                'count': 0,
                'count_label': 'No calls yet',
                'days': [],
                'days_label': '',
                'period': 'This Week'
            },
            'overall_mood': {
                'value': 'Unknown',
                'emoji': '❓',
                'description': 'No conversations yet',
                'score': 0
            },
            'engagement': {
                'value': 'Unknown',
                'description': f'Waiting for {elder_name} to make their first call',
                'score': 0
            },
            'latest_conversation': None,
            'highlights': [],
            'period': 'This Week'
        }
    
    def _generate_latest_conversation_summary(self, conv, elder_name):
        """
        Generate a rich narrative summary of the latest conversation.
        
        Matches demo format:
        - Date and time
        - Duration
        - Narrative description
        - Key moments (bullet list)
        - Topics loved
        - Mood at start/end
        """
        analysis = conv.get('analysis', {})
        conv_data = analysis.get('conversation', {})
        bio_data = analysis.get('biography', {})
        health_data = analysis.get('health', {})
        
        # Date and time
        ts = conv.get('timestamp', '')
        if ts:
            conv_time = self._to_local_time(ts)
            date_formatted = conv_time.strftime('%A, %B %d, %Y at %I:%M %p') if conv_time else 'Unknown'
        else:
            date_formatted = 'Unknown'
        
        # Duration
        duration = self._calculate_duration(conv.get('transcript', ''))
        
        # Topics
        topics = conv_data.get('topics', [])
        mood = conv_data.get('mood', 'neutral')
        engagement = conv_data.get('engagement', 'moderate')
        quotes = conv_data.get('memorable_quotes', [])
        stories = bio_data.get('stories', [])
        
        # Generate narrative
        narrative = self._generate_conversation_narrative(
            elder_name, mood, engagement, topics, stories, quotes, health_data
        )
        
        # Key moments (from stories, quotes, and topics)
        key_moments = []
        
        # Add story-based moments
        for story in stories[:2]:
            if isinstance(story, dict):
                topic = story.get('topic', '')
                details = story.get('details', '')
                if topic:
                    key_moments.append(f"Shared about {topic.lower()}")
                elif details:
                    key_moments.append(f"Talked about {details[:50]}...")
        
        # Add topic-based moments
        for topic in topics[:3]:
            if topic and not any(topic.lower() in km.lower() for km in key_moments):
                key_moments.append(f"Discussed {topic}")
        
        # Health notes
        if health_data.get('red_flags'):
            key_moments.append("Mentioned some health concerns")
        
        # Limit to 5 key moments
        key_moments = key_moments[:5]
        
        # Topics loved
        topics_loved = [t for t in topics if t and not self._is_meta_topic(t)][:5]
        
        # Mood analysis
        mood_lower = str(mood).lower()
        if any(w in mood_lower for w in ['positive', 'happy', 'good']):
            mood_emoji = '😊'
            mood_label = 'Positive'
        elif any(w in mood_lower for w in ['negative', 'sad', 'upset']):
            mood_emoji = '😔'
            mood_label = 'Reflective'
        else:
            mood_emoji = '😌'
            mood_label = 'Relaxed'
        
        return {
            'date': date_formatted,
            'duration': duration,
            'duration_label': f"{duration} minutes" if duration else "Brief call",
            'narrative': narrative,
            'key_moments': key_moments,
            'topics_loved': topics_loved,
            'topics_loved_label': ', '.join(topics_loved) if topics_loved else 'General conversation',
            'mood': mood_label,
            'mood_emoji': mood_emoji,
            'engagement': engagement.title() if isinstance(engagement, str) else 'Moderate'
        }
    
    def _generate_conversation_narrative(self, elder_name, mood, engagement, topics, stories, quotes, health_data):
        """Generate a natural-language narrative summary of a conversation"""
        parts = []
        
        # Opening based on mood
        mood_lower = str(mood).lower()
        if any(w in mood_lower for w in ['positive', 'happy', 'good', 'great']):
            parts.append(f"{elder_name} had a wonderful conversation today!")
        elif any(w in mood_lower for w in ['negative', 'sad', 'low']):
            parts.append(f"{elder_name} had a quieter conversation today.")
        else:
            parts.append(f"{elder_name} had a nice chat today.")
        
        # Main content based on stories/topics
        if stories:
            story = stories[0]
            if isinstance(story, dict):
                topic = story.get('topic', '')
                details = story.get('details', '')
                if topic:
                    parts.append(f"They shared a story about {topic.lower()}.")
                elif details and len(details) > 20:
                    parts.append(f"They shared memories about {details[:60]}...")
        elif topics:
            main_topics = [t for t in topics[:2] if t and not self._is_meta_topic(t)]
            if main_topics:
                parts.append(f"They talked about {' and '.join(main_topics).lower()}.")
        
        # Health note if relevant
        if health_data.get('red_flags'):
            parts.append("They also mentioned some health concerns worth noting.")
        elif health_data.get('summary'):
            summary = health_data['summary']
            if 'better' in summary.lower() or 'improving' in summary.lower():
                parts.append("They mentioned feeling better recently.")
        
        return ' '.join(parts)
    
    def _generate_weekly_highlights(self, conversations, elder_name):
        """
        Generate day-by-day highlights for the week.
        
        Format per highlight:
        - Day and date
        - Mood indicator
        - Duration
        - Brief description
        """
        highlights = []
        
        for conv in reversed(conversations):  # Most recent first
            ts = conv.get('timestamp', '')
            analysis = conv.get('analysis', {})
            conv_data = analysis.get('conversation', {})
            
            # Date
            if ts:
                conv_time = self._to_local_time(ts)
                day_date = conv_time.strftime('%A, %B %d') if conv_time else 'Unknown'
            else:
                day_date = 'Unknown'
            
            # Mood
            mood = conv_data.get('mood', 'neutral')
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good']):
                mood_label = 'Positive'
                mood_emoji = '😊'
            elif any(w in mood_lower for w in ['negative', 'sad', 'upset']):
                mood_label = 'Reflective'
                mood_emoji = '😔'
            else:
                mood_label = 'Neutral'
                mood_emoji = '😌'
            
            # Duration
            duration = self._calculate_duration(conv.get('transcript', ''))
            
            # Brief description based on topics
            topics = conv_data.get('topics', [])
            stories = analysis.get('biography', {}).get('stories', [])
            
            if stories and isinstance(stories[0], dict):
                topic = stories[0].get('topic', '')
                if topic:
                    description = f"Shared stories about {topic.lower()}."
                else:
                    description = "Shared personal memories."
            elif topics:
                clean_topics = [t for t in topics[:2] if t and not self._is_meta_topic(t)]
                if clean_topics:
                    description = f"Discussed {' and '.join(clean_topics).lower()}."
                else:
                    description = "Had a nice conversation."
            else:
                description = "Had a pleasant chat."
            
            highlights.append({
                'day_date': day_date,
                'mood': mood_label,
                'mood_emoji': mood_emoji,
                'duration': duration,
                'duration_label': f"{duration} min" if duration else "Brief",
                'description': description
            })
        
        return highlights[:7]  # Max 7 highlights
    
    # =========================================================================
    # HEALTH INSIGHTS (v2 - matching demo format)
    # =========================================================================
    
    def _generate_health_insights_v2(self, conversations, health_events, elder_name):
        """
        Generate health insights matching the demo component structure.
        
        Returns:
        {
            alert: { title, message, date, time, severity },
            wellbeing_timeline: [{ date, wellbeing, event? }],
            health_timeline: [{ date_range, status, details, badge, badge_type }],
            habits: [{ label, icon, frequency, active }]
        }
        """
        now = datetime.now(self.local_tz)
        two_weeks_ago = now - timedelta(days=14)
        
        # 1. BUILD WELLBEING TIMELINE (last 2 weeks)
        wellbeing_timeline = []
        daily_scores = {}
        daily_events = {}
        
        for conv in conversations:
            ts = conv.get('timestamp', '')
            if not ts:
                continue
                
            conv_time = self._to_local_time(ts)
            if not conv_time or conv_time < two_weeks_ago:
                continue
            
            date_key = conv_time.strftime('%b %d')
            
            # Calculate wellbeing score from mood and health
            analysis = conv.get('analysis', {})
            mood = analysis.get('conversation', {}).get('mood', 'neutral')
            health = analysis.get('health', {})
            
            # Base score from mood
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good', 'great']):
                base_score = 90
            elif any(w in mood_lower for w in ['negative', 'sad', 'low', 'tired']):
                base_score = 70
            else:
                base_score = 82
            
            # Adjust for health concerns
            if health.get('red_flags'):
                base_score -= 10
            if health.get('summary'):
                summary_lower = health['summary'].lower()
                if any(w in summary_lower for w in ['not feeling well', 'tired', 'pain', 'hurt']):
                    base_score -= 8
                if any(w in summary_lower for w in ['better', 'improving', 'good']):
                    base_score += 5
            
            base_score = max(60, min(100, base_score))  # Clamp 60-100
            daily_scores[date_key] = base_score
            
            # Track events
            if health.get('red_flags'):
                flags = health['red_flags']
                if flags:
                    flag_text = flags[0] if isinstance(flags[0], str) else str(flags[0])
                    daily_events[date_key] = flag_text[:30]
            elif health.get('summary'):
                summary = health['summary']
                if any(w in summary.lower() for w in ['cough', 'cold', 'sick', 'pain', 'fell', 'tired']):
                    # Extract key phrase
                    for phrase in ['cough', 'cold', 'not feeling well', 'tired', 'pain', 'fell']:
                        if phrase in summary.lower():
                            daily_events[date_key] = phrase.title()
                            break
        
        # Convert to sorted list
        for date_key in sorted(daily_scores.keys()):
            entry = {
                'date': date_key,
                'wellbeing': daily_scores[date_key]
            }
            if date_key in daily_events:
                entry['event'] = daily_events[date_key]
            wellbeing_timeline.append(entry)
        
        # If no data, generate placeholder
        if not wellbeing_timeline:
            for i in range(7):
                day = now - timedelta(days=6-i)
                wellbeing_timeline.append({
                    'date': day.strftime('%b %d'),
                    'wellbeing': 85
                })
        
        # 2. BUILD ALERT (from most recent health concern)
        alert = None
        if health_events:
            active_events = [e for e in health_events if e.get('status') == 'active']
            if active_events:
                latest = active_events[-1]
                alert = {
                    'title': 'Health Note',
                    'message': f"{elder_name} {latest.get('description', 'mentioned a health concern')}",
                    'date': latest.get('detected_on_formatted', 'Recently'),
                    'time': '',
                    'severity': 'warning' if latest.get('severity') == 'high' else 'info'
                }
        
        # Check recent conversations for health mentions
        if not alert and conversations:
            for conv in reversed(conversations[-3:]):
                health = conv.get('analysis', {}).get('health', {})
                if health.get('red_flags'):
                    ts = conv.get('timestamp', '')
                    conv_time = self._to_local_time(ts) if ts else None
                    alert = {
                        'title': 'Minor Health Note',
                        'message': f"{elder_name} mentioned some health concerns in recent conversation.",
                        'date': conv_time.strftime('%b %d') if conv_time else 'Recently',
                        'time': conv_time.strftime('%I:%M %p') if conv_time else '',
                        'severity': 'info'
                    }
                    break
        
        # 3. BUILD HEALTH TIMELINE (recent health-related events)
        health_timeline = []
        health_periods = self._group_health_by_period(conversations)
        
        for period in health_periods[-3:]:  # Last 3 periods
            badge_type = 'success'
            if period['trend'] == 'declining':
                badge_type = 'danger'
                badge = 'Needs attention'
            elif period['trend'] == 'improving':
                badge_type = 'success'
                badge = 'Improving'
            else:
                badge_type = 'warning'
                badge = 'Monitoring'
            
            health_timeline.append({
                'date_range': period['date_range'],
                'status': period['status'],
                'details': period['details'],
                'badge': badge,
                'badge_type': badge_type
            })
        
        # If no health timeline, show positive default
        if not health_timeline:
            health_timeline.append({
                'date_range': 'This week',
                'status': 'Generally well',
                'details': f'{elder_name} has been in good spirits during conversations.',
                'badge': 'Good',
                'badge_type': 'success'
            })
        
        # 4. BUILD HABITS (extract from conversations)
        habits = self._extract_habits(conversations)
        
        return {
            'alert': alert,
            'wellbeing_timeline': wellbeing_timeline,
            'health_timeline': health_timeline,
            'habits': habits
        }
    
    def _group_health_by_period(self, conversations):
        """Group health mentions into time periods"""
        periods = []
        
        # Simple grouping: look at last few conversations
        recent = conversations[-5:] if len(conversations) >= 5 else conversations
        
        current_period = {
            'date_range': '',
            'status': '',
            'details': '',
            'trend': 'stable'
        }
        
        health_notes = []
        dates = []
        
        for conv in recent:
            ts = conv.get('timestamp', '')
            health = conv.get('analysis', {}).get('health', {})
            
            if ts:
                conv_time = self._to_local_time(ts)
                if conv_time:
                    dates.append(conv_time)
            
            if health.get('summary'):
                health_notes.append(health['summary'])
            
            for flag in health.get('red_flags', []):
                if isinstance(flag, str):
                    health_notes.append(flag)
        
        if dates and health_notes:
            start_date = min(dates).strftime('%B %d')
            end_date = max(dates).strftime('%d')
            
            # Determine trend from notes
            trend = 'stable'
            combined = ' '.join(health_notes).lower()
            if 'better' in combined or 'improving' in combined:
                trend = 'improving'
            elif 'worse' in combined or 'not feeling well' in combined:
                trend = 'declining'
            
            periods.append({
                'date_range': f"{start_date}-{end_date}",
                'status': health_notes[0][:50] if health_notes else 'General wellness',
                'details': ' '.join(health_notes[:2])[:150],
                'trend': trend
            })
        
        return periods
    
    def _extract_habits(self, conversations):
        """Extract habits and routines mentioned in conversations"""
        habit_mentions = defaultdict(int)
        
        habit_keywords = {
            'tea': ('Herbal tea routine', 'coffee', 'Daily'),
            'walk': ('Daily walks', 'heart', 'Regular'),
            'tv': ('Watching shows', 'tv', 'Entertainment'),
            'read': ('Reading', 'book-open', 'Regular'),
            'family': ('Family time', 'users', 'Social'),
            'friend': ('Social connections', 'users', 'Social'),
            'garden': ('Gardening', 'flower', 'Hobby'),
            'cook': ('Cooking', 'utensils', 'Daily'),
            'church': ('Faith activities', 'heart', 'Regular'),
            'exercise': ('Exercise routine', 'activity', 'Regular'),
        }
        
        for conv in conversations:
            transcript = conv.get('transcript', '').lower()
            for keyword, habit_info in habit_keywords.items():
                if keyword in transcript:
                    habit_mentions[keyword] += 1
        
        # Build habits list from most mentioned
        habits = []
        for keyword, count in sorted(habit_mentions.items(), key=lambda x: -x[1])[:4]:
            if count >= 1:
                label, icon, frequency = habit_keywords[keyword]
                habits.append({
                    'label': label,
                    'icon': icon,
                    'frequency': frequency,
                    'active': True
                })
        
        # Default habits if none found
        if not habits:
            habits = [
                {'label': 'Regular conversations', 'icon': 'message-circle', 'frequency': 'Ongoing', 'active': True},
                {'label': 'Sharing memories', 'icon': 'brain', 'frequency': 'Mental stimulation', 'active': True},
            ]
        
        return habits
    
    # =========================================================================
    # LIFE STORY (matching demo format)
    # =========================================================================
    
    def _generate_life_story(self, conversations, knowledge_base, elder_name):
        """
        Generate life story section matching the demo component structure.
        
        Returns:
        {
            progress: { total_conversations, status_label, total_stories, total_themes, completeness_percent },
            themes: [{ id, title, story_count, preview?, stories: [{ title, date_shared, excerpt, key_details }] }],
            timeline: [{ era, label, detail, icon }]
        }
        """
        # 1. PROGRESS
        total_conversations = len(conversations)
        
        # Count stories from in_their_words data
        in_their_words = self._build_in_their_words(conversations, elder_name)
        themes_data = in_their_words.get('themes', [])
        
        total_stories = sum(t.get('total_quotes', 0) for t in themes_data)
        total_themes = len(themes_data)
        
        # Calculate completeness (rough estimate)
        # Assume 100 stories = complete biography
        completeness = min(95, int((total_stories / 100) * 100))
        if completeness < 10:
            completeness = max(5, total_conversations * 3)  # At least show some progress
        
        # Status label based on progress
        if completeness < 20:
            status_label = "Early chapters being written..."
        elif completeness < 50:
            status_label = "Story taking shape..."
        elif completeness < 80:
            status_label = "Rich narrative emerging..."
        else:
            status_label = "Comprehensive life story captured"
        
        progress = {
            'total_conversations': total_conversations,
            'status_label': status_label,
            'total_stories': total_stories,
            'total_themes': total_themes,
            'completeness_percent': completeness
        }
        
        # 2. THEMES (from in_their_words, converted to demo format)
        themes = []
        for theme in themes_data[:6]:  # Top 6 themes
            theme_id = theme.get('theme_id', 'general')
            theme_name = theme.get('theme_name', 'Life Stories')
            quotes = theme.get('quotes', [])
            
            # Convert quotes to stories format
            stories = []
            for quote in quotes[:4]:  # Max 4 stories per theme
                stories.append({
                    'title': self._generate_story_title(quote.get('quote', ''), theme_name),
                    'date_shared': quote.get('date', ''),
                    'excerpt': quote.get('quote', ''),
                    'key_details': []  # Could extract from quote content
                })
            
            themes.append({
                'id': theme_id,
                'title': theme_name,
                'story_count': len(quotes),
                'preview': f"Stories about {theme_name.lower()}" if not stories else None,
                'stories': stories
            })
        
        # 3. TIMELINE (generate from stories/knowledge base)
        timeline = self._generate_life_timeline(conversations, knowledge_base, elder_name)
        
        return {
            'progress': progress,
            'themes': themes,
            'timeline': timeline
        }
    
    def _generate_story_title(self, quote, theme_name):
        """Generate a short title for a story/quote"""
        if not quote:
            return theme_name
        
        # Try to extract a meaningful title from the quote
        quote_lower = quote.lower()
        
        # Look for key phrases
        title_patterns = [
            ('remember', 'A Memory'),
            ('my mother', 'About Mother'),
            ('my father', 'About Father'),
            ('when i was', 'Childhood Memory'),
            ('years ago', 'Looking Back'),
            ('we used to', 'How Things Were'),
            ('my favorite', 'A Favorite Memory'),
        ]
        
        for pattern, title in title_patterns:
            if pattern in quote_lower:
                return title
        
        # Default: use first few words
        words = quote.split()[:5]
        return ' '.join(words) + '...' if len(words) >= 5 else quote[:30]
    
    def _generate_life_timeline(self, conversations, knowledge_base, elder_name):
        """Generate life timeline events from conversation data"""
        timeline = []
        
        # Extract years/eras mentioned
        years_mentioned = set()
        locations_mentioned = set()
        
        for conv in conversations:
            transcript = conv.get('transcript', '')
            
            # Find years (1940-2025)
            import re
            years = re.findall(r'\b(19[4-9][0-9]|20[0-2][0-9])\b', transcript)
            years_mentioned.update(years)
            
            # Find locations
            for loc in ['Poland', 'Canada', 'Toronto', 'Vancouver', 'Chicago', 'Arizona', 'England', 'London']:
                if loc.lower() in transcript.lower():
                    locations_mentioned.add(loc)
        
        # Build timeline from extracted data
        sorted_years = sorted(years_mentioned)
        
        if sorted_years:
            # Earliest year
            earliest = sorted_years[0]
            if int(earliest) < 1980:
                timeline.append({
                    'era': f"{earliest}s",
                    'label': 'Early memories',
                    'detail': 'Family history',
                    'icon': 'heart'
                })
            
            # Birth/childhood era
            childhood_years = [y for y in sorted_years if 1970 <= int(y) <= 1990]
            if childhood_years:
                timeline.append({
                    'era': childhood_years[0],
                    'label': f'{elder_name} born',
                    'detail': list(locations_mentioned)[0] if locations_mentioned else 'Unknown',
                    'icon': 'baby'
                })
        
        # Always add present
        timeline.append({
            'era': '2025',
            'label': 'Present day',
            'detail': 'Conversations with Aila',
            'icon': 'home'
        })
        
        # If no timeline data, create default
        if len(timeline) < 2:
            timeline = [
                {'era': 'Past', 'label': 'Life experiences', 'detail': 'Stories being captured', 'icon': 'book-open'},
                {'era': 'Present', 'label': 'Current chapter', 'detail': 'Conversations with Aila', 'icon': 'home'}
            ]
        
        return timeline
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
                # Deduplicate - only one fall incident
                seen_fall = False
                unique_titles = []
                for e in active_high:
                    title = e['title']
                    if 'fall' in title.lower():
                        if seen_fall:
                            continue
                        seen_fall = True
                    unique_titles.append(title)
                
                active_summary = f"Active concerns: {', '.join(unique_titles[:3])}"
        
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
            
            # Get conversation default mood
            mood_lower = str(mood).lower()
            if any(w in mood_lower for w in ['positive', 'happy', 'good']):
                conv_mood_emoji, conv_mood_label = '😊', 'Happy'
            elif any(w in mood_lower for w in ['negative', 'sad', 'upset']):
                conv_mood_emoji, conv_mood_label = '😔', 'Reflective'
            else:
                conv_mood_emoji, conv_mood_label = '😌', 'Relaxed'
            
            for quote in conv_quotes:
                if not quote or not isinstance(quote, str):
                    continue
                
                quote_stripped = quote.strip()
                
                # Use improved meta filtering
                if self._is_meta_quote(quote_stripped):
                    continue
                
                if len(quote_stripped.split()) < 5:
                    continue
                
                # Detect theme for category (now returns 3 values)
                theme_id, theme_name, _ = self._detect_theme(quote_stripped, topics, stories)
                
                # Analyze quote-specific sentiment
                quote_mood_emoji, quote_mood_label = self._analyze_quote_sentiment(
                    quote_stripped, conv_mood_emoji, conv_mood_label
                )
                
                quotes.append({
                    'quote': quote_stripped,
                    'date': date_fmt,
                    'timestamp': timestamp,
                    'category': theme_name,
                    'topics': topics,
                    'mood': quote_mood_label,
                    'mood_emoji': quote_mood_emoji
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
        
        # Add alerts from health events - but only ONE fall incident
        fall_alert_added = False
        if health_events:
            for event in health_events:
                if event.get('severity') == 'high' and event.get('needs_family_followup'):
                    # Skip additional fall incidents - they should be merged
                    if 'fall' in event.get('title', '').lower():
                        if fall_alert_added:
                            continue
                        fall_alert_added = True
                    
                    alerts.append({
                        'type': 'health_event',
                        'severity': 'high',
                        'message': f"{event['title']}: {event['description']}",
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
        
        # Deduplicate - use smarter matching
        seen = set()
        unique = []
        for a in alerts:
            msg = a.get('message', '').lower()
            
            # Create a simplified key for deduplication
            # Fall incidents should all map to same key
            if 'fall' in msg:
                dedup_key = 'fall_incident'
            else:
                dedup_key = msg[:50]
            
            if dedup_key not in seen:
                seen.add(dedup_key)
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
