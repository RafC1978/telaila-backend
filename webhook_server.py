"""
TelAila Production Webhook Server
Standardized for Google Cloud Run, Firestore, and Vertex AI.
"""

import os
import json
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
from google.cloud import firestore

# Production Managers (Refactored for GCP)
from beta_tester_manager import BetaTesterManager
from conversation_analyzer import ConversationAnalyzer
from elevenlabs_agent_manager import ElevenLabsAgentManager

app = Flask(__name__)
CORS(app)

# Initialize Production Clients
db = firestore.Client()
beta_manager = BetaTesterManager()
analyzer = ConversationAnalyzer()
agent_manager = ElevenLabsAgentManager()

# ============================================
# CORE PRODUCT ENDPOINTS
# ============================================

@app.route('/')
def health_check():
    """Confirms the server is live in Montreal."""
    return jsonify({
        'status': 'online',
        'service': 'TelAila Production Backend',
        'region': 'northamerica-northeast1',
        'timestamp': datetime.now().isoformat()
    }), 200

@app.route('/api/beta/register', methods=['POST'])
def register():
    """Lovable signup -> Firestore + ElevenLabs Agent Creation."""
    try:
        signup_data = request.json
        print(f"🎯 New Registration: {signup_data.get('theirName')}")

        # 1. Register in Firestore Vault
        reg_result = beta_manager.register_beta_tester(signup_data)
        beta_id = reg_result['beta_id']

        # 2. FETCH THE FULL RECORD (This fixes the 'signup_data' error)
        # We need the full data to personalize the AI
        tester_record = db.collection("testers").document(beta_id).get().to_dict()

        # 3. Automated Agent Creation
        if agent_manager and tester_record:
            agent_id = agent_manager.create_personalized_agent(tester_record)
            if agent_id:
                beta_manager.link_agent(beta_id, agent_id)

        return jsonify(reg_result), 200
    except Exception as e:
        print(f"❌ Registration failed: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/elevenlabs/conversation-ended', methods=['POST'])
def on_conversation_ended():
    """
    The 'Moment of Truth'. ElevenLabs calls this when Mike hangs up.
    This triggers the Brain (Vertex AI) to build the bio and health report.
    """
    try:
        payload = request.json
        # ElevenLabs sends transcript data in the 'data' block
        data = payload.get('data', {})
        agent_id = data.get('agent_id')
        transcript_turns = data.get('transcript', [])

        # Format the raw transcript turns into a readable block
        transcript_text = ""
        for turn in transcript_turns:
            role = "Aila" if turn.get('role') == 'agent' else "User"
            transcript_text += f"{role}: {turn.get('message')}\n"

        print(f"📞 Call ended for Agent: {agent_id}. Processing Bio & Health...")

        # 1. Identify the Tester
        tester = beta_manager.get_tester_by_agent_id(agent_id)
        if not tester:
            return jsonify({'error': 'Agent not linked to a tester'}), 404

        # 2. Trigger the Brain (Vertex AI)
        # This updates health_logs, biography snippets, and dashboard automatically
        analysis = analyzer.analyze_and_save(
            beta_id=tester['beta_id'],
            transcript=transcript_text,
            elder_name=tester['signup_data']['theirName']
        )

        return jsonify({'success': True, 'analysis_complete': True}), 200

    except Exception as e:
        print(f"❌ Webhook processing error: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================
# DASHBOARD ENDPOINTS (FOR LOVABLE FRONTEND)
# ============================================

@app.route('/api/family-dashboard/<beta_id>', methods=['GET'])
def get_dashboard(beta_id):
    """Fetches real-time insights from the Firestore Vault."""
    try:
        # Get the main tester record
        doc = db.collection("testers").document(beta_id.upper()).get()
        if not doc.exists:
            return jsonify({'error': 'Tester not found'}), 404
        
        tester_data = doc.to_dict()

        # Fetch recent health logs
        health_query = db.collection("testers").document(beta_id).collection("health_logs")\
                         .order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream()
        
        health_history = [log.to_dict() for log in health_query]

        return jsonify({
            'success': True,
            'elder_name': tester_data['signup_data']['theirName'],
            'current_status': tester_data.get('current_health_status', 'No calls yet'),
            'health_history': health_history,
            'conversation_count': tester_data.get('conversation_count', 0)
        }), 200

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    # Cloud Run provides the PORT environment variable
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
