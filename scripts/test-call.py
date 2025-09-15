#!/usr/bin/env python3

"""
Test Call Script
Makes a test call to verify the voice agent is working
"""

import os
import sys
import json
import time
from typing import Optional
import requests
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException

# Load environment variables
from dotenv import load_dotenv
load_dotenv('config/.env')


def make_test_call(to_number: str, test_scenario: Optional[str] = None) -> bool:
    """
    Make a test call to the voice agent
    
    Args:
        to_number: Phone number to call
        test_scenario: Optional test scenario to run
        
    Returns:
        True if call was successful
    """
    # Initialize Twilio client
    account_sid = os.getenv('TWILIO_ACCOUNT_SID')
    auth_token = os.getenv('TWILIO_AUTH_TOKEN')
    from_number = os.getenv('TWILIO_PHONE_NUMBER')
    
    if not all([account_sid, auth_token, from_number]):
        print("❌ Error: Twilio credentials not configured")
        print("Please check your config/.env file")
        return False
    
    try:
        client = Client(account_sid, auth_token)
        
        # Prepare TwiML for the test call
        twiml = generate_test_twiml(test_scenario)
        
        # Make the call
        print(f"📞 Calling {to_number} from {from_number}...")
        
        call = client.calls.create(
            to=to_number,
            from_=from_number,
            twiml=twiml,
            record=False,  # Don't record test calls
            status_callback=f"{os.getenv('TWILIO_STATUS_CALLBACK_URL', '')}"
        )
        
        print(f"✓ Call initiated with SID: {call.sid}")
        print(f"  Status: {call.status}")
        
        # Wait and check call status
        time.sleep(5)
        call = client.calls(call.sid).fetch()
        print(f"  Current status: {call.status}")
        
        if call.status in ['completed', 'in-progress', 'ringing', 'queued']:
            print("✅ Test call successful!")
            
            # Display call details
            print("\nCall Details:")
            print(f"  Duration: {call.duration or 'In progress'} seconds")
            print(f"  Direction: {call.direction}")
            print(f"  Price: {call.price or 'Pending'}")
            
            return True
        else:
            print(f"⚠️ Call status: {call.status}")
            return False
            
    except TwilioRestException as e:
        print(f"❌ Twilio error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error making test call: {e}")
        return False


def generate_test_twiml(scenario: Optional[str] = None) -> str:
    """
    Generate TwiML for test scenarios
    
    Args:
        scenario: Test scenario type
        
    Returns:
        TwiML string
    """
    base_url = os.getenv('TWILIO_VOICE_URL', 'https://your-domain.com/webhooks/twilio/voice')
    
    if scenario == "appointment":
        # Test appointment booking flow
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>This is a test call for appointment booking. You will now be connected to the automated assistant.</Say>
    <Pause length="2"/>
    <Say>Please say: I would like to schedule an appointment for next Monday.</Say>
    <Redirect>{base_url}</Redirect>
</Response>"""
    
    elif scenario == "results":
        # Test lab results inquiry
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>This is a test call for lab results inquiry. You will now be connected to the automated assistant.</Say>
    <Pause length="2"/>
    <Say>Please say: I would like to check my lab results.</Say>
    <Redirect>{base_url}</Redirect>
</Response>"""
    
    elif scenario == "refill":
        # Test prescription refill
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>This is a test call for prescription refill. You will now be connected to the automated assistant.</Say>
    <Pause length="2"/>
    <Say>Please say: I need to refill my blood pressure medication.</Say>
    <Redirect>{base_url}</Redirect>
</Response>"""
    
    elif scenario == "emergency":
        # Test emergency handling
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>This is a test call for emergency handling. The system should direct you to call 911.</Say>
    <Pause length="2"/>
    <Say>Please say: This is an emergency, I need immediate help.</Say>
    <Redirect>{base_url}</Redirect>
</Response>"""
    
    else:
        # Default test call
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>This is a test call for the HIPAA voice agent. You will now be connected to the automated assistant.</Say>
    <Redirect>{base_url}</Redirect>
</Response>"""


def check_system_health() -> bool:
    """
    Check if the system is healthy before making test call
    
    Returns:
        True if system is healthy
    """
    health_url = "http://localhost:8081/health"
    
    try:
        print("🔍 Checking system health...")
        response = requests.get(health_url, timeout=5)
        
        if response.status_code == 200:
            health_data = response.json()
            print(f"✓ System status: {health_data.get('status', 'unknown')}")
            
            if health_data.get('compliance_check'):
                print("✓ Compliance check: Passed")
            else:
                print("⚠️ Compliance check: Failed")
                
            return health_data.get('status') == 'healthy'
        else:
            print(f"⚠️ Health check returned status {response.status_code}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to health endpoint. Is the system running?")
        print("Run 'make deploy' to start the system")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False


def list_test_scenarios():
    """Display available test scenarios"""
    print("\nAvailable Test Scenarios:")
    print("========================")
    print("1. default     - Basic connectivity test")
    print("2. appointment - Test appointment booking flow")
    print("3. results     - Test lab results inquiry")
    print("4. refill      - Test prescription refill")
    print("5. emergency   - Test emergency handling")
    print("\nUsage: python scripts/test-call.py [phone_number] [scenario]")
    print("Example: python scripts/test-call.py +15025551234 appointment")


def main():
    """Main function"""
    # Parse arguments
    if len(sys.argv) < 2:
        print("❌ Error: Phone number required")
        print("Usage: python scripts/test-call.py [phone_number] [scenario]")
        list_test_scenarios()
        sys.exit(1)
    
    phone_number = sys.argv[1]
    scenario = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Validate phone number format
    if not phone_number.startswith('+'):
        print("⚠️ Warning: Phone number should start with '+' and country code")
        print("Example: +15025551234")
        
        # Try to fix common formats
        if phone_number.startswith('1') and len(phone_number) == 11:
            phone_number = f"+{phone_number}"
        elif len(phone_number) == 10:
            phone_number = f"+1{phone_number}"
        else:
            print("❌ Invalid phone number format")
            sys.exit(1)
        
        print(f"Using: {phone_number}")
    
    print("="*50)
    print("HIPAA Voice Agent - Test Call")
    print("="*50)
    
    # Check system health first
    if not check_system_health():
        print("\n⚠️ System health check failed")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            print("Test cancelled")
            sys.exit(1)
    
    # Display test info
    print(f"\nTest Configuration:")
    print(f"  To: {phone_number}")
    print(f"  From: {os.getenv('TWILIO_PHONE_NUMBER', 'Not configured')}")
    print(f"  Scenario: {scenario or 'default'}")
    print()
    
    # Make the test call
    success = make_test_call(phone_number, scenario)
    
    if success:
        print("\n✅ Test call completed successfully!")
        print("\nNext steps:")
        print("1. Answer the phone when it rings")
        print("2. Follow the voice prompts")
        print("3. Test the requested scenario")
        print("4. Check logs: make logs-pipecat")
    else:
        print("\n❌ Test call failed")
        print("\nTroubleshooting:")
        print("1. Check Twilio credentials in config/.env")
        print("2. Verify phone number is correct")
        print("3. Check system logs: make logs")
        print("4. Run compliance check: make audit")
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
