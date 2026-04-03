import { useState } from 'react'
import { Card } from './ui/Card'
import { Button } from './ui/Button'
import { Input } from './ui/Input'
import { CheckCircle2, XCircle, FileVideo, Loader2 } from 'lucide-react'
import { tiktokApi, AuditReport } from '../api/tiktok'
import toast from 'react-hot-toast'

export function TikTokAuditor() {
  const [file, setFile] = useState<File | null>(null)
  const [caption, setCaption] = useState('')
  const [primaryKeyword, setPrimaryKeyword] = useState('')
  const [secondaryKeywords, setSecondaryKeywords] = useState('')
  
  const [isAuditing, setIsAuditing] = useState(false)
  const [report, setReport] = useState<AuditReport | null>(null)

  const handleAudit = async () => {
    if (!file) {
      toast.error('Please select a video file first')
      return
    }
    
    setIsAuditing(true)
    setReport(null)
    
    try {
      const formData = new FormData()
      formData.append('video', file)
      formData.append('caption', caption)
      formData.append('primary_keyword', primaryKeyword)
      formData.append('secondary_keywords', secondaryKeywords)
      
      const res = await tiktokApi.runAudit(formData)
      setReport(res.report)
      toast.success('Audit completed!')
    } catch (err: any) {
      console.error(err)
      toast.error(err.response?.data?.detail || 'Failed to run audit')
    } finally {
      setIsAuditing(false)
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Upload Form */}
      <Card className="p-6 bg-slate-900 border-slate-800">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Run Legibility Audit</h2>
        
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">
              Video File
            </label>
            <div className="border-2 border-dashed border-slate-700 rounded-lg p-6 flex flex-col items-center justify-center bg-slate-800/50">
              <FileVideo className="h-8 w-8 text-slate-500 mb-2" />
              <input 
                type="file" 
                accept="video/mp4,video/quicktime"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="text-sm text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-cyan-500/10 file:text-cyan-400 hover:file:bg-cyan-500/20"
              />
            </div>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-400 mb-1">
              Caption
            </label>
            <Input 
              value={caption} 
              onChange={e => setCaption(e.target.value)} 
              placeholder="Post caption..." 
            />
          </div>
          
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1">
                Primary Keyword
              </label>
              <Input 
                value={primaryKeyword} 
                onChange={e => setPrimaryKeyword(e.target.value)} 
                placeholder="e.g. nike shoes" 
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-400 mb-1">
                Secondary Keywords
              </label>
              <Input 
                value={secondaryKeywords} 
                onChange={e => setSecondaryKeywords(e.target.value)} 
                placeholder="e.g. running, fitness (comma sep)" 
              />
            </div>
          </div>
          
          <Button 
            className="w-full bg-cyan-600 hover:bg-cyan-500" 
            onClick={handleAudit}
            disabled={isAuditing || !file}
          >
            {isAuditing ? (
               <><Loader2 className="mr-2 h-4 w-4 animate-spin" /> Processing (takes ~20s)</>
            ) : (
               'Start Audit'
            )}
          </Button>
        </div>
      </Card>
      
      {/* Report Summary */}
      <Card className="p-6 bg-slate-900 border-slate-800">
        <h2 className="text-lg font-semibold text-slate-100 mb-4">Audit Scorecard</h2>
        
        {!report && !isAuditing && (
          <div className="h-48 flex items-center justify-center text-slate-500 border border-dashed border-slate-800 rounded-lg">
            Upload a video to see the scorecard
          </div>
        )}
        
        {isAuditing && (
          <div className="h-48 flex flex-col items-center justify-center text-cyan-500 border border-dashed border-slate-800 rounded-lg">
            <Loader2 className="h-8 w-8 animate-spin mb-4" />
            <p className="text-sm font-medium">Extracting Frames & Audio...</p>
            <p className="text-xs text-slate-500 mt-2">Running ASR + OCR analysis</p>
          </div>
        )}
        
        {report && (
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-slate-800/80 rounded-lg border border-slate-700">
              <div>
                <h3 className="font-medium text-slate-200">ASR Match (First 3s)</h3>
                <p className="text-sm text-slate-400">Primary keyword spoken early</p>
              </div>
              {report.asr_passed ? <CheckCircle2 className="text-green-500" /> : <XCircle className="text-red-500" />}
            </div>
            
            <div className="flex items-center justify-between p-4 bg-slate-800/80 rounded-lg border border-slate-700">
              <div>
                <h3 className="font-medium text-slate-200">OCR Safe Zone</h3>
                <p className="text-sm text-slate-400">On-screen text avoiding TikTok UI</p>
              </div>
              {report.ocr_passed ? <CheckCircle2 className="text-green-500" /> : <XCircle className="text-red-500" />}
            </div>
            
            <div className="flex items-center justify-between p-4 bg-slate-800/80 rounded-lg border border-slate-700">
              <div>
                <h3 className="font-medium text-slate-200">Caption Density (<span className={(report.caption_density || 0) > 0.08 ? "text-green-400" : "text-amber-400"}>{Math.round((report.caption_density || 0) * 100)}%</span>)</h3>
                <p className="text-sm text-slate-400">First 150 chars optimized</p>
              </div>
              {report.caption_passed ? <CheckCircle2 className="text-green-500" /> : <XCircle className="text-red-500" />}
            </div>
            
            {!report.asr_passed && (
               <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-lg">
                 <h4 className="text-sm font-semibold text-red-400 mb-1">Remediation: ASR Failed</h4>
                 <p className="text-xs text-slate-400">Re-record the opening narration to front-load "{primaryKeyword}".</p>
               </div>
            )}
            
            {!report.ocr_passed && (
               <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-lg">
                 <h4 className="text-sm font-semibold text-red-400 mb-1">Remediation: OCR Safe Zone</h4>
                 <p className="text-xs text-slate-400">Ensure text overlay is positioned at least 150px below the top margin.</p>
               </div>
            )}
          </div>
        )}
      </Card>
    </div>
  )
}
