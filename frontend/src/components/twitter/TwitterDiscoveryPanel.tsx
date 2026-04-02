import { useEffect, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Download, Printer, Save, Search, Sparkles, Star, Users } from 'lucide-react'
import toast from 'react-hot-toast'

import {
  discoveryApi,
  type DiscoveryResponse,
  type SharedFollowingsResponse,
} from '../../api/discovery'
import { KeywordTagInput } from '../ui/KeywordTagInput'
import { Button } from '../ui/Button'
import { Card, CardHeader, CardTitle } from '../ui/Card'
import { Input } from '../ui/Input'
import { SharedFollowingRow, StatTile, UserRow } from './TwitterDiscoveryRows'
import { createManualDraft, parseManualList, printDiscoveryReport } from './twitterDiscoveryUtils'

export function TwitterDiscoveryPanel() {
  const [seedKeywords, setSeedKeywords] = useState<string[]>([])
  const [expandedKeywords, setExpandedKeywords] = useState<string[]>([])
  const [dummyMode, setDummyMode] = useState(() => {
    if (typeof window === 'undefined') return false
    return window.localStorage.getItem('meruem_discovery_dummy_mode') === 'true'
  })
  const [location, setLocation] = useState('Nigeria')
  const [dateFrom, setDateFrom] = useState(() => {
    const d = new Date()
    d.setDate(d.getDate() - 56)
    return d.toISOString().split('T')[0]
  })
  const [dateTo, setDateTo] = useState(() => new Date().toISOString().split('T')[0])
  const [maxResults, setMaxResults] = useState(200)

  const [results, setResults] = useState<DiscoveryResponse | null>(null)
  const [selectedUsers, setSelectedUsers] = useState<Set<number>>(new Set())
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set())
  const [manualDrafts, setManualDrafts] = useState<Record<number, { followersText: string; followingText: string; notes: string }>>({})
  const [sharedFollowings, setSharedFollowings] = useState<SharedFollowingsResponse | null>(null)
  const [selectedMicroInfluencers, setSelectedMicroInfluencers] = useState<Set<string>>(new Set())
  const [savingManualIndex, setSavingManualIndex] = useState<number | null>(null)

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('meruem_discovery_dummy_mode', String(dummyMode))
  }, [dummyMode])

  const expandMutation = useMutation({
    mutationFn: () => discoveryApi.expandKeywords(seedKeywords),
    onSuccess: (data) => {
      setExpandedKeywords(data.expanded)
      toast.success(`Generated ${data.expanded.length} related keywords`)
    },
    onError: (err: Error) => toast.error(`Expansion failed: ${err.message}`),
  })

  const searchMutation = useMutation({
    mutationFn: () =>
      discoveryApi.search({
        seed_keywords: seedKeywords,
        expanded_keywords: expandedKeywords,
        location,
        date_from: dateFrom,
        date_to: dateTo,
        max_results: maxResults,
        dummy_mode: dummyMode,
      }),
    onSuccess: (data) => {
      setResults(data)
      setSelectedUsers(new Set())
      setExpandedRows(new Set())
      setManualDrafts({})
      setSharedFollowings(null)
      setSelectedMicroInfluencers(new Set(data.selected_micro_influencers))
      toast.success(`Profiled ${data.profiled_users_count} users and surfaced ${data.high_value_users_found} high-value leads`)
    },
    onError: (err: Error) => toast.error(`Search failed: ${err.message}`),
  })

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!results) throw new Error('No results to save')
      return discoveryApi.saveUsers(results.job_id, Array.from(selectedUsers))
    },
    onSuccess: (data) => {
      toast.success(`Saved ${data.saved_count} profiles with their recent tweet context`)
      setSelectedUsers(new Set())
    },
    onError: (err: Error) => toast.error(`Save failed: ${err.message}`),
  })

  const manualEnrichmentMutation = useMutation({
    mutationFn: async ({ userIndex }: { userIndex: number }) => {
      if (!results) throw new Error('No discovery results loaded')
      const payload = manualDrafts[userIndex] ?? createManualDraft(results.users[userIndex])
      setSavingManualIndex(userIndex)
      return discoveryApi.updateManualEnrichment(results.job_id, userIndex, {
        followers_list: parseManualList(payload.followersText),
        following_list: parseManualList(payload.followingText),
        notes: payload.notes.trim() || null,
      })
    },
    onSuccess: (updatedUser, variables) => {
      setResults((prev) => {
        if (!prev) return prev
        const users = prev.users.map((user, index) => (index === variables.userIndex ? updatedUser : user))
        return { ...prev, users }
      })
      setManualDrafts((prev) => ({
        ...prev,
        [variables.userIndex]: createManualDraft(updatedUser),
      }))
      setSharedFollowings(null)
      toast.success(`Saved manual enrichment for @${updatedUser.username}`)
    },
    onError: (err: Error) => toast.error(`Manual enrichment failed: ${err.message}`),
    onSettled: () => setSavingManualIndex(null),
  })

  const sharedFollowingsMutation = useMutation({
    mutationFn: () => {
      if (!results) throw new Error('No discovery results loaded')
      return discoveryApi.analyzeSharedFollowings(results.job_id, {
        user_indices: Array.from(selectedUsers),
        min_overlap: 2,
        max_candidates: 30,
      })
    },
    onSuccess: (data) => {
      setSharedFollowings(data)
      setSelectedMicroInfluencers(new Set(data.candidates.filter((candidate) => candidate.selected).map((candidate) => candidate.username)))
      toast.success(`Found ${data.total_candidates} shared-following candidates`)
    },
    onError: (err: Error) => toast.error(`Shared-followings analysis failed: ${err.message}`),
  })

  const saveMicroInfluencersMutation = useMutation({
    mutationFn: () => {
      if (!results) throw new Error('No discovery results loaded')
      return discoveryApi.saveSharedFollowingSelection(results.job_id, Array.from(selectedMicroInfluencers))
    },
    onSuccess: (data) => {
      setSharedFollowings(data)
      setResults((prev) => (prev ? { ...prev, selected_micro_influencers: Array.from(selectedMicroInfluencers) } : prev))
      toast.success(`Saved ${selectedMicroInfluencers.size} micro-influencer selections`)
    },
    onError: (err: Error) => toast.error(`Saving selections failed: ${err.message}`),
  })

  const toggleUser = (idx: number) => {
    setSelectedUsers((prev) => {
      const next = new Set(prev)
      next.has(idx) ? next.delete(idx) : next.add(idx)
      return next
    })
  }

  const toggleSelectAll = () => {
    if (!results) return
    if (selectedUsers.size === results.users.length) {
      setSelectedUsers(new Set())
    } else {
      setSelectedUsers(new Set(results.users.map((_, i) => i)))
    }
  }

  const updateManualDraft = (index: number, patch: Partial<{ followersText: string; followingText: string; notes: string }>) => {
    setManualDrafts((prev) => ({
      ...prev,
      [index]: {
        ...(prev[index] ?? createManualDraft(results?.users[index])),
        ...patch,
      },
    }))
  }

  const handleExportCsv = async () => {
    if (!results) return
    try {
      const blob = await discoveryApi.downloadCsv(results.job_id)
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `discovery-${results.job_id}.csv`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'CSV export failed')
    }
  }

  const handlePrint = () => {
    if (!results) return
    try {
      printDiscoveryReport(results, sharedFollowings, selectedMicroInfluencers)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Print failed')
    }
  }

  const allKeywords = [...seedKeywords, ...expandedKeywords]

  return (
    <div className="space-y-6">
      <Card className="bg-gradient-to-br from-slate-800 to-slate-800/80 border-slate-700/60 print:hidden">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Search size={20} className="text-sky-400" />
            User Discovery
          </CardTitle>
          <p className="text-sm text-slate-400 mt-1">Discover Twitter users, enrich them manually, and identify shared-following micro-influencers.</p>
        </CardHeader>
        <div className="space-y-5">
          <KeywordTagInput tags={seedKeywords} onChange={setSeedKeywords} label="Seed Keywords" placeholder="e.g. 'Fuel price pain' - press Enter to add" />
          {seedKeywords.length > 0 && (
            <div className="flex items-center gap-3">
              <Button variant="secondary" size="sm" onClick={() => expandMutation.mutate()} loading={expandMutation.isPending}>
                <Sparkles size={14} className="text-amber-400" />
                Expand with AI
              </Button>
            </div>
          )}
          {expandedKeywords.length > 0 && <KeywordTagInput tags={expandedKeywords} onChange={setExpandedKeywords} label="AI-Expanded Keywords (edit or remove)" />}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Input label="Target Location" value={location} onChange={(e) => setLocation(e.target.value)} id="discovery-location" />
            <Input label="From Date" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} id="discovery-date-from" />
            <Input label="To Date" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} id="discovery-date-to" />
          </div>
          <div className="w-32">
            <Input label="Max Tweets" type="number" value={maxResults} onChange={(e) => setMaxResults(Number(e.target.value))} min={10} max={1000} id="discovery-max-results" />
          </div>
          <label className="flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/10 px-4 py-3 cursor-pointer">
            <input
              type="checkbox"
              checked={dummyMode}
              onChange={(e) => setDummyMode(e.target.checked)}
              className="mt-1 rounded border-slate-600 bg-slate-800 text-amber-400 focus:ring-amber-400"
            />
            <span>
              <span className="block text-sm font-medium text-amber-200">Dummy Mode</span>
              <span className="block text-xs text-amber-100/70">Return seeded sample users so we can test discovery, enrichment, export, and micro-influencer selection without hitting the live Twitter API.</span>
            </span>
          </label>
          <Button onClick={() => searchMutation.mutate()} loading={searchMutation.isPending} disabled={allKeywords.length === 0 || !location} size="lg">
            <Search size={16} />
            {searchMutation.isPending
              ? dummyMode ? 'Simulating Discovery...' : 'Searching and Profiling...'
              : dummyMode ? 'Run Dummy Discovery' : 'Discover and Profile Users'}
          </Button>
        </div>
      </Card>

      {results && (
        <div className="space-y-4">
          {results.dummy_mode && (
            <Card className="border-amber-500/25 bg-amber-500/10">
              <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                <div>
                  <CardTitle className="text-base text-amber-100">Simulation Output</CardTitle>
                  <p className="mt-1 text-sm text-amber-100/75">
                    These users, scores, and tweets are generated sample data for workflow testing. Export, print, and shared-followings analysis will still work normally against this simulated run.
                  </p>
                </div>
                <div className="text-xs uppercase tracking-[0.18em] text-amber-200/80">
                  Test Mode Active
                </div>
              </div>
            </Card>
          )}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <StatTile label="Users Found" value={results.total_users_found} color="text-slate-100" />
            <StatTile label="Profiled" value={results.profiled_users_count} color="text-sky-400" />
            <StatTile label="High-Value" value={results.high_value_users_found} color="text-emerald-400" />
            <StatTile label="Tweets Scanned" value={results.total_tweets_scanned} color="text-amber-400" />
          </div>

          <Card>
            <div className="flex items-center justify-between mb-4 gap-3 flex-wrap print:hidden">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Users size={18} className="text-sky-400" />
                  Profiled Users
                  {results.dummy_mode && (
                    <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium uppercase tracking-wide text-amber-200">
                      Dummy Data
                    </span>
                  )}
                </CardTitle>
                <p className="text-xs text-slate-500 mt-1">Use the manual followers/following columns below to enrich the list before export and micro-influencer analysis.</p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <label className="flex items-center gap-2 text-sm text-slate-400 cursor-pointer">
                  <input type="checkbox" checked={selectedUsers.size === results.users.length && results.users.length > 0} onChange={toggleSelectAll} className="rounded border-slate-600 bg-slate-700 text-brand-600 focus:ring-brand-500" />
                  Select all
                </label>
                <Button variant="secondary" size="sm" onClick={handleExportCsv}><Download size={14} />Export CSV</Button>
                <Button variant="secondary" size="sm" onClick={handlePrint}><Printer size={14} />Print</Button>
                <Button variant="secondary" size="sm" onClick={() => sharedFollowingsMutation.mutate()} loading={sharedFollowingsMutation.isPending} disabled={selectedUsers.size < 2}><Users size={14} />Analyze Shared Followings</Button>
                <Button variant="primary" size="sm" onClick={() => saveMutation.mutate()} loading={saveMutation.isPending} disabled={selectedUsers.size === 0}><Save size={14} />Save {selectedUsers.size > 0 ? `(${selectedUsers.size})` : ''} to Profiles</Button>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-xs text-slate-500 border-b border-slate-700">
                    <th className="pb-2 font-medium w-8 print:hidden"></th>
                    <th className="pb-2 font-medium">User</th>
                    <th className="pb-2 font-medium">Type</th>
                    <th className="pb-2 font-medium">Location</th>
                    <th className="pb-2 font-medium text-right">Followers</th>
                    <th className="pb-2 font-medium text-right">High-Value</th>
                    <th className="pb-2 font-medium print:hidden w-8"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/50">
                  {results.users.map((user, idx) => (
                    <UserRow
                      key={user.platform_user_id}
                      user={user}
                      selected={selectedUsers.has(idx)}
                      expanded={expandedRows.has(idx)}
                      selectedAsMicroInfluencer={selectedMicroInfluencers.has(user.username.toLowerCase())}
                      manualDraft={manualDrafts[idx] ?? createManualDraft(user)}
                      manualSaving={manualEnrichmentMutation.isPending && savingManualIndex === idx}
                      onToggleSelect={() => toggleUser(idx)}
                      onToggleExpand={() => setExpandedRows((prev) => {
                        const next = new Set(prev)
                        next.has(idx) ? next.delete(idx) : next.add(idx)
                        return next
                      })}
                      onManualDraftChange={(patch) => updateManualDraft(idx, patch)}
                      onSaveManual={() => manualEnrichmentMutation.mutate({ userIndex: idx })}
                    />
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <Card className="print:hidden">
            <div className="flex items-center justify-between gap-4 flex-wrap mb-4">
              <div>
                <CardTitle className="flex items-center gap-2"><Star size={18} className="text-amber-400" />Shared Followings Workbench</CardTitle>
                <p className="text-xs text-slate-500 mt-1">Select overlapping followed accounts that best fit as micro-influencers for your target audience.</p>
              </div>
              <Button variant="primary" size="sm" onClick={() => saveMicroInfluencersMutation.mutate()} loading={saveMicroInfluencersMutation.isPending} disabled={selectedMicroInfluencers.size === 0}>
                <Save size={14} />
                Save Selections ({selectedMicroInfluencers.size})
              </Button>
            </div>

            {sharedFollowings ? (
              <div className="space-y-4">
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <StatTile label="Analyzed Users" value={sharedFollowings.analyzed_user_handles.length} color="text-slate-100" />
                  <StatTile label="Overlap Candidates" value={sharedFollowings.total_candidates} color="text-sky-400" />
                  <StatTile label="Selected Micro-Influencers" value={selectedMicroInfluencers.size} color="text-emerald-400" />
                </div>
                {sharedFollowings.candidates.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-slate-500 border-b border-slate-700">
                          <th className="pb-2 font-medium w-8"></th>
                          <th className="pb-2 font-medium">Candidate</th>
                          <th className="pb-2 font-medium text-right">Overlap</th>
                          <th className="pb-2 font-medium text-right">Followers</th>
                          <th className="pb-2 font-medium text-right">Fit</th>
                          <th className="pb-2 font-medium">Reasons</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-700/50">
                        {sharedFollowings.candidates.map((candidate) => (
                          <SharedFollowingRow
                            key={candidate.username}
                            candidate={candidate}
                            selected={selectedMicroInfluencers.has(candidate.username)}
                            onToggle={() => setSelectedMicroInfluencers((prev) => {
                              const next = new Set(prev)
                              next.has(candidate.username) ? next.delete(candidate.username) : next.add(candidate.username)
                              return next
                            })}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">No overlap candidates yet. Add manual following lists for at least two selected users and run the analysis again.</p>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-500">Select at least two users, enrich their following lists manually, and run the shared-followings analysis.</p>
            )}
          </Card>
        </div>
      )}
    </div>
  )
}
