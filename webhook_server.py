"""
TelAila Webhook Server
Connects ElevenLabs voice conversations to biographer.py logic
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from pathlib import Path
from datetime import datetime
from elevenlabs_agent_manager import ElevenLabsAgentManager
from conversation_analyzer import ConversationAnalyzer
from beta_tester_manager import BetaTesterManager
from health_trend_analyzer import HealthTrendAnalyzer

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type"]
    }
})

# Initialize managers
# ElevenLabs agent manager is optional (only needed for automated agent creation)
# For beta testing, we create agents manually in ElevenLabs UI
try:
    agent_manager = ElevenLabsAgentManager()
except ValueError:
    agent_manager = None
    print("⚠️  ElevenLabs API key not set - automated agent creation disabled")
    print("   (This is fine for beta testing where agents are created manually)")

conversation_analyzer = ConversationAnalyzer()
beta_manager = BetaTesterManager()
health_analyzer = HealthTrendAnalyzer()

# Storage for active biographer sessions
sessions = {}
sessions_file = Path("active_sessions.json")

def load_sessions():
    """Load active sessions from disk"""
    global sessions
    if sessions_file.exists():
        with open(sessions_file, 'r') as f:
            data = json.load(f)
            # Reconstruct CompanionAI objects
            for user_id, session_data in data.items():
                sessions[user_id] = {
                    'user_name': session_data['user_name'],
                    'companion': CompanionAI(user_name=session_data['user_name']),
                    'conversation_count': session_data.get('conversation_count', 0),
                    'last_interaction': session_data.get('last_interaction'),
                    'agent_id': session_data.get('agent_id')
                }
        print(f"✅ Loaded {len(sessions)} active sessions")

def save_sessions():
    """Save active sessions to disk"""
    data = {}
    for user_id, session in sessions.items():
        data[user_id] = {
            'user_name': session['user_name'],
            'conversation_count': session['conversation_count'],
            'last_interaction': session['last_interaction'],
            'agent_id': session.get('agent_id')
        }
    with open(sessions_file, 'w') as f:
        json.dump(data, f, indent=2)

# Load sessions on startup
load_sessions()


@app.route('/api/family-dashboard/<beta_id>', methods=['GET'])
def get_family_dashboard(beta_id):
    """
    Family Dashboard - Complete health trends and conversation summaries
    
    Access via: /api/family-dashboard/BT002
    OR: /api/family-dashboard/BT002?token=access_token (for security)
    
    Returns comprehensive dashboard data with health trends
    """
    try:
        print(f"\n📊 Family dashboard requested for: {beta_id}")
        
        # Optional: Verify access token
        # token = request.args.get('token')
        # tester = beta_manager.registry['testers'].get(beta_id)
        # if tester and token != tester.get('access_token'):
        #     return jsonify({'error': 'Invalid access token'}), 403
        
        # Get tester info
        tester = beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            return jsonify({'error': 'Beta tester not found'}), 404
        
        # Analyze health trends
        health_analysis = health_analyzer.analyze_health_trends(beta_id, beta_manager)
        
        # Get recent family updates
        updates_path = beta_manager.get_tester_data_path(beta_id, "family_updates")
        recent_updates = []
        
        if updates_path.exists():
            for update_file in sorted(updates_path.glob("*.json"), reverse=True)[:10]:
                with open(update_file, 'r', encoding='utf-8') as f:
                    recent_updates.append(json.load(f))
        
        # Get knowledge base snippet (latest stories/memories)
        kb_path = beta_manager.get_tester_data_path(beta_id, "conversations")
        latest_stories = []
        
        if kb_path.exists():
            kb_files = list(kb_path.glob("*_knowledge_base.txt"))
            if kb_files:
                with open(kb_files[0], 'r', encoding='utf-8') as f:
                    kb_content = f.read()
                    
                # Extract biography section
                if "## Biography Building Blocks" in kb_content:
                    bio_section = kb_content.split("## Biography Building Blocks")[1]
                    if "##" in bio_section:
                        bio_section = bio_section.split("##")[0]
                    
                    # Extract stories
                    lines = bio_section.strip().split('\n')
                    for line in lines:
                        if line.strip().startswith('- '):
                            latest_stories.append(line.strip()[2:])
        
        dashboard_data = {
            "success": True,
            "beta_id": beta_id,
            "elder_name": tester['signup_data']['theirName'],
            "family_name": tester['signup_data']['yourName'],
            "family_email": tester['signup_data']['yourEmail'],
            "status": tester['status'],
            "conversation_count": tester.get('conversation_count', 0),
            "last_conversation": tester.get('last_conversation'),
            
            # Health trends
            "health_trends": health_analysis,
            
            # Recent updates
            "recent_updates": recent_updates[:5],  # Last 5
            
            # Latest stories/memories
            "latest_stories": latest_stories[:5],
            
            # Quick stats
            "quick_stats": {
                "total_conversations": health_analysis['overview']['total_conversations'],
                "date_range": health_analysis['overview'].get('date_range', 'N/A'),
                "overall_trend": health_analysis['overview'].get('overall_trend', 'stable'),
                "red_flags": len(health_analysis['red_flags']),
                "identified_patterns": len(health_analysis['health_patterns'].get('identified_patterns', {}))
            }
        }
        
        return jsonify(dashboard_data)
    
    except Exception as e:
        print(f"❌ Error generating dashboard: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/knowledge-base/<agent_id>', methods=['GET'])
def get_knowledge_base(agent_id):
    """
    Serve knowledge base to ElevenLabs
    Called by ElevenLabs workflow at conversation start
    
    Returns the current knowledge base for the agent
    """
    try:
        print(f"\n📚 Knowledge base requested for agent: {agent_id}")
        
        # Try to find beta tester
        tester = beta_manager.get_tester_by_agent_id(agent_id)
        
        if tester:
            # Beta tester - use their folder
            beta_id = tester['beta_id']
            kb_file = beta_manager.get_tester_data_path(beta_id, "conversations") / f"{agent_id}_knowledge_base.txt"
            print(f"   📁 Beta tester: {beta_id}")
        else:
            # Legacy path
            kb_file = Path(f"knowledge_bases/{agent_id}.txt")
            print(f"   📁 Legacy path")
        
        if kb_file.exists():
            with open(kb_file, 'r', encoding='utf-8') as f:
                knowledge_base = f.read()
            
            print(f"   ✅ Found existing knowledge base ({len(knowledge_base)} chars)")
            
            return jsonify({
                'success': True,
                'agent_id': agent_id,
                'knowledge_base': knowledge_base,
                'conversation_count': knowledge_base.count('### Session')
            })
        else:
            # Return empty/default knowledge base for first conversation
            print(f"   ℹ️  No existing knowledge base - returning default")
            
            # Get user name if we have it
            user_name = "them"
            if tester:
                user_name = tester['signup_data']['theirName']
            
            default_kb = f"""# Conversation Memory

