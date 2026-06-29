'use client'

import React, { useState, useEffect } from 'react'
import { 
  Shield, 
  UserCheck, 
  MessageSquare, 
  Radio, 
  VolumeX, 
  BookOpen, 
  Trash2, 
  Lock, 
  Users, 
  FileText,
  Play, 
  Square, 
  RefreshCw, 
  Eye, 
  EyeOff, 
  Layers,
  ArrowRight,
  Sparkles,
  CheckCircle2,
  AlertTriangle
} from 'lucide-react'

// Define the available features and their names in the python bot
const FEATURES = [
  { id: 'muting', name: 'Mute Management', icon: VolumeX, desc: 'Mute/unmute members, manage temporary silence periods, and track mute logs.' },
  { id: 'filters', name: 'Smart Filters', icon: MessageSquare, desc: 'Set keyword triggers to auto-respond, delete spam, or warn users.' },
  { id: 'welcome', name: 'Custom Greetings', icon: UserCheck, desc: 'Greet new members with customized media, text, and interactive buttons.' },
  { id: 'federation', name: 'Federation Bans', icon: Radio, desc: 'Share ban lists across multiple chats to keep toxic users out globally.' },
  { id: 'spam_shield', name: 'Spam Shield', icon: Shield, desc: 'Combat automated raid attacks, flood messages, and malicious userbots.' },
  { id: 'rules', name: 'Chat Rules', icon: BookOpen, desc: 'Define rules for your chat and allow users to view them via commands.' },
  { id: 'purge', name: 'Quick Purges', icon: Trash2, desc: 'Instantly bulk delete messages by user or message count with one command.' },
  { id: 'lockings', name: 'Media Locking', icon: Lock, desc: 'Block stickers, links, voice messages, documents, or games dynamically.' },
  { id: 'admins', name: 'Admin Tools', icon: Users, desc: 'Quickly promote, demote, or check admin permissions and statistics.' },
  { id: 'notes', name: 'Notes & Triggers', icon: FileText, desc: 'Save custom text snippets or links for easy callout with hashtags.' }
]

interface BotInstance {
  hash: string
  ownerId: string
  enabledPlugins: string[]
  status: 'running' | 'stopped'
  updatedAt: string
}

