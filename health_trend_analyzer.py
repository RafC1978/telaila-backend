"""
Health Trend Analyzer
Analyzes cumulative health data across conversations to detect patterns and trends
"""

import json
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import statistics

class HealthTrendAnalyzer:
    """
    Analyzes health data over time to identify patterns, trends, and concerns
    """
    
    def __init__(self):
        pass
    
    def analyze_health_trends(self, beta_id, beta_manager):
        """
        Analyze all health data for a beta tester
        
        Returns comprehensive health analysis with trends
        """
        
        # Get all family updates for this tester
        updates_path = beta_manager.get_tester_data_path(beta_id, "family_updates")
        
        if not updates_path.exists():
            return self._empty_analysis()
        
        # Load all updates
        updates = []
        for update_file in sorted(updates_path.glob("*.json")):
            with open(update_file, 'r', encoding='utf-8') as f:
                update = json.load(f)
                update['filename'] = update_file.name
                updates.append(update)
        
        if not updates:
            return self._empty_analysis()
        
        # Analyze trends
        analysis = {
            "overview": self._analyze_overview(updates),
            "mood_trends": self._analyze_mood_trends(updates),
            "health_patterns": self._analyze_health_patterns(updates),
            "alert_history": self._analyze_alerts(updates),
            "engagement_trends": self._analyze_engagement(updates),
            "recommendations": self._generate_recommendations(updates),
            "red_flags": self._identify_red_flags(updates),
            "weekly_summary": self._generate_weekly_summary(updates),
            "charts_data": self._generate_chart_data(updates)
        }
        
        return analysis
    
    def _empty_analysis(self):
        """Return empty analysis structure"""
        return {
            "overview": {
                "total_conversations": 0,
                "date_range": "No data yet",
                "overall_trend": "insufficient_data"
            },
            "mood_trends": [],
            "health_patterns": {},
            "alert_history": [],
            "engagement_trends": [],
            "recommendations": ["Continue having regular conversations to build baseline data"],
            "red_flags": [],
            "weekly_summary": "Not enough data for weekly summary",
            "charts_data": {}
        }
    
    def _analyze_overview(self, updates):
        """Generate overview statistics"""
        dates = [datetime.fromisoformat(u['date']) for u in updates if 'date' in u]
        
        if not dates:
            return {"total_conversations": 0}
        
        date_range = f"{min(dates).strftime('%B %d')} - {max(dates).strftime('%B %d, %Y')}"
        
        # Calculate overall trend
        recent_moods = [u.get('mood', 'unknown') for u in updates[-5:]]
        positive_count = recent_moods.count('positive')
        
        if positive_count >= 4:
            trend = "improving"
        elif positive_count >= 2:
            trend = "stable"
        else:
            trend = "needs_attention"
        
        return {
            "total_conversations": len(updates),
            "date_range": date_range,
            "overall_trend": trend,
            "days_active": (max(dates) - min(dates)).days + 1
        }
    
    def _analyze_mood_trends(self, updates):
        """Track mood over time"""
        mood_timeline = []
        
        for update in updates:
            mood_timeline.append({
                "date": update.get('date', 'unknown'),
                "mood": update.get('mood', 'unknown'),
                "engagement": update.get('engagement', 'unknown')
            })
        
        return mood_timeline
    
    def _analyze_health_patterns(self, updates):
        """Identify recurring health issues"""
        
        patterns = {
            "pain_mentions": [],
            "sleep_issues": [],
            "appetite_changes": [],
            "medication_mentions": [],
            "recurring_symptoms": []
        }
        
        # Keywords to look for
        pain_keywords = ['pain', 'hurt', 'ache', 'sore', 'headache', 'backache']
        sleep_keywords = ['sleep', 'tired', 'fatigue', 'exhausted', 'insomnia']
        appetite_keywords = ['appetite', 'hungry', 'eating', 'food', 'meal']
        
        for update in updates:
            date = update.get('date', 'unknown')
            summary = update.get('health_summary', '').lower()
            concerns = update.get('concerns', [])
            
            # Check for pain
            if any(keyword in summary for keyword in pain_keywords):
                patterns['pain_mentions'].append({
                    "date": date,
                    "description": summary
                })
            
            # Check for sleep
            if any(keyword in summary for keyword in sleep_keywords):
                patterns['sleep_issues'].append({
                    "date": date,
                    "description": summary
                })
            
            # Check for appetite
            if any(keyword in summary for keyword in appetite_keywords):
                patterns['appetite_changes'].append({
                    "date": date,
                    "description": summary
                })
            
            # Track concerns
            for concern in concerns:
                patterns['recurring_symptoms'].append({
                    "date": date,
                    "concern": concern
                })
        
        # Identify patterns (3+ mentions = pattern)
        pattern_summary = {}
        
        if len(patterns['pain_mentions']) >= 3:
            pattern_summary['chronic_pain'] = {
                "frequency": len(patterns['pain_mentions']),
                "dates": [p['date'] for p in patterns['pain_mentions']],
                "severity": "high" if len(patterns['pain_mentions']) >= 5 else "moderate"
            }
        
        if len(patterns['sleep_issues']) >= 3:
            pattern_summary['sleep_problems'] = {
                "frequency": len(patterns['sleep_issues']),
                "dates": [s['date'] for s in patterns['sleep_issues']],
                "severity": "high" if len(patterns['sleep_issues']) >= 5 else "moderate"
            }
        
        return {
            "detailed": patterns,
            "identified_patterns": pattern_summary
        }
    
    def _analyze_alerts(self, updates):
        """Track alert level history"""
        alert_history = []
        
        alert_levels = {
            "🔴 High": 3,
            "🟡 Moderate": 2,
            "🟢 Low": 1
        }
        
        for update in updates:
            alert = update.get('alert_level', '🟢 Low')
            alert_history.append({
                "date": update.get('date'),
                "level": alert,
                "severity": alert_levels.get(alert, 1),
                "concerns": update.get('concerns', [])
            })
        
        return alert_history
    
    def _analyze_engagement(self, updates):
        """Track engagement over time"""
        engagement_data = []
        
        for update in updates:
            engagement = update.get('engagement', 'unknown')
            
            # Map engagement to numeric score
            score = 0
            if 'high' in engagement.lower():
                score = 3
            elif 'moderate' in engagement.lower() or 'medium' in engagement.lower():
                score = 2
            elif 'low' in engagement.lower():
                score = 1
            
            engagement_data.append({
                "date": update.get('date'),
                "engagement": engagement,
                "score": score
            })
        
        return engagement_data
    
    def _generate_recommendations(self, updates):
        """Generate actionable recommendations based on trends"""
        recommendations = []
        
        # Get recent updates (last 5)
        recent = updates[-5:]
        
        # Check mood trend
        recent_moods = [u.get('mood') for u in recent]
        if recent_moods.count('negative') >= 2:
            recommendations.append("Consider more frequent check-ins - recent mood has been lower than usual")
        
        # Check engagement
        recent_engagement = [u.get('engagement', '') for u in recent]
        low_engagement = sum(1 for e in recent_engagement if 'low' in e.lower())
        if low_engagement >= 2:
            recommendations.append("Try shorter, more frequent conversations to maintain engagement")
        
        # Check concerns
        all_concerns = []
        for u in recent:
            all_concerns.extend(u.get('concerns', []))
        
        if all_concerns:
            recommendations.append(f"Address ongoing concerns: {', '.join(set(all_concerns)[:3])}")
        
        # Default recommendation
        if not recommendations:
            recommendations.append("Continue regular conversations to maintain connection")
        
        return recommendations
    
    def _identify_red_flags(self, updates):
        """Identify any red flags from recent conversations"""
        red_flags = []
        
        for update in updates[-5:]:  # Last 5 conversations
            update_flags = update.get('red_flags', [])
            if update_flags:
                red_flags.append({
                    "date": update.get('date'),
                    "flags": update_flags,
                    "severity": "high"
                })
        
        return red_flags
    
    def _generate_weekly_summary(self, updates):
        """Generate weekly summary text"""
        
        if len(updates) < 2:
            return "Not enough data for weekly summary. Continue having conversations to build comprehensive insights."
        
        # Get last 7 days of updates
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        
        recent_updates = [
            u for u in updates 
            if datetime.fromisoformat(u.get('date', '2000-01-01')) >= week_ago
        ]
        
        if not recent_updates:
            recent_updates = updates[-3:]  # Fallback to last 3
        
        # Analyze week
        moods = [u.get('mood') for u in recent_updates]
        positive_days = moods.count('positive')
        
        concerns = []
        for u in recent_updates:
            concerns.extend(u.get('concerns', []))
        
        notable = []
        for u in recent_updates:
            notable.extend(u.get('notable_moments', []))
        
        # Build summary
        summary = f"**Weekly Summary** (Last {len(recent_updates)} conversations)\n\n"
        
        # Mood
        if positive_days == len(recent_updates):
            summary += "✅ **Mood:** Consistently positive throughout the week\n\n"
        elif positive_days >= len(recent_updates) / 2:
            summary += f"🟡 **Mood:** Mostly positive ({positive_days}/{len(recent_updates)} conversations)\n\n"
        else:
            summary += "⚠️ **Mood:** Some challenges this week\n\n"
        
        # Concerns
        if concerns:
            summary += f"**Concerns:** {len(concerns)} items noted\n"
            for concern in set(concerns)[:3]:
                summary += f"- {concern}\n"
            summary += "\n"
        else:
            summary += "**Concerns:** No significant concerns\n\n"
        
        # Notable moments
        if notable:
            summary += "**Highlights:**\n"
            for moment in notable[:3]:
                summary += f"- {moment}\n"
        
        return summary
    
    def _generate_chart_data(self, updates):
        """Generate data formatted for charts"""
        
        # Mood over time
        mood_chart = {
            "labels": [],
            "data": [],
            "colors": []
        }
        
        for update in updates:
            mood_chart['labels'].append(update.get('date', 'Unknown'))
            
            mood = update.get('mood', 'unknown')
            if mood == 'positive':
                mood_chart['data'].append(3)
                mood_chart['colors'].append('#10B981')  # Green
            elif mood == 'neutral':
                mood_chart['data'].append(2)
                mood_chart['colors'].append('#F59E0B')  # Yellow
            elif mood == 'negative':
                mood_chart['data'].append(1)
                mood_chart['colors'].append('#EF4444')  # Red
            else:
                mood_chart['data'].append(0)
                mood_chart['colors'].append('#6B7280')  # Gray
        
        # Alert level over time
        alert_chart = {
            "labels": [],
            "data": [],
            "colors": []
        }
        
        for update in updates:
            alert_chart['labels'].append(update.get('date', 'Unknown'))
            
            alert = update.get('alert_level', '🟢 Low')
            if '🔴' in alert or 'High' in alert:
                alert_chart['data'].append(3)
                alert_chart['colors'].append('#EF4444')
            elif '🟡' in alert or 'Moderate' in alert:
                alert_chart['data'].append(2)
                alert_chart['colors'].append('#F59E0B')
            else:
                alert_chart['data'].append(1)
                alert_chart['colors'].append('#10B981')
        
        # Engagement over time
        engagement_chart = {
            "labels": [],
            "data": []
        }
        
        for update in updates:
            engagement_chart['labels'].append(update.get('date', 'Unknown'))
            
            engagement = update.get('engagement', 'unknown').lower()
            if 'high' in engagement:
                engagement_chart['data'].append(3)
            elif 'moderate' in engagement or 'medium' in engagement:
                engagement_chart['data'].append(2)
            elif 'low' in engagement:
                engagement_chart['data'].append(1)
            else:
                engagement_chart['data'].append(0)
        
        return {
            "mood": mood_chart,
            "alerts": alert_chart,
            "engagement": engagement_chart
        }


if __name__ == "__main__":
    # Test with mock data
    from beta_tester_manager import BetaTesterManager
    
    manager = BetaTesterManager()
    analyzer = HealthTrendAnalyzer()
    
    # Test with BT002 (if it exists)
    analysis = analyzer.analyze_health_trends("BT002", manager)
    
    print("\n=== HEALTH TREND ANALYSIS ===\n")
    print(f"Total Conversations: {analysis['overview']['total_conversations']}")
    print(f"Overall Trend: {analysis['overview'].get('overall_trend', 'N/A')}")
    print(f"\nRecommendations:")
    for rec in analysis['recommendations']:
        print(f"  - {rec}")
    
    if analysis['red_flags']:
        print(f"\n⚠️ Red Flags: {len(analysis['red_flags'])}")
    
    print("\n" + analysis['weekly_summary'])
