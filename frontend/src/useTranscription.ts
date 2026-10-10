import { useEffect, useRef, useState } from 'react'

export type TranscriptLine = { person: string; initials: string; time: string; text: string }
type Status = 'stopped' | 'connecting' | 'recording' | 'paused' | 'saving'
const base = (import.meta.env.VITE_TRANSCRIBER_URL || '/api').replace(/\/$/, '')

export function useTranscription() {
  const [transcript, setTranscript] = useState<TranscriptLine[]>([])
  const [recording, setRecording] = useState<Status>('stopped')
  const [error, setError] = useState('')
  const [loaded, setLoaded] = useState(false)
  const [elapsedSeconds, setElapsedSeconds] = useState(0)
  const resources = useRef<{ stream?: MediaStream; context?: AudioContext; node?: AudioWorkletNode; socket?: WebSocket }>({})
  const busy = useRef(false)
  const mounted = useRef(true)
  const target = useRef<Status>('stopped')

  function releaseAudio() {
    const r = resources.current
    r.node?.disconnect()
    r.stream?.getTracks().forEach(track => track.stop())
    if (r.context) void r.context.close()
    r.node = undefined
    r.stream = undefined
    r.context = undefined
  }

  async function loadTranscript(signal?: AbortSignal) {
    const response = await fetch(`${base}/transcript`, { signal })
    if (!response.ok) throw new Error('Could not load the existing transcript.')
    const data = await response.json() as { transcript: string }
    if (!mounted.current) return
    setTranscript(data.transcript.split('\n').filter(line => line.trim()).map(line => {
      const match = line.match(/^\[([^\]]+)\]\s*(.*)$/)
      return { person: 'Room', initials: 'RM', time: match?.[1] || '', text: match?.[2] || line }
    }))
    setLoaded(true)
  }

  useEffect(() => {
    mounted.current = true
    const controller = new AbortController()
    const activeResources = resources.current
    void loadTranscript(controller.signal).catch(err => {
      if (!controller.signal.aborted) setError(`Backend unavailable: ${err.message}`)
    })
    return () => {
      mounted.current = false
      controller.abort()
      releaseAudio()
      const socket = activeResources.socket
      if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify({ action: 'stop' }))
      socket?.close()
    }
  }, [])

  useEffect(() => {
    if (recording !== 'recording') return
    const timer = window.setInterval(() => setElapsedSeconds(value => value + 1), 1000)
    return () => window.clearInterval(timer)
  }, [recording])

  async function startRecording() {
    if (busy.current) return
    busy.current = true
    setError('')
    setRecording('connecting')
    target.current = 'stopped'
    try {
      // Hydrate first so a late history response cannot overwrite live captions.
      if (!loaded) await loadTranscript()
      if (!navigator.mediaDevices?.getUserMedia) throw new Error('Microphone access requires localhost or HTTPS.')
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 }, video: false })
      if (!mounted.current) { stream.getTracks().forEach(track => track.stop()); return }
      resources.current.stream = stream
      const context = new AudioContext({ sampleRate: 24000 })
      resources.current.context = context
      await context.resume()
      if (context.sampleRate !== 24000) throw new Error('This browser does not support 24 kHz microphone audio.')
      await context.audioWorklet.addModule('/pcm-worklet.js')
      if (!mounted.current) { releaseAudio(); return }
      const node = new AudioWorkletNode(context, 'pcm-recorder')
      resources.current.node = node
      const url = new URL(`${base}/ws/transcribe`, window.location.href)
      url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
      const socket = new WebSocket(url)
      resources.current.socket = socket
      let ready = false
      let failed = false
      stream.getAudioTracks()[0].onended = () => {
        failed = true
        setError('Microphone disconnected. Recording stopped.')
        stopRecording()
      }
      const timeout = window.setTimeout(() => {
        failed = true
        setError('The transcription service did not become ready. Try again.')
        releaseAudio()
        socket.close()
      }, 15000)
      node.port.onmessage = event => {
        if (ready && socket.readyState === WebSocket.OPEN) {
          if (socket.bufferedAmount > 240000) {
            failed = true
            setError('Connection too slow to record reliably. Please retry.')
            stopRecording()
            return
          }
          socket.send(event.data)
        }
      }
      socket.onmessage = event => {
        const message = JSON.parse(event.data)
        if (message.type === 'ready') {
          window.clearTimeout(timeout)
          ready = true
          context.createMediaStreamSource(stream).connect(node)
          node.connect(context.destination)
          setRecording('recording')
        } else if (message.type === 'transcript') {
          setTranscript(current => [...current, { person: 'Room', initials: 'RM', time: message.timestamp, text: message.text }])
        } else if (message.type === 'error') {
          failed = true
          setError(message.message || 'Transcription failed.')
          releaseAudio()
        }
      }
      socket.onerror = () => { failed = true; setError('Cannot connect to the transcription backend.') }
      socket.onclose = event => {
        window.clearTimeout(timeout)
        releaseAudio()
        resources.current.socket = undefined
        busy.current = false
        if (!mounted.current) return
        if (event.code !== 1000 && !failed) setError('Recording disconnected; final transcript saving was not confirmed.')
        setRecording(target.current)
      }
    } catch (err) {
      releaseAudio()
      busy.current = false
      if (mounted.current) {
        setError(err instanceof Error ? err.message : 'Could not start recording.')
        setRecording('stopped')
      }
    }
  }

  function stopRecording(pause = false) {
    target.current = pause ? 'paused' : 'stopped'
    releaseAudio()
    const socket = resources.current.socket
    if (socket?.readyState === WebSocket.OPEN) {
      setRecording('saving')
      socket.send(JSON.stringify({ action: 'stop' }))
    }
  }

  function exportTranscript() {
    const blob = new Blob([transcript.map(line => `[${line.time}] ${line.text}`).join('\n')], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'transcript.txt'
    link.click()
    URL.revokeObjectURL(url)
  }

  return { transcript, recording, error, loaded, elapsedSeconds, startRecording, stopRecording, exportTranscript }
}