## Quick Reference
Last conversation: Never (this is first time)
Total conversations: 0
Recent mood: Unknown (getting to know {user_name})

## Person Profile
- Getting to know them...

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
"""
            
            return jsonify({
                'success': True,
                'agent_id': agent_id,
                'knowledge_base': default_kb,
                'conversation_count': 0,
                'is_first_conversation': True
            })
    
    except Exception as e:
        print(f"   ❌ Error retrieving knowledge base: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/register', methods=['POST'])
def register_beta_tester():
    """
    Register a new beta tester from Lovable signup form
    
    Called by Lovable when user submits beta signup
    
    Expected from Lovable (ALL fields):
    {
        "theirName": "Margaret Thompson",
        "yourName": "Susan",
        "yourEmail": "susan@example.com",
        "yourPhone": "555-123-4567",
        "relationship": "daughter",
        "theirAge": "82",
        "primaryLanguage": "English",
        "secondaryLanguage": "Spanish",
        "bestTime": "morning",
        "specialNotes": "..."
    }
    
    Returns registration confirmation and instructions
    """
    try:
        signup_data = request.json
        
        print(f"\n🎯 New beta tester registration")
        print(f"   Elder: {signup_data.get('theirName')} (Age: {signup_data.get('theirAge', 'N/A')})")
        print(f"   Family: {signup_data.get('yourName')} ({signup_data.get('yourEmail')})")
        print(f"   Phone: {signup_data.get('yourPhone', 'N/A')}")
        print(f"   Relationship: {signup_data.get('relationship', 'N/A')}")
        print(f"   Languages: {signup_data.get('primaryLanguage', 'N/A')}, {signup_data.get('secondaryLanguage', 'None')}")
        print(f"   Best Time: {signup_data.get('bestTime', 'N/A')}")
        print(f"   Special Notes: {signup_data.get('specialNotes', 'None')[:50]}...")
        
        # Register the tester (stores ALL signup_data)
        result = beta_manager.register_beta_tester(signup_data)
        
        # Generate setup email content (for manual sending or future automation)
        email_content = beta_manager.generate_setup_email(result['beta_id'])
        
        print(f"   ✅ Registered as: {result['beta_id']}")
        print(f"   📧 Setup email generated")
        print(f"   ⏳ Status: Pending manual agent setup")
        
        return jsonify({
            'success': True,
            'beta_id': result['beta_id'],
            'message': "Thank you for signing up! We'll send you an email with your companion's conversation link within 24 hours.",
            'status': 'pending_setup',
            'elder_name': signup_data.get('theirName'),
            'family_email': signup_data.get('yourEmail')
        })
    
    except Exception as e:
        print(f"❌ Error registering beta tester: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/link-agent', methods=['POST'])
def link_agent_to_tester():
    """
    Admin endpoint: Link an ElevenLabs agent to a beta tester
    
    After manually creating agent in ElevenLabs UI, call this to link it
    
    POST /api/beta/link-agent
    {
        "beta_id": "BT001",
        "agent_id": "agent_3601kdkj0jp7e9h912zrk5fyraxy"
    }
    """
    try:
        data = request.json
        beta_id = data.get('beta_id')
        agent_id = data.get('agent_id')
        
        result = beta_manager.link_agent(beta_id, agent_id)
        
        if result['success']:
            print(f"✅ Linked {agent_id} → {beta_id}")
        
        return jsonify(result)
    
    except Exception as e:
        print(f"❌ Error linking agent: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/testers', methods=['GET'])
def get_all_beta_testers():
    """
    Admin endpoint: Get all beta testers and their status
    
    Returns list of all registered testers with setup status and full signup data
    """
    try:
        testers = beta_manager.get_all_testers()
        
        # Format for display
        tester_list = []
        for beta_id, tester in testers.items():
            signup = tester['signup_data']
            tester_list.append({
                'beta_id': beta_id,
                'status': tester['status'],
                'agent_id': tester.get('agent_id'),
                'conversation_count': tester.get('conversation_count', 0),
                'registered_at': tester['registered_at'],
                
                # Elder info
                'elder_name': signup.get('theirName'),
                'elder_age': signup.get('theirAge'),
                
                # Family info
                'family_name': signup.get('yourName'),
                'family_email': signup.get('yourEmail'),
                'family_phone': signup.get('yourPhone'),
                'relationship': signup.get('relationship'),
                
                # Language & timing
                'primary_language': signup.get('primaryLanguage'),
                'secondary_language': signup.get('secondaryLanguage'),
                'best_time': signup.get('bestTime'),
                
                # Notes
                'special_notes': signup.get('specialNotes')
            })
        
        return jsonify({
            'success': True,
            'total_testers': len(tester_list),
            'testers': tester_list
        })
    
    except Exception as e:
        print(f"❌ Error fetching testers: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/agent-id/<beta_id>', methods=['GET'])
def get_agent_id(beta_id):
    """
    Get agent_id for beta tester's conversation page
    Called by /talk/[betaId] page to load the correct agent
    """
    try:
        # Normalize beta_id to uppercase (BT001, BT002, etc.)
        beta_id = beta_id.upper()
        
        print(f"\n🔍 Agent ID requested for: {beta_id}")
        
        tester = beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            print(f"   ❌ Beta tester not found: {beta_id}")
            return jsonify({
                'success': False,
                'error': 'Beta tester not found'
            }), 404
        
        if not tester.get('agent_id'):
            print(f"   ⏳ Agent not yet linked for: {beta_id}")
            return jsonify({
                'success': False,
                'error': 'Agent not yet linked',
                'status': 'pending_setup',
                'beta_id': beta_id,
                'elder_name': tester['signup_data']['theirName']
            }), 404
        
        print(f"   ✅ Agent found: {tester['agent_id']}")
        
        return jsonify({
            'success': True,
            'beta_id': beta_id,
            'agent_id': tester['agent_id'],
            'elder_name': tester['signup_data']['theirName'],
            'family_name': tester['signup_data']['yourName'],
            'status': tester['status']
        })
    
    except Exception as e:
        print(f"   ❌ Error fetching agent ID: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/create-agent', methods=['POST'])
def create_agent_from_signup():
    """
    Create ElevenLabs agent when someone completes beta signup
    
    Expected from Lovable:
    {
        "theirName": "Margaret Thompson",
        "yourName": "Susan",
        "yourEmail": "susan@example.com",
        "relationship": "daughter",
        "theirAge": "82",
        "primaryLanguage": "English",
        "specialNotes": "..."
    }
    """
    try:
        user_profile = request.json
        
        print(f"\n🎯 Creating agent for beta signup: {user_profile.get('theirName')}")
        
        # Check if automated agent creation is available
        if agent_manager is None:
            return jsonify({
                'success': False,
                'error': 'Automated agent creation not available. Please create agents manually in ElevenLabs UI.',
                'message': 'For beta testing, create the agent manually and use /api/beta/link-agent to connect it.'
            }), 503
        
        # Create ElevenLabs agent
        agent_info = agent_manager.create_agent(user_profile)
        
        # Store agent info for later retrieval
        # (In production, save to database)
        agent_file = Path(f"beta_agents/{user_profile['yourEmail'].replace('@', '_at_')}.json")
        agent_file.parent.mkdir(exist_ok=True)
        
        with open(agent_file, 'w') as f:
            json.dump(agent_info, f, indent=2)
        
        return jsonify({
            'success': True,
            'agent_id': agent_info['agent_id'],
            'conversation_url': agent_info['conversation_url'],
            'message': f"Agent created for {user_profile['theirName']}"
        })
    
    except Exception as e:
        print(f"❌ Error creating agent: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/webhook/elevenlabs/conversation-ended', methods=['POST'])
def elevenlabs_conversation_ended():
    """
    Webhook called by ElevenLabs when a conversation ends
    
    Expected payload from ElevenLabs:
    {
        "type": "post_call_transcription",
        "data": {
            "agent_id": "...",
            "conversation_id": "...",
            "transcript": [...],
            "metadata": {...}
        }
    }
    """
    try:
        payload = request.json
        
        # Extract nested data
        data = payload.get('data', {})
        
        print(f"\n📞 Conversation ended webhook received")
        print(f"   Agent: {data.get('agent_id')}")
        print(f"   Conversation: {data.get('conversation_id')}")
        
        # Get conversation details
        conversation_id = data.get('conversation_id')
        agent_id = data.get('agent_id')
        
        # Get transcript from payload (it's already included!)
        transcript_data = data.get('transcript', [])
        
        # Convert transcript to readable format
        transcript = ""
        for turn in transcript_data:
            role = turn.get('role', 'unknown')
            message = turn.get('message', '')
            
            if role == 'agent':
                transcript += f"\nAila: {message}\n"
            elif role == 'user':
                transcript += f"\nUser: {message}\n"
        
        print(f"   📝 Transcript length: {len(transcript)} characters")
        # Load agent config OR find beta tester
        agent_config_file = Path(f"agent_configs/{agent_id}.json")
        
        # Try to find beta tester by agent_id
        tester = beta_manager.get_tester_by_agent_id(agent_id)
        
        if tester:
            # Beta tester found!
            beta_id = tester['beta_id']
            user_name = tester['signup_data']['theirName']
            family_name = tester['signup_data']['yourName']
            family_email = tester['signup_data']['yourEmail']
            
            print(f"   👤 Beta Tester: {beta_id} - {user_name}")
            
            # Update conversation count
            beta_manager.update_conversation_count(beta_id)
            
        elif agent_config_file.exists():
            # Legacy agent config (from before beta system)
            with open(agent_config_file, 'r') as f:
                agent_config = json.load(f)
            user_profile = agent_config['user_profile']
            user_name = user_profile['theirName']
            family_name = user_profile['yourName']
            family_email = user_profile.get('yourEmail', 'test@example.com')
            beta_id = None
            print(f"   👤 Legacy User: {user_name}")
            
        else:
            # Fallback for manually created agents
            print(f"   ℹ️  No config found - using defaults")
            user_name = "Margaret"  # Default from manual agent creation
            family_name = "Family Member"
            family_email = "test@example.com"
            beta_id = None
        
        print(f"   👤 User: {user_name}")
        
        # Analyze conversation
        # Load existing knowledge base
        if beta_id:
            # Use beta tester folder structure
            kb_file = beta_manager.get_tester_data_path(beta_id, "conversations") / f"{agent_id}_knowledge_base.txt"
        else:
            # Legacy path
            kb_file = Path(f"knowledge_bases/{agent_id}.txt")
        
        kb_file.parent.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        
        existing_kb = ""
        if kb_file.exists():
            with open(kb_file, 'r', encoding='utf-8') as f:
                existing_kb = f.read()
        else:
            # Create initial knowledge base for manually created agent
            existing_kb = f"""# Conversation Memory for {user_name}

