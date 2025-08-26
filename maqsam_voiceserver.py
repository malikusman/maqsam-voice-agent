#!/usr/bin/env python3
"""
Maqsam Voice Agent Integration - Python WebSocket Server
Simple implementation for handling voice agent calls through Maqsam
"""

import asyncio
import websockets
import json
import base64
import logging
from typing import Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MaqsamVoiceAgent:
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self.websocket = None
        self.call_context = None
        
    async def authenticate_connection(self, websocket, path):
        """
        Handle authentication - checking for Auth header in request
        Question for Maqsam: Where exactly do we configure our WebSocket URL in the Maqsam portal?
        """
        # Check for authentication header (Method 1: HTTP Auth Header)
        auth_header = websocket.request_headers.get('Auth')
        if auth_header != self.auth_token:
            logger.warning("Authentication failed - invalid or missing Auth header")
            await websocket.close(code=1008, reason="Unauthorized")
            return False
        
        logger.info("Authentication successful via HTTP Auth Header")
        return True
    
    async def handle_session_setup(self, message_data):
        """
        Handle session setup message with call context and optional token auth
        Question for Maqsam: Can you generate a unique token for us, or should we provide our own?
        """
        # Method 2: Token over WebSocket (alternative authentication)
        api_key = message_data.get('apiKey')
        if api_key and api_key != self.auth_token:
            logger.warning("WebSocket token authentication failed")
            return False
            
        # Extract call context
        self.call_context = message_data.get('data', {}).get('context', {})
        
        logger.info(f"Session setup complete. Call ID: {self.call_context.get('id')}")
        logger.info(f"Call direction: {self.call_context.get('direction')}")
        logger.info(f"Caller: {self.call_context.get('caller')} ({self.call_context.get('caller_number')})")
        logger.info(f"Custom context: {self.call_context.get('custom', {})}")
        
        return True
    
    async def send_session_ready(self):
        """Send session ready confirmation to Maqsam"""
        ready_message = {"type": "session.ready"}
        await self.websocket.send(json.dumps(ready_message))
        logger.info("Sent session.ready confirmation")
    
    async def handle_audio_input(self, message_data):
        """
        Process incoming audio from customer
        Audio format: Base64 encoded mulaw, 8000 sample rate
        """
        audio_data = message_data.get('data', {}).get('audio', '')
        
        # TODO: Process customer audio here
        # - Decode base64 audio
        # - Convert from mulaw format
        # - Send to your AI voice processing service
        logger.info(f"Received audio input: {len(audio_data)} bytes (base64)")
        
        # Example: Detect if customer is speaking
        # if self.is_customer_speaking(audio_data):
        #     await self.send_speech_started()
        
        # Generate AI response (placeholder)
        await self.generate_ai_response()
    
    async def send_audio_response(self, audio_base64: str):
        """Send AI voice response back to customer"""
        response_message = {
            "type": "response.stream",
            "data": {"audio": audio_base64}
        }
        await self.websocket.send(json.dumps(response_message))
        logger.info(f"Sent audio response: {len(audio_base64)} bytes (base64)")
    
    async def send_speech_started(self):
        """Notify Maqsam that customer started speaking (interruption handling)"""
        speech_message = {"type": "speech.started"}
        await self.websocket.send(json.dumps(speech_message))
        logger.info("Sent speech.started (customer interruption)")
    
    async def send_call_redirect(self):
        """Redirect call to human agent"""
        redirect_message = {"type": "call.redirect"}
        await self.websocket.send(json.dumps(redirect_message))
        logger.info("Redirecting call to human agent")
    
    async def send_call_hangup(self):
        """End the call gracefully"""
        hangup_message = {"type": "call.hangup"}
        await self.websocket.send(json.dumps(hangup_message))
        logger.info("Ending call")
    
    async def generate_ai_response(self):
        """
        Placeholder for AI response generation
        TODO: Integrate with your AI voice generation service
        """
        # This is where you would:
        # 1. Process the customer's speech/text
        # 2. Generate appropriate AI response
        # 3. Convert text to speech
        # 4. Encode as base64 mulaw format
        # 5. Send via send_audio_response()
        
        # For now, just log that we need to generate response
        logger.info("TODO: Generate AI response based on customer input")
        
        # Example of sending a response (you need actual audio data):
        # sample_audio_base64 = "your_base64_encoded_mulaw_audio_here"
        # await self.send_audio_response(sample_audio_base64)
    
    async def handle_connection(self, websocket, path):
        """Main WebSocket connection handler"""
        self.websocket = websocket
        
        # Authenticate the connection
        if not await self.authenticate_connection(websocket, path):
            return
        
        try:
            # Send session ready immediately after authentication
            await self.send_session_ready()
            
            # Listen for messages
            async for message in websocket:
                try:
                    data = json.loads(message)
                    message_type = data.get('type')
                    
                    if message_type == 'session.setup':
                        if await self.handle_session_setup(data):
                            logger.info("Session setup completed successfully")
                        else:
                            await websocket.close(code=1002)
                            return
                    
                    elif message_type == 'audio.input':
                        await self.handle_audio_input(data)
                    
                    else:
                        logger.warning(f"Unknown message type: {message_type}")
                
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON message")
                    await websocket.close(code=1002)
                    return
        
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in WebSocket handler: {e}")
        finally:
            self.websocket = None
            self.call_context = None

def main():
    """
    Start the WebSocket server
    Question for Maqsam: What should be our server URL format? 
    Examples from docs: wss://voice.service.ai/client_name?agent=ar
    """
    
    # Using API key from Maqsam portal as auth token (as confirmed by Maqsam)
    AUTH_TOKEN = "2BUrGJJPmN7WvNzEtDmD"  # Your API key from portal
    
    # Create voice agent instance
    voice_agent = MaqsamVoiceAgent(AUTH_TOKEN)
    
    # Server configuration - using different port than your website
    HOST = "0.0.0.0"  # Listen on all interfaces
    PORT = 8080       # Different port from your website (80/443)
    
    # Start WebSocket server (no SSL needed - Cloudflare handles it)
    logger.info(f"Starting Maqsam Voice Agent WebSocket server on {HOST}:{PORT}")
    logger.info("Using Cloudflare SSL termination")
    logger.info("Waiting for connections from Maqsam...")
    
    start_server = websockets.serve(voice_agent.handle_connection, HOST, PORT)
    
    # No SSL context needed when using Cloudflare proxy
    
    # Run the server
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    """
    Installation requirements:
    pip install websockets
    
    Questions for Maqsam team:
    1. Where in the Maqsam portal do we configure our WebSocket URL?
    2. Can you generate a unique authentication token for us?
    3. Should we use the API key from portal as the auth token?
    4. What should our WebSocket URL format be? (wss://our-domain.com/path?)
    5. Any specific requirements for server hosting/SSL certificates?
    """
    main()