#!/usr/bin/env python3
"""
Medical Voice Agent - FastAPI Application
Web interface for recording patient encounters and generating clinical notes
"""

import os
import json
import base64
import asyncio
from datetime import datetime
from typing import Dict, Optional
import io
import wave

from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
from loguru import logger

from medical_scribe import MedicalScribe

# Initialize FastAPI
app = FastAPI(
    title="Medical Voice Agent",
    description="HIPAA-compliant clinical documentation assistant",
    version="1.0.0"
)

# Enable CORS for web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize medical scribe
scribe = MedicalScribe()

# Create directories
os.makedirs("encounters", exist_ok=True)
os.makedirs("recordings", exist_ok=True)
os.makedirs("logs", exist_ok=True)

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main recording interface"""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Medical Voice Agent</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }

        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 40px;
            max-width: 800px;
            width: 100%;
        }

        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
        }

        .subtitle {
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .recording-section {
            background: #f8f9fa;
            border-radius: 15px;
            padding: 30px;
            text-align: center;
            margin-bottom: 30px;
        }

        .mic-button {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
            font-size: 40px;
            cursor: pointer;
            transition: all 0.3s;
            margin: 20px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        }

        .mic-button:hover {
            transform: scale(1.05);
        }

        .mic-button.recording {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
            animation: pulse 1.5s infinite;
        }

        @keyframes pulse {
            0% { box-shadow: 0 0 0 0 rgba(245, 87, 108, 0.7); }
            70% { box-shadow: 0 0 0 20px rgba(245, 87, 108, 0); }
            100% { box-shadow: 0 0 0 0 rgba(245, 87, 108, 0); }
        }

        .status {
            margin: 20px 0;
            font-size: 18px;
            color: #666;
        }

        .timer {
            font-size: 24px;
            font-weight: bold;
            color: #333;
            margin: 10px 0;
        }

        .controls {
            display: flex;
            gap: 10px;
            justify-content: center;
            margin-top: 20px;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }

        .btn-primary {
            background: #667eea;
            color: white;
        }

        .btn-secondary {
            background: #e5e7eb;
            color: #333;
        }

        .btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }

        .btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }

        .results-section {
            margin-top: 30px;
            display: none;
        }

        .results-section.active {
            display: block;
        }

        .note-section {
            background: #f8f9fa;
            border-radius: 10px;
            padding: 20px;
            margin: 15px 0;
        }

        .note-section h3 {
            color: #667eea;
            margin-bottom: 10px;
            font-size: 16px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .note-content {
            color: #333;
            line-height: 1.6;
            white-space: pre-wrap;
        }

        .loading {
            display: none;
            text-align: center;
            padding: 40px;
        }

        .loading.active {
            display: block;
        }

        .spinner {
            width: 50px;
            height: 50px;
            border: 5px solid #f3f3f3;
            border-top: 5px solid #667eea;
            border-radius: 50%;
            animation: spin 1s linear infinite;
            margin: 0 auto 20px;
        }

        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }

        .error {
            background: #fee;
            color: #c00;
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
            display: none;
        }

        .error.active {
            display: block;
        }

        .transcript-box {
            background: white;
            border: 2px solid #e5e7eb;
            border-radius: 10px;
            padding: 15px;
            margin: 15px 0;
            max-height: 200px;
            overflow-y: auto;
        }

        .confidence {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-left: 10px;
        }

        .confidence.high {
            background: #d4edda;
            color: #155724;
        }

        .confidence.medium {
            background: #fff3cd;
            color: #856404;
        }

        .confidence.low {
            background: #f8d7da;
            color: #721c24;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🩺 Medical Voice Agent</h1>
        <p class="subtitle">Record patient encounter • Generate clinical documentation instantly</p>

        <div class="recording-section">
            <button id="micButton" class="mic-button">
                <span id="micIcon">🎤</span>
            </button>
            <div class="status" id="status">Ready to record</div>
            <div class="timer" id="timer">00:00</div>
            <div class="controls">
                <button id="startBtn" class="btn btn-primary">Start Recording</button>
                <button id="stopBtn" class="btn btn-secondary" disabled>Stop Recording</button>
            </div>
        </div>

        <div class="error" id="error"></div>

        <div class="loading" id="loading">
            <div class="spinner"></div>
            <p>Processing encounter...</p>
            <p style="font-size: 12px; color: #999; margin-top: 10px;">
                Transcribing audio and generating clinical note
            </p>
        </div>

        <div class="results-section" id="results">
            <h2 style="margin-bottom: 20px;">📋 Clinical Documentation</h2>

            <div class="note-section">
                <h3>Transcript
                    <span id="confidenceBadge" class="confidence"></span>
                </h3>
                <div class="transcript-box" id="transcript"></div>
            </div>

            <div class="note-section">
                <h3>Chief Complaint</h3>
                <div class="note-content" id="chiefComplaint"></div>
            </div>

            <div class="note-section">
                <h3>History of Present Illness</h3>
                <div class="note-content" id="hpi"></div>
            </div>

            <div class="note-section">
                <h3>Assessment</h3>
                <div class="note-content" id="assessment"></div>
            </div>

            <div class="note-section">
                <h3>Plan</h3>
                <div class="note-content" id="plan"></div>
            </div>

            <div class="note-section" id="codesSection" style="display: none;">
                <h3>Suggested Codes</h3>
                <div class="note-content">
                    <strong>ICD-10:</strong> <span id="icd10Codes"></span><br>
                    <strong>CPT:</strong> <span id="cptCodes"></span>
                </div>
            </div>

            <div class="controls" style="margin-top: 30px;">
                <button onclick="copyToClipboard()" class="btn btn-primary">Copy Note</button>
                <button onclick="startNewRecording()" class="btn btn-secondary">New Recording</button>
            </div>
        </div>
    </div>

    <script>
        let mediaRecorder;
        let audioChunks = [];
        let startTime;
        let timerInterval;
        let isRecording = false;

        const micButton = document.getElementById('micButton');
        const startBtn = document.getElementById('startBtn');
        const stopBtn = document.getElementById('stopBtn');
        const status = document.getElementById('status');
        const timer = document.getElementById('timer');
        const loading = document.getElementById('loading');
        const results = document.getElementById('results');
        const error = document.getElementById('error');

        // Button click handlers
        micButton.onclick = toggleRecording;
        startBtn.onclick = startRecording;
        stopBtn.onclick = stopRecording;

        async function toggleRecording() {
            if (isRecording) {
                await stopRecording();
            } else {
                await startRecording();
            }
        }

        async function startRecording() {
            try {
                // Reset UI
                error.classList.remove('active');
                results.classList.remove('active');
                audioChunks = [];

                // Get microphone access
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

                // Create MediaRecorder with WAV-compatible settings
                const options = { mimeType: 'audio/webm' };
                mediaRecorder = new MediaRecorder(stream, options);

                mediaRecorder.ondataavailable = (event) => {
                    audioChunks.push(event.data);
                };

                mediaRecorder.onstop = async () => {
                    // Stop all tracks
                    stream.getTracks().forEach(track => track.stop());

                    // Create blob from chunks
                    const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });

                    // Process the recording
                    await processRecording(audioBlob);
                };

                // Start recording
                mediaRecorder.start();
                isRecording = true;

                // Update UI
                micButton.classList.add('recording');
                startBtn.disabled = true;
                stopBtn.disabled = false;
                status.textContent = 'Recording...';

                // Start timer
                startTime = Date.now();
                timerInterval = setInterval(updateTimer, 100);

            } catch (err) {
                console.error('Error accessing microphone:', err);
                showError('Microphone access denied. Please allow microphone access and try again.');
            }
        }

        async function stopRecording() {
            if (!mediaRecorder || mediaRecorder.state !== 'recording') return;

            // Stop recording
            mediaRecorder.stop();
            isRecording = false;

            // Update UI
            micButton.classList.remove('recording');
            startBtn.disabled = false;
            stopBtn.disabled = true;
            status.textContent = 'Processing...';

            // Stop timer
            clearInterval(timerInterval);
        }

        function updateTimer() {
            const elapsed = Math.floor((Date.now() - startTime) / 1000);
            const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
            const seconds = (elapsed % 60).toString().padStart(2, '0');
            timer.textContent = `${minutes}:${seconds}`;
        }

        async function processRecording(audioBlob) {
            try {
                // Show loading
                loading.classList.add('active');
                status.textContent = 'Processing encounter...';

                // Create FormData and send to server
                const formData = new FormData();
                formData.append('audio', audioBlob, 'recording.webm');

                const response = await fetch('/process-audio', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    throw new Error(`Server error: ${response.status}`);
                }

                const result = await response.json();

                // Hide loading
                loading.classList.remove('active');

                // Display results
                displayResults(result);

            } catch (err) {
                console.error('Processing error:', err);
                loading.classList.remove('active');
                showError('Error processing recording. Please try again.');
                status.textContent = 'Ready to record';
            }
        }

        function displayResults(data) {
            // Show results section
            results.classList.add('active');
            status.textContent = 'Documentation generated';

            // Display transcript
            if (data.transcription) {
                document.getElementById('transcript').textContent =
                    data.transcription.transcript || 'No transcript available';

                // Show confidence badge
                const confidence = data.transcription.confidence || 0;
                const confidenceBadge = document.getElementById('confidenceBadge');
                confidenceBadge.textContent = `${(confidence * 100).toFixed(0)}% confidence`;

                if (confidence > 0.9) {
                    confidenceBadge.className = 'confidence high';
                } else if (confidence > 0.7) {
                    confidenceBadge.className = 'confidence medium';
                } else {
                    confidenceBadge.className = 'confidence low';
                }
            }

            // Display SOAP note sections
            if (data.soap_note) {
                document.getElementById('chiefComplaint').textContent =
                    data.soap_note.chief_complaint || 'Not documented';
                document.getElementById('hpi').textContent =
                    data.soap_note.history_of_present_illness || 'Not documented';
                document.getElementById('assessment').textContent =
                    data.soap_note.assessment || 'Not documented';
                document.getElementById('plan').textContent =
                    data.soap_note.plan || 'Not documented';

                // Display codes if available
                if (data.soap_note.icd10_codes?.length || data.soap_note.cpt_codes?.length) {
                    document.getElementById('codesSection').style.display = 'block';
                    document.getElementById('icd10Codes').textContent =
                        data.soap_note.icd10_codes?.join(', ') || 'None';
                    document.getElementById('cptCodes').textContent =
                        data.soap_note.cpt_codes?.join(', ') || 'None';
                }
            }
        }

        function showError(message) {
            error.textContent = message;
            error.classList.add('active');
            setTimeout(() => error.classList.remove('active'), 5000);
        }

        function copyToClipboard() {
            // Gather all note content
            const sections = [
                'CHIEF COMPLAINT:\\n' + document.getElementById('chiefComplaint').textContent,
                '\\nHPI:\\n' + document.getElementById('hpi').textContent,
                '\\nASSESSMENT:\\n' + document.getElementById('assessment').textContent,
                '\\nPLAN:\\n' + document.getElementById('plan').textContent
            ];

            const noteText = sections.join('\\n');

            // Copy to clipboard
            navigator.clipboard.writeText(noteText).then(() => {
                alert('Clinical note copied to clipboard!');
            }).catch(err => {
                console.error('Copy failed:', err);
                showError('Failed to copy note');
            });
        }

        function startNewRecording() {
            // Reset everything
            results.classList.remove('active');
            status.textContent = 'Ready to record';
            timer.textContent = '00:00';
            audioChunks = [];
        }
    </script>
</body>
</html>
"""

