"""
Beta Tester Management System
Handles registration, agent linking, and data organization for TelAila beta testers
"""

import json
from pathlib import Path
from datetime import datetime
import secrets

class BetaTesterManager:
    """
    Manages beta testers - registration, agent linking, data organization
    """
    
    def __init__(self):
        self.data_dir = Path("beta_testers")
        self.data_dir.mkdir(exist_ok=True)
        
        self.registry_file = self.data_dir / "registry.json"
        self.registry = self._load_registry()
    
    def _load_registry(self):
        """Load beta tester registry"""
        if self.registry_file.exists():
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {
            "testers": {},
            "next_id": 1
        }
    
    def _save_registry(self):
        """Save beta tester registry"""
        with open(self.registry_file, 'w', encoding='utf-8') as f:
            json.dump(self.registry, f, indent=2)
    
    def register_beta_tester(self, signup_data):
        """
        Register a new beta tester from Lovable signup form
        
        Args:
            signup_data: Dict from Lovable form
                {
                    'theirName': 'Margaret Thompson',
                    'yourName': 'Susan',
                    'yourEmail': 'susan@example.com',
                    'relationship': 'daughter',
                    'theirAge': '82',
                    'primaryLanguage': 'English',
                    'specialNotes': '...'
                }
        
        Returns:
            Dict with beta_id and instructions
        """
        
        # Generate beta tester ID
        beta_id = f"BT{self.registry['next_id']:03d}"
        self.registry['next_id'] += 1
        
        # Generate access token for family dashboard
        access_token = secrets.token_urlsafe(32)
        
        # Create tester record
        tester_record = {
            "beta_id": beta_id,
            "status": "pending_setup",  # pending_setup, active, completed
            "signup_data": signup_data,
            "access_token": access_token,
            "registered_at": datetime.now().isoformat(),
            "agent_id": None,  # Will be linked manually
            "conversation_count": 0,
            "last_conversation": None,
            "setup_instructions_sent": False
        }
        
        self.registry['testers'][beta_id] = tester_record
        self._save_registry()
        
        # Create tester folder structure
        self._create_tester_folders(beta_id)
        
        print(f"✅ Registered beta tester: {beta_id} - {signup_data['theirName']}")
        
        return {
            "success": True,
            "beta_id": beta_id,
            "tester_name": signup_data['theirName'],
            "family_name": signup_data['yourName'],
            "status": "pending_setup",
            "message": "Registration successful! We'll set up your companion and send you access details within 24 hours.",
            "access_token": access_token  # For future family dashboard access
        }
    
    def _create_tester_folders(self, beta_id):
        """Create folder structure for beta tester"""
        tester_dir = self.data_dir / beta_id
        tester_dir.mkdir(exist_ok=True)
        
        # Create subfolders
        (tester_dir / "conversations").mkdir(exist_ok=True)
        (tester_dir / "family_updates").mkdir(exist_ok=True)
        (tester_dir / "health_data").mkdir(exist_ok=True)
        
        # Create info file
        info_file = tester_dir / "info.json"
        if not info_file.exists():
            with open(info_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "beta_id": beta_id,
                    "created_at": datetime.now().isoformat(),
                    "folders": {
                        "conversations": "Full conversation transcripts",
                        "family_updates": "Weekly/daily family summaries",
                        "health_data": "Cumulative health tracking"
                    }
                }, f, indent=2)
    
    def link_agent(self, beta_id, agent_id):
        """
        Link an ElevenLabs agent to a beta tester
        
        Args:
            beta_id: Beta tester ID (e.g., "BT001")
            agent_id: ElevenLabs agent ID
        
        Returns:
            Success status
        """
        if beta_id not in self.registry['testers']:
            return {"success": False, "error": "Beta tester not found"}
        
        tester = self.registry['testers'][beta_id]
        tester['agent_id'] = agent_id
        tester['status'] = "active"
        tester['activated_at'] = datetime.now().isoformat()
        
        self._save_registry()
        
        print(f"✅ Linked agent {agent_id} to {beta_id}")
        
        return {
            "success": True,
            "beta_id": beta_id,
            "agent_id": agent_id,
            "status": "active"
        }
    
    def get_tester_by_agent_id(self, agent_id):
        """Get beta tester info by agent ID"""
        for beta_id, tester in self.registry['testers'].items():
            if tester.get('agent_id') == agent_id:
                return tester
        return None
    
    def get_tester_by_email(self, email):
        """Get beta tester info by family email"""
        for beta_id, tester in self.registry['testers'].items():
            if tester['signup_data'].get('yourEmail') == email:
                return tester
        return None
    
    def get_all_testers(self):
        """Get all beta testers (for admin dashboard)"""
        return self.registry['testers']
    
    def get_tester_data_path(self, beta_id, data_type):
        """
        Get path for specific tester data
        
        Args:
            beta_id: Beta tester ID
            data_type: 'conversations', 'family_updates', 'health_data'
        """
        return self.data_dir / beta_id / data_type
    
    def update_conversation_count(self, beta_id):
        """Increment conversation count for tester"""
        if beta_id in self.registry['testers']:
            self.registry['testers'][beta_id]['conversation_count'] += 1
            self.registry['testers'][beta_id]['last_conversation'] = datetime.now().isoformat()
            self._save_registry()
    
    def generate_setup_email(self, beta_id):
        """
        Generate setup instructions email for family
        
        Returns:
            Dict with email content
        """
        tester = self.registry['testers'].get(beta_id)
        if not tester:
            return None
        
        signup = tester['signup_data']
        
        email_content = {
            "to": signup['yourEmail'],
            "subject": f"TelAila Beta - {signup['theirName']}'s Companion is Ready!",
            "body": f"""
Hello {signup['yourName']},

Thank you for signing up for the TelAila beta program!

We've set up a personal AI companion for {signup['theirName']}. Here's what you need to know:

**Beta Tester ID:** {beta_id}

**How It Works:**
1. {signup['theirName']} will receive regular calls from Aila, their AI companion
2. Aila will have natural conversations, check in on wellbeing, and preserve memories
3. You'll receive weekly summaries with health insights and notable moments

**Your Family Dashboard:**
Access your dashboard here: [URL]/family-dashboard?token={tester['access_token']}

This dashboard shows:
- Recent conversation summaries
- Health tracking and trends
- Notable stories and memories shared
- Recommendations for family

**Next Steps:**
- We'll schedule the first conversation with {signup['theirName']}
- You'll receive your first family update after the first conversation
- You can access the dashboard anytime

**Questions?**
Reply to this email or contact us at support@telaila.com

Thank you for being part of our beta program!

The TelAila Team
            """
        }
        
        return email_content


if __name__ == "__main__":
    # Test the system
    manager = BetaTesterManager()
    
    # Test registration
    test_signup = {
        'theirName': 'Margaret Thompson',
        'yourName': 'Susan',
        'yourEmail': 'susan@example.com',
        'relationship': 'daughter',
        'theirAge': '82',
        'primaryLanguage': 'English',
        'specialNotes': 'Loves roses, widowed 5 years ago'
    }
    
    result = manager.register_beta_tester(test_signup)
    print(f"\nRegistration result: {result}")
    
    # Test agent linking
    link_result = manager.link_agent(result['beta_id'], "agent_test123")
    print(f"\nLink result: {link_result}")
    
    # Test retrieval
    tester = manager.get_tester_by_agent_id("agent_test123")
    print(f"\nRetrieved tester: {tester['beta_id']}")
