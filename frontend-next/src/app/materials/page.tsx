'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/context/AuthContext';
import AppLayout from '@/components/AppLayout';
import { materialsService } from '@/services/materials';
import { Search, Upload, Download, Trash2, FileText } from 'lucide-react';
import Link from 'next/link';
import { toast } from 'sonner';

const SUBJECTS = ['', 'Mathematics', 'Physics', 'Chemistry', 'Biology', 'Computer Science', 'History', 'Literature', 'Other'];

export default function MaterialsPage() {
  const router = useRouter();
  const { isAuthenticated, isLoading, user } = useAuth();

  const [materials, setMaterials] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [subject, setSubject] = useState('');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);

  const fetchMaterials = async (q = search, sub = subject, p = 1) => {
    setLoading(true);
    try {
      const data = await materialsService.getAll({ q, subject: sub, page: p });
      const results = data.results || data.materials || data || [];
      setMaterials(p === 1 ? results : (prev: any[]) => [...prev, ...results]);
      setHasMore(!!data.next);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMaterials();
  }, [isAuthenticated]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    fetchMaterials(search, subject, 1);
  };

  const handleDownload = async (id: string | number, title: string) => {
    try {
      const url = await materialsService.download(id);
      window.open(url, '_blank');
    } catch { toast.error('Download failed.'); }
  };

  const handleDelete = async (id: string | number) => {
    if (!confirm('Delete this material?')) return;
    try {
      await materialsService.delete(id);
      setMaterials((prev) => prev.filter((m) => m.id !== id));
      toast.success('Material deleted.');
    } catch { toast.error('Delete failed.'); }
  };

  const handleExtractQuiz = async (id: string | number) => {
    try {
      const data = await materialsService.extractForQuiz(id);
      localStorage.setItem('quiz_source_text', data.text || '');
      router.push('/quiz/create');
    } catch { toast.error('Extraction failed.'); }
  };

  return (
    <AppLayout title="Study Materials">
      <div className="container mx-auto max-w-4xl px-4 py-8 flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Study Materials</h1>
            <p className="text-muted-foreground">Browse and download materials shared by the community.</p>
          </div>
          {isAuthenticated && (
            <Link href="/materials/upload" className="flex items-center gap-2 px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
              <Upload size={14} /> Upload
            </Link>
          )}
        </div>

        {/* Search & Filter */}
        <form onSubmit={handleSearch} className="flex gap-2">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search materials..."
              className="w-full pl-9 pr-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <select value={subject} onChange={(e) => setSubject(e.target.value)}
            className="px-3 py-2 rounded-md border border-input bg-background text-sm focus:outline-none focus:ring-2 focus:ring-ring">
            {SUBJECTS.map((s) => <option key={s} value={s}>{s || 'All Subjects'}</option>)}
          </select>
          <button type="submit" className="px-4 py-2 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors">
            Search
          </button>
        </form>

        {/* Materials List */}
        {loading && materials.length === 0 ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <div key={i} className="rounded-xl border border-border bg-card h-28 animate-pulse" />
            ))}
          </div>
        ) : materials.length === 0 ? (
          <div className="text-center py-16 flex flex-col items-center gap-3">
            <FileText size={40} className="text-muted-foreground" />
            <p className="text-muted-foreground">No materials found.</p>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {materials.map((m: any) => {
              const isOwner = user && (user.id === m.uploaded_by_id || user.is_admin);
              return (
                <div key={m.id} className="rounded-xl border border-border bg-card p-4 flex items-start gap-4">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center shrink-0">
                    <FileText size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-medium text-sm truncate">{m.title}</h3>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {m.subject && <span className="mr-2">{m.subject}</span>}
                      {m.file_size_display && <span className="mr-2">{m.file_size_display}</span>}
                      <span>{m.download_count ?? 0} downloads</span>
                      {m.uploaded_by && <span className="ml-2">· by {m.uploaded_by}</span>}
                    </p>
                    {m.description && <p className="text-xs text-muted-foreground mt-1 line-clamp-1">{m.description}</p>}
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button onClick={() => handleExtractQuiz(m.id)}
                      className="text-xs px-2.5 py-1 rounded-md border border-border hover:bg-accent transition-colors">
                      Quiz
                    </button>
                    <button onClick={() => handleDownload(m.id, m.title)}
                      className="p-1.5 rounded-md border border-border hover:bg-accent transition-colors">
                      <Download size={14} />
                    </button>
                    {isOwner && (
                      <button onClick={() => handleDelete(m.id)}
                        className="p-1.5 rounded-md border border-destructive/30 text-destructive hover:bg-destructive/10 transition-colors">
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {hasMore && (
          <button
            onClick={() => { const next = page + 1; setPage(next); fetchMaterials(search, subject, next); }}
            className="self-center px-6 py-2 rounded-md border border-border hover:bg-accent transition-colors text-sm font-medium"
          >
            Load More
          </button>
        )}
      </div>
    </AppLayout>
  );
}