export default function Dashboard() {
  // Form State
  const [token, setToken] = useState('')
  const [ownerId, setOwnerId] = useState('')
  const [selectedFeatures, setSelectedFeatures] = useState<string[]>([
    'muting', 'filters', 'welcome' // default selected
  ])
  
  // UI State
  const [showToken, setShowToken] = useState(false)
  const [loading, setLoading] = useState(false)
  const [statusMessage, setStatusMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null)
  
  // Active Bots List
  const [activeBots, setActiveBots] = useState<BotInstance[]>([])
  const [loadingBots, setLoadingBots] = useState(true)

  // Fetch registered bots on load
  const fetchBots = async () => {
    try {
      setLoadingBots(true)
      const res = await fetch('/api/bot/status')
      const data = await res.json()
      if (data.bots) {
        setActiveBots(data.bots)
      }
    } catch (err) {
      console.error('Failed to load active bots:', err)
    } finally {
      setLoadingBots(false)
    }
  }

  useEffect(() => {
    fetchBots()
  }, [])

  // Toggle feature selection
  const toggleFeature = (id: string) => {
    setSelectedFeatures(prev => 
      prev.includes(id) 
        ? prev.filter(f => f !== id) 
        : [...prev, id]
    )
  }

  // Handle bot submission (Launch)
  const handleLaunch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!token.trim() || !ownerId.trim()) {
      setStatusMessage({ type: 'error', text: 'Please fill in both the Bot Token and Owner ID.' })
      return
    }

    if (selectedFeatures.length === 0) {
      setStatusMessage({ type: 'error', text: 'Please select at least one feature to enable.' })
      return
    }

    setLoading(true)
    setStatusMessage(null)

    try {
      const res = await fetch('/api/bot/launch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token: token.trim(),
          ownerId: ownerId.trim(),
          enabledPlugins: selectedFeatures
        })
      })

      const data = await res.json()
      if (data.success) {
        setStatusMessage({ type: 'success', text: `Bot started successfully! Hash ID: ${data.hash}` })
        // Clear form
        setToken('')
        setOwnerId('')
        // Refresh active list
        fetchBots()
      } else {
        setStatusMessage({ type: 'error', text: data.error || 'Failed to start bot' })
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Network error occurred'
      setStatusMessage({ type: 'error', text: msg })
    } finally {
      setLoading(false)
    }
  }

  // Handle stopping a bot
  const handleStop = async (hash: string) => {
    if (!confirm('Are you sure you want to stop and remove this bot instance?')) return

    try {
      const res = await fetch('/api/bot/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          hash,
          action: 'stop'
        })
      })

      const data = await res.json()
      if (data.success) {
        // Refresh status
        fetchBots()
      } else {
        alert(data.error || 'Failed to stop bot')
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Error stopping bot'
      alert(msg)
    }
  }

  // Edit/populate form with existing bot details
  const handleEdit = (bot: BotInstance) => {
    // Populate form (note: raw token isn't fetched back for security reasons, they must enter it again)
    setOwnerId(bot.ownerId)
    setSelectedFeatures(bot.enabledPlugins)
    setStatusMessage({
      type: 'success',
      text: `Loaded configuration for bot ${bot.hash}. Please re-enter the Bot Token to deploy updates.`
    })
  }

  return (
    <div className="min-h-screen pb-16 px-4 md:px-8 max-w-7xl mx-auto">
      
      {/* Header */}
      <header className="py-12 flex flex-col md:flex-row justify-between items-center border-b border-slate-800/60 mb-12">
        <div className="flex items-center gap-4 mb-6 md:mb-0">
          <div className="p-3 bg-indigo-600/20 border border-indigo-500/30 rounded-2xl shadow-indigo-500/10 shadow-lg">
            <Layers className="w-8 h-8 text-indigo-400" />
          </div>
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-indigo-200 via-slate-100 to-indigo-100 bg-clip-text text-transparent">
              Anjani Control Hub
            </h1>
            <p className="text-slate-400 text-sm mt-1">Multi-tenant custom feature manager for Telegram groups</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={fetchBots}
            className="p-2.5 bg-slate-800/80 hover:bg-slate-700/80 border border-slate-700/50 rounded-xl transition-all"
            title="Refresh bot list"
          >
            <RefreshCw className="w-5 h-5 text-slate-300" />
          </button>
          <span className="px-3.5 py-1.5 bg-slate-900/60 border border-slate-800 text-xs font-semibold text-indigo-400 rounded-full flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-indigo-400 animate-pulse"></span>
            System Online
          </span>
        </div>
      </header>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        
        {/* Left Side: Create/Deploy Form */}
        <div className="lg:col-span-8 space-y-8">
          
          {/* Status Alert Banner */}
          {statusMessage && (
            <div className={`p-4 rounded-xl flex items-start gap-3 border ${
              statusMessage.type === 'success' 
                ? 'bg-emerald-950/30 border-emerald-500/20 text-emerald-300' 
                : 'bg-rose-950/30 border-rose-500/20 text-rose-300'
            }`}>
              {statusMessage.type === 'success' ? (
                <CheckCircle2 className="w-5 h-5 flex-shrink-0 text-emerald-400" />
              ) : (
                <AlertTriangle className="w-5 h-5 flex-shrink-0 text-rose-400" />
              )}
              <span className="text-sm font-medium">{statusMessage.text}</span>
            </div>
          )}

          {/* Form wrapper */}
          <form onSubmit={handleLaunch} className="glass-panel rounded-3xl p-6 md:p-8 space-y-8">
            <div>
              <h2 className="text-xl font-bold flex items-center gap-2 text-slate-100">
                <Sparkles className="w-5 h-5 text-indigo-400" />
                Customize Features
              </h2>
              <p className="text-slate-400 text-sm mt-1">Select the specific plugins to load onto your bot container.</p>
            </div>

            {/* Feature Cards Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {FEATURES.map(feat => {
                const isSelected = selectedFeatures.includes(feat.id)
                return (
                  <div 
                    key={feat.id}
                    onClick={() => toggleFeature(feat.id)}
                    className={`glass-card rounded-2xl p-5 cursor-pointer flex gap-4 text-left select-none relative overflow-hidden ${
                      isSelected ? 'border-indigo-500/50 bg-indigo-950/15' : ''
                    }`}
                  >
                    <div className={`p-3 rounded-xl self-start ${
                      isSelected 
                        ? 'bg-indigo-600/20 border border-indigo-400/30 text-indigo-400' 
                        : 'bg-slate-800/50 border border-slate-700/50 text-slate-400'
                    }`}>
                      <feat.icon className="w-6 h-6" />
                    </div>
                    <div className="space-y-1">
                      <h3 className={`font-semibold text-sm ${isSelected ? 'text-slate-100' : 'text-slate-300'}`}>
                        {feat.name}
                      </h3>
                      <p className="text-slate-400 text-xs leading-relaxed">
                        {feat.desc}
                      </p>
                    </div>
                    {isSelected && (
                      <div className="absolute top-2 right-2 w-2 h-2 rounded-full bg-indigo-400 shadow-[0_0_10px_#6366f1]" />
                    )}
                  </div>
                )
              })}
            </div>

            {/* Credentials Fields */}
            <div className="border-t border-slate-800/60 pt-8 space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-100">Configuration Credentials</h3>
                <p className="text-slate-400 text-sm mt-0.5">We need the Telegram credentials to host your instance.</p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                
                {/* Telegram Token input */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                    BotFather Token
                  </label>
                  <div className="relative">
                    <input 
                      type={showToken ? 'text' : 'password'}
                      value={token}
                      onChange={e => setToken(e.target.value)}
                      placeholder="e.g. 123456:ABC-DEF1234..."
                      className="w-full bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all font-mono"
                    />
                    <button
                      type="button"
                      onClick={() => setShowToken(!showToken)}
                      className="absolute right-3 top-3.5 text-slate-500 hover:text-slate-300 transition-colors"
                    >
                      {showToken ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Owner ID input */}
                <div className="space-y-2">
                  <label className="block text-xs font-semibold uppercase tracking-wider text-slate-400">
                    Owner User ID
                  </label>
                  <input 
                    type="text"
                    value={ownerId}
                    onChange={e => setOwnerId(e.target.value)}
                    placeholder="e.g. 1919814914"
                    className="w-full bg-slate-950/60 border border-slate-800 rounded-xl px-4 py-3 text-sm text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-all font-mono"
                  />
                </div>

              </div>
            </div>

            {/* Launch Button */}
            <div className="border-t border-slate-800/60 pt-6 flex justify-end">
              <button
                type="submit"
                disabled={loading}
                className="px-6 py-3.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-indigo-800 text-sm font-semibold rounded-xl transition-all shadow-lg shadow-indigo-600/20 hover:shadow-indigo-600/30 flex items-center gap-2 group"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Deploying container...
                  </>
                ) : (
                  <>
                    Launch Custom Instance
                    <ArrowRight className="w-4 h-4 group-hover:translate-x-0.5 transition-transform" />
                  </>
                )}
              </button>
            </div>

          </form>

        </div>

        {/* Right Side: Active Instances Dashboard */}
        <div className="lg:col-span-4 space-y-6">
          <div className="glass-panel rounded-3xl p-6 space-y-6">
            <div>
              <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <Play className="w-4 h-4 text-emerald-400 fill-emerald-400" />
                Active Instances
              </h2>
              <p className="text-slate-400 text-xs mt-0.5">Manage your running bot containers.</p>
            </div>

            <div className="space-y-4 max-h-[600px] overflow-y-auto pr-1">
              {loadingBots ? (
                <div className="text-center py-8 text-slate-500 text-sm">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto mb-2 text-slate-600" />
                  Querying containers...
                </div>
              ) : activeBots.length === 0 ? (
                <div className="text-center py-10 border border-dashed border-slate-800 rounded-2xl text-slate-500 text-sm px-4">
                  No active bot containers found. Configure your bot on the left to start hosting.
                </div>
              ) : (
                activeBots.map(bot => (
                  <div key={bot.hash} className="p-4 rounded-2xl bg-slate-950/40 border border-slate-900 flex flex-col gap-3">
                    
                    {/* Bot header info */}
                    <div className="flex justify-between items-start">
                      <div>
                        <div className="font-mono text-xs font-semibold text-slate-300">
                          ID: {bot.hash}
                        </div>
                        <div className="text-[10px] text-slate-500 mt-0.5">
                          Owner: {bot.ownerId}
                        </div>
                      </div>
                      
                      <div className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          bot.status === 'running' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
                        }`} />
                        <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                          {bot.status}
                        </span>
                      </div>
                    </div>

                    {/* Features list pills */}
                    <div className="flex flex-wrap gap-1">
                      {bot.enabledPlugins.map(plugin => (
                        <span key={plugin} className="px-2 py-0.5 bg-slate-900 border border-slate-800/80 rounded-md text-[9px] text-indigo-300 font-medium">
                          {plugin}
                        </span>
                      ))}
                    </div>

                    {/* Actions bar */}
                    <div className="flex justify-between items-center border-t border-slate-900/60 pt-3 mt-1">
                      <button
                        onClick={() => handleEdit(bot)}
                        className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 transition-colors"
                      >
                        Modify Config
                      </button>
                      <button
                        onClick={() => handleStop(bot.hash)}
                        className="p-1.5 bg-rose-950/20 hover:bg-rose-900/30 border border-rose-500/10 hover:border-rose-500/20 rounded-lg text-rose-400 hover:text-rose-300 transition-colors flex items-center gap-1.5 text-xs font-medium"
                      >
                        <Square className="w-3.5 h-3.5 fill-rose-400" />
                        Stop
                      </button>
                    </div>

                  </div>
                ))
              )}
            </div>

          </div>
        </div>

      </div>

    </div>
  )
}
