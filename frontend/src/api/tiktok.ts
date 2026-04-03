import { api } from './client'

export interface AuditReport {
  asr_passed: boolean
  ocr_passed: boolean
  caption_passed: boolean
  asr_text: string
  caption_density: number
  violating_ocr_boxes: any[]
}

export interface AuditResponse {
  status: string
  report: AuditReport
}

export const tiktokApi = {
  async runAudit(data: FormData): Promise<AuditResponse> {
    return api.postForm<AuditResponse>('/tiktok/audit', data)
  },
}
