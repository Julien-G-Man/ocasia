'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import AppLayout from '@/components/AppLayout';
import djangoApi from '@/services/api';
import { Upload, Keyboard, ListOrdered, Pen, Clock, BarChart2, Loader2, AlertCircle, FileText, Sparkles, Info } from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

const SUBJECTS = [
  'Mathematics', 'Computer Science', 'Engineering', 'Biology',
  'Chemistry', 'Physics', 'English', 'History', 'Geography', 'Economics',
];
const QUIZ_PREFILL_KEY = 'lamla_quiz_prefill';

export default function CreateQuizPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<'file' | 'text'>('file');
  const [subject, setSubject] = useState('');
  const [customSubject, setCustomSubject] = useState('');
  const [isOther, setIsOther] = useState(false);
  const [studyText, setStudyText] = useState('');
  const [numMcq, setNumMcq] = useState(7);
  const [numShort, setNumShort] = useState(3);
  const [quizTime, setQuizTime] = useState(10);
  const [difficulty, setDifficulty] = useState('random');
  const [isExtracting, setIsExtracting] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [fileDisplay, setFileDisplay] = useState('');
  const [sourceFilename, setSourceFilename] = useState('');
  const [pendingExtractedText, setPendingExtractedText] = useState('');
  const [errors, setErrors] = useState<string[]>([]);

  const fileRef = useRef<HTMLInputElement>(null);
  const generateAbortRef = useRef<AbortController | null>(null);
  const latestStudyTextRef = useRef('');
  const isProcessing = isExtracting || isGenerating;

  useEffect(() => {
    latestStudyTextRef.current = studyText;
  }, [studyText]);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) router.push('/auth/login');
  }, [isLoading, isAuthenticated, router]);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(QUIZ_PREFILL_KEY);
      if (!raw) return;
      const parsed = JSON.parse(raw) as { studyText?: string; subject?: string };

      const prefillText = parsed.studyText?.trim();
      if (prefillText) {
        setStudyText(prefillText);
        setActiveTab('text');
      }

      const prefillSubject = parsed.subject?.trim();
      if (prefillSubject) {
        if (SUBJECTS.includes(prefillSubject)) {
          setSubject(prefillSubject);
          setCustomSubject('');
          setIsOther(false);
        } else {
          setSubject('Other');
          setCustomSubject(prefillSubject);
          setIsOther(true);
        }
      }

      if (prefillText || prefillSubject) {
        toast.success('Imported content from AI Tutor. You can edit before generating.');
      }
    } catch {
      // Ignore malformed prefill payload
    } finally {
      localStorage.removeItem(QUIZ_PREFILL_KEY);
    }
  }, []);

  const handleSubjectChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const val = e.target.value;
    setSubject(val);
    setIsOther(val === 'Other');
  };

  const handleFileChange = async (file: File) => {
    if (isExtracting) return;
    setSourceFilename(file.name);
    setFileDisplay(`${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)`);
    setIsExtracting(true);
    setPendingExtractedText('');
    const fd = new FormData();
    fd.append('slide_file', file);
    try {
      const res = await djangoApi.post('/quiz/ajax-extract-text/', fd, {
        timeout: 0, // no timeout — AI text extraction can be slow
      });
      const extractedText = res.data.text as string;
      if (extractedText) {
        if (!latestStudyTextRef.current.trim()) {
          setStudyText(extractedText);
          setActiveTab('text');
          toast.success('Text extracted successfully!');
        } else {
          setPendingExtractedText(extractedText);
          toast.success('Text extracted. Choose how to insert it.');
        }
      }
    } catch {
      toast.error('Failed to extract text from file.');
    } finally {
      setIsExtracting(false);
    }
  };

  const validate = () => {
    const errs: string[] = [];
    const finalSubject = isOther ? customSubject.trim() : subject;
    if (!finalSubject) errs.push('Please select or enter a subject');
    if (activeTab === 'text') {
      if (studyText.trim().length < 30) errs.push('Please enter at least 30 characters of text');
      if (studyText.length > 50000) errs.push('Text is too long (max 50,000 characters)');
    } else {
      if (!fileRef.current?.files?.length && !studyText) errs.push('Please upload a file');
    }
    if (numMcq <= 0 && numShort <= 0) errs.push('Select at least one question type');
    if (numMcq > 20) errs.push('Maximum 20 MCQ questions');
    if (numShort > 10) errs.push('Maximum 10 Short Answer questions');
    setErrors(errs);
    return errs.length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;
    const finalSubject = isOther ? customSubject.trim() : subject;
    const controller = new AbortController();
    generateAbortRef.current = controller;
    setIsGenerating(true);
    try {
      const res = await djangoApi.post('/quiz/generate/', {
        subject: finalSubject,
        extractedText: studyText,
        num_mcq: numMcq,
        num_short: numShort,
        quiz_time: quizTime,
        difficulty,
        source_filename: sourceFilename,
      }, {
        signal: controller.signal,
      });
      localStorage.setItem('current_quiz', JSON.stringify(res.data));
      generateAbortRef.current = null;
      router.push('/quiz/play');
    } catch (err: unknown) {
      const maybeErr = err as { code?: string; name?: string; response?: { data?: { error?: string } } };
      if (maybeErr?.code === 'ERR_CANCELED' || maybeErr?.name === 'CanceledError') {
        toast.info('Quiz generation canceled. You can update your settings and try again.');
      } else {
        toast.error(maybeErr?.response?.data?.error || 'Generation failed. Please try again.');
      }
      generateAbortRef.current = null;
      setIsGenerating(false);
    }
  };

  const handleCancelGeneration = () => {
    if (!isGenerating) return;
    generateAbortRef.current?.abort();
  };

  useEffect(() => {
    return () => {
      generateAbortRef.current?.abort();
    };
  }, []);

  const handleClear = () => {
    if (!confirm('Clear all fields?')) return;
    setSubject(''); setCustomSubject(''); setIsOther(false);
    setStudyText(''); setFileDisplay(''); setSourceFilename('');
    setPendingExtractedText('');
    setNumMcq(7); setNumShort(3); setQuizTime(10); setDifficulty('random');
    setErrors([]);
    if (fileRef.current) fileRef.current.value = '';
    toast.info('Form cleared');
  };

  const insertExtractedText = (mode: 'replace' | 'append') => {
    if (!pendingExtractedText) return;
    setStudyText(prev => {
      if (mode === 'append' && prev.trim()) return `${prev}\n\n${pendingExtractedText}`;
      return pendingExtractedText;
    });
    setActiveTab('text');
    setPendingExtractedText('');
    toast.success(mode === 'append' ? 'Extracted text appended.' : 'Extracted text inserted.');
  };

  const discardExtractedText = () => {
    setPendingExtractedText('');
    toast.info('Extracted text discarded.');
  };

  return (
    <AppLayout title="Create Quiz">
      {/* Generating overlay */}
      {isGenerating && (
        <div className="fixed inset-0 z-50 bg-black/45 dark:bg-black/60 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-background/95 backdrop-blur-xl border border-border rounded-2xl shadow-2xl w-full max-w-sm flex flex-col overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                <Sparkles size={16} className="text-primary" />
              </div>
              <div>
                <p className="text-sm font-semibold">Generating Quiz</p>
                <p className="text-xs text-muted-foreground">This may take a few seconds</p>
              </div>
            </div>
            <div className="px-5 py-6 flex flex-col items-center gap-4">
              <Loader2 size={36} className="animate-spin text-primary" />
              <p className="text-sm text-muted-foreground text-center">
                AI is creating your questions…
              </p>
              <div className="w-full h-1.5 rounded-full bg-border overflow-hidden">
                <div className="h-full gradient-bg rounded-full animate-pulse w-2/3" />
              </div>
              <button
                type="button"
                onClick={handleCancelGeneration}
                className="mt-1 px-4 py-2 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-surface-hover transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-2xl mx-auto px-4 sm:px-6 py-8 flex flex-col gap-6">
        <div>
          <h1 className="text-2xl font-bold">Quiz Mode</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Upload your study materials or paste content to create customised quiz questions with AI.
          </p>
        </div>

        {isExtracting && (
          <div className="rounded-xl border border-border bg-background/95 backdrop-blur-xl px-4 py-3 flex items-center gap-3">
            <Loader2 size={16} className="animate-spin text-primary shrink-0" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-foreground">Extracting text in background…</p>
              {fileDisplay && <p className="text-xs text-muted-foreground truncate">{fileDisplay}</p>}
            </div>
          </div>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* Subject */}
          <div className="glass rounded-xl p-5 flex flex-col gap-3">
            <label className="text-sm font-semibold flex items-center gap-2">
              <Info size={14} className="text-primary" /> Subject / Topic
            </label>
            <select
              value={subject}
              onChange={handleSubjectChange}
              className="px-3 py-2.5 rounded-lg border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
            >
              <option value="" disabled>Select a subject or topic</option>
              {SUBJECTS.map(s => <option key={s} value={s}>{s}</option>)}
              <option value="Other">Other (type your own)</option>
            </select>
            {isOther && (
              <input
                type="text"
                autoFocus
                value={customSubject}
                onChange={e => setCustomSubject(e.target.value)}
                placeholder="Type subject/topic (e.g. Quantum Mechanics)"
                className="px-3 py-2.5 rounded-lg border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow"
              />
            )}
          </div>

          {/* Tabs */}
          <div className="flex rounded-lg border border-border overflow-hidden">
            <button
              type="button"
              onClick={() => setActiveTab('file')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors',
                activeTab === 'file'
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-surface-hover'
              )}
            >
              <Upload size={14} /> Upload File
            </button>
            <button
              type="button"
              onClick={() => setActiveTab('text')}
              className={cn(
                'flex-1 flex items-center justify-center gap-2 py-2.5 text-sm font-medium transition-colors',
                activeTab === 'text'
                  ? 'bg-primary/10 text-primary'
                  : 'text-muted-foreground hover:bg-surface-hover'
              )}
            >
              <Keyboard size={14} /> Enter Text
            </button>
          </div>

          {pendingExtractedText && (
            <div className="rounded-xl border border-primary/30 bg-primary/8 px-4 py-3 flex flex-col gap-3">
              <p className="text-sm text-foreground">
                Extraction finished. You can insert the extracted text without losing your current edits.
              </p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => insertExtractedText('replace')}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium border border-primary/40 text-primary hover:bg-primary/10 transition-colors"
                >
                  Replace text
                </button>
                <button
                  type="button"
                  onClick={() => insertExtractedText('append')}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium border border-border text-foreground hover:bg-surface-hover transition-colors"
                >
                  Append text
                </button>
                <button
                  type="button"
                  onClick={discardExtractedText}
                  className="px-3 py-1.5 rounded-lg text-sm font-medium border border-border text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
                >
                  Discard
                </button>
              </div>
            </div>
          )}

          {activeTab === 'file' ? (
            <div
              className="glass rounded-xl p-6 flex flex-col items-center gap-4 border-2 border-dashed border-border hover:border-primary/50 transition-colors cursor-pointer"
              onDragOver={e => { e.preventDefault(); e.currentTarget.classList.add('border-primary'); }}
              onDragLeave={e => e.currentTarget.classList.remove('border-primary')}
              onDrop={e => {
                if (isExtracting) return;
                e.preventDefault();
                e.currentTarget.classList.remove('border-primary');
                const file = e.dataTransfer.files[0];
                if (file) handleFileChange(file);
              }}
              onClick={() => { if (!isExtracting) fileRef.current?.click(); }}
            >
              <div className="w-14 h-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                <FileText size={24} className="text-primary" />
              </div>
              <div className="text-center">
                <p className="font-medium">Upload your study materials</p>
                <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, PPT, PPTX, or TXT</p>
              </div>
              <input
                ref={fileRef}
                type="file"
                className="hidden"
                accept=".pdf,.docx,.ppt,.pptx,.txt"
                onChange={e => { const f = e.target.files?.[0]; if (f && !isExtracting) handleFileChange(f); }}
              />
              <button
                type="button"
                disabled={isExtracting}
                className="px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors disabled:opacity-60"
                onClick={e => { e.stopPropagation(); if (!isExtracting) fileRef.current?.click(); }}
              >
                {isExtracting ? 'Extracting…' : 'Select file'}
              </button>
              {fileDisplay && (
                <p className="text-xs text-muted-foreground">{fileDisplay}</p>
              )}
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              <textarea
                value={studyText}
                onChange={e => setStudyText(e.target.value)}
                rows={9}
                placeholder="Paste your study materials here…"
                className="px-4 py-3 rounded-xl border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/50 transition-shadow resize-none placeholder:text-muted-foreground"
              />
              <div className="text-xs text-muted-foreground text-right">
                <span className={studyText.length > 50000 ? 'text-destructive font-medium' : ''}>
                  {studyText.length.toLocaleString()}
                </span>{' '}/ 50,000
              </div>
            </div>
          )}

          {/* Settings */}
          <div className="glass rounded-xl p-5 flex flex-col gap-4">
            <p className="text-sm font-semibold">Settings</p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <ListOrdered size={12} /> MCQ Questions
                </label>
                <input
                  type="number" min={0} max={20} value={numMcq}
                  onChange={e => setNumMcq(Number(e.target.value))}
                  className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-center font-semibold focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <Pen size={12} /> Short Answer
                </label>
                <input
                  type="number" min={0} max={10} value={numShort}
                  onChange={e => setNumShort(Number(e.target.value))}
                  className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-center font-semibold focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <Clock size={12} /> Time (min)
                </label>
                <input
                  type="number" min={1} max={120} value={quizTime}
                  onChange={e => setQuizTime(Math.max(1, Number(e.target.value) || 10))}
                  className="px-3 py-2 rounded-lg border border-border bg-surface text-sm text-center font-semibold focus:outline-none focus:ring-2 focus:ring-primary/50"
                />
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                  <BarChart2 size={12} /> Difficulty
                </label>
                <select
                  value={difficulty}
                  onChange={e => setDifficulty(e.target.value)}
                  className="px-2 py-2 rounded-lg border border-border bg-surface text-sm focus:outline-none focus:ring-2 focus:ring-primary/50"
                >
                  <option value="random">Random</option>
                  <option value="easy">Easy</option>
                  <option value="medium">Medium</option>
                  <option value="hard">Hard</option>
                </select>
              </div>
            </div>
          </div>

          {/* Errors */}
          {errors.length > 0 && (
            <div className="flex flex-col gap-2">
              {errors.map((err, i) => (
                <div key={i} className="flex items-start gap-2.5 px-4 py-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm">
                  <AlertCircle size={15} className="mt-0.5 shrink-0" /> {err}
                </div>
              ))}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={isProcessing}
              className="flex-1 py-3 rounded-xl gradient-bg text-white font-semibold hover:opacity-90 transition-opacity disabled:opacity-60 flex items-center justify-center gap-2 glow-blue-sm"
            >
              {isGenerating
                ? <><Loader2 size={16} className="animate-spin" /> Generating…</>
                : <><Sparkles size={16} /> Generate Questions</>}
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="px-5 py-3 rounded-xl border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
            >
              Clear
            </button>
          </div>
        </form>
      </div>

    </AppLayout>
  );
}