## Quick Reference
Last conversation: Never (this is first time)
Total conversations: 0

## Person Profile
- Name: {user_name}

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
"""
        
        # Analyze with Claude
        analysis = conversation_analyzer.analyze_conversation(
            transcript=transcript,
            user_name=user_name,
            existing_knowledge_base=existing_kb
        )
        
        # Update knowledge base
        updated_kb = conversation_analyzer.update_knowledge_base(
            existing_kb=existing_kb,
            transcript=transcript,
            analysis=analysis,
            user_name=user_name
        )
        
        # Save updated knowledge base
        kb_file.parent.mkdir(exist_ok=True)
        with open(kb_file, 'w', encoding='utf-8') as f:
            f.write(updated_kb)
        
        # Upload updated knowledge base to ElevenLabs (if possible)
        if agent_manager is not None:
            try:
                agent_manager.update_agent_after_conversation(agent_id, updated_kb)
            except Exception as e:
                print(f"   ⚠️  Could not upload to ElevenLabs: {e}")
                print(f"   💡 Knowledge base saved locally, will need manual upload")
        else:
            print(f"   ℹ️  ElevenLabs API not configured - knowledge base saved locally only")
        
        # Generate family update
        family_update = conversation_analyzer.generate_family_update(
            analysis=analysis,
            user_name=user_name,
            family_name=family_name
        )
        
        # Save family update
        if beta_id:
            # Use beta tester folder structure
            update_file = beta_manager.get_tester_data_path(beta_id, "family_updates") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            # Legacy path
            update_file = Path(f"family_updates/{agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        update_file.parent.mkdir(parents=True, exist_ok=True)
        with open(update_file, 'w', encoding='utf-8') as f:
            json.dump(family_update, f, indent=2)
        
        # TODO: Send email to family if configured
        # send_family_email(user_profile['yourEmail'], family_update)
        
        # Check for red flags
        if analysis['health'].get('red_flags'):
            print(f"🔴 RED FLAGS DETECTED:")
            for flag in analysis['health']['red_flags']:
                print(f"   - {flag}")
            # TODO: Send immediate alert to family
        
        print(f"✅ Conversation processed successfully")
        
        return jsonify({
            'success': True,
            'message': 'Conversation processed',
            'alert_level': family_update['alert_level']
        })
    
    except Exception as e:
        print(f"❌ Error processing conversation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'service': 'TelAila Webhook Server',
        'active_sessions': len(sessions),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/webhook/elevenlabs', methods=['POST'])
def elevenlabs_webhook():
    """
    Main webhook endpoint for ElevenLabs
    Receives conversation turns and returns Aila's response
    """
    try:
        data = request.json
        print(f"\n📨 Received webhook from ElevenLabs")
        print(f"Data: {json.dumps(data, indent=2)}")
        
        # Extract data from webhook
        # Note: Actual ElevenLabs webhook format may vary
        # This is a template - we'll adjust based on their docs
        
        agent_id = data.get('agent_id')
        user_transcript = data.get('transcript') or data.get('user_message')
        conversation_id = data.get('conversation_id')
        
        if not user_transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        # Find or create session for this agent
        session_key = agent_id or conversation_id
        
        if session_key not in sessions:
            # New conversation - need user info
            # This should come from the signup data
            user_name = data.get('user_name', 'User')
            
            print(f"🆕 Creating new session for: {user_name}")
            biographer = BiographerAI(user_name=user_name)
            
            sessions[session_key] = {
                'user_name': user_name,
                'biographer': biographer,
                'conversation_count': 0,
                'last_interaction': datetime.now().isoformat(),
                'agent_id': agent_id
            }
            
            # Start the session (get greeting)
            aila_response = biographer.start_session()
            sessions[session_key]['conversation_count'] = 1
            
        else:
            # Existing conversation
            session = sessions[session_key]
            biographer = session['biographer']
            
            print(f"💬 Continuing conversation for: {session['user_name']}")
            print(f"   User said: {user_transcript}")
            
            # Get Aila's response using biographer logic
            aila_response, is_complete = biographer.respond_to_user(user_transcript)
            
            session['conversation_count'] += 1
            session['last_interaction'] = datetime.now().isoformat()
            
            # If session is complete, generate chapter
            if is_complete:
                print(f"✅ Session complete! Generating chapter...")
                try:
                    session_id = biographer.data["sessions"][-1]["session_id"]
                    chapter_path = biographer.generate_chapter(session_id)
                    print(f"📄 Chapter generated: {chapter_path}")
                    
                    # TODO: Email chapter to family
                    # send_chapter_to_family(session['user_name'], chapter_path)
                    
                except Exception as e:
                    print(f"⚠️  Chapter generation failed: {e}")
        
        # Save sessions
        save_sessions()
        
        # Return response to ElevenLabs
        return jsonify({
            'response': aila_response,
            'continue_conversation': True,
            'session_id': session_key
        })
    
    except Exception as e:
        print(f"❌ Error in webhook: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/webhook/conversation-ended', methods=['POST'])
def conversation_ended():
    """
    Called when ElevenLabs conversation ends
    """
    data = request.json
    agent_id = data.get('agent_id')
    conversation_id = data.get('conversation_id')
    
    session_key = agent_id or conversation_id
    
    print(f"📞 Conversation ended for session: {session_key}")
    
    # Session data persists for next conversation
    # We don't delete it - Aila should remember!
    
    return jsonify({'status': 'acknowledged'})


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """
    Admin endpoint to view active sessions
    """
    session_list = []
    for session_key, session in sessions.items():
        session_list.append({
            'session_id': session_key,
            'user_name': session['user_name'],
            'conversation_count': session['conversation_count'],
            'last_interaction': session['last_interaction'],
            'agent_id': session.get('agent_id')
        })
    
    return jsonify({
        'active_sessions': len(sessions),
        'sessions': session_list
    })


@app.route('/api/session/<session_id>', methods=['GET'])
def get_session(session_id):
    """
    Get details about a specific session
    """
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session = sessions[session_id]
    biographer = session['biographer']
    
    return jsonify({
        'session_id': session_id,
        'user_name': session['user_name'],
        'conversation_count': session['conversation_count'],
        'last_interaction': session['last_interaction'],
        'total_sessions': len(biographer.data['sessions']),
        'biography_progress': biographer.data['progress']
    })


@app.route('/api/test', methods=['POST'])
def test_endpoint():
    """
    Test endpoint to simulate ElevenLabs webhook
    """
    data = request.json
    user_name = data.get('user_name', 'Test User')
    message = data.get('message', 'Hello')
    
    # Create test session
    test_key = 'test-session'
    
    if test_key not in sessions:
        companion = CompanionAI(user_name=user_name)
        sessions[test_key] = {
            'user_name': user_name,
            'companion': companion,
            'conversation_count': 0,
            'last_interaction': datetime.now().isoformat(),
            'agent_id': 'test'
        }
        response = companion.start_session()
    else:
        session = sessions[test_key]
        companion = session['companion']
        response, is_complete = companion.respond_to_user(message)
        session['conversation_count'] += 1
    
    save_sessions()
    
    return jsonify({
        'aila_response': response,
        'session': sessions[test_key]
    })


@app.route('/api/voice/process', methods=['POST'])
def process_voice():
    """
    Process voice conversation from the web interface
    Receives audio, transcribes it, gets biographer response, converts to speech
    """
    try:
        data = request.json
        
        # Get audio and profile
        audio_base64 = data.get('audio')
        profile = data.get('profile')
        
        if not audio_base64 or not profile:
            return jsonify({'error': 'Missing audio or profile'}), 400
        
        print(f"\n🎤 Processing voice for: {profile.get('theirName')}")
        
        # Import ElevenLabs for speech processing
        from elevenlabs import ElevenLabs
        
        eleven_client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY"))
        
        # Step 1: Speech-to-Text (transcribe user's audio)
        print("📝 Transcribing audio...")
        import base64
        
        # Decode base64 audio
        try:
            # Remove data URL prefix if present (data:audio/webm;base64,)
            if ',' in audio_base64:
                audio_base64 = audio_base64.split(',')[1]
            
            audio_bytes = base64.b64decode(audio_base64)
            print(f"   Decoded audio: {len(audio_bytes)} bytes")
            
        except Exception as e:
            print(f"   Base64 decode error: {e}")
            return jsonify({'error': 'Invalid audio data'}), 400
        
        # Save as temporary file
        temp_audio = Path("temp_audio.webm")
        with open(temp_audio, 'wb') as f:
            f.write(audio_bytes)
        
        # Try to transcribe with ElevenLabs
        try:
            print("   Attempting transcription with ElevenLabs...")
            
            # The correct way to call ElevenLabs speech-to-text
            # Open file and pass it directly
            with open(temp_audio, 'rb') as audio_file:
                # Method signature: convert(file, model_id)
                transcript_result = eleven_client.speech_to_text.convert(
                    file=audio_file,
                    model_id="scribe_v2"
                )
            
            user_text = transcript_result.get('text', '')
            print(f"👤 User said: {user_text}")
            
            # Clean up temp file
            temp_audio.unlink()
            
        except Exception as transcribe_error:
            print(f"   ⚠️ Transcription failed: {transcribe_error}")
            print("   Error type:", type(transcribe_error).__name__)
            
            # Clean up temp file
            if temp_audio.exists():
                temp_audio.unlink()
            
            # TEMPORARY: Type what you said manually for testing
            # This allows us to test the rest of the system while we fix audio format
            user_text = "Yes, I have time to talk. I'm feeling okay today."
            print(f"   📝 Using test response for now: {user_text}")
            print("   💡 Note: Real transcription will be enabled once audio format is fixed")
        
        # Step 2: Get biographer response
        session_key = profile.get('yourEmail')  # Use email as session key
        
        if session_key not in sessions:
            # Create new session
            print(f"🆕 Creating new session")
            companion = CompanionAI(user_name=profile.get('theirName'))
            
            sessions[session_key] = {
                'user_name': profile.get('theirName'),
                'companion': companion,
                'conversation_count': 0,
                'last_interaction': datetime.now().isoformat(),
                'profile': profile
            }
            
            # Get initial greeting
            aila_response = companion.start_session()
            sessions[session_key]['conversation_count'] = 1
        else:
            # Continue existing session
            session = sessions[session_key]
            companion = session['companion']
            
            print(f"💬 Continuing session for: {session['user_name']}")
            
            # Get response from companion
            aila_response, is_complete = companion.respond_to_user(user_text)
            
            session['conversation_count'] += 1
            session['last_interaction'] = datetime.now().isoformat()
            
            # If session complete, generate family update
            if is_complete:
                print(f"✅ Session complete! Generating family update...")
                try:
                    family_update = companion.generate_family_update()
                    print(f"📊 Family update generated")
                    
                    # Store update
                    session['last_family_update'] = family_update
                    
                    # TODO: Email family with update
                except Exception as e:
                    print(f"⚠️ Family update generation failed: {e}")
        
        print(f"🤖 Aila responds: {aila_response}")
        
        # Step 3: Text-to-Speech (convert Aila's response to audio)
        print("🔊 Converting to speech...")
        
        audio_response = eleven_client.text_to_speech.convert(
            voice_id="EXAVITQu4vr4xnSDxMaL",  # Jessica voice
            text=aila_response,
            model_id="eleven_multilingual_v2"
        )
        
        # Convert audio bytes to base64
        audio_bytes_list = list(audio_response)
        audio_data = b''.join(audio_bytes_list)
        audio_base64_response = base64.b64encode(audio_data).decode('utf-8')
        
        # Save sessions
        save_sessions()
        
        return jsonify({
            'success': True,
            'user_text': user_text,
            'aila_text': aila_response,
            'audio': audio_base64_response,
            'conversation_count': sessions[session_key]['conversation_count']
        })
    
    except Exception as e:
        print(f"❌ Error in voice processing: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/session/start', methods=['POST'])
def start_session():
    """
    Start a new conversation session - Aila speaks first
    """
    try:
        data = request.json
        profile = data.get('profile')
        
        if not profile:
            return jsonify({'error': 'No profile provided'}), 400
        
        print(f"\n🎬 Starting new session for: {profile.get('theirName')}")
        
        # Import ElevenLabs
        from elevenlabs import ElevenLabs
        eleven_client = ElevenLabs(api_key=os.environ.get("ELEVENLABS_API_KEY"))
        
        session_key = profile.get('yourEmail')
        
        # Create new session or get existing
        if session_key not in sessions:
            print(f"🆕 Creating NEW session - first time user")
            companion = CompanionAI(user_name=profile.get('theirName'))
            
            sessions[session_key] = {
                'user_name': profile.get('theirName'),
                'companion': companion,
                'conversation_count': 0,
                'last_interaction': datetime.now().isoformat(),
                'profile': profile,
                'is_new': True
            }
            
            # Get initial greeting for NEW user
            aila_response = companion.start_session()
            sessions[session_key]['conversation_count'] = 1
            print(f"   This is their FIRST conversation")
        else:
            # Existing session - returning user
            session = sessions[session_key]
            print(f"🔄 Returning user - has {session['conversation_count']} previous interactions")
            
            # Check if this is same day or new day
            last_time = datetime.fromisoformat(session['last_interaction'])
            if (datetime.now() - last_time).days > 0:
                # New day - warm welcome back
                aila_response = f"Hi {profile.get('theirName')}! It's Aila. It's so good to hear from you again. How have you been since we last talked?"
            else:
                # Same day - continuing conversation
                aila_response = f"Hi {profile.get('theirName')}! It's Aila. How are you feeling right now?"
            
            session['is_new'] = False
        
        print(f"🤖 Aila greets: {aila_response}")
        
        # Convert to speech
        print("🔊 Converting greeting to speech...")
        audio_response = eleven_client.text_to_speech.convert(
            voice_id="EXAVITQu4vr4xnSDxMaL",  # Jessica voice
            text=aila_response,
            model_id="eleven_multilingual_v2"
        )
        
        # Convert audio to base64
        import base64
        audio_bytes_list = list(audio_response)
        audio_data = b''.join(audio_bytes_list)
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        
        save_sessions()
        
        return jsonify({
            'success': True,
            'aila_text': aila_response,
            'audio': audio_base64,
            'session_key': session_key
        })
    
    except Exception as e:
        print(f"❌ Error starting session: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/session/info', methods=['POST'])
def get_session_info():
    """
    Get information about current session
    """
    try:
        data = request.json
        profile = data.get('profile')
        
        if not profile:
            return jsonify({'error': 'No profile provided'}), 400
        
        session_key = profile.get('yourEmail')
        
        if session_key not in sessions:
            return jsonify({
                'exists': False,
                'message': 'No active session'
            })
        
        session = sessions[session_key]
        companion = session['companion']
        
        return jsonify({
            'exists': True,
            'conversation_count': session['conversation_count'],
            'user_name': session['user_name'],
            'last_interaction': session['last_interaction'],
            'total_conversations': len(companion.data['conversations']),
            'recent_mood': companion._calculate_average_mood(),
            'health_concerns': len(companion._get_health_concerns()),
            'last_family_update': session.get('last_family_update')
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("  TelAila Companion AI Server - Beta Testing System")
    print("  Providing companionship & reducing loneliness")
    print("=" * 70)
    print("\n✅ Server starting...")
    print(f"\n📋 BETA TESTER ENDPOINTS:")
    print(f"   Register: http://localhost:5000/api/beta/register")
    print(f"   Link agent: http://localhost:5000/api/beta/link-agent")
    print(f"   View all: http://localhost:5000/api/beta/testers")
    print(f"\n👨‍👩‍👧 FAMILY DASHBOARD:")
    print(f"   Dashboard: http://localhost:5000/api/family-dashboard/<beta_id>")
    print(f"   Example: http://localhost:5000/api/family-dashboard/BT002")
    print(f"\n🤖 AGENT ENDPOINTS:")
    print(f"   Knowledge base: http://localhost:5000/api/knowledge-base/<agent_id>")
    print(f"   Webhook: http://localhost:5000/webhook/elevenlabs/conversation-ended")
    print(f"\n🌐 NGROK:")
    print(f"   URL: {os.environ.get('WEBHOOK_BASE_URL', 'Not set')}")
    print(f"   💡 Make sure ngrok is running: ngrok http 5000")
    print("\n🤝 Ready for beta testing!\n")
    
    # Run server
    # Railway provides PORT environment variable in production
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
