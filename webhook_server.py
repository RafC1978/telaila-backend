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
from family_dashboard_generator import FamilyDashboardGenerator
from memory_manager import MemoryManager
from biography_builder import BiographyBuilder

app = Flask(__name__)
CORS(app, resources={
    r"/api/*": {
        "origins": "*",
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
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
dashboard_generator = FamilyDashboardGenerator(beta_manager)
memory_manager = MemoryManager()
biography_builder = BiographyBuilder(beta_manager)

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


@app.route('/api/beta/transcripts/<beta_id>', methods=['GET'])
def get_beta_transcripts(beta_id):
    """
    Get all conversation transcripts for a beta tester
    """
    try:
        beta_id = beta_id.upper()
        print(f"\n📄 Transcripts requested for: {beta_id}")
        
        tester = beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            return jsonify({'success': False, 'error': 'Beta tester not found'}), 404
        
        conversations_path = beta_manager.get_tester_data_path(beta_id, "conversations")
        transcripts_path = beta_manager.get_tester_data_path(beta_id, "transcripts")
        
        all_conversations = []
        
        if conversations_path.exists():
            for conv_file in sorted(conversations_path.glob("*.json")):
                try:
                    with open(conv_file, 'r', encoding='utf-8') as f:
                        conv_data = json.load(f)
                    
                    transcript_file = transcripts_path / f"{conv_file.stem}.txt"
                    transcript_text = ""
                    if transcript_file.exists():
                        with open(transcript_file, 'r', encoding='utf-8') as f:
                            transcript_text = f.read()
                    
                    all_conversations.append({
                        'filename': conv_file.name,
                        'timestamp': conv_data.get('timestamp'),
                        'conversation_id': conv_data.get('conversation_id'),
                        'transcript': transcript_text or conv_data.get('transcript', ''),
                        'analysis': conv_data.get('analysis', {})
                    })
                    
                except Exception as e:
                    print(f"⚠️  Could not load {conv_file.name}: {e}")
        
        print(f"   ✅ Found {len(all_conversations)} conversations")
        
        return jsonify({
            'success': True,
            'beta_id': beta_id,
            'elder_name': tester['signup_data']['theirName'],
            'total_conversations': len(all_conversations),
            'conversations': all_conversations
        })
    
    except Exception as e:
        print(f"❌ Error getting transcripts: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/beta/conversation/<beta_id>/<int:session_number>', methods=['GET'])
def get_single_conversation(beta_id, session_number):
    """Get a specific conversation by session number"""
    try:
        beta_id = beta_id.upper()
        print(f"\n📄 Conversation {session_number} requested for: {beta_id}")
        
        tester = beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            return jsonify({'success': False, 'error': 'Beta tester not found'}), 404
        
        conversations_path = beta_manager.get_tester_data_path(beta_id, "conversations")
        
        if not conversations_path.exists():
            return jsonify({'success': False, 'error': 'No conversations found'}), 404
        
        conv_files = sorted(conversations_path.glob("*.json"))
        
        if session_number < 1 or session_number > len(conv_files):
            return jsonify({
                'success': False, 
                'error': f'Session {session_number} not found. Valid range: 1-{len(conv_files)}'
            }), 404
        
        conv_file = conv_files[session_number - 1]
        
        with open(conv_file, 'r', encoding='utf-8') as f:
            conv_data = json.load(f)
        
        transcripts_path = beta_manager.get_tester_data_path(beta_id, "transcripts")
        transcript_file = transcripts_path / f"{conv_file.stem}.txt"
        
        transcript_text = ""
        if transcript_file.exists():
            with open(transcript_file, 'r', encoding='utf-8') as f:
                transcript_text = f.read()
        
        print(f"   ✅ Returning session {session_number}")
        
        return jsonify({
            'success': True,
            'beta_id': beta_id,
            'session_number': session_number,
            'timestamp': conv_data.get('timestamp'),
            'conversation_id': conv_data.get('conversation_id'),
            'transcript': transcript_text or conv_data.get('transcript', ''),
            'analysis': conv_data.get('analysis', {})
        })
    
    except Exception as e:
        print(f"❌ Error getting conversation: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/knowledge-base/<agent_id>', methods=['GET'])
def get_knowledge_base(agent_id):
    """Serve knowledge base to ElevenLabs"""
    try:
        print(f"\n📚 Knowledge base requested for agent: {agent_id}")
        
        optimized_mode = request.args.get('optimized', 'false').lower() == 'true'
        
        tester = beta_manager.get_tester_by_agent_id(agent_id)
        
        if tester:
            beta_id = tester['beta_id']
            kb_file = beta_manager.get_tester_data_path(beta_id, "knowledge_base.md")
            user_name = tester['signup_data']['theirName']
            print(f"   📁 Beta tester: {beta_id}")
        else:
            kb_file = Path(f"knowledge_bases/{agent_id}.txt")
            user_name = "them"
            print(f"   📁 Legacy path")
        
        if kb_file.exists():
            with open(kb_file, 'r', encoding='utf-8') as f:
                knowledge_base = f.read()
            
            conversation_count = knowledge_base.count('### Session')
            is_first = conversation_count == 0
            
            print(f"   ✅ Found existing knowledge base ({len(knowledge_base)} chars)")
            print(f"   📊 Conversation count: {conversation_count}")
            
            if optimized_mode:
                print(f"   🚀 Building optimized context...")
                optimized_context = memory_manager.build_optimized_context(knowledge_base, user_name)
                print(f"   ✅ Optimized: {len(knowledge_base)} → {len(optimized_context)} chars")
                knowledge_base = optimized_context
            
            return jsonify({
                'success': True,
                'agent_id': agent_id,
                'knowledge_base': knowledge_base,
                'conversation_count': conversation_count,
                'is_first_conversation': is_first,
                'optimized': optimized_mode
            })
        else:
            print(f"   ℹ️  No existing knowledge base - returning default")
            
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
    """Register a new beta tester from Lovable signup form"""
    try:
        signup_data = request.json
        
        print(f"\n🎯 New beta tester registration")
        print(f"   Elder: {signup_data.get('theirName')} (Age: {signup_data.get('theirAge', 'N/A')})")
        print(f"   Family: {signup_data.get('yourName')} ({signup_data.get('yourEmail')})")
        
        result = beta_manager.register_beta_tester(signup_data)
        email_content = beta_manager.generate_setup_email(result['beta_id'])
        
        print(f"   ✅ Registered as: {result['beta_id']}")
        
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
    """Link an ElevenLabs agent to a beta tester"""
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
    """Get all beta testers and their status"""
    try:
        testers = beta_manager.get_all_testers()
        
        tester_list = []
        for beta_id, tester in testers.items():
            signup = tester.get('signup_data', {})
            tester_list.append({
                'beta_id': beta_id,
                'status': tester.get('status', 'unknown'),
                'agent_id': tester.get('agent_id'),
                'conversation_count': tester.get('conversation_count', 0),
                'registered_at': tester.get('registered_at'),
                'elder_name': signup.get('theirName'),
                'elder_age': signup.get('theirAge'),
                'family_name': signup.get('yourName'),
                'family_email': signup.get('yourEmail'),
                'family_phone': signup.get('yourPhone'),
                'relationship': signup.get('relationship'),
                'primary_language': signup.get('primaryLanguage'),
                'secondary_language': signup.get('secondaryLanguage'),
                'best_time': signup.get('bestTime'),
                'special_notes': signup.get('specialNotes'),
                'signup_data': signup
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
    """Get agent_id for beta tester's conversation page"""
    try:
        beta_id = beta_id.upper()
        print(f"\n🔍 Agent ID requested for: {beta_id}")
        
        tester = beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            print(f"   ❌ Beta tester not found: {beta_id}")
            return jsonify({'success': False, 'error': 'Beta tester not found'}), 404
        
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


# ============================================
# ADMIN ENDPOINTS FOR TESTER MANAGEMENT
# ============================================

@app.route('/api/beta/tester/<beta_id>', methods=['GET'])
def get_beta_tester(beta_id):
    """Get a specific beta tester's info"""
    try:
        beta_id = beta_id.upper()
        beta_manager._load_registry()
        tester = beta_manager.registry['testers'].get(beta_id)
        
        if not tester:
            return jsonify({'error': 'Tester not found', 'beta_id': beta_id}), 404
        
        return jsonify({
            'success': True,
            'beta_id': beta_id,
            'tester': tester
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/tester/<beta_id>', methods=['DELETE'])
def delete_beta_tester(beta_id):
    """Delete a beta tester"""
    try:
        beta_id = beta_id.upper()
        beta_manager._load_registry()
        
        if beta_id not in beta_manager.registry['testers']:
            return jsonify({'error': 'Tester not found', 'beta_id': beta_id}), 404
        
        tester = beta_manager.registry['testers'][beta_id]
        elder_name = tester.get('signup_data', {}).get('theirName', 'Unknown')
        
        del beta_manager.registry['testers'][beta_id]
        beta_manager._save_registry()
        
        print(f"🗑️  Deleted beta tester: {beta_id} ({elder_name})")
        
        return jsonify({
            'success': True,
            'message': f'Deleted {beta_id} ({elder_name})',
            'deleted_beta_id': beta_id,
            'deleted_elder_name': elder_name
        })
    except Exception as e:
        print(f"❌ Error deleting tester: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/tester/<beta_id>', methods=['PUT'])
def update_beta_tester(beta_id):
    """Update a beta tester's info"""
    try:
        beta_id = beta_id.upper()
        beta_manager._load_registry()
        
        if beta_id not in beta_manager.registry['testers']:
            return jsonify({'error': 'Tester not found', 'beta_id': beta_id}), 404
        
        data = request.json
        tester = beta_manager.registry['testers'][beta_id]
        
        if 'status' in data:
            tester['status'] = data['status']
        
        if 'agent_id' in data:
            tester['agent_id'] = data['agent_id']
        
        signup_fields = ['theirName', 'yourName', 'yourEmail', 'relationship', 
                        'theirAge', 'primaryLanguage', 'secondaryLanguage',
                        'bestTime', 'specialNotes', 'yourPhone']
        
        if 'signup_data' not in tester:
            tester['signup_data'] = {}
        
        for field in signup_fields:
            if field in data:
                tester['signup_data'][field] = data[field]
        
        beta_manager._save_registry()
        
        print(f"✏️  Updated beta tester: {beta_id}")
        
        return jsonify({
            'success': True,
            'message': f'Updated {beta_id}',
            'beta_id': beta_id,
            'tester': tester
        })
    except Exception as e:
        print(f"❌ Error updating tester: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/beta/cleanup', methods=['POST'])
def cleanup_beta_testers():
    """
    Bulk cleanup: delete specified testers and update others
    
    Body example:
    {
        "delete": ["BT004", "BT007", "BT008"],
        "update": {
            "BT006": {
                "status": "active",
                "theirName": "Helen Lewis",
                "yourName": "Dawn Szczesiak",
                "yourEmail": "dawnszczesiak@gmail.com"
            }
        }
    }
    """
    try:
        data = request.json
        beta_manager._load_registry()
        
        results = {
            'deleted': [],
            'updated': [],
            'errors': []
        }
        
        for beta_id in data.get('delete', []):
            beta_id = beta_id.upper()
            if beta_id in beta_manager.registry['testers']:
                name = beta_manager.registry['testers'][beta_id].get('signup_data', {}).get('theirName', 'Unknown')
                del beta_manager.registry['testers'][beta_id]
                results['deleted'].append(f'{beta_id} ({name})')
                print(f"🗑️  Deleted: {beta_id} ({name})")
            else:
                results['errors'].append(f'{beta_id} not found')
        
        for beta_id, updates in data.get('update', {}).items():
            beta_id = beta_id.upper()
            if beta_id in beta_manager.registry['testers']:
                tester = beta_manager.registry['testers'][beta_id]
                
                if 'status' in updates:
                    tester['status'] = updates['status']
                
                if 'agent_id' in updates:
                    tester['agent_id'] = updates['agent_id']
                
                if 'signup_data' not in tester:
                    tester['signup_data'] = {}
                
                for key, value in updates.items():
                    if key not in ['status', 'agent_id']:
                        tester['signup_data'][key] = value
                
                results['updated'].append(beta_id)
                print(f"✏️  Updated: {beta_id}")
            else:
                results['errors'].append(f'{beta_id} not found for update')
        
        beta_manager._save_registry()
        
        print(f"✅ Cleanup complete: {len(results['deleted'])} deleted, {len(results['updated'])} updated")
        
        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        print(f"❌ Error in cleanup: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ============================================
# END ADMIN ENDPOINTS
# ============================================


@app.route('/api/beta/create-agent', methods=['POST'])
def create_agent_from_signup():
    """Create ElevenLabs agent when someone completes beta signup"""
    try:
        user_profile = request.json
        
        print(f"\n🎯 Creating agent for beta signup: {user_profile.get('theirName')}")
        
        if agent_manager is None:
            return jsonify({
                'success': False,
                'error': 'Automated agent creation not available.',
                'message': 'Create the agent manually and use /api/beta/link-agent to connect it.'
            }), 503
        
        agent_info = agent_manager.create_agent(user_profile)
        
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
    """Webhook called by ElevenLabs when a conversation ends"""
    try:
        payload = request.json
        data = payload.get('data', {})
        
        print(f"\n📞 Conversation ended webhook received")
        print(f"   Agent: {data.get('agent_id')}")
        print(f"   Conversation: {data.get('conversation_id')}")
        
        conversation_id = data.get('conversation_id')
        agent_id = data.get('agent_id')
        
        transcript_data = data.get('transcript', [])
        
        transcript = ""
        for turn in transcript_data:
            role = turn.get('role', 'unknown')
            message = turn.get('message', '')
            
            if role == 'agent':
                transcript += f"\nAila: {message}\n"
            elif role == 'user':
                transcript += f"\nUser: {message}\n"
        
        print(f"   📝 Transcript length: {len(transcript)} characters")
        
        agent_config_file = Path(f"agent_configs/{agent_id}.json")
        tester = beta_manager.get_tester_by_agent_id(agent_id)
        
        if tester:
            beta_id = tester['beta_id']
            user_name = tester['signup_data']['theirName']
            family_name = tester['signup_data']['yourName']
            family_email = tester['signup_data']['yourEmail']
            
            print(f"   👤 Beta Tester: {beta_id} - {user_name}")
            beta_manager.update_conversation_count(beta_id)
            
        elif agent_config_file.exists():
            with open(agent_config_file, 'r') as f:
                agent_config = json.load(f)
            user_profile = agent_config['user_profile']
            user_name = user_profile['theirName']
            family_name = user_profile['yourName']
            family_email = user_profile.get('yourEmail', 'test@example.com')
            beta_id = None
            print(f"   👤 Legacy User: {user_name}")
            
        else:
            print(f"   ℹ️  No config found - using defaults")
            user_name = "Margaret"
            family_name = "Family Member"
            family_email = "test@example.com"
            beta_id = None
        
        print(f"   👤 User: {user_name}")
        
        if beta_id:
            kb_file = beta_manager.get_tester_data_path(beta_id, "knowledge_base.md")
        else:
            kb_file = Path(f"knowledge_bases/{agent_id}.txt")
        
        kb_file.parent.mkdir(parents=True, exist_ok=True)
        
        existing_kb = ""
        if kb_file.exists():
            with open(kb_file, 'r', encoding='utf-8') as f:
                existing_kb = f.read()
        else:
            existing_kb = f"""# Conversation Memory for {user_name}

## Quick Reference
Last conversation: Never (this is first time)
Total conversations: 0

## Person Profile
- Name: {user_name}
"""
        
        analysis = conversation_analyzer.analyze_conversation(
            transcript=transcript,
            user_name=user_name,
            existing_knowledge_base=existing_kb
        )
        
        updated_kb = conversation_analyzer.update_knowledge_base(
            existing_kb=existing_kb,
            transcript=transcript,
            analysis=analysis,
            user_name=user_name
        )
        
        kb_file.parent.mkdir(exist_ok=True)
        with open(kb_file, 'w', encoding='utf-8') as f:
            f.write(updated_kb)
        
        print(f"   📝 Updating knowledge base for {user_name}...")
        print(f"   ✅ Knowledge base updated ({len(updated_kb)} chars)")
        
        compressed_kb, should_save = memory_manager.manage_knowledge_base(updated_kb, user_name)
        if should_save:
            with open(kb_file, 'w', encoding='utf-8') as f:
                f.write(compressed_kb)
            print(f"   🗜️  Knowledge base compressed and saved")
            updated_kb = compressed_kb
        
        if beta_id:
            conversation_data = {
                'conversation_id': conversation_id,
                'agent_id': agent_id,
                'timestamp': datetime.now().isoformat(),
                'transcript': transcript,
                'analysis': analysis,
                'user_name': user_name,
                'beta_id': beta_id
            }
            
            conv_folder = beta_manager.get_tester_data_path(beta_id, "conversations")
            conv_folder.mkdir(parents=True, exist_ok=True)
            
            conv_file = conv_folder / f"{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.json"
            with open(conv_file, 'w', encoding='utf-8') as f:
                json.dump(conversation_data, f, indent=2)
            
            print(f"   💾 Conversation saved: {conv_file.name}")
            
            transcript_folder = beta_manager.get_tester_data_path(beta_id, "transcripts")
            transcript_folder.mkdir(parents=True, exist_ok=True)
            
            transcript_file = transcript_folder / f"{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.txt"
            with open(transcript_file, 'w', encoding='utf-8') as f:
                f.write(transcript)
            
            print(f"   📄 Transcript saved: {transcript_file.name}")
        
        if agent_manager is not None:
            try:
                agent_manager.update_agent_after_conversation(agent_id, updated_kb)
            except Exception as e:
                print(f"   ⚠️  Could not upload to ElevenLabs: {e}")
        else:
            print(f"   ℹ️  ElevenLabs API not configured - knowledge base saved locally only")
        
        print(f"   📊 Generating family update...")
        family_update = conversation_analyzer.generate_family_update(
            analysis=analysis,
            user_name=user_name,
            family_name=family_name
        )
        
        print(f"   ✅ Family update generated - Alert level: {family_update.get('alert_level', 'N/A')}")
        
        if beta_id:
            update_file = beta_manager.get_tester_data_path(beta_id, "family_updates") / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        else:
            update_file = Path(f"family_updates/{agent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        
        update_file.parent.mkdir(parents=True, exist_ok=True)
        with open(update_file, 'w', encoding='utf-8') as f:
            json.dump(family_update, f, indent=2)
        
        if analysis['health'].get('red_flags'):
            print(f"🔴 RED FLAGS DETECTED:")
            for flag in analysis['health']['red_flags']:
                print(f"   - {flag}")
        
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
    """Main webhook endpoint for ElevenLabs"""
    try:
        data = request.json
        print(f"\n📨 Received webhook from ElevenLabs")
        print(f"Data: {json.dumps(data, indent=2)}")
        
        agent_id = data.get('agent_id')
        user_transcript = data.get('transcript') or data.get('user_message')
        conversation_id = data.get('conversation_id')
        
        if not user_transcript:
            return jsonify({'error': 'No transcript provided'}), 400
        
        session_key = agent_id or conversation_id
        
        if session_key not in sessions:
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
            
            aila_response = biographer.start_session()
            sessions[session_key]['conversation_count'] = 1
            
        else:
            session = sessions[session_key]
            biographer = session['biographer']
            
            print(f"💬 Continuing conversation for: {session['user_name']}")
            print(f"   User said: {user_transcript}")
            
            aila_response, is_complete = biographer.respond_to_user(user_transcript)
            
            session['conversation_count'] += 1
            session['last_interaction'] = datetime.now().isoformat()
            
            if is_complete:
                print(f"✅ Session complete! Generating chapter...")
                try:
                    session_id = biographer.data["sessions"][-1]["session_id"]
                    chapter_path = biographer.generate_chapter(session_id)
                    print(f"📄 Chapter generated: {chapter_path}")
                except Exception as e:
                    print(f"⚠️  Chapter generation failed: {e}")
        
        save_sessions()
        
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
    """Called when ElevenLabs conversation ends"""
    data = request.json
    agent_id = data.get('agent_id')
    conversation_id = data.get('conversation_id')
    
    session_key = agent_id or conversation_id
    
    print(f"📞 Conversation ended for session: {session_key}")
    
    return jsonify({'status': 'acknowledged'})


@app.route('/api/sessions', methods=['GET'])
def list_sessions():
    """Admin endpoint to view active sessions"""
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
    """Get details about a specific session"""
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
    """Test endpoint to simulate ElevenLabs webhook"""
    data = request.json
    user_name = data.get('user_name', 'Test User')
    message = data.get('message', 'Hello')
    
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


@app.route('/api/family-dashboard/<beta_id>', methods=['GET'])
def get_family_dashboard(beta_id):
    """Get comprehensive family dashboard for a beta tester"""
    try:
        beta_id = beta_id.upper()
        
        print(f"\n📊 Generating family dashboard for {beta_id}...")
        
        dashboard = dashboard_generator.generate_dashboard(beta_id)
        
        if not dashboard.get('success'):
            print(f"❌ Dashboard generation failed: {dashboard.get('error')}")
            return jsonify(dashboard), 404
        
        print(f"✅ Dashboard generated successfully")
        print(f"   Total conversations analyzed: {dashboard['summary']['total_conversations']}")
        print(f"   Health insights: {len(dashboard['health_insights'].get('active_concerns', []))} concerns")
        print(f"   Alerts: {len(dashboard['alerts'])} active alerts")
        
        return jsonify(dashboard)
    
    except Exception as e:
        print(f"❌ Error generating dashboard: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/biography/<beta_id>', methods=['GET'])
def get_full_biography(beta_id):
    """Get FULL biography built from complete conversation archive"""
    try:
        beta_id = beta_id.upper()
        
        print(f"\n📖 Generating full biography for {beta_id}...")
        
        biography = biography_builder.build_biography(beta_id)
        
        print(f"✅ Biography generated")
        print(f"   Total stories: {biography['total_stories']}")
        print(f"   Total people: {len(biography['people'])}")
        print(f"   Word count: {biography['word_count']}")
        print(f"   Data source: {biography['data_source']}")
        
        return jsonify({
            'success': True,
            'beta_id': beta_id,
            'biography': biography
        })
    
    except Exception as e:
        print(f"❌ Error generating biography: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/biography/<beta_id>/export', methods=['GET'])
def export_biography_document(beta_id):
    """Export full biography as a formatted document"""
    try:
        beta_id = beta_id.upper()
        format_type = request.args.get('format', 'markdown')
        
        print(f"\n📄 Exporting biography for {beta_id} as {format_type}...")
        
        document = biography_builder.export_biography_document(beta_id, format=format_type)
        
        if format_type == 'markdown':
            return document, 200, {'Content-Type': 'text/markdown; charset=utf-8'}
        elif format_type == 'json':
            return document, 200, {'Content-Type': 'application/json; charset=utf-8'}
        else:
            return jsonify({'success': False, 'error': f'Unsupported format: {format_type}'}), 400
    
    except Exception as e:
        print(f"❌ Error exporting biography: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/admin/reset-all-beta-data', methods=['POST'])
def reset_all_beta_data():
    """ADMIN ONLY: Reset all beta tester data"""
    try:
        data = request.json
        
        if not data or data.get('confirm') != 'RESET_ALL_DATA':
            return jsonify({
                'error': 'Confirmation required',
                'message': 'Send {"confirm": "RESET_ALL_DATA"} to confirm deletion',
                'warning': 'This will permanently delete all beta tester data!'
            }), 400
        
        print("\n⚠️  RESETTING ALL BETA DATA...")
        
        beta_dir = Path("beta_testers")
        
        if not beta_dir.exists():
            return jsonify({
                'success': True,
                'message': 'No beta data exists yet'
            })
        
        registry_file = beta_dir / "registry.json"
        tester_count = 0
        conversation_count = 0
        
        if registry_file.exists():
            with open(registry_file, 'r') as f:
                registry = json.load(f)
                tester_count = len(registry.get('testers', {}))
        
        for tester_dir in beta_dir.iterdir():
            if tester_dir.is_dir() and tester_dir.name.startswith('BT'):
                conv_dir = tester_dir / 'conversations'
                if conv_dir.exists():
                    conversation_count += len(list(conv_dir.glob('*.json')))
        
        import shutil
        for item in beta_dir.iterdir():
            if item.is_file():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        
        new_registry = {
            "next_id": 1,
            "testers": {}
        }
        
        with open(registry_file, 'w') as f:
            json.dump(new_registry, f, indent=2)
        
        global beta_manager
        beta_manager = BetaTesterManager()
        
        print(f"   ✅ Deleted {tester_count} beta testers")
        print(f"   ✅ Deleted {conversation_count} conversations")
        print(f"   ✅ Reset complete - ready for fresh start")
        
        return jsonify({
            'success': True,
            'message': 'All beta data has been reset',
            'deleted': {
                'beta_testers': tester_count,
                'conversations': conversation_count
            },
            'status': 'System ready for fresh beta testing'
        })
    
    except Exception as e:
        print(f"❌ Error resetting data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("  TelAila Companion AI Server - Beta Testing System")
    print("  Providing companionship & reducing loneliness")
    print("=" * 70)
    print("\n✅ Server starting...")
    print(f"\n📋 BETA TESTER ENDPOINTS:")
    print(f"   Register: POST /api/beta/register")
    print(f"   Link agent: POST /api/beta/link-agent")
    print(f"   View all: GET /api/beta/testers")
    print(f"   Get one: GET /api/beta/tester/<beta_id>")
    print(f"   Update: PUT /api/beta/tester/<beta_id>")
    print(f"   Delete: DELETE /api/beta/tester/<beta_id>")
    print(f"   Cleanup: POST /api/beta/cleanup")
    print(f"\n👨‍👩‍👧 FAMILY DASHBOARD:")
    print(f"   Dashboard: GET /api/family-dashboard/<beta_id>")
    print("\n🤝 Ready for beta testing!\n")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
