<template>
  <div class="global-voice-widget" :class="{ 'is-recording': isRecording, 'is-speaking': isSpeaking }">
    <button class="voice-btn" @click="toggleRecording" :title="isRecording ? 'Stop Listening' : 'Start Listening'">
      <svg v-if="isRecording" class="mic-icon pulse" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="22" />
      </svg>
      <svg v-else class="mic-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
        <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
        <line x1="12" y1="19" x2="12" y2="22" />
        <line x1="1" y1="1" x2="23" y2="23" stroke="var(--color-accent-red)" />
      </svg>
    </button>
    <div class="voice-status" v-if="isRecording || isSpeaking || processing">
      <span v-if="processing">Processing...</span>
      <span v-else-if="isSpeaking">Hugo is speaking...</span>
      <span v-else-if="isRecording">Listening...</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useSpeech } from '../composables/useSpeech'
import api from '../services/api'
import { useAgentsStore } from '../stores/agents'

const { isSpeaking, isRecording, detectLanguage, speakResponse, stopSpeaking } = useSpeech()
const agentsStore = useAgentsStore()

let recognition: any = null
const processing = ref(false)

function initSpeechRecognition() {
  const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition
  if (!SpeechRecognition) {
    console.warn('Speech recognition not supported in this browser.')
    return
  }

  recognition = new SpeechRecognition()
  recognition.continuous = true
  recognition.interimResults = false
  recognition.lang = 'vi-VN' // Default to Vietnamese

  recognition.onstart = () => {
    isRecording.value = true
  }

  recognition.onend = () => {
    if (isRecording.value) {
      // Auto restart if it was meant to be continuous
      try {
        recognition.start()
      } catch (e) {
        console.warn('Restart recognition error:', e)
        isRecording.value = false
      }
    }
  }

  recognition.onresult = async (event: any) => {
    let finalTranscript = ''
    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript
      }
    }
    
    if (finalTranscript) {
      const lang = detectLanguage(finalTranscript)
      if (lang === 'unknown') {
        console.log('[GlobalVoice] Unrecognized text filtered out:', finalTranscript)
        return
      }
      
      // Stop recognition temporarily while agent is processing/speaking
      isRecording.value = false
      recognition.stop()
      
      await handleVoiceInput(finalTranscript)
    }
  }

  recognition.onerror = (event: any) => {
    console.warn('Speech recognition error', event.error)
    if (event.error === 'not-allowed') {
      isRecording.value = false
    }
  }
}

async function handleVoiceInput(text: string) {
  processing.value = true
  try {
    const resp = await api.post('/agents/empathetic/interact', { message: text }, { timeout: 30000 })
    const reply = resp.data.data?.response || 'Không nhận được câu trả lời hợp lệ.'
    
    // Add to chat history in store so Companion page also sees it
    agentsStore.chatLog.push({
      role: 'user',
      content: text,
      timestamp: new Date().toTimeString().split(' ')[0]
    })
    agentsStore.chatLog.push({
      role: 'hugo',
      content: reply,
      timestamp: new Date().toTimeString().split(' ')[0]
    })
    
    speakResponse(reply)
  } catch (err) {
    console.error("GlobalVoice Agent Uplink Error:", err)
    speakResponse("Lỗi kết nối. Vui lòng kiểm tra đường truyền.")
  } finally {
    processing.value = false
    // Resume listening automatically after speaking if it was active
    setTimeout(() => {
      if (!isRecording.value && recognition) {
        isRecording.value = true
        try { recognition.start() } catch (e) {}
      }
    }, 1000)
  }
}

function toggleRecording() {
  if (isRecording.value) {
    isRecording.value = false
    if (recognition) recognition.stop()
    stopSpeaking()
  } else {
    stopSpeaking()
    if (!recognition) initSpeechRecognition()
    if (recognition) {
      isRecording.value = true
      try {
        recognition.start()
      } catch (e) {
        console.warn(e)
      }
    }
  }
}

onMounted(() => {
  initSpeechRecognition()
})

onUnmounted(() => {
  if (recognition) {
    isRecording.value = false
    recognition.stop()
  }
})
</script>

<style scoped>
.global-voice-widget {
  position: fixed;
  bottom: 30px;
  right: 30px;
  display: flex;
  align-items: center;
  gap: 12px;
  z-index: 9999;
  font-family: var(--font-hud);
}

.voice-btn {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid var(--color-border-dim);
  color: var(--color-text-dim);
  display: flex;
  justify-content: center;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  backdrop-filter: blur(10px);
}

.voice-btn:hover {
  border-color: var(--color-accent-cyan);
  color: var(--color-accent-cyan);
  box-shadow: 0 0 15px rgba(0, 229, 255, 0.3);
}

.mic-icon {
  width: 24px;
  height: 24px;
}

.is-recording .voice-btn {
  border-color: var(--color-accent-green);
  color: var(--color-accent-green);
  box-shadow: 0 0 20px rgba(0, 255, 102, 0.4);
}

.pulse {
  animation: pulse-ring 1.5s infinite cubic-bezier(0.215, 0.61, 0.355, 1);
}

.is-speaking .voice-btn {
  border-color: var(--color-accent-cyan);
  color: var(--color-accent-cyan);
  box-shadow: 0 0 20px rgba(0, 229, 255, 0.5);
  animation: speak-pulse 1s infinite alternate;
}

.voice-status {
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid var(--color-accent-cyan);
  color: var(--color-accent-cyan);
  padding: 6px 12px;
  border-radius: 4px;
  font-size: 0.8rem;
  letter-spacing: 1px;
  text-transform: uppercase;
  backdrop-filter: blur(5px);
  box-shadow: 0 0 10px rgba(0, 229, 255, 0.2);
}

.is-recording .voice-status {
  border-color: var(--color-accent-green);
  color: var(--color-accent-green);
  box-shadow: 0 0 10px rgba(0, 255, 102, 0.2);
}

@keyframes pulse-ring {
  0% { transform: scale(0.95); opacity: 1; }
  50% { transform: scale(1.1); opacity: 0.8; }
  100% { transform: scale(0.95); opacity: 1; }
}

@keyframes speak-pulse {
  from { box-shadow: 0 0 10px rgba(0, 229, 255, 0.4); }
  to { box-shadow: 0 0 25px rgba(0, 229, 255, 0.8); }
}
</style>
