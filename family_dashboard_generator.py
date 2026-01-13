"""
Family Dashboard Generator
Creates comprehensive family reports from conversation data
"""

import json
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
        # Set timezone for Vancouver, BC (PST/PDT)
        self.local_tz = pytz.timezone('America/Vancouver')
    
    def _to_local_time(self, timestamp_str):
        """Convert UTC timestamp to Vancouver local time (PST/PDT)"""
        try:
            # Parse the timestamp (assuming it's in UTC or naive)
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
            # If naive (no timezone), assume UTC
            if dt.tzinfo is None:
                dt = pytz.utc.localize(dt)
            
            # Convert to Vancouver time
            local_dt = dt.astimezone(self.local_tz)
            return local_dt
        except Exception as e:
            print(f"⚠️ Error converting timestamp: {e}")
            # Fallback to original
            return datetime.fromisoformat(timestamp_str)
    
    def _calculate_duration(self, transcript):
        """Estimate conversation duration from transcript"""
        if not transcript:
            return "Unknown"
        
        # Count turns in conversation
        turns = transcript.count('\nAila:') + transcript.count('\nUser:')
        
        # Rough estimate: average 30 seconds per turn
        estimated_seconds = turns * 30
        
        # Convert to minutes
        minutes = estimated_seconds // 60
        
        if minutes < 1:
            return "< 1 minute"
        elif minutes == 1:
            return "1 minute"
        else:
            return f"{minutes} minutes"
    
    def generate_dashboard(self, beta_id):
        """
        Generate complete family dashboard for a beta tester
        
        Args:
            beta_id: Beta tester ID (e.g., "BT001")
            
        Returns:
            Dict with all dashboard data
        """
        # Reload registry to get latest beta testers
        self.beta_manager._load_registry()
        
        # Get beta tester info
        tester = self.beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            return {
                'success': False,
                'error': 'Beta tester not found'
            }
        
        # Get all conversation data
        conversations_path = self.beta_manager.get_tester_data_path(beta_id, "conversations")
        transcripts_path = self.beta_manager.get_tester_data_path(beta_id, "transcripts")
        kb_path = self.beta_manager.get_tester_data_path(beta_id, "knowledge_base.md")
        
        # Load all conversations
        conversations = self._load_conversations(conversations_path)
        
        # Load knowledge base
        knowledge_base = ""
        if kb_path.exists():
            with open(kb_path, 'r', encoding='utf-8') as f:
                knowledge_base = f.read()
        
        # Generate dashboard sections
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
            'summary': self._generate_summary(conversations, tester),
            'biography_progress': self._analyze_biography_progress(knowledge_base, conversations),  # MOVED UP - Priority #1
            'life_story_quotes': self._extract_biographical_quotes(conversations),  # NEW - filtered quotes
            'recent_conversations': self._generate_recent_conversations(conversations),
            'health_insights': self._generate_health_insights(conversations),
            'alerts': self._identify_alerts(conversations),
            'trends': self._generate_trends(conversations),
            'recommendations': self._generate_recommendations(conversations, tester),
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
                    conv_data = json.load(f)
                    conversations.append(conv_data)
            except Exception as e:
                print(f"⚠️  Could not load {conv_file.name}: {e}")
        
        return conversations
    
    def _generate_summary(self, conversations, tester):
        """Generate high-level summary"""
        total_conversations = len(conversations)
        
        if total_conversations == 0:
            return {
                'total_conversations': 0,
                'message': 'No conversations yet',
                'status': 'waiting_for_first_call'
            }
        
        # Calculate date range (convert to PST)
        dates = []
        for c in conversations:
            if 'timestamp' in c:
                local_dt = self._to_local_time(c['timestamp'])
                dates.append(local_dt)
        
        first_conversation = min(dates) if dates else None
        last_conversation = max(dates) if dates else None
        
        # Calculate average engagement
        engagements = [c.get('analysis', {}).get('conversation', {}).get('engagement', 'moderate') 
                      for c in conversations]
        engagement_map = {'high': 3, 'moderate': 2, 'low': 1}
        avg_engagement_score = sum(engagement_map.get(e, 2) for e in engagements) / len(engagements)
        
        if avg_engagement_score >= 2.5:
            overall_engagement = 'high'
        elif avg_engagement_score >= 1.5:
            overall_engagement = 'moderate'
        else:
            overall_engagement = 'low'
        
        # Calculate mood trend
        moods = [c.get('analysis', {}).get('conversation', {}).get('mood', 'neutral') 
                for c in conversations]
        mood_counts = {'positive': 0, 'neutral': 0, 'negative': 0}
        for mood in moods:
            mood_counts[mood] = mood_counts.get(mood, 0) + 1
        
        dominant_mood = max(mood_counts, key=mood_counts.get)
        
        # Time since last conversation (use PST for current time)
        now_pst = datetime.now(self.local_tz)
        days_since_last = (now_pst - last_conversation).days if last_conversation else 0
        
        return {
            'total_conversations': total_conversations,
            'first_conversation_date': first_conversation.strftime('%B %d, %Y') if first_conversation else None,
            'last_conversation_date': last_conversation.strftime('%B %d, %Y') if last_conversation else None,
            'days_since_last_conversation': days_since_last,
            'overall_engagement': overall_engagement,
            'mood_trend': dominant_mood,
            'status': 'active' if days_since_last < 7 else 'inactive'
        }
    
    def _generate_health_insights(self, conversations):
        """Analyze health patterns across conversations"""
        health_mentions = []
        concerns = []
        patterns = defaultdict(int)
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            health = analysis.get('health', {})
            
            # Track health mentions
            if health.get('summary'):
                health_mentions.append({
                    'date': conv.get('timestamp', ''),
                    'summary': health.get('summary', ''),
                    'mood': analysis.get('conversation', {}).get('mood', 'neutral')
                })
            
            # Identify concerns
            red_flags = health.get('red_flags', [])
            for flag in red_flags:
                concerns.append({
                    'date': conv.get('timestamp', ''),
                    'concern': flag,
                    'severity': 'high'
                })
            
            # Track patterns
            if health.get('pain'):
                patterns['pain_mentions'] += 1
            if health.get('sleep'):
                patterns['sleep_discussions'] += 1
            if health.get('medications'):
                patterns['medication_mentions'] += 1
        
        # Get most recent health status
        latest_health = None
        if conversations:
            latest = conversations[-1]
            latest_health = latest.get('analysis', {}).get('health', {}).get('summary')
        
        return {
            'current_status': latest_health or 'No recent health information',
            'total_health_mentions': len(health_mentions),
            'active_concerns': concerns[-3:] if concerns else [],  # Last 3 concerns
            'patterns': dict(patterns),
            'trend': self._determine_health_trend(health_mentions)
        }
    
    def _determine_health_trend(self, health_mentions):
        """Determine if health is improving, declining, or stable"""
        if len(health_mentions) < 2:
            return 'insufficient_data'
        
        # Simple heuristic based on mood associated with health mentions
        recent_moods = [m['mood'] for m in health_mentions[-3:]]
        
        positive_count = recent_moods.count('positive')
        negative_count = recent_moods.count('negative')
        
        if positive_count > negative_count:
            return 'improving'
        elif negative_count > positive_count:
            return 'declining'
        else:
            return 'stable'
    
    def _generate_recent_conversations(self, conversations):
        """Get summaries of last 3 conversations"""
        recent = conversations[-3:] if len(conversations) >= 3 else conversations
        
        summaries = []
        for conv in reversed(recent):  # Most recent first
            analysis = conv.get('analysis', {})
            conversation_data = analysis.get('conversation', {})
            
            # Convert timestamp to PST
            if 'timestamp' in conv:
                local_time = self._to_local_time(conv['timestamp'])
                date_str = local_time.strftime('%B %d, %Y %I:%M %p')
            else:
                date_str = 'Unknown'
            
            # Calculate actual duration from transcript
            transcript = conv.get('transcript', '')
            duration = self._calculate_duration(transcript)
            
            summaries.append({
                'date': date_str,
                'topics': conversation_data.get('topics', []),
                'mood': conversation_data.get('mood', 'neutral'),
                'engagement': conversation_data.get('engagement', 'moderate'),
                'duration_estimate': duration,
                'highlights': conversation_data.get('follow_ups', [])[:2]  # First 2 follow-ups
            })
        
        return summaries
    
    def _extract_biographical_quotes(self, conversations):
        """
        Extract quotes specifically about their life and stories
        Filter out meta-conversations, technical issues, AI discussions
        """
        biographical_quotes = []
        
        # Keywords that indicate NON-biographical quotes
        meta_keywords = [
            'ai', 'aila', 'sleep', 'you', 'conversation', 'talking', 
            'understand', 'feel', 'experience', 'artificial', 'human',
            'call', 'chat', 'speaking'
        ]
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            quotes = analysis.get('conversation', {}).get('memorable_quotes', [])
            topics = analysis.get('conversation', {}).get('topics', [])
            bio = analysis.get('biography', {})
            stories = bio.get('stories', [])
            
            # Convert timestamp to PST
            if 'timestamp' in conv:
                local_time = self._to_local_time(conv['timestamp'])
                date_str = local_time.strftime('%B %d, %Y')
            else:
                date_str = 'Unknown'
            
            for quote in quotes:
                quote_lower = quote.lower()
                
                # Skip if it's meta-conversation
                if any(keyword in quote_lower for keyword in meta_keywords):
                    continue
                
                # Skip if it's too short (likely just "yes" or "okay")
                if len(quote.split()) < 4:
                    continue
                
                # Try to find context from stories
                story_context = None
                for story in stories:
                    if any(word in quote_lower for word in story.get('topic', '').lower().split()):
                        story_context = story.get('topic')
                        break
                
                biographical_quotes.append({
                    'quote': quote,
                    'date': date_str,
                    'context': story_context or (topics[0] if topics else 'From their life'),
                    'topics': topics
                })
        
        # Return last 8 quotes (more than before to show richness)
        return biographical_quotes[-8:] if len(biographical_quotes) > 8 else biographical_quotes
    
    def _build_life_story_profile(self, conversations):
        """
        Build comprehensive life story profile showing what we're learning
        This is the HERO section of the dashboard
        """
        
        profile = {
            'places': [],
            'people': [],
            'work_career': [],
            'interests_hobbies': [],
            'life_events': [],
            'stories': [],
            'chapters_captured': set()
        }
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            bio = analysis.get('biography', {})
            
            # Extract stories with rich detail
            stories = bio.get('stories', [])
            for story in stories:
                topic = story.get('topic', '')
                details = story.get('details', '')
                people_involved = story.get('people_involved', [])
                
                # Categorize the story
                topic_lower = topic.lower()
                
                # Add to appropriate category
                if any(word in topic_lower for word in ['live', 'lived', 'home', 'house', 'city', 'town', 'country', 'place']):
                    if details:
                        profile['places'].append({
                            'detail': details,
                            'date_captured': conv.get('timestamp', '')
                        })
                        profile['chapters_captured'].add('Places & Locations')
                
                if any(word in topic_lower for word in ['work', 'job', 'career', 'business', 'profession']):
                    if details:
                        profile['work_career'].append({
                            'detail': details,
                            'date_captured': conv.get('timestamp', '')
                        })
                        profile['chapters_captured'].add('Work & Career')
                
                if any(word in topic_lower for word in ['hobby', 'interest', 'love', 'enjoy', 'passion', 'favorite']):
                    if details:
                        profile['interests_hobbies'].append({
                            'detail': details,
                            'date_captured': conv.get('timestamp', '')
                        })
                        profile['chapters_captured'].add('Interests & Hobbies')
                
                # All stories get added regardless
                profile['stories'].append({
                    'topic': topic,
                    'details': details,
                    'people': people_involved,
                    'date_captured': conv.get('timestamp', '')
                })
            
            # Extract people mentioned
            people = bio.get('people', [])
            for person in people:
                if isinstance(person, dict):
                    name = person.get('name', '')
                    relationship = person.get('relationship', '')
                    if name:
                        profile['people'].append({
                            'name': name,
                            'relationship': relationship,
                            'date_captured': conv.get('timestamp', '')
                        })
                elif isinstance(person, str) and person:
                    profile['people'].append({
                        'name': person,
                        'relationship': 'mentioned',
                        'date_captured': conv.get('timestamp', '')
                    })
            
            if profile['people']:
                profile['chapters_captured'].add('Important People')
            
            # Extract timeline events
            timeline_events = bio.get('timeline_events', [])
            for event in timeline_events:
                profile['life_events'].append({
                    'event': event,
                    'date_captured': conv.get('timestamp', '')
                })
            
            if profile['life_events']:
                profile['chapters_captured'].add('Life Events')
        
        # Deduplicate people by name
        seen_names = set()
        unique_people = []
        for person in profile['people']:
            name = person.get('name', '').lower()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_people.append(person)
        profile['people'] = unique_people
        
        # Convert chapters set to list
        profile['chapters_captured'] = sorted(list(profile['chapters_captured']))
        
        # Calculate meaningful progress
        total_chapters = 8  # Places, People, Work, Hobbies, Childhood, Family, Travel, Life Events
        chapters_with_content = len(profile['chapters_captured'])
        
        profile['progress'] = {
            'chapters_captured': chapters_with_content,
            'total_chapters': total_chapters,
            'percentage': int((chapters_with_content / total_chapters) * 100),
            'next_areas': self._suggest_biography_areas_v2(profile)
        }
        
        return profile
    
    def _suggest_biography_areas_v2(self, profile):
        """Suggest which chapters of their life to explore next"""
        
        all_chapters = {
            'Places & Locations': 'Where have you lived? Where have you traveled?',
            'Important People': 'Family, friends, mentors who shaped your life',
            'Work & Career': 'What did you do for work? What did you enjoy about it?',
            'Interests & Hobbies': 'What do you love doing? What are you passionate about?',
            'Childhood': 'Growing up, early memories, school days',
            'Family': 'Parents, siblings, children, spouse',
            'Travel & Adventures': 'Places visited, favorite trips, adventures',
            'Life Events': 'Marriages, moves, achievements, challenges'
        }
        
        captured = set(profile['chapters_captured'])
        missing = []
        
        for chapter, description in all_chapters.items():
            if chapter not in captured:
                missing.append({
                    'chapter': chapter,
                    'description': description
                })
        
        return missing[:3]  # Suggest top 3 areas to explore
    
    def _analyze_biography_progress(self, knowledge_base, conversations):
        """Analyze how much of life story has been captured"""
        
        # Build the rich life story profile
        life_story = self._build_life_story_profile(conversations)
        
        # Analyze knowledge base for depth
        kb_sections = knowledge_base.count('###') if knowledge_base else 0
        kb_words = len(knowledge_base.split()) if knowledge_base else 0
        
        return {
            'total_stories_captured': len(life_story['stories']),
            'life_story_profile': life_story,
            'knowledge_base_sections': kb_sections,
            'knowledge_base_words': kb_words,
            'completeness_estimate': life_story['progress']['percentage'],
            'next_areas_to_explore': life_story['progress']['next_areas']
        }
            'knowledge_base_sections': kb_sections,
            'knowledge_base_words': kb_words,
            'completeness_estimate': min(100, (total_stories * 2) + (kb_sections * 0.5)),  # More realistic: ~50 stories = 100%
            'next_areas_to_explore': self._suggest_biography_areas(conversations)
        }
    
    def _suggest_biography_areas(self, conversations):
        """Suggest areas of life story not yet explored"""
        # Track what's been discussed
        discussed = set()
        
        for conv in conversations:
            topics = conv.get('analysis', {}).get('conversation', {}).get('topics', [])
            for topic in topics:
                topic_lower = topic.lower()
                if 'family' in topic_lower or 'child' in topic_lower:
                    discussed.add('family')
                if 'work' in topic_lower or 'career' in topic_lower or 'job' in topic_lower:
                    discussed.add('career')
                if 'travel' in topic_lower or 'trip' in topic_lower:
                    discussed.add('travel')
                if 'hobby' in topic_lower or 'interest' in topic_lower:
                    discussed.add('hobbies')
        
        # Suggest undiscussed areas
        all_areas = {'family', 'career', 'travel', 'hobbies', 'childhood', 'traditions'}
        remaining = all_areas - discussed
        
        return list(remaining)[:3] if remaining else ['Continue exploring past stories']
    
    def _identify_alerts(self, conversations):
        """Identify important things family should know"""
        alerts = []
        
        # Keywords that indicate false alarms (technical issues, not real health concerns)
        false_alarm_keywords = [
            'technical', 'ai', 'repetition', 'glitch', 'error', 'system',
            'connectivity', 'internet', 'network', 'response', 'processing',
            'lag', 'delay', 'timeout', 'crashed', 'frozen', 'bug'
        ]
        
        def is_false_alarm(message):
            """Check if concern is actually a technical issue, not health"""
            if not message:
                return True
            
            # Handle both string and dict formats
            if isinstance(message, dict):
                # If it's a dict, extract the text content
                message_text = message.get('concern') or message.get('message') or message.get('text') or str(message)
            else:
                message_text = str(message)
            
            message_lower = message_text.lower()
            return any(keyword in message_lower for keyword in false_alarm_keywords)
        
        for conv in conversations:
            analysis = conv.get('analysis', {})
            
            # Check for red flags (but filter out false alarms)
            red_flags = analysis.get('health', {}).get('red_flags', [])
            for flag in red_flags:
                if not is_false_alarm(flag):
                    # Extract message text from dict or use string directly
                    if isinstance(flag, dict):
                        message_text = flag.get('concern') or flag.get('message') or flag.get('text') or str(flag)
                    else:
                        message_text = str(flag)
                    
                    alerts.append({
                        'type': 'health_concern',
                        'severity': 'high',
                        'message': message_text,
                        'date': conv.get('timestamp', ''),
                        'action_needed': True
                    })
            
            # Check family dashboard concerns (but filter out false alarms)
            dashboard_concerns = analysis.get('family_dashboard', {}).get('concerns', [])
            for concern in dashboard_concerns:
                if not is_false_alarm(concern):
                    # Extract message text from dict or use string directly
                    if isinstance(concern, dict):
                        message_text = concern.get('concern') or concern.get('message') or concern.get('text') or str(concern)
                    else:
                        message_text = str(concern)
                    
                    alerts.append({
                        'type': 'general_concern',
                        'severity': 'medium',
                        'message': message_text,
                        'date': conv.get('timestamp', ''),
                        'action_needed': False
                    })
        
        # Return most recent 5 alerts
        return sorted(alerts, key=lambda x: x.get('date', ''), reverse=True)[:5]
    
    def _generate_trends(self, conversations):
        """Generate trend data for visualization"""
        
        # Mood trend over time
        mood_timeline = []
        for conv in conversations:
            mood_raw = conv.get('analysis', {}).get('conversation', {}).get('mood', 'neutral')
            date = conv.get('timestamp', '')
            
            # Parse mood - handle both simple and descriptive moods
            mood_lower = mood_raw.lower() if mood_raw else 'neutral'
            
            # Determine mood score from descriptive text
            if any(word in mood_lower for word in ['positive', 'happy', 'good', 'cheerful', 'upbeat', 'joyful']):
                mood_score = 3
                mood_category = 'positive'
            elif any(word in mood_lower for word in ['negative', 'sad', 'upset', 'down', 'depressed', 'anxious', 'worried', 'emotional', 'distressed']):
                mood_score = 1
                mood_category = 'negative'
            else:
                mood_score = 2
                mood_category = 'neutral'
            
            mood_timeline.append({
                'date': date,
                'mood': mood_category,  # Simplified category
                'mood_raw': mood_raw,  # Keep original for reference
                'mood_score': mood_score
            })
        
        # Engagement trend
        engagement_timeline = []
        for conv in conversations:
            engagement = conv.get('analysis', {}).get('conversation', {}).get('engagement', 'moderate')
            date = conv.get('timestamp', '')
            
            engagement_score = {'high': 3, 'moderate': 2, 'low': 1}.get(engagement.lower() if engagement else 'moderate', 2)
            
            engagement_timeline.append({
                'date': date,
                'engagement': engagement,
                'engagement_score': engagement_score
            })
        
        # Conversation frequency (by week)
        frequency = defaultdict(int)
        for conv in conversations:
            if 'timestamp' in conv:
                date = datetime.fromisoformat(conv['timestamp'])
                week = date.strftime('%Y-W%W')
                frequency[week] += 1
        
        return {
            'mood_timeline': mood_timeline,
            'engagement_timeline': engagement_timeline,
            'conversation_frequency': dict(frequency),
            'total_data_points': len(conversations)
        }
    
    def _generate_recommendations(self, conversations, tester):
        """Generate recommendations for family"""
        recommendations = []
        
        if not conversations:
            recommendations.append({
                'priority': 'high',
                'category': 'getting_started',
                'message': f"Schedule first conversation with {tester['signup_data'].get('theirName', 'your loved one')}",
                'action': 'Share conversation link'
            })
            return recommendations
        
        # Check conversation frequency
        if len(conversations) < 2:
            recommendations.append({
                'priority': 'medium',
                'category': 'engagement',
                'message': 'Encourage regular conversations to build rapport',
                'action': 'Suggest 2-3 conversations per week'
            })
        
        # Check for health concerns
        latest_health = conversations[-1].get('analysis', {}).get('health', {})
        if latest_health.get('red_flags'):
            recommendations.append({
                'priority': 'high',
                'category': 'health',
                'message': 'Health concerns were mentioned - consider follow-up',
                'action': 'Review recent conversation and consider doctor visit'
            })
        
        # Check for loneliness indicators
        for conv in conversations[-3:]:  # Last 3 conversations
            analysis = conv.get('analysis', {})
            concerns = analysis.get('family_dashboard', {}).get('concerns', [])
            
            for concern in concerns:
                if 'lonely' in concern.lower() or 'isolated' in concern.lower():
                    recommendations.append({
                        'priority': 'high',
                        'category': 'social',
                        'message': 'Signs of loneliness detected',
                        'action': 'Consider scheduling in-person visit or call'
                    })
                    break
        
        # Suggest reviewing interesting stories
        total_stories = sum(len(c.get('analysis', {}).get('biography', {}).get('stories', [])) 
                          for c in conversations)
        if total_stories > 0:
            recommendations.append({
                'priority': 'low',
                'category': 'connection',
                'message': f"{total_stories} meaningful {'story' if total_stories == 1 else 'stories'} shared",
                'action': 'Read through conversation highlights to stay connected'
            })
        
        return recommendations