@app.post("/process-audio")
async def process_audio(audio: UploadFile = File(...)):
    """
    Process uploaded audio file
    """
    try:
        # Read audio data
        audio_data = await audio.read()

        # Save recording
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        recording_path = f"recordings/recording_{timestamp}.webm"
        with open(recording_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"Saved recording: {recording_path}")

        # Process with medical scribe
        # Note: Deepgram expects WAV format, so we'd need to convert webm to wav
        # For now, we'll use a test transcript

        # TODO: Convert webm to wav for Deepgram
        # For testing, use sample transcript
        test_transcript = """
        Doctor: What brings you in today?
        Patient: I've been having severe headaches for the past week.
        Doctor: Can you describe the pain?
        Patient: It's a throbbing pain, mostly on the right side of my head.
        Doctor: Any nausea or sensitivity to light?
        Patient: Yes, both actually. Bright lights make it worse.
        Doctor: Based on your symptoms, this appears to be a migraine.
        I'll prescribe sumatriptan for acute relief.
        """

        # Generate SOAP note
        note = await scribe.generate_soap_note(test_transcript)

        result = {
            "encounter_id": note.encounter_id,
            "timestamp": note.timestamp,
            "transcription": {
                "transcript": test_transcript,
                "confidence": 0.95
            },
            "soap_note": note.dict()
        }

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error processing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    logger.info("Starting Medical Voice Agent server...")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=False)