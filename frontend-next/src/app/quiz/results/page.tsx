'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import MathRenderer from '@/components/MathRenderer';
import AppLayout from '@/components/AppLayout';
import djangoApi from '@/services/api';
import { dashboardService } from '@/services/dashboard';
import {
  CheckCircle2, XCircle, MinusCircle, Trophy, RotateCcw, Share2,
  FileText, FileDown, Star,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';

const downloadAsText = (results: any) => {
  const { score, total, score_percent, details, subject, difficulty } = results;
  const timestamp = new Date().toLocaleString();
  let content = 'QUIZ RESULTS REPORT\n';
  content += `${'='.repeat(60)}\n\n`;
  content += `Subject: ${subject || 'Quiz'}\n`;
  if (difficulty) content += `Difficulty: ${difficulty}\n`;
  content += `Date: ${timestamp}\n`;
  content += `Score: ${score}/${total} (${Number(score_percent).toFixed(1)}%)\n`;
  content += `${'='.repeat(60)}\n\nDETAILED ANSWER REVIEW\n${'-'.repeat(60)}\n\n`;

  (details || []).forEach((d: any, i: number) => {
    content += `Q${i + 1}. ${d.question}\n`;
    content += `Your Answer: ${d.user_answer || '(Unanswered)'}\n`;
    content += `Correct Answer: ${d.correct_answer}\n`;
    content += `Status: ${d.is_correct ? 'CORRECT' : 'INCORRECT'}\n`;
    if (d.reasoning) content += `Evaluation: ${d.reasoning}\n`;
    if (d.explanation) content += `Explanation: ${d.explanation}\n`;
    content += '\n';
  });

  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `Quiz_Results_${(subject || 'Quiz').replace(/\s+/g, '_')}.txt`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(link.href);
};

const downloadFromApi = async (results: any, format: 'pdf' | 'docx') => {
  try {
    const res = await djangoApi.post('/quiz/download/', { results, format }, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const link = document.createElement('a');
    link.href = url;
    link.download = `Quiz_Results_${(results.subject || 'Quiz').replace(/\s+/g, '_')}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  } catch {
    toast.error(`Failed to download ${format.toUpperCase()}. Please try another format.`);
  }
};

export default function QuizResultsPage() {
  const router = useRouter();
  const [results, setResults] = useState<any>(null);
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [feedbackSent, setFeedbackSent] = useState(false);
  const [feedbackMsg, setFeedbackMsg] = useState('');

  useEffect(() => {
    const stored = localStorage.getItem('quiz_results');
    if (!stored) { router.push('/quiz/create'); return; }
    setResults(JSON.parse(stored));
  }, [router]);

  useEffect(() => {
    if (!results) return;
    dashboardService.getQuizFeedbackSummary('quiz_results')
      .then(data => {
        if (data?.user_rating) {
          setRating(Number(data.user_rating));
          setFeedbackSent(true);
          setFeedbackMsg('Your rating is saved.');
        }
      })
      .catch(() => {});
  }, [results]);

  const submitFeedback = async (val: number) => {
    try {
      const payload = await dashboardService.submitQuizFeedback({ rating: val, source: 'quiz_results' });
      setRating(Number(payload?.rating || val));
      setFeedbackSent(true);
      setFeedbackMsg('Thanks! Your rating was saved.');
    } catch {
      setRating(val);
      setFeedbackSent(true);
      setFeedbackMsg('Saved locally. Could not sync right now.');
    }
  };

  const handleShare = () => {
    const shareData = {
      title: 'Lamla AI Quiz',
      text: `I scored ${results.score}/${results.total} on the ${results.subject || 'Lamla AI'} quiz!`,
      url: window.location.origin,
    };
    if (navigator.share) {
      navigator.share(shareData);
    } else {
      navigator.clipboard.writeText(`${shareData.text} ${shareData.url}`);
      toast.success('Link copied to clipboard.');
    }
  };

  if (!results) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <p className="text-muted-foreground">Loading results…</p>
      </div>
    );
  }

  // Support both old API format (details) and new (questions/results)
  const { score, total, score_percent, subject, difficulty } = results;
  const pct = Number(score_percent ?? score ?? 0);
  const details: any[] = results.details || results.questions || results.results || [];

  const scoreBadgeClass =
    pct >= 80 ? 'text-green-400' : pct >= 50 ? 'text-yellow-400' : 'text-red-400';
  const performanceLabel =
    pct >= 80 ? 'Excellent Work 🎉' : pct >= 50 ? 'Good Effort' : 'Time to Review';

  // SVG score ring
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (pct / 100) * circumference;

  return (
    <AppLayout title="Quiz Results">
      <div className="max-w-2xl mx-auto w-full px-4 py-8 flex flex-col gap-6">

        {/* Score card */}
        <div className="glass rounded-2xl p-8 flex flex-col items-center text-center gap-4">
          <div className="relative w-36 h-36">
            <svg width="144" height="144" className="-rotate-90">
              <circle cx="72" cy="72" r={radius} fill="none" stroke="oklch(0.24 0.025 255)" strokeWidth="10" />
              <circle
                cx="72" cy="72" r={radius}
                fill="none" stroke="url(#scoreGrad)"
                strokeWidth="10" strokeLinecap="round"
                strokeDasharray={circumference}
                strokeDashoffset={dashOffset}
                style={{ transition: 'stroke-dashoffset 1s ease' }}
              />
              <defs>
                <linearGradient id="scoreGrad" x1="0%" y1="0%" x2="100%" y2="0%">
                  <stop offset="0%" stopColor="#2563eb" />
                  <stop offset="100%" stopColor="#06b6d4" />
                </linearGradient>
              </defs>
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <span className={`text-3xl font-bold ${scoreBadgeClass}`}>{pct.toFixed(1)}%</span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Trophy size={20} className="text-primary" />
            <h1 className="text-2xl font-bold">{subject ? `${subject} Results` : 'Quiz Complete!'}</h1>
          </div>

          <p className="text-lg font-semibold text-muted-foreground">{performanceLabel}</p>

          <div className="flex items-center gap-6 text-sm">
            <div className="flex flex-col items-center gap-0.5">
              <span className="text-2xl font-bold text-foreground">{score}/{total}</span>
              <span className="text-xs text-muted-foreground">Correct</span>
            </div>
            {difficulty && (
              <div className="flex flex-col items-center gap-0.5">
                <span className="text-sm font-semibold text-foreground capitalize">{difficulty}</span>
                <span className="text-xs text-muted-foreground">Difficulty</span>
              </div>
            )}
          </div>

          {/* Progress bar */}
          <div className="w-full h-2 rounded-full bg-border overflow-hidden">
            <div
              className="h-full gradient-bg rounded-full transition-all duration-1000"
              style={{ width: `${pct}%` }}
            />
          </div>

          <div className="flex gap-3 mt-1 flex-wrap justify-center">
            <Link
              href="/quiz/create"
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg gradient-bg text-white font-semibold hover:opacity-90 transition-opacity text-sm glow-blue-sm"
            >
              <RotateCcw size={14} /> New Quiz
            </Link>
            <button
              onClick={handleShare}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-lg border border-border hover:bg-surface-hover transition-colors font-semibold text-sm"
            >
              <Share2 size={14} /> Share
            </button>
          </div>
        </div>

        {/* Downloads */}
        <div className="glass rounded-xl p-5 flex flex-col gap-3">
          <p className="text-sm font-semibold">Download Results</p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => downloadAsText(results)}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
            >
              <FileText size={14} /> TXT
            </button>
            <button
              onClick={() => downloadFromApi(results, 'pdf')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
            >
              <FileDown size={14} /> PDF
            </button>
            <button
              onClick={() => downloadFromApi(results, 'docx')}
              className="flex items-center gap-2 px-4 py-2 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
            >
              <FileDown size={14} /> DOCX
            </button>
          </div>
        </div>

        {/* Star rating */}
        <div className="glass rounded-xl p-5 flex flex-col gap-3">
          <p className="text-sm font-semibold">Rate this quiz experience</p>
          <div className="flex items-center gap-1">
            {[1, 2, 3, 4, 5].map(star => (
              <button
                key={star}
                type="button"
                disabled={feedbackSent}
                aria-label={`Rate ${star} star${star > 1 ? 's' : ''}`}
                onMouseEnter={() => !feedbackSent && setHoverRating(star)}
                onMouseLeave={() => setHoverRating(0)}
                onClick={() => !feedbackSent && submitFeedback(star)}
                className="transition-transform hover:scale-110 disabled:cursor-default"
              >
                <Star
                  size={24}
                  className={cn(
                    'transition-colors',
                    (hoverRating || rating) >= star
                      ? 'fill-yellow-400 text-yellow-400'
                      : 'text-muted-foreground'
                  )}
                />
              </button>
            ))}
          </div>
          {feedbackSent && (
            <p className="text-xs text-muted-foreground">{feedbackMsg}</p>
          )}
        </div>

        {/* Detailed review */}
        {details.length > 0 && (
          <div className="flex flex-col gap-3">
            <h2 className="font-bold text-lg">Detailed Answer Review</h2>
            {details.map((d: any, i: number) => {
              const isCorrect = d.is_correct ?? d.correct;
              const isUnanswered = !d.user_answer && !d.your_answer;
              return (
                <div
                  key={i}
                  className={cn(
                    'glass rounded-xl p-4 flex flex-col gap-3 border-l-4',
                    isCorrect ? 'border-l-green-500' : isUnanswered ? 'border-l-border' : 'border-l-red-500'
                  )}
                >
                  <div className="flex items-start gap-3">
                    {isCorrect
                      ? <CheckCircle2 size={16} className="text-green-400 mt-0.5 shrink-0" />
                      : isUnanswered
                      ? <MinusCircle size={16} className="text-muted-foreground mt-0.5 shrink-0" />
                      : <XCircle size={16} className="text-red-400 mt-0.5 shrink-0" />}
                    <p className="text-sm font-medium flex-1">
                      <span className="text-muted-foreground mr-1">Q{i + 1}.</span>
                      <MathRenderer text={d.question} />
                    </p>
                  </div>

                  <div className="flex flex-col gap-1.5 pl-7 text-xs">
                    <div className="flex gap-2">
                      <span className="text-muted-foreground shrink-0 w-28">Your answer</span>
                      <span className={cn(
                        'font-medium',
                        isCorrect ? 'text-green-400' : isUnanswered ? 'text-muted-foreground italic' : 'text-red-400'
                      )}>
                        {d.user_answer || d.your_answer
                          ? <MathRenderer text={d.user_answer || d.your_answer} />
                          : '(Unanswered)'}
                      </span>
                    </div>
                    <div className="flex gap-2">
                      <span className="text-muted-foreground shrink-0 w-28">Correct answer</span>
                      <span className="font-medium text-green-400 flex items-center gap-2 flex-wrap">
                        <MathRenderer text={d.correct_answer} />
                        <button
                          onClick={() => navigator.clipboard.writeText(d.correct_answer)}
                          className="text-muted-foreground hover:text-foreground border border-border rounded px-1.5 py-0.5 text-[10px] transition-colors"
                        >
                          Copy
                        </button>
                      </span>
                    </div>
                    {d.reasoning && (
                      <div className="flex gap-2">
                        <span className="text-muted-foreground shrink-0 w-28">Evaluation</span>
                        <span className="text-foreground/80"><MathRenderer text={d.reasoning} /></span>
                      </div>
                    )}
                    {d.explanation && (
                      <div className="flex gap-2">
                        <span className="text-muted-foreground shrink-0 w-28">Explanation</span>
                        <span className="text-foreground/80"><MathRenderer text={d.explanation} /></span>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        <Link
          href="/dashboard"
          className="text-center text-sm text-muted-foreground hover:text-foreground transition-colors py-2"
        >
          ← Back to Dashboard
        </Link>
      </div>
    </AppLayout>
  );
}
