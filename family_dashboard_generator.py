"""
Family Dashboard Generator
Creates comprehensive family reports from conversation data
Phase 1: Health Event Tracking + Enhanced Quotes
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
        
        # Detect health events FIRST (needed by other sections)
        health_events = self._detect_health_events(conversations, knowledge_base)
        
        dashboard = {
            'success': True,
            'beta_id': beta_id,
            'elder': {
                'name': tester['signup_data'].get('theirName', 'Unknown'),
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
            'biography_progress': self._analyze_biography_progress(knowledge_base, conversations),
            'life_story_quotes': self._extract_biographical_quotes(conversations),
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
            
            # Detect from health summary
            if summary:
                self._extract_health_mentions(event_mentions, summary, timestamp, 'health_summary')
            
            # Detect from red flags
            for flag in red_flags:
                flag_text = flag if isinstance(flag, str) else str(flag)
                self._extract_health_mentions(event_mentions, flag_text, timestamp, 'red_flag')
            
            # Detect from transcript (especially falls)
            if transcript:
                self._extract_health_mentions(event_mentions, transcript, timestamp, 'transcript')
        
        # Also check knowledge base
        if knowledge_base:
            self._extract_health_mentions(event_mentions, knowledge_base, '', 'knowledge_base')
        
        # Consolidate and link events
        events = self._consolidate_health_events(event_mentions)
        return self._link_symptoms_to_causes(events)
    
    def _extract_health_mentions(self, event_mentions, text, timestamp, source):
        """Extract health-related mentions from text"""
        if not text:
            return
        
        text_lower = text.lower()
        
        # Check for injuries (HIGH PRIORITY)
        for keyword in self.injury_keywords:
            if keyword in text_lower:
                body_part = self._extract_body_part(text_lower)
                
                # Special handling for falls
                if keyword in ['fell', 'fall', 'fallen', 'ladder']:
                    event_key = f"injury_fall_{body_part or 'general'}"
                    severity = 'high'
                else:
                    event_key = f"injury_{keyword}_{body_part or 'general'}"
                    severity = 'high'
                
                # Extract context around the keyword
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
        
        # Check for symptoms (link to injuries)
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
            
            # Filter out mentions without timestamps (from knowledge base) if we have dated ones
            dated_mentions = [m for m in mentions if m.get('timestamp')]
            if dated_mentions:
                sorted_mentions = sorted(dated_mentions, key=lambda x: x.get('timestamp', ''))
            else:
                sorted_mentions = mentions
            
            if not sorted_mentions:
                continue
            
            first = sorted_mentions[0]
            last = sorted_mentions[-1]
            
            # Determine severity
            event_type = first.get('type', 'symptom')
            keyword = first.get('keyword', '')
            body_part = first.get('body_part')
            
            # Falls are always high severity
            if keyword in ['fell', 'fall', 'fallen', 'ladder'] or event_type == 'injury':
                severity = 'high'
            elif len(sorted_mentions) >= 3:
                severity = 'moderate'
            else:
                severity = 'low'
            
            # Generate title
            if keyword in ['fell', 'fall', 'fallen', 'ladder']:
                title = "Fall Incident"
                if body_part:
                    title = f"Fall Incident - {body_part.title()} Injury"
            elif body_part:
                title = f"{body_part.title()} {keyword.title()}"
            else:
                title = keyword.replace('_', ' ').title()
            
            # Generate event ID
            event_id = hashlib.md5(f"{event_key}_{first.get('timestamp', 'unknown')}".encode()).hexdigest()[:8]
            
            # Get best description
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
                'family_actions': [],  # For Phase 2
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
                
                # Link if: same body part OR cause has no body part (general injury)
                # AND cause happened before or same time as symptom
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
        
        # Sort: high severity first, then by date
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
        
        # Engagement
        scores = []
        for conv in conversations:
            eng = conv.get('analysis', {}).get('conversation', {}).get('engagement', 'moderate')
            scores.append({'high': 3, 'moderate': 2, 'low': 1}.get(str(eng).lower(), 2))
        
        avg_eng = sum(scores) / len(scores) if scores else 2
        engagement = 'High' if avg_eng >= 2.5 else 'Moderate' if avg_eng >= 1.5 else 'Low'
        
        # Mood
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
        
        # Mood context from health events
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
        """Extract quotes with rich context"""
        quotes = []
        
        meta_keywords = ['ai', 'aila', 'conversation', 'talking', 'understand', 'robot']
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            conv_quotes = analysis.get('conversation', {}).get('memorable_quotes', [])
            topics = analysis.get('conversation', {}).get('topics', [])
            mood = analysis.get('conversation', {}).get('mood', 'neutral')
            stories = analysis.get('biography', {}).get('stories', [])
            
            timestamp = conv.get('timestamp', '')
            date_fmt = self._format_date(timestamp)
            
            # Mood emoji
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
                
                quote_lower = quote.lower()
                
                if any(kw in quote_lower for kw in meta_keywords):
                    continue
                
                if len(quote.split()) < 4 or not quote.strip():
                    continue
                
                # Find context
                category = None
                for story in stories:
                    if isinstance(story, dict):
                        topic = story.get('topic', '')
                    elif isinstance(story, str):
                        topic = story
                    else:
                        continue
                    
                    if topic and any(w in quote_lower for w in topic.lower().split()):
                        category = topic
                        break
                
                if not category:
                    category = topics[0] if topics else 'Life Story'
                
                quotes.append({
                    'quote': quote.strip(),
                    'date': date_fmt,
                    'timestamp': timestamp,
                    'category': category,
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
        
        # Add health event alerts
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
        
        # Add conversation alerts
        for conv in conversations:
            analysis = conv.get('analysis', {})
            
            for flag in analysis.get('health', {}).get('red_flags', []):
                if not is_false_alarm(flag):
                    text = flag if isinstance(flag, str) else str(flag)
                    # Skip if covered by health event
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
        
        # Deduplicate
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
        
        # Health event follow-ups
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
                    break  # Just top 1
        
        if len(conversations) < 2:
            recs.append({
                'priority': 'medium',
                'category': 'engagement',
                'message': 'Encourage regular conversations',
                'action': 'Suggest 2-3 conversations per week'
            })
        
        # Stories
        total_stories = sum(len(c.get('analysis', {}).get('biography', {}).get('stories', [])) for c in conversations)
        if total_stories > 0:
            recs.append({
                'priority': 'low',
                'category': 'connection',
                'message': f"{total_stories} stories shared",
                'action': 'Read highlights to stay connected'
            })
        
        return recs
