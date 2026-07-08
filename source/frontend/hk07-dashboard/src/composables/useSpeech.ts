import { ref } from 'vue'

export function useSpeech() {
  const isSpeaking = ref(false)
  const isRecording = ref(false)

  function detectLanguage(text: string): 'en' | 'vi' | 'unknown' {
    const viAccents = /[àáảãạâầấẩẫậăằắẳẵặèéẻẽẹêềếểễệđìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]/i
    if (viAccents.test(text)) {
      return 'vi'
    }
    
    // Common Vietnamese words without accents
    const commonViWords = /\b(chao|sep|toi|co|khong|di|dao|nhip|tim|suc|khoe|o|day|giup|chi|so|met|moi|dau|nguc|binh|thuong|thoi|tiet|hom|nay|the|nao|cho|loi|khuyen|bao|ve|cuu|voi|nga|roi|phat|tin|hieu|khan|cap|oi|cam|thay|nho|lon|vua|tram|cao|nhanh|cham|trai|phai|ban|dang|lam|gi)\b/i
    
    const words = text.toLowerCase().split(/\s+/)
    let viCount = 0
    let enCount = 0
    
    const commonEnWords = new Set([
      "hello", "hi", "hey", "you", "there", "is", "are", "am", "how", "what", "weather", "today", "go", "walk", 
      "robot", "check", "sensor", "status", "connection", "heart", "rate", "health", "vitals", "feel", "tired", 
      "dizzy", "pain", "chest", "severe", "help", "me", "fall", "emergency", "signal", "please", "advice", 
      "protect", "who", "where", "why", "can", "do", "should", "thank", "thanks"
    ])
    
    for (const w of words) {
      if (viAccents.test(w) || commonViWords.test(w)) {
        viCount++
      } else if (commonEnWords.has(w)) {
        enCount++
      }
    }
    
    // Strict filtering: If no known words detected, return unknown.
    if (enCount === 0 && viCount === 0 && words.length > 0) {
      // Small allowance for numbers or short inputs.
      if (!/^\d+$/.test(text.trim()) && text.trim().length > 2) {
        return 'unknown'
      }
    }
    
    if (enCount > viCount) {
      return 'en'
    }
    return 'vi'
  }

  function speakResponse(text: string, isMuted: boolean = false) {
    if (isMuted) return
    if (!('speechSynthesis' in window)) return

    window.speechSynthesis.cancel()
    
    const getBestVoice = (langCode: 'vi-VN' | 'en-US') => {
      const voices = window.speechSynthesis.getVoices()
      let voice = voices.find(v => {
        const l = v.lang.toLowerCase().replace('_', '-')
        return l === langCode.toLowerCase()
      })
      if (!voice) {
        const prefix = langCode.split('-')[0].toLowerCase()
        voice = voices.find(v => {
          const l = v.lang.toLowerCase().replace('_', '-')
          return l === prefix || l.startsWith(prefix + '-')
        })
      }
      return voice
    }
    
    const viVoice = getBestVoice('vi-VN')
    const enVoice = getBestVoice('en-US')
    
    const bracketMatch = text.match(/^\[(.*?)\](.*)$/s)
    if (bracketMatch) {
      const tagText = bracketMatch[1].replace(/_/g, ' ')
      const bodyText = bracketMatch[2].trim()
      
      const utteranceTag = new SpeechSynthesisUtterance(tagText)
      utteranceTag.lang = 'en-US'
      if (enVoice) utteranceTag.voice = enVoice
      utteranceTag.rate = 0.95
      utteranceTag.pitch = 0.95
      
      const utteranceBody = new SpeechSynthesisUtterance(bodyText)
      const bodyLang = detectLanguage(bodyText)
      if (bodyLang === 'en') {
        utteranceBody.lang = 'en-US'
        if (enVoice) utteranceBody.voice = enVoice
      } else {
        utteranceBody.lang = 'vi-VN'
        if (viVoice) utteranceBody.voice = viVoice
      }
      utteranceBody.rate = 0.95
      utteranceBody.pitch = 0.95
      
      utteranceTag.onstart = () => { isSpeaking.value = true }
      utteranceBody.onend = () => { isSpeaking.value = false }
      utteranceTag.onerror = () => { isSpeaking.value = false }
      utteranceBody.onerror = () => { isSpeaking.value = false }
      
      window.speechSynthesis.speak(utteranceTag)
      window.speechSynthesis.speak(utteranceBody)
    } else {
      const cleanText = text.trim()
      const utterance = new SpeechSynthesisUtterance(cleanText)
      
      const lang = detectLanguage(cleanText)
      if (lang === 'en') {
        utterance.lang = 'en-US'
        if (enVoice) utterance.voice = enVoice
      } else {
        utterance.lang = 'vi-VN'
        if (viVoice) utterance.voice = viVoice
      }
      utterance.rate = 0.95
      utterance.pitch = 0.95
      
      utterance.onstart = () => { isSpeaking.value = true }
      utterance.onend = () => { isSpeaking.value = false }
      utterance.onerror = () => { isSpeaking.value = false }
      
      window.speechSynthesis.speak(utterance)
    }
  }

  function stopSpeaking() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel()
      isSpeaking.value = false
    }
  }

  return {
    isSpeaking,
    isRecording,
    detectLanguage,
    speakResponse,
    stopSpeaking
  }
}
