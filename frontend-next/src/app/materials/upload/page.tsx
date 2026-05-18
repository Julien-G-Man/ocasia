'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import AppLayout from '@/components/AppLayout';
import { materialsService } from '@/services/materials';
import { Upload, FileText, X } from 'lucide-react';
import Link from 'next/link';
import { toast } from 'sonner';


const SUBJECTS = ['Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science', 'History', 'Literature', 'Other'];

export default function MaterialUploadPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading } = useAuth();

  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [subject, setSubject] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    if (f.size > 50 * 1024 * 1024) { toast.error('File must be under 50MB.'); return; }
    setFile(f);
    if (!title) setTitle(f.name.replace(/\.[^.]+$/, ''));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) { toast.error('Please select a file.'); return; }
    setUploading(true);
    setProgress(0);
    try {
      await materialsService.upload({ title, description, subject, file }, setProgress);
      router.push('/materials');
    } catch (err) {
      toast.error(typeof err === 'string' ? err : 'Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  return (
    <AppLayout title="Upload Material">
      <div className="container mx-auto max-w-xl px-4 py-8 flex flex-col gap-6">
        <div className="flex items-center gap-3">
          <Link href="/materials" className="text-sm text-muted-foreground hover:text-foreground transition-colors">
            &larr; Materials
          </Link>
        </div>
        <div>
          <h1 className="text-2xl font-bold">Upload Material</h1>
          <p className="text-muted-foreground">Share study materials with the community.</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-5">
          {/* File Drop Zone */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="rounded-xl border-2 border-dashed border-border hover:border-primary/50 bg-card p-8 text-center cursor-pointer transition-colors flex flex-col items-center gap-3"
          >
            {file ? (
              <>
                <FileText size={32} className="text-primary" />
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{file.name}</span>
                  <button type="button" onClick={(e) => { e.stopPropagation(); setFile(null); }}
                    className="p-0.5 rounded hover:bg-accent transition-colors">
                    <X size={14} />
                  </button>
                </div>
                <span className="text-xs text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
              </>
            ) : (
              <>
                <Upload size={32} className="text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">Click to upload a file</p>
                  <p className="text-xs text-muted-foreground mt-1">PDF, DOCX, PPTX, TXT — max 50MB</p>
                </div>
              </>
            )}
          </div>
          <input ref={fileInputRef} type="file" accept=".pdf,.docx,.pptx,.txt" className="hidden" onChange={handleFileChange} />

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Title</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} required placeholder="e.g. Organic Chemistry Notes"
              className="px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring" />
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Subject</label>
            <select value={subject} onChange={(e) => setSubject(e.target.value)}
              className="px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring">
              <option value="">— Select subject —</option>
              {SUBJECTS.map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>

          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium">Description (optional)</label>
            <textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3}
              placeholder="Brief description of the material..."
              className="px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring resize-none" />
          </div>

          {uploading && (
            <div className="flex flex-col gap-1.5">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>Uploading...</span><span>{progress}%</span>
              </div>
              <div className="h-1.5 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary transition-all duration-200" style={{ width: `${progress}%` }} />
              </div>
            </div>
          )}

          <button type="submit" disabled={uploading || !file}
            className="w-full py-3 rounded-md bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-60">
            {uploading ? `Uploading (${progress}%)...` : 'Upload Material'}
          </button>
        </form>
      </div>
    </AppLayout>
  );
}
