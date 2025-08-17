#!/usr/bin/env node

/**
 * Test direct audio playback through daemon
 * Send PCM data to daemon and verify actual audio output
 */

const WebSocket = require('ws');
const fs = require('fs');

const testDaemonAudio = async () => {
  console.log('🎵 Testing direct audio playback through daemon...');
  
  try {
    // Read the PCM data we just generated
    const pcmData = fs.readFileSync('/tmp/test_pcm.raw');
    console.log(`📦 Loaded PCM data: ${pcmData.length} bytes`);
    
    // Connect to daemon
    const ws = new WebSocket('ws://localhost:8081');
    
    await new Promise((resolve, reject) => {
      ws.on('open', () => {
        console.log('✅ Connected to audio daemon');
        
        // Send audio format and start playback
        ws.send(JSON.stringify({
          type: 'control',
          timestamp: Date.now(),
          data: { action: 'play' }
        }));
        
        console.log('📡 Sent play command');
        
        // Send PCM data in chunks
        const chunkSize = 2400; // 50ms chunks at 24kHz 16-bit mono
        let offset = 0;
        let sequence = 0;
        
        const sendChunk = () => {
          if (offset >= pcmData.length) {
            console.log('📦 All chunks sent, sending end_stream');
            ws.send(JSON.stringify({
              type: 'end_stream',
              timestamp: Date.now(),
              data: {}
            }));
            
            // Wait for playback to complete
            setTimeout(() => {
              ws.close();
              resolve();
            }, 2000);
            return;
          }
          
          const chunk = pcmData.slice(offset, offset + chunkSize);
          ws.send(JSON.stringify({
            type: 'audio_chunk',
            timestamp: Date.now(),
            data: {
              chunk: Array.from(chunk), // Convert to array for JSON
              format: {
                format: 'pcm',
                sampleRate: 24000,
                channels: 1,
                bitDepth: 16
              },
              sequence: sequence++
            }
          }));
          
          console.log(`📦 Sent chunk ${sequence}: ${chunk.length} bytes (offset: ${offset})`);
          offset += chunkSize;
          
          // Send next chunk after short delay
          setTimeout(sendChunk, 10);
        };
        
        // Start sending chunks
        setTimeout(sendChunk, 100);
      });
      
      ws.on('message', (data) => {
        try {
          const message = JSON.parse(data);
          console.log(`📨 Daemon message: ${message.type}`);
          if (message.type === 'status') {
            console.log(`   📊 Status: playing=${message.data.isPlaying}, chunks=${message.data.performance?.stats?.chunksReceived || 0}`);
          } else if (message.type === 'completed') {
            console.log('🎉 Playback completed!');
          }
        } catch (e) {
          console.log('📨 Raw message:', data.toString().substring(0, 100));
        }
      });
      
      ws.on('error', (error) => {
        console.error('❌ WebSocket error:', error.message);
        reject(error);
      });
      
      ws.on('close', () => {
        console.log('🔌 Connection closed');
        resolve();
      });
    });
    
  } catch (error) {
    console.error('❌ Test failed:', error.message);
  }
};

testDaemonAudio().catch(console.error);
