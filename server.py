#!/usr/bin/env python3
"""
Maqsam Voice Agent Integration - Python WebSocket Server
Improved implementation with better error handling and connection management
"""

import asyncio
import websockets
import json
import base64
import logging
from typing import Optional
import traceback
from websockets.exceptions import InvalidUpgrade, ConnectionClosed

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MaqsamVoiceAgent:
    def __init__(self, auth_token: str):
        self.auth_token = auth_token
        self.websocket = None
        self.call_context = None
        self.heartbeat_task = None
        
    async def authenticate_connection(self, websocket, path):
        """
        Handle authentication - checking for Auth header in request
        """
        try:
            auth_header = websocket.request.headers.get('Auth') or websocket.request.headers.get('Authorization')
            if auth_header != self.auth_token:
                logger.warning(f"Authentication failed - invalid or missing Auth header. Received: {auth_header}")
                await websocket.close(code=1008, reason="Unauthorized")
                return False
            logger.info("Authentication successful via HTTP Auth Header")
            return True
        except Exception as e:
            logger.error(f"Error during authentication: {e}")
            return False
    
    async def handle_session_setup(self, message_data):
        """
        Handle session setup message with call context and optional token auth
        """
        try:
            api_key = message_data.get('apiKey')
            if api_key and api_key != self.auth_token:
                logger.warning("WebSocket token authentication failed")
                return False
            self.call_context = message_data.get('data', {}).get('context', {})
            logger.info(f"Session setup complete. Call ID: {self.call_context.get('id')}")
            logger.info(f"Call direction: {self.call_context.get('direction')}")
            logger.info(f"Caller: {self.call_context.get('caller')} ({self.call_context.get('caller_number')})")
            logger.info(f"Custom context: {self.call_context.get('custom', {})}")
            return True
        except Exception as e:
            logger.error(f"Error in session setup: {e}")
            return False
    
    async def send_session_ready(self):
        """Send session ready confirmation to Maqsam"""
        try:
            ready_message = {"type": "session.ready"}
            await self.websocket.send(json.dumps(ready_message))
            logger.info("Sent session.ready confirmation")
        except Exception as e:
            logger.error(f"Error sending session.ready: {e}")
            raise
    
    async def handle_audio_input(self, message_data):
        """
        Process incoming audio from customer
        Audio format: Base64 encoded mulaw, 8000 sample rate
        """
        try:
            audio_data = message_data.get('data', {}).get('audio', '')
            logger.info(f"Received audio input: {len(audio_data)} bytes (base64)")
            await self.generate_ai_response()
        except Exception as e:
            logger.error(f"Error handling audio input: {e}")
    
    async def send_audio_response(self, audio_base64: str):
        """Send AI voice response back to customer"""
        try:
            response_message = {"type": "response.stream", "data": {"audio": audio_base64}}
            await self.websocket.send(json.dumps(response_message))
            logger.info(f"Sent audio response: {len(audio_base64)} bytes (base64)")
        except Exception as e:
            logger.error(f"Error sending audio response: {e}")
    
    async def send_speech_started(self):
        """Notify Maqsam that customer started speaking (interruption handling)"""
        try:
            speech_message = {"type": "speech.started"}
            await self.websocket.send(json.dumps(speech_message))
            logger.info("Sent speech.started (customer interruption)")
        except Exception as e:
            logger.error(f"Error sending speech.started: {e}")
    
    async def send_call_redirect(self):
        """Redirect call to human agent"""
        try:
            redirect_message = {"type": "call.redirect"}
            await self.websocket.send(json.dumps(redirect_message))
            logger.info("Redirecting call to human agent")
        except Exception as e:
            logger.error(f"Error redirecting call: {e}")
    
    async def send_call_hangup(self):
        """End the call gracefully"""
        try:
            hangup_message = {"type": "call.hangup"}
            await self.websocket.send(json.dumps(hangup_message))
            logger.info("Ending call")
        except Exception as e:
            logger.error(f"Error hanging up call: {e}")
    
    async def generate_ai_response(self):
        """Placeholder for AI response generation"""
        logger.info("TODO: Generate AI response based on customer input")
    
    async def start_heartbeat(self):
        """Start heartbeat to keep connection alive"""
        self.heartbeat_task = asyncio.create_task(self.heartbeat_loop())
    
    async def heartbeat_loop(self):
        """Send periodic ping to keep connection alive"""
        try:
            while True:
                await asyncio.sleep(30)  # Send heartbeat every 30 seconds
                if self.websocket and not self.websocket.closed:
                    try:
                        await self.websocket.ping()
                        logger.debug("Sent heartbeat ping")
                    except Exception as e:
                        logger.warning(f"Heartbeat failed: {e}")
                        break
                else:
                    break
        except asyncio.CancelledError:
            logger.debug("Heartbeat task cancelled")
        except Exception as e:
            logger.error(f"Error in heartbeat loop: {e}")
    
    async def stop_heartbeat(self):
        """Stop heartbeat task"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass
            self.heartbeat_task = None
    
    async def handle_connection(self, websocket, path=None):
        """Main WebSocket connection handler"""
        self.websocket = websocket
        client_info = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}" if websocket.remote_address else "unknown"
        logger.info(f"New connection from {client_info}")
        
        if not await self.authenticate_connection(websocket, path):
            return
        
        try:
            # Start heartbeat to keep connection alive
            await self.start_heartbeat()
            # DON'T send session.ready immediately - wait for session.setup first
            logger.info("Waiting for session.setup message from Maqsam...")
            
            async for message in websocket:
                logger.debug(f"Received raw message: {message}")
                if not message:  # Handle empty messages
                    logger.debug("Received empty message, continuing to wait")
                    continue
                
                try:
                    data = json.loads(message)
                    message_type = data.get('type')
                    logger.info(f"Processing message type: {message_type}")
                    
                    if message_type == 'session.setup':
                        if await self.handle_session_setup(data):
                            logger.info("Session setup completed successfully")
                            # Send session.ready AFTER successful session setup
                            await self.send_session_ready()
                        else:
                            await websocket.close(code=1002, reason="Session setup failed")
                            return
                    elif message_type == 'audio.input':
                        await self.handle_audio_input(data)
                    else:
                        logger.warning(f"Unknown message type: {message_type}")
                        
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON message: {message}. Error: {e}")
                    await websocket.close(code=1002, reason="Invalid JSON")
                    return
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    logger.error(f"Traceback: {traceback.format_exc()}")
                    
        except ConnectionClosed as e:
            logger.info(f"WebSocket connection closed: {e.code} - {e.reason}")
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket handler: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
        finally:
            await self.stop_heartbeat()
            self.websocket = None
            self.call_context = None
            logger.info(f"Connection cleanup completed for {client_info}")

async def main():
    """
    Start the WebSocket server with improved error handling
    """
    AUTH_TOKEN = "2BUrGJJPmN7WvNzEtDmD"
    voice_agent = MaqsamVoiceAgent(AUTH_TOKEN)
    HOST = "0.0.0.0"
    PORT = 8080
    
    logger.info(f"Starting Maqsam Voice Agent WebSocket server on {HOST}:{PORT}")
    logger.info("Using Cloudflare SSL termination")
    logger.info("Waiting for connections from Maqsam...")
    
    try:
        # Start server without process_request to avoid HTTP handling issues
        server = await websockets.serve(
            voice_agent.handle_connection,
            HOST,
            PORT,
            ping_interval=30,  # Send ping every 30 seconds
            ping_timeout=10,   # Wait 10 seconds for pong response
            close_timeout=10   # Wait 10 seconds when closing
        )
        
        logger.info("Server started successfully")
        await server.wait_closed()
        
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.error(f"Server crashed: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")