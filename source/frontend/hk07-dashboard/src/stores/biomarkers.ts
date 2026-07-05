import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface BiomarkersData {
  cortisol_ug_dl: number
  adrenaline_pg_ml: number
  dopamine_pg_ml: number
  serotonin_ng_ml: number
}

export const useBiomarkersStore = defineStore('biomarkers', () => {
  const dopamine = ref<number | null>(null)
  const serotonin = ref<number | null>(null)
  const adrenaline = ref<number | null>(null)
  const cortisol = ref<number | null>(null)
  const lastUpdatedMs = ref<number>(0)

  const isLive = computed(() => {
    if (lastUpdatedMs.value === 0) return false
    return Date.now() - lastUpdatedMs.value < 10000 // 10 seconds timeout
  })

  // Derive dynamic secondary biomarkers logically
  const gnrh = computed(() => {
    if (!isLive.value || cortisol.value === null) return null
    // High cortisol inhibits GnRH
    return Math.max(5, Math.round(75 - (cortisol.value * 3)))
  })

  const lh = computed(() => {
    if (!isLive.value || gnrh.value === null) return null
    return Math.max(2, Math.round(gnrh.value * 0.15))
  })

  const fsh = computed(() => {
    if (!isLive.value || gnrh.value === null) return null
    return Math.max(1, Math.round(gnrh.value * 0.12))
  })

  const testosterone = computed(() => {
    if (!isLive.value || lh.value === null) return null
    return Math.max(50, Math.round(lh.value * 50))
  })

  const estradiol = computed(() => {
    if (!isLive.value || fsh.value === null) return null
    return Math.max(5, Math.round(fsh.value * 3.5))
  })

  function updateBiomarkers(data: any) {
    const rawBiomarkers = data.biomarkers
    if (rawBiomarkers) {
      dopamine.value = rawBiomarkers.dopamine_pg_ml ?? null
      serotonin.value = rawBiomarkers.serotonin_ng_ml ?? null
      adrenaline.value = rawBiomarkers.adrenaline_pg_ml ?? null
      cortisol.value = rawBiomarkers.cortisol_ug_dl ?? null
      lastUpdatedMs.value = Date.now()
    }
  }

  function setOffline() {
    lastUpdatedMs.value = 0
  }

  return {
    dopamine,
    serotonin,
    adrenaline,
    cortisol,
    lastUpdatedMs,
    isLive,
    gnrh,
    lh,
    fsh,
    testosterone,
    estradiol,
    updateBiomarkers,
    setOffline
  }
})
