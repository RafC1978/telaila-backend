"""
TelAila Beta Tester Management (Production Version)
Handles persistent registration and data organization using Google Firestore.
"""

import secrets
from datetime import datetime
from google.cloud import firestore

class BetaTesterManager:
    """
    Manages beta testers using a Google Firestore backend for high availability.
    """
    
    def __init__(self):
        # Automatically connects to the (default) database in your project
        self.db = firestore.Client()
        self.collection = "testers"
    
    def register_beta_tester(self, signup_data):
        """
        Register a new beta tester from Lovable signup form into Firestore.
        """
        try:
            # Generate a professional, unique ID (e.g., BT-A1B2C3D4)
            # We use a random hex to ensure no collisions even with millions of users
            beta_id = f"BT-{secrets.token_hex(4).upper()}"
            access_token = secrets.token_urlsafe(32)
            
            tester_record = {
                "beta_id": beta_id,
                "status": "active",  # Changed to active for immediate use
                "signup_data": signup_data,
                "access_token": access_token,
                "registered_at": datetime.now().isoformat(),
                "agent_id": None,
                "conversation_count": 0,
                "last_conversation": None,
                "setup_instructions_sent": False
            }
            
            # Save the record to the Firestore collection
            self.db.collection(self.collection).document(beta_id).set(tester_record)
            
            print(f"✅ Registered beta tester in Firestore: {beta_id} - {signup_data.get('theirName')}")
            
            return {
                "success": True,
                "beta_id": beta_id,
                "tester_name": signup_data.get('theirName'),
                "family_name": signup_data.get('yourName'),
                "status": "active",
                "message": "Registration successful! Data is now persistent in Google Cloud.",
                "access_token": access_token
            }
        except Exception as e:
            print(f"❌ Error in register_beta_tester: {e}")
            return {"success": False, "error": str(e)}

    def link_agent(self, beta_id, agent_id):
        """
        Links an ElevenLabs agent ID to the tester document.
        """
        try:
            doc_ref = self.db.collection(self.collection).document(beta_id)
            doc_ref.update({
                "agent_id": agent_id,
                "activated_at": datetime.now().isoformat()
            })
            print(f"✅ Linked agent {agent_id} to {beta_id}")
            return {"success": True, "beta_id": beta_id, "agent_id": agent_id}
        except Exception as e:
            print(f"❌ Error linking agent: {e}")
            return {"success": False, "error": str(e)}

    def get_tester_by_agent_id(self, agent_id):
        """
        Queries Firestore for a tester linked to a specific ElevenLabs agent.
        """
        query = self.db.collection(self.collection).where("agent_id", "==", agent_id).stream()
        for doc in query:
            return doc.to_dict()
        return None

    def get_all_testers(self):
        """
        Retrieves all registered testers from the vault.
        """
        docs = self.db.collection(self.collection).stream()
        return {doc.id: doc.to_dict() for doc in docs}

    def update_conversation_count(self, beta_id):
        """
        Increments the conversation counter in the cloud record.
        """
        doc_ref = self.db.collection(self.collection).document(beta_id)
        doc_ref.update({
            "conversation_count": firestore.Increment(1),
            "last_conversation": datetime.now().isoformat()
        })

    def generate_setup_email(self, beta_id):
        """
        Generates the email template content for the family.
        """
        doc = self.db.collection(self.collection).document(beta_id).get()
        if not doc.exists:
            return None
        
        tester = doc.to_dict()
        signup = tester['signup_data']
        
        return {
            "to": signup['yourEmail'],
            "subject": f"TelAila Beta - {signup['theirName']}'s Companion is Ready!",
            "body": f"Hello {signup['yourName']}, your dashboard is here: [URL]?token={tester['access_token']}"
        }
