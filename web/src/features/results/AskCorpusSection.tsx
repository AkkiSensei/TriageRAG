import React, { useState } from 'react'
import { BookOpen, Search, AlertCircle, CheckCircle } from 'lucide-react'
import { api } from '@/lib/api'

export const AskCorpusSection: React.FC = () => {
  const [question, setQuestion] = useState('')
  const [population, setPopulation] = useState('adult')
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<{
    question: string
    answer: string
    abstained: boolean
    abstain_reason?: string
    citations: Array<{ chunk_id: string; doc_id: string; section: string; license: string; exact_quote: string }>
    generator_badge: string
  } | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleAsk = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setError(null)
    try {
      const data = await api.askCorpus({
        question: question.trim(),
        population,
        top_k: 3,
      })
      setResult(data)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to query protocol corpus')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="rounded-2xl border border-slate-200 dark:border-[#1e3840] bg-white dark:bg-[#132226] p-5 shadow-soft transition-all">
      <div className="flex items-center justify-between border-b border-slate-100 dark:border-[#1e3840] pb-3 mb-4">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-teal-50 dark:bg-teal-950/60 text-teal-700 dark:text-teal-300">
            <BookOpen className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-900 dark:text-slate-100">
              Ask-the-Corpus (Extractive Evidence Q&amp;A)
            </h3>
            <p className="text-[11px] text-slate-500 dark:text-slate-400">
              Verbatim guideline retrieval without LLM hallucination or synthetic dose generation
            </p>
          </div>
        </div>
        <span className="rounded-full bg-teal-50 dark:bg-teal-950/70 border border-teal-200 dark:border-teal-800 px-2.5 py-0.5 text-teal-800 dark:text-teal-300 font-mono font-bold text-[10px]">
          EXTRACTIVE ONLY
        </span>
      </div>

      <form onSubmit={handleAsk} className="flex flex-col sm:flex-row gap-2 mb-4">
        <div className="relative flex-1">
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question about emergency protocol management (e.g. anaphylaxis, asthma)..."
            className="w-full rounded-xl border border-slate-200 dark:border-[#1e3840] bg-slate-50 dark:bg-[#0c1618] px-3.5 py-2 text-xs text-slate-800 dark:text-slate-200 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-teal-500/20 focus:border-teal-500"
          />
        </div>

        <select
          value={population}
          onChange={(e) => setPopulation(e.target.value)}
          className="rounded-xl border border-slate-200 dark:border-[#1e3840] bg-slate-50 dark:bg-[#0c1618] px-3 py-2 text-xs font-mono text-slate-700 dark:text-slate-300 focus:outline-none"
        >
          <option value="adult">Adult</option>
          <option value="paediatric">Paediatric</option>
        </select>

        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="flex items-center justify-center gap-1.5 rounded-xl bg-teal-600 hover:bg-teal-700 disabled:opacity-50 text-white font-medium px-4 py-2 text-xs transition-colors shadow-soft-sm"
        >
          <Search className="h-3.5 w-3.5" />
          <span>{loading ? 'Searching...' : 'Ask Corpus'}</span>
        </button>
      </form>

      {error && (
        <div className="mb-4 flex items-center gap-2 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 p-3 text-xs text-rose-800 dark:text-rose-200">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {result && (
        <div className="rounded-xl border border-slate-100 dark:border-slate-800 bg-slate-50/70 dark:bg-[#0c1618]/70 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono font-bold text-slate-500">
              Question: &ldquo;{result.question}&rdquo;
            </span>
            <span className="rounded-full bg-purple-50 dark:bg-purple-950/60 border border-purple-200 dark:border-purple-800 px-2 py-0.5 text-purple-700 dark:text-purple-300 font-mono font-bold text-[10px]">
              {result.generator_badge}
            </span>
          </div>

          {result.abstained ? (
            <div className="rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-800 p-3 text-xs text-amber-900 dark:text-amber-200">
              <div className="font-bold flex items-center gap-1.5">
                <AlertCircle className="h-3.5 w-3.5 text-amber-600" />
                <span>System Abstained (Fail-Closed)</span>
              </div>
              <p className="mt-1 text-[11px] font-sans leading-relaxed">
                {result.abstain_reason || 'Evidence insufficient to provide a grounded extractive answer.'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              <div className="bg-white dark:bg-[#132226] p-3 rounded-lg border border-slate-200 dark:border-[#1e3840] text-xs font-sans text-slate-800 dark:text-slate-200 leading-relaxed shadow-soft-sm">
                <div className="flex items-center gap-1.5 text-teal-700 dark:text-teal-300 text-[11px] font-bold mb-1">
                  <CheckCircle className="h-3.5 w-3.5" />
                  <span>Verbatim Protocol Statement:</span>
                </div>
                &ldquo;{result.answer}&rdquo;
              </div>

              {result.citations.length > 0 && (
                <div className="mt-2 text-[10px] font-mono text-slate-500 dark:text-slate-400 space-y-1">
                  <div className="font-bold uppercase tracking-wider text-slate-400">Grounding Citation:</div>
                  {result.citations.map((c, i) => (
                    <div key={i} className="flex flex-wrap items-center gap-2">
                      <span className="font-bold text-teal-700 dark:text-teal-300">{c.doc_id}</span>
                      <span>&bull;</span>
                      <span>{c.section}</span>
                      <span>&bull;</span>
                      <span className="text-slate-400">{c.chunk_id}</span>
                      <span>&bull;</span>
                      <span className="text-slate-400">License: {c.license}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default AskCorpusSection
