"use client";

import { useState, useRef, useEffect, useCallback, useMemo, memo } from "react";
import { useRouter } from "next/navigation";
import AppLayout from "@/components/AppLayout";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import "katex/dist/katex.min.css";
import Image from "next/image";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import {
  Send,
  Paperclip,
  X,
  Copy,
  Check,
  Globe,
  Loader2,
  Bot,
  PanelLeft,
  Square,
  RefreshCw,
  MoreHorizontal,
  PencilLine,
  ListCollapse,
  Lightbulb,
  Layers,
  Brain,
  ChevronDown,
  Trash2,
  ThumbsUp,
  ThumbsDown,
  Download,
  Search,
  Edit2,
  FileText,
} from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import djangoApi from "@/services/api";

type SearchMode = "disabled" | "web_search" | "deep_research";

interface SourceCard {
  title: string;
  url: string;
  domain: string;
}

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  isStreaming?: boolean;
  prompt?: string;
  mode?: SearchMode;
  sources?: SourceCard[];
  error?: string | null;
  stopped?: boolean;
  rating?: "up" | "down" | null;
  attachments?: { name: string; size: number }[];
}

interface StagedFile {
  id: string;
  file: File;
}

interface ChatSession {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  searchMode: SearchMode;
  messages: Message[];
  customTitle?: boolean;
}

const DJANGO_API_URL =
  process.env.NEXT_PUBLIC_DJANGO_API_URL || "http://localhost:8000/api";
const SESSIONS_STORAGE_KEY = "lamla_ai_tutor_sessions_v1";
const FLASHCARD_PREFILL_KEY = "lamla_flashcards_prefill";
const QUIZ_PREFILL_KEY = "lamla_quiz_prefill";
const MAX_FILE_SIZE_MB = 10; // backend hard limit is 10MB
const ALLOWED_FILE_EXTENSIONS = ["pdf", "docx", "pptx", "txt"];

const suggestedPrompts = [
  "Explain this concept in simple terms",
  "Create a study plan for my exam",
  "What are the key topics I should focus on?",
  "Help me understand this formula",
];

const welcomeVariants: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: 0.45,
      ease: "easeOut" as const,
      when: "beforeChildren",
      staggerChildren: 0.08,
    },
  },
};

const welcomeItemVariants: Variants = {
  hidden: { opacity: 0, y: 14 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.35, ease: "easeOut" as const },
  },
};

const bubbleEnterVariants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.16, ease: "easeOut" as const },
  },
};

const sessionTitleFromMessages = (messages: Message[]) => {
  const firstUser = messages.find(
    (message) => message.role === "user" && message.content.trim(),
  );
  if (!firstUser) return "New Chat";
  const trimmed = firstUser.content.replace(/\s+/g, " ").trim();
  return trimmed.length > 54 ? `${trimmed.slice(0, 54)}...` : trimmed;
};

const formatSessionTime = (timestamp: number) =>
  new Date(timestamp).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

const formatFileSize = (bytes: number) => {
  if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

const formatMessageTime = (ts: number): string => {
  const d = new Date(ts);
  const now = new Date();
  const isToday =
    d.getDate() === now.getDate() &&
    d.getMonth() === now.getMonth() &&
    d.getFullYear() === now.getFullYear();
  return isToday
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], {
        weekday: "short",
        hour: "2-digit",
        minute: "2-digit",
      });
};

const extractSourcesFromText = (content: string): SourceCard[] => {
  if (!content) return [];

  const sourceMap = new Map<string, SourceCard>();
  const markdownLinkRegex = /\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g;
  const plainUrlRegex = /https?:\/\/[^\s<>"'`]+/g;

  const normalizeUrl = (rawUrl: string) => rawUrl.replace(/[),.;!?]+$/g, "");

  const pushSource = (urlValue: string, titleValue?: string) => {
    const normalized = normalizeUrl(urlValue);
    if (!normalized) return;
    try {
      const parsed = new URL(normalized);
      if (!sourceMap.has(normalized)) {
        sourceMap.set(normalized, {
          url: normalized,
          title: (titleValue || parsed.hostname).trim(),
          domain: parsed.hostname,
        });
      }
    } catch {
      // Ignore invalid URLs
    }
  };

  for (const match of content.matchAll(markdownLinkRegex)) {
    const title = match[1] || "";
    const url = match[2] || "";
    pushSource(url, title);
  }

  for (const match of content.matchAll(plainUrlRegex)) {
    const url = match[0] || "";
    pushSource(url);
  }

  return Array.from(sourceMap.values()).slice(0, 6);
};

const createEmptySession = (): ChatSession => {
  const now = Date.now();
  return {
    id: `session-${now}-${Math.random().toString(36).slice(2, 8)}`,
    title: "New Chat",
    createdAt: now,
    updatedAt: now,
    searchMode: "disabled",
    messages: [],
  };
};

const exportSessionAsMarkdown = (session: ChatSession) => {
  const date = new Date().toLocaleDateString([], {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  const lines: string[] = [`# ${session.title}`, `_Exported ${date}_`, ""];
  for (const msg of session.messages) {
    if (msg.isStreaming) continue;
    const label = msg.role === "user" ? "**You:**" : "**Lamla AI:**";
    lines.push(label, msg.content.trim(), "");
  }
  const md = lines.join("\n");
  const blob = new Blob([md], { type: "text/markdown" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${
    session.title
      .replace(/[^\w\s-]/g, "")
      .replace(/\s+/g, "-")
      .toLowerCase() || "chat"
  }.md`;
  a.click();
  URL.revokeObjectURL(url);
};

// ---------------------------------------------------------------------------
// MessageBubble — memoised so only the actively-streaming bubble re-renders
// ---------------------------------------------------------------------------

interface BubbleProps {
  message: Message;
  user: { username?: string; email?: string; profile_image?: string } | null;
  userInitials: string;
  copiedId: string | null;
  isLoading: boolean;
  isMenuOpen: boolean;
  isEditing: boolean;
  onCopy: (content: string, id: string) => void;
  onRetry: (msg: Message) => void;
  onRegenerate: (msg: Message) => void;
  onQuickAction: (
    action: "summarize" | "simple" | "flashcards" | "quiz",
    msg: Message,
  ) => void;
  onEditResend: (msg: Message) => void;
  onToggleMenu: (id: string) => void;
  onRate: (id: string, rating: "up" | "down" | null) => void;
}

const MessageBubble = memo(function MessageBubble({
  message,
  user,
  userInitials,
  copiedId,
  isLoading,
  isMenuOpen,
  isEditing,
  onCopy,
  onRetry,
  onRegenerate,
  onQuickAction,
  onEditResend,
  onToggleMenu,
  onRate,
}: BubbleProps) {
  return (
    <motion.div
      variants={bubbleEnterVariants}
      initial="hidden"
      animate="show"
      className={cn(
        "group flex items-start gap-2.5",
        message.role === "user" ? "justify-end" : "justify-start",
      )}
    >
      {message.role === "assistant" && (
        <div className="w-8 h-8 rounded-lg overflow-hidden border border-border/70 shrink-0 mt-0.5 bg-background/80">
          <Image
            src="/lamla_logo.png"
            alt="Lamla AI"
            width={32}
            height={32}
            className="w-full h-full object-cover"
          />
        </div>
      )}

      <div className="w-fit max-w-[91%] sm:max-w-[83%] space-y-1.5">
        <div
          className={cn(
            "w-fit max-w-full rounded-2xl px-3 py-2.5",
            message.role === "assistant"
              ? "border border-border/70 bg-secondary/55 rounded-tl-sm"
              : "border border-primary/35 bg-primary/14 rounded-tr-sm text-right",
          )}
        >
          {message.role === "assistant" ? (
            <div className="prose prose-sm dark:prose-invert max-w-none text-foreground/95 leading-relaxed">
              {message.isStreaming && !message.content ? (
                <div className="flex items-center gap-1 py-2 px-0.5">
                  <span
                    className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-bounce"
                    style={{ animationDelay: "0ms" }}
                  />
                  <span
                    className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-bounce"
                    style={{ animationDelay: "150ms" }}
                  />
                  <span
                    className="w-2 h-2 rounded-full bg-muted-foreground/60 animate-bounce"
                    style={{ animationDelay: "300ms" }}
                  />
                </div>
              ) : message.isStreaming ? (
                <div className="text-sm leading-relaxed whitespace-pre-wrap">
                  {message.content}
                  <span className="inline-block w-0.5 h-4 bg-primary animate-pulse ml-0.5 align-middle" />
                </div>
              ) : (
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkMath]}
                  rehypePlugins={[rehypeKatex]}
                  components={{
                    code(props) {
                      const { children, className } = props as {
                        children?: React.ReactNode;
                        className?: string;
                        inline?: boolean;
                      };
                      const inline = (props as { inline?: boolean }).inline;
                      const lang = /language-(\w+)/.exec(className || "")?.[1];
                      const codeString = String(children).replace(/\n$/, "");
                      if (!inline && lang) {
                        return (
                          <div className="relative group/codeblock">
                            <SyntaxHighlighter
                              language={lang}
                              style={oneDark}
                              PreTag="div"
                              customStyle={{
                                borderRadius: "0.5rem",
                                fontSize: "0.8rem",
                                margin: "0.5rem 0",
                              }}
                            >
                              {codeString}
                            </SyntaxHighlighter>
                            <button
                              onClick={() =>
                                navigator.clipboard.writeText(codeString)
                              }
                              className="absolute top-2 right-2 h-6 px-2 rounded text-[10px] bg-white/10 text-white/70 hover:bg-white/20 hover:text-white transition-colors opacity-0 group-hover/codeblock:opacity-100"
                            >
                              Copy
                            </button>
                          </div>
                        );
                      }
                      return <code className={className}>{children}</code>;
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              )}
            </div>
          ) : (
            <div>
              {message.attachments && message.attachments.length > 0 && (
                <div className="flex flex-col gap-1.5 mb-2">
                  {message.attachments.map((att, idx) => (
                    <div
                      key={idx}
                      className="flex items-center gap-2 px-2.5 py-2 rounded-lg border border-primary/25 bg-primary/8 text-xs"
                    >
                      <FileText size={13} className="shrink-0 text-primary/70" />
                      <div className="min-w-0">
                        <p className="font-medium truncate max-w-[200px]">
                          {att.name}
                        </p>
                        <p className="text-[10px] text-muted-foreground">
                          {formatFileSize(att.size)}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              )}
              <p className="text-sm leading-relaxed whitespace-pre-wrap">
                {message.content}
              </p>
              {isEditing && (
                <p className="text-[11px] text-primary mt-1">Editing source</p>
              )}
            </div>
          )}
        </div>

        {message.stopped && !message.error && (
          <div className="text-xs text-muted-foreground">
            Generation stopped.
          </div>
        )}

        {message.role === "assistant" &&
          message.sources &&
          message.sources.length > 0 &&
          message.mode !== "disabled" && (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-0.5">
              {message.sources.map((source) => (
                <a
                  key={`${message.id}-${source.url}`}
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="rounded-lg border border-border/70 bg-background/45 px-2.5 py-2 hover:border-primary/40 hover:bg-background/70 transition-colors"
                >
                  <p
                    className="text-xs font-medium truncate"
                    title={source.title}
                  >
                    {source.title}
                  </p>
                  <p
                    className="text-[11px] text-muted-foreground truncate"
                    title={source.domain}
                  >
                    {source.domain}
                  </p>
                </a>
              ))}
            </div>
          )}

        {!message.isStreaming && message.role === "assistant" && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <div className="relative group/copy">
              <button
                onClick={() => onCopy(message.content, message.id)}
                aria-label={copiedId === message.id ? "Copied" : "Copy"}
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border hover:bg-surface-hover transition-colors"
              >
                {copiedId === message.id ? (
                  <Check size={12} className="text-green-500" />
                ) : (
                  <Copy size={12} />
                )}
              </button>
              <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/copy:opacity-100 transition-opacity z-20">
                {copiedId === message.id ? "Copied" : "Copy"}
              </span>
            </div>
            <div className="relative group/thumbsup">
              <button
                onClick={() =>
                  onRate(message.id, message.rating === "up" ? null : "up")
                }
                aria-label="Helpful"
                className={cn(
                  "inline-flex h-7 w-7 items-center justify-center rounded-md border transition-colors",
                  message.rating === "up"
                    ? "border-primary/50 bg-primary/10 text-primary"
                    : "border-border hover:bg-surface-hover text-muted-foreground hover:text-foreground",
                )}
              >
                <ThumbsUp size={11} />
              </button>
              <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/thumbsup:opacity-100 transition-opacity z-20">
                Helpful
              </span>
            </div>
            <div className="relative group/thumbsdown">
              <button
                onClick={() =>
                  onRate(message.id, message.rating === "down" ? null : "down")
                }
                aria-label="Not helpful"
                className={cn(
                  "inline-flex h-7 w-7 items-center justify-center rounded-md border transition-colors",
                  message.rating === "down"
                    ? "border-destructive/50 bg-destructive/10 text-destructive"
                    : "border-border hover:bg-surface-hover text-muted-foreground hover:text-foreground",
                )}
              >
                <ThumbsDown size={11} />
              </button>
              <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/thumbsdown:opacity-100 transition-opacity z-20">
                Not helpful
              </span>
            </div>
            {message.error ? (
              <div className="relative group/retry">
                <button
                  onClick={() => onRetry(message)}
                  aria-label="Retry"
                  disabled={!message.prompt || isLoading}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border hover:bg-surface-hover transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} />
                </button>
                <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/retry:opacity-100 transition-opacity z-20">
                  Retry
                </span>
              </div>
            ) : (
              <div className="relative group/regenerate">
                <button
                  onClick={() => onRegenerate(message)}
                  aria-label="Regenerate"
                  disabled={!message.prompt || isLoading}
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border hover:bg-surface-hover transition-colors disabled:opacity-50"
                >
                  <RefreshCw size={12} />
                </button>
                <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/regenerate:opacity-100 transition-opacity z-20">
                  Regenerate
                </span>
              </div>
            )}
            <div className="relative group/summarize">
              <button
                onClick={() => onQuickAction("summarize", message)}
                aria-label="Summarize"
                className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border hover:bg-surface-hover transition-colors"
              >
                <ListCollapse size={12} />
              </button>
              <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/summarize:opacity-100 transition-opacity z-20">
                Summarize
              </span>
            </div>
            <div className="relative group/more" data-action-menu-root>
              <button
                onClick={() => onToggleMenu(message.id)}
                aria-label="More actions"
                className={cn(
                  "inline-flex h-7 w-7 items-center justify-center rounded-md border border-border hover:bg-surface-hover transition-colors",
                  isMenuOpen && "bg-surface-hover",
                )}
              >
                <MoreHorizontal size={12} />
              </button>
              <span className="pointer-events-none absolute top-full mt-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/more:opacity-100 transition-opacity z-20">
                More
              </span>

              {isMenuOpen && (
                <div className="absolute top-full mt-2 right-0 z-30 min-w-37 rounded-lg border border-border bg-background/95 backdrop-blur-xl shadow-xl p-1.5 flex flex-col gap-1">
                  <button
                    onClick={() => onQuickAction("simple", message)}
                    className="inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-surface-hover transition-colors"
                  >
                    <Lightbulb size={12} />
                    Explain
                  </button>
                  <button
                    onClick={() => onQuickAction("flashcards", message)}
                    className="inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-surface-hover transition-colors"
                  >
                    <Layers size={12} />
                    Flashcards
                  </button>
                  <button
                    onClick={() => onQuickAction("quiz", message)}
                    className="inline-flex items-center gap-2 rounded-md px-2 py-1.5 text-xs hover:bg-surface-hover transition-colors"
                  >
                    <Brain size={12} />
                    Quiz
                  </button>
                </div>
              )}
            </div>
            <p className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity mt-0.5 select-none">
              {formatMessageTime(message.createdAt)}
            </p>
          </div>
        )}

        {!message.isStreaming && message.role === "user" && (
          <div className="flex justify-end flex-col items-end gap-0.5">
            <div className="flex justify-end">
              <div className="relative group/edit">
                <button
                  onClick={() => onEditResend(message)}
                  aria-label="Edit & Resend"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md border border-border text-xs hover:bg-surface-hover transition-colors"
                >
                  <PencilLine size={12} />
                </button>
                <span className="pointer-events-none absolute top-full mt-1 right-0 whitespace-nowrap rounded-md border border-border bg-background/95 px-2 py-0.5 text-[10px] text-foreground opacity-0 group-hover/edit:opacity-100 transition-opacity z-20">
                  Edit & Resend
                </span>
              </div>
            </div>
            <p className="text-[10px] text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity mt-0.5 select-none text-right">
              {formatMessageTime(message.createdAt)}
            </p>
          </div>
        )}
      </div>

      {message.role === "user" && (
        <div className="w-8 h-8 rounded-lg overflow-hidden border border-border/70 shrink-0 mt-0.5 bg-background/80">
          {user?.profile_image ? (
            <Image
              src={user.profile_image}
              alt="You"
              width={32}
              height={32}
              className="w-full h-full object-cover"
            />
          ) : (
            <div className="w-full h-full grid place-items-center text-[11px] font-semibold text-foreground/85">
              {userInitials}
            </div>
          )}
        </div>
      )}
    </motion.div>
  );
});

// ---------------------------------------------------------------------------
// Main page component
// ---------------------------------------------------------------------------

export default function AITutorPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [stagedFiles, setStagedFiles] = useState<StagedFile[]>([]);
  const [fileError, setFileError] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("disabled");
  const [isLoading, setIsLoading] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [showSearchMenu, setShowSearchMenu] = useState(false);
  const [showSessionSidebar, setShowSessionSidebar] = useState(false);
  const [showDesktopSessionSidebar, setShowDesktopSessionSidebar] =
    useState(false);
  const [openActionMenuId, setOpenActionMenuId] = useState<string | null>(null);
  const [greeting, setGreeting] = useState("Hello");
  const [isOffline, setIsOffline] = useState(false);
  const [isDragActive, setIsDragActive] = useState(false);
  const [editingSourceId, setEditingSourceId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState("");
  const [sessionReady, setSessionReady] = useState(false);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [renamingSessionId, setRenamingSessionId] = useState<string | null>(
    null,
  );
  const [renameValue, setRenameValue] = useState("");
  const [showChatSearch, setShowChatSearch] = useState(false);
  const [chatSearchQuery, setChatSearchQuery] = useState("");

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const rafScrollRef = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    if (isLoading) {
      // Always follow the streaming response — no distance guard.
      // Double-RAF ensures the DOM has repainted (important on the first
      // message when the welcome screen unmounts and the list mounts).
      if (rafScrollRef.current !== null)
        cancelAnimationFrame(rafScrollRef.current);
      rafScrollRef.current = requestAnimationFrame(() => {
        rafScrollRef.current = requestAnimationFrame(() => {
          if (scrollContainerRef.current) {
            scrollContainerRef.current.scrollTop =
              scrollContainerRef.current.scrollHeight;
          }
          rafScrollRef.current = null;
        });
      });
    } else {
      // Only auto-scroll to bottom when idle if user is already near the bottom
      const distanceFromBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      if (distanceFromBottom <= 140) {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages, isLoading]);

  useEffect(() => {
    const hour = new Date().getHours();
    if (hour < 12) setGreeting("Good morning");
    else if (hour < 17) setGreeting("Good afternoon");
    else if (hour < 22) setGreeting("Good evening");
    else setGreeting("Good night");
  }, []);

  useEffect(() => {
    setIsOffline(typeof navigator !== "undefined" ? !navigator.onLine : false);
    const onOnline = () => setIsOffline(false);
    const onOffline = () => setIsOffline(true);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, []);

  useEffect(() => {
    return () => {
      abortControllerRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const onScroll = () => {
      const distanceFromBottom =
        container.scrollHeight - container.scrollTop - container.clientHeight;
      setShowScrollButton(distanceFromBottom > 140);
    };
    container.addEventListener("scroll", onScroll, { passive: true });
    return () => container.removeEventListener("scroll", onScroll);
  }, [sessionReady]);

  useEffect(() => {
    const handleOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest("[data-action-menu-root]")) return;
      setOpenActionMenuId(null);
    };
    window.addEventListener("mousedown", handleOutside);
    return () => window.removeEventListener("mousedown", handleOutside);
  }, []);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(SESSIONS_STORAGE_KEY);
      let loaded: ChatSession[] = [];
      if (raw) {
        const parsed = JSON.parse(raw) as ChatSession[];
        if (Array.isArray(parsed)) {
          loaded = parsed
            .filter((session) => session?.id && Array.isArray(session.messages))
            .map((session) => ({
              ...session,
              searchMode: session.searchMode || "disabled",
              messages: session.messages || [],
              updatedAt: session.updatedAt || Date.now(),
              createdAt: session.createdAt || Date.now(),
              title: session.title || "New Chat",
            }));
        }
      }

      if (loaded.length === 0) {
        loaded = [createEmptySession()];
      }

      loaded.sort((a, b) => b.updatedAt - a.updatedAt);
      const initial = loaded[0];
      setSessions(loaded);
      setActiveSessionId(initial.id);
      setMessages(initial.messages);
      setSearchMode(initial.searchMode);
      setSessionReady(true);
    } catch {
      const fallback = createEmptySession();
      setSessions([fallback]);
      setActiveSessionId(fallback.id);
      setMessages([]);
      setSearchMode("disabled");
      setSessionReady(true);
    }
  }, []);

  useEffect(() => {
    if (!sessionReady || !activeSessionId) return;
    setSessions((prev) =>
      prev
        .map((session) =>
          session.id === activeSessionId
            ? {
                ...session,
                messages,
                searchMode,
                updatedAt: Date.now(),
                title: session.customTitle
                  ? session.title
                  : sessionTitleFromMessages(messages),
              }
            : session,
        )
        .sort((a, b) => b.updatedAt - a.updatedAt),
    );
  }, [messages, searchMode, activeSessionId, sessionReady]);

  useEffect(() => {
    if (!sessionReady) return;
    localStorage.setItem(SESSIONS_STORAGE_KEY, JSON.stringify(sessions));
  }, [sessions, sessionReady]);

  const getAuthToken = () =>
    typeof window !== "undefined" ? localStorage.getItem("auth_token") : null;

  const validateFile = (candidate: File): string => {
    const extension = candidate.name.split(".").pop()?.toLowerCase() || "";
    if (!ALLOWED_FILE_EXTENSIONS.includes(extension)) {
      return `Unsupported file type. Use ${ALLOWED_FILE_EXTENSIONS.join(", ").toUpperCase()}.`;
    }
    if (candidate.size > MAX_FILE_SIZE_MB * 1024 * 1024) {
      return `File is too large. Max size is ${MAX_FILE_SIZE_MB}MB.`;
    }
    return "";
  };

  const handleSelectFile = (candidate: File | null) => {
    if (!candidate) return;
    const error = validateFile(candidate);
    if (error) {
      setFileError(error);
      toast.error(error);
      return;
    }
    setFileError("");
    setStagedFiles((prev) => [
      ...prev,
      {
        id: `staged-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        file: candidate,
      },
    ]);
  };

  const handleRemoveStagedFile = useCallback((id: string) => {
    setStagedFiles((prev) => prev.filter((f) => f.id !== id));
  }, []);

  const handleStopGenerating = useCallback(() => {
    if (!abortControllerRef.current) return;
    abortControllerRef.current.abort();
  }, []);

  const openSession = (id: string) => {
    if (isLoading) handleStopGenerating();
    const selected = sessions.find((session) => session.id === id);
    if (!selected) return;
    setActiveSessionId(selected.id);
    setMessages(selected.messages || []);
    setSearchMode(selected.searchMode || "disabled");
    setInput("");
    setStagedFiles([]);
    setFileError("");
    setShowSearchMenu(false);
    setShowSessionSidebar(false);
    setOpenActionMenuId(null);
    setEditingSourceId(null);
  };

  const deleteSession = (id: string) => {
    if (isLoading && activeSessionId === id) handleStopGenerating();
    setSessions((prev) => {
      const remaining = prev.filter((s) => s.id !== id);
      if (remaining.length === 0) {
        const next = createEmptySession();
        setActiveSessionId(next.id);
        setMessages([]);
        setSearchMode("disabled");
        return [next];
      }
      if (activeSessionId === id) {
        const next = remaining[0];
        setActiveSessionId(next.id);
        setMessages(next.messages);
        setSearchMode(next.searchMode);
      }
      return remaining;
    });
  };

  const createNewSession = () => {
    if (isLoading) handleStopGenerating();
    const next = createEmptySession();
    setSessions((prev) => [next, ...prev]);
    setActiveSessionId(next.id);
    setMessages([]);
    setSearchMode("disabled");
    setInput("");
    setStagedFiles([]);
    setFileError("");
    setShowSearchMenu(false);
    setShowSessionSidebar(false);
    setOpenActionMenuId(null);
    setEditingSourceId(null);
    textareaRef.current?.focus();
  };

  const handleCopy = useCallback(async (content: string, id: string) => {
    await navigator.clipboard.writeText(content);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }, []);

  const commitRename = useCallback((id: string, value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      setRenamingSessionId(null);
      return;
    }
    setSessions((prev) =>
      prev.map((s) =>
        s.id === id ? { ...s, title: trimmed, customTitle: true } : s,
      ),
    );
    setRenamingSessionId(null);
  }, []);

  const handleRate = useCallback((id: string, rating: "up" | "down" | null) => {
    setMessages((prev) =>
      prev.map((m) => (m.id === id ? { ...m, rating } : m)),
    );
  }, []);

  const streamAssistantResponse = useCallback(
    async ({
      prompt,
      includeUserMessage = true,
      targetAssistantId,
    }: {
      prompt: string;
      includeUserMessage?: boolean;
      targetAssistantId?: string;
    }) => {
      const trimmedPrompt = prompt.trim();
      if (!trimmedPrompt || isLoading) return;
      if (isOffline) {
        toast.error("You are offline. Reconnect and try again.");
        return;
      }

      setIsLoading(true);
      setShowSearchMenu(false);
  
      if (includeUserMessage) {
        setMessages((prev) => [
          ...prev,
          {
            id: `user-${Date.now()}`,
            role: "user",
            content: trimmedPrompt,
            createdAt: Date.now(),
          },
        ]);
      }

      const assistantId = targetAssistantId || `assistant-${Date.now()}`;
      if (targetAssistantId) {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content: "",
                  isStreaming: true,
                  error: null,
                  stopped: false,
                  prompt: trimmedPrompt,
                  mode: searchMode,
                  sources: [],
                }
              : message,
          ),
        );
      } else {
        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: "assistant",
            content: "",
            isStreaming: true,
            prompt: trimmedPrompt,
            mode: searchMode,
            sources: [],
            createdAt: Date.now(),
          },
        ]);
      }

      const controller = new AbortController();
      abortControllerRef.current = controller;

      try {
        const token = getAuthToken();

        const baseUrl = (djangoApi.defaults.baseURL || "").replace(/\/+$/, "");

        const res = await fetch(`${baseUrl}/chat/stream/`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Token ${token}` } : {}),
          },
          body: JSON.stringify({
            message: trimmedPrompt,
            search_mode: searchMode,
          }),
          signal: controller.signal,
        });

        if (!res.ok) {
          let detail = `Request failed (${res.status}).`;
          try {
            const errJson = await res.json();
            if (typeof errJson?.detail === "string") detail = errJson.detail;
            else if (typeof errJson?.error === "string") detail = errJson.error;
          } catch {
            // Ignore JSON parse errors
          }
          throw new Error(detail);
        }

        if (!res.body) throw new Error("No stream body");

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let accumulated = "";
        let sseMode = false;
        let buffered = "";

        // RAF-throttled chunk batching
        let rafPending = false;

        const appendChunk = (chunkText: string) => {
          if (!chunkText) return;
          accumulated += chunkText;
          if (!rafPending) {
            rafPending = true;
            requestAnimationFrame(() => {
              rafPending = false;
              const snap = accumulated;
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId ? { ...m, content: snap } : m,
                ),
              );
            });
          }
        };

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          if (!chunk) continue;

          if (chunk.includes("data:")) sseMode = true;

          if (sseMode) {
            buffered += chunk;
            const lines = buffered.split(/\r?\n/);
            buffered = lines.pop() || "";

            for (const rawLine of lines) {
              const line = rawLine.trim();
              if (!line) continue;
              if (!line.startsWith("data:")) {
                appendChunk(rawLine);
                continue;
              }
              const payload = line.slice(5).trim();
              if (!payload || payload === "[DONE]") continue;

              try {
                const parsed = JSON.parse(payload);
                const text =
                  parsed.text ||
                  parsed.content ||
                  parsed.delta ||
                  parsed.message ||
                  "";
                if (typeof text === "string") appendChunk(text);
              } catch {
                appendChunk(payload);
              }
            }
          } else {
            appendChunk(chunk);
          }
        }

        if (buffered && sseMode) {
          const remainder = buffered.trim();
          if (remainder.startsWith("data:")) {
            const payload = remainder.slice(5).trim();
            if (payload && payload !== "[DONE]") {
              try {
                const parsed = JSON.parse(payload);
                const text =
                  parsed.text ||
                  parsed.content ||
                  parsed.delta ||
                  parsed.message ||
                  "";
                if (typeof text === "string") appendChunk(text);
              } catch {
                appendChunk(payload);
              }
            }
          } else {
            appendChunk(buffered);
          }
        }

        const extractedSources = extractSourcesFromText(accumulated);
        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content: accumulated.trim()
                    ? message.content
                    : "I couldn't get a response this time. Please tap retry.",
                  isStreaming: false,
                  stopped: false,
                  error: accumulated.trim() ? null : "temporary_failure",
                  sources: extractedSources,
                }
              : message,
          ),
        );
      } catch (err: unknown) {
        const maybeErr = err as { name?: string; message?: string };
        const aborted = maybeErr?.name === "AbortError";
        const offlineNow =
          typeof navigator !== "undefined" && !navigator.onLine;
        const fallbackReply = offlineNow
          ? "I can't reach the server right now. Please reconnect and tap retry."
          : "I couldn't fetch a response right now. Please tap retry.";

        setMessages((prev) =>
          prev.map((message) =>
            message.id === assistantId
              ? {
                  ...message,
                  content: aborted
                    ? message.content
                    : message.content.trim()
                      ? message.content
                      : fallbackReply,
                  isStreaming: false,
                  stopped: aborted,
                  error: aborted ? null : "temporary_failure",
                }
              : message,
          ),
        );

        if (!aborted) {
          // toast.info("Response unavailable. Use retry.");
        }
      } finally {
        abortControllerRef.current = null;
        setIsLoading(false);
      }
    },
    [isLoading, isOffline, searchMode],
  );

  const handleFilesUpload = useCallback(
    async (userMessage: string) => {
      if (stagedFiles.length === 0 || isLoading) return;
      if (isOffline) {
        toast.error("You are offline. Reconnect and try again.");
        return;
      }

      const filesToProcess = [...stagedFiles];
      setStagedFiles([]);
      setInput("");
      setIsLoading(true);
        setShowSearchMenu(false);

      const assistantId = `assistant-${Date.now()}`;

      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          role: "user" as const,
          content: userMessage,
          createdAt: Date.now(),
          attachments: filesToProcess.map((sf) => ({
            name: sf.file.name,
            size: sf.file.size,
          })),
        },
        {
          id: assistantId,
          role: "assistant" as const,
          content: "",
          isStreaming: true,
          createdAt: Date.now(),
          prompt: userMessage,
          mode: searchMode,
        },
      ]);

      for (let i = 0; i < filesToProcess.length; i++) {
        const sf = filesToProcess[i];
        const msg = i === 0 ? userMessage : `Also analyze: ${sf.file.name}`;
        const formData = new FormData();
        formData.append("file_upload", sf.file);
        formData.append("message", msg);
        formData.append("search_mode", searchMode);

        const controller = new AbortController();
        abortControllerRef.current = controller;

        try {
          const res = await djangoApi.post("/chat/file/", formData, {
            signal: controller.signal,
            timeout: 0,
            headers: { "Content-Type": "multipart/form-data" },
          });

          const responseText =
            res.data?.response || res.data?.message || "No response received.";
          const sources = extractSourcesFromText(responseText);

          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: responseText, isStreaming: false, sources }
                : m,
            ),
          );
        } catch (err: unknown) {
          const maybeErr = err as {
            code?: string;
            name?: string;
            response?: { data?: { error?: string; detail?: string } };
          };
          const cancelled =
            maybeErr?.name === "CanceledError" ||
            maybeErr?.code === "ERR_CANCELED";
          if (!cancelled) {
            const offlineNow =
              typeof navigator !== "undefined" && !navigator.onLine;
            const backendMsg =
              maybeErr?.response?.data?.error ||
              maybeErr?.response?.data?.detail;
            const errMsg = offlineNow
              ? "You are offline. Reconnect and retry."
              : backendMsg ||
                "Sorry, I could not process your file. Please try again.";
            toast.error(errMsg);
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: errMsg, isStreaming: false, error: errMsg }
                  : m,
              ),
            );
          } else {
            toast.info("Upload stopped.");
            break;
          }
        }
      }

      abortControllerRef.current = null;
        setIsLoading(false);
    },
    [stagedFiles, isLoading, isOffline, searchMode],
  );

  const handleSend = useCallback(() => {
    const prompt = input.trim();
    if (isLoading) return;

    if (stagedFiles.length > 0) {
      const message =
        prompt || "Please analyze this file and summarize the key points.";
      void handleFilesUpload(message);
      return;
    }

    if (!prompt) return;
    setInput("");
    setEditingSourceId(null);
    void streamAssistantResponse({ prompt, includeUserMessage: true });
  }, [input, stagedFiles, isLoading, handleFilesUpload, streamAssistantResponse]);

  const handleEditResend = useCallback((message: Message) => {
    setInput(message.content);
    setEditingSourceId(message.id);
    textareaRef.current?.focus();
  }, []);

  const handleRegenerate = useCallback(
    (message: Message) => {
      if (!message.prompt) {
        toast.error("Cannot regenerate: original prompt not found.");
        return;
      }
      setEditingSourceId(null);
      void streamAssistantResponse({
        prompt: message.prompt,
        includeUserMessage: false,
        targetAssistantId: message.id,
      });
    },
    [streamAssistantResponse],
  );

  const handleRetry = useCallback(
    (message: Message) => {
      if (!message.prompt) {
        toast.error("Cannot retry: original prompt not found.");
        return;
      }
      void streamAssistantResponse({
        prompt: message.prompt,
        includeUserMessage: false,
        targetAssistantId: message.id,
      });
    },
    [streamAssistantResponse],
  );

  const handleQuickAction = useCallback(
    (
      action: "summarize" | "simple" | "flashcards" | "quiz",
      message: Message,
    ) => {
      setOpenActionMenuId(null);
      const trimmed = message.content.trim();
      if (!trimmed) return;

      if (action === "flashcards") {
        localStorage.setItem(
          FLASHCARD_PREFILL_KEY,
          JSON.stringify({
            sourceText: trimmed,
            title: "AI Tutor Deck",
            subject: "AI Tutor",
          }),
        );
        router.push("/flashcards/create");
        return;
      }

      if (action === "quiz") {
        localStorage.setItem(
          QUIZ_PREFILL_KEY,
          JSON.stringify({
            studyText: trimmed,
            subject: "AI Tutor",
          }),
        );
        router.push("/quiz/create");
        return;
      }

      const prompt =
        action === "summarize"
          ? `Summarize the following answer into 5 concise bullet points:\n\n${trimmed}`
          : `Explain the following answer in very simple terms for a beginner:\n\n${trimmed}`;

      void streamAssistantResponse({ prompt, includeUserMessage: true });
    },
    [router, streamAssistantResponse],
  );

  const handleToggleMenu = useCallback((id: string) => {
    setOpenActionMenuId((prev) => (prev === id ? null : id));
  }, []);

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      if (!isLoading && (input.trim() || stagedFiles.length > 0)) handleSend();
    }
  };

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typingInField =
        !!target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable);

      if (event.key === "Escape") {
        setShowSearchMenu(false);
        setShowSessionSidebar(false);
        setOpenActionMenuId(null);
        if (showChatSearch) {
          setShowChatSearch(false);
          setChatSearchQuery("");
        }
        return;
      }

      if (event.key === "/" && !typingInField) {
        event.preventDefault();
        textareaRef.current?.focus();
        return;
      }

      if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
        if (!isLoading && (input.trim() || stagedFiles.length > 0)) {
          event.preventDefault();
          handleSend();
        }
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [stagedFiles, handleSend, input, isLoading, showChatSearch]);

  const searchModeLabels: Record<SearchMode, string> = {
    disabled: "No Search",
    web_search: "Web Search",
    deep_research: "Deep Research",
  };

  const sortedSessions = useMemo(
    () => [...sessions].sort((a, b) => b.updatedAt - a.updatedAt),
    [sessions],
  );
  const userInitials = useMemo(() => {
    const username = user?.username?.trim();
    const email = user?.email?.trim();
    const base = username || email || "User";
    const parts = base.split(/\s+/).filter(Boolean);
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return `${parts[0][0] || ""}${parts[1][0] || ""}`.toUpperCase();
  }, [user?.email, user?.username]);

  const activeSession = useMemo(
    () => sessions.find((s) => s.id === activeSessionId) ?? null,
    [sessions, activeSessionId],
  );

  const displayMessages = useMemo(() => {
    if (!chatSearchQuery.trim()) return messages;
    const q = chatSearchQuery.toLowerCase();
    return messages.filter((m) => m.content.toLowerCase().includes(q));
  }, [messages, chatSearchQuery]);

  const canSend =
    !isLoading && (stagedFiles.length > 0 || Boolean(input.trim()));

  // suppress unused warning — DJANGO_API_URL is used indirectly via djangoApi
  void DJANGO_API_URL;

  if (!sessionReady) {
    return (
      <AppLayout title="AI Tutor">
        <div className="grid place-items-center h-full min-h-[60vh]">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 size={18} className="animate-spin" />
            Loading your sessions...
          </div>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout title="AI Tutor" mainClassName="overflow-hidden relative pb-0">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute inset-0 bg-grid opacity-[0.2] dark:opacity-[0.1]" />
          <div
            className="absolute inset-0 opacity-[0.55] dark:opacity-[0.35]"
            style={{
              background:
                "radial-gradient(120% 70% at 0% 0%, color-mix(in oklch, var(--primary) 22%, transparent), transparent 55%), radial-gradient(100% 60% at 100% 0%, color-mix(in oklch, var(--accent) 35%, transparent), transparent 60%), radial-gradient(120% 80% at 50% 100%, color-mix(in oklch, var(--primary) 14%, transparent), transparent 65%)",
            }}
          />
          <motion.div
            aria-hidden
            className="absolute -top-24 left-1/2 -translate-x-1/2 w-[140%] h-64 blur-3xl opacity-30 dark:opacity-20"
            style={{
              background:
                "linear-gradient(95deg, color-mix(in oklch, var(--primary) 55%, transparent), color-mix(in oklch, var(--accent) 48%, transparent), color-mix(in oklch, var(--primary) 38%, transparent))",
            }}
            animate={{ x: [-80, 40, -80], rotate: [-4, 2, -4] }}
            transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            aria-hidden
            className="absolute top-[18%] right-[8%] w-56 h-56 rounded-full blur-3xl bg-cyan-500/25 dark:bg-cyan-500/15"
            animate={{ y: [0, -26, 0], scale: [1, 1.08, 1] }}
            transition={{ duration: 9.2, repeat: Infinity, ease: "easeInOut" }}
          />
          <motion.div
            aria-hidden
            className="absolute bottom-[8%] left-[10%] w-72 h-72 rounded-full blur-3xl bg-primary/25 dark:bg-primary/18"
            animate={{ y: [0, 22, 0], x: [0, 12, 0], scale: [1, 0.94, 1] }}
            transition={{ duration: 11.6, repeat: Infinity, ease: "easeInOut" }}
          />
        </div>

        <div className="relative h-full max-w-6xl mx-auto w-full px-3 py-3 sm:px-4 sm:py-4">
          <AnimatePresence initial={false}>
            {showDesktopSessionSidebar && (
              <motion.aside
                initial={{ x: -24, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                exit={{ x: -24, opacity: 0 }}
                transition={{ duration: 0.22, ease: "easeOut" }}
                className="hidden md:flex absolute inset-y-4 left-4 w-68 glass rounded-2xl border border-border/70 p-3 flex-col"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold text-muted-foreground">
                    Saved Sessions
                  </p>
                  <button
                    onClick={createNewSession}
                    className="h-8 px-2.5 rounded-lg border border-border text-xs font-medium hover:bg-surface-hover transition-colors"
                  >
                    New Chat
                  </button>
                </div>

                <div className="mt-3 flex-1 min-h-0 overflow-y-auto no-scrollbar space-y-1.5 pr-1">
                  {sortedSessions.map((session) => (
                    <div
                      key={session.id}
                      className={cn(
                        "group/session relative rounded-xl border transition-colors",
                        activeSessionId === session.id
                          ? "border-primary/55 bg-primary/12"
                          : "border-transparent hover:border-border/70 hover:bg-surface-hover/70",
                      )}
                    >
                      {renamingSessionId === session.id ? (
                        <input
                          autoFocus
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => commitRename(session.id, renameValue)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter")
                              commitRename(session.id, renameValue);
                            if (e.key === "Escape") setRenamingSessionId(null);
                          }}
                          className="w-full px-3 py-2 text-sm bg-transparent border-none outline-none focus:ring-1 focus:ring-primary/50 rounded-lg"
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <button
                          onDoubleClick={(e) => {
                            e.stopPropagation();
                            setRenamingSessionId(session.id);
                            setRenameValue(session.title);
                          }}
                          onClick={() => openSession(session.id)}
                          className="w-full text-left px-3 py-2.5 pr-16"
                        >
                          <p className="text-sm font-medium line-clamp-2">
                            {session.title}
                          </p>
                          <p className="text-[11px] text-muted-foreground mt-1">
                            {formatSessionTime(session.updatedAt)}
                          </p>
                        </button>
                      )}
                      {renamingSessionId !== session.id && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setRenamingSessionId(session.id);
                            setRenameValue(session.title);
                          }}
                          aria-label="Rename session"
                          className="absolute top-2 right-8 h-6 w-6 rounded-md grid place-items-center text-muted-foreground opacity-0 group-hover/session:opacity-100 hover:text-foreground hover:bg-surface-hover transition-all"
                        >
                          <Edit2 size={11} />
                        </button>
                      )}
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteSession(session.id);
                        }}
                        aria-label="Delete session"
                        className="absolute top-2 right-2 h-6 w-6 rounded-md grid place-items-center text-muted-foreground opacity-0 group-hover/session:opacity-100 hover:text-destructive hover:bg-destructive/10 transition-all"
                      >
                        <Trash2 size={12} />
                      </button>
                    </div>
                  ))}
                </div>
              </motion.aside>
            )}
          </AnimatePresence>

          <div
            className={cn(
              "h-full flex flex-col transition-[padding] duration-300 ease-out",
              showDesktopSessionSidebar ? "md:pl-71.5" : "md:pl-0",
            )}
          >
            <div
              className={cn(
                "relative min-h-0 flex-1 flex flex-col rounded-2xl border border-border/70 bg-background/55 dark:bg-background/45 backdrop-blur-xl overflow-hidden transition-colors",
                isDragActive && "border-primary/60 bg-primary/5",
              )}
              onDragEnter={(event) => {
                event.preventDefault();
                setIsDragActive(true);
              }}
              onDragOver={(event) => {
                event.preventDefault();
                if (!isDragActive) setIsDragActive(true);
              }}
              onDragLeave={(event) => {
                event.preventDefault();
                const nextTarget = event.relatedTarget as Node | null;
                if (!nextTarget || !event.currentTarget.contains(nextTarget)) {
                  setIsDragActive(false);
                }
              }}
              onDrop={(event) => {
                event.preventDefault();
                setIsDragActive(false);
                const candidate = event.dataTransfer.files?.[0] || null;
                handleSelectFile(candidate);
              }}
            >
              <div className="shrink-0 border-b border-border/60 px-3 py-2.5">
                <div className="hidden md:flex items-center justify-between gap-2">
                  <button
                    onClick={() =>
                      setShowDesktopSessionSidebar((prev) => !prev)
                    }
                    className="h-10 px-3 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors inline-flex items-center gap-2"
                  >
                    <PanelLeft size={15} />
                    {showDesktopSessionSidebar
                      ? "Hide Sessions"
                      : "Show Sessions"}
                  </button>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => {
                        setShowChatSearch((p) => !p);
                        setChatSearchQuery("");
                      }}
                      title="Search in chat"
                      className={cn(
                        "h-10 px-3 rounded-lg border text-sm hover:bg-surface-hover transition-colors inline-flex items-center gap-2",
                        showChatSearch
                          ? "border-primary/55 text-primary bg-primary/10"
                          : "border-border",
                      )}
                    >
                      <Search size={15} />
                      Search
                    </button>
                    <button
                      onClick={() =>
                        activeSession && exportSessionAsMarkdown(activeSession)
                      }
                      disabled={!messages.length}
                      title="Export conversation"
                      className="h-10 px-3 rounded-lg border border-border text-sm hover:bg-surface-hover transition-colors inline-flex items-center gap-2 disabled:opacity-40"
                    >
                      <Download size={15} />
                      Export
                    </button>
                    {!showDesktopSessionSidebar && (
                      <button
                        onClick={createNewSession}
                        className="h-10 px-3 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
                      >
                        New Chat
                      </button>
                    )}
                  </div>
                </div>

                <div className="md:hidden flex items-center justify-between gap-2">
                  <button
                    onClick={() => setShowSessionSidebar(true)}
                    className="h-10 px-3 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors inline-flex items-center gap-2"
                  >
                    <PanelLeft size={15} />
                    Sessions
                  </button>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={createNewSession}
                      className="h-10 px-3 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
                    >
                      New Chat
                    </button>
                  </div>
                </div>
              </div>

              <AnimatePresence>
                {showChatSearch && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className="overflow-hidden shrink-0 border-b border-border/60"
                  >
                    <div className="flex items-center gap-2 px-3 py-2">
                      <Search
                        size={13}
                        className="text-muted-foreground shrink-0"
                      />
                      <input
                        autoFocus
                        value={chatSearchQuery}
                        onChange={(e) => setChatSearchQuery(e.target.value)}
                        placeholder="Search messages..."
                        className="flex-1 bg-transparent text-sm focus:outline-none placeholder:text-muted-foreground"
                      />
                      {chatSearchQuery && (
                        <span className="text-[11px] text-muted-foreground">
                          {displayMessages.length} result
                          {displayMessages.length !== 1 ? "s" : ""}
                        </span>
                      )}
                      <button
                        onClick={() => {
                          setShowChatSearch(false);
                          setChatSearchQuery("");
                        }}
                        className="text-muted-foreground hover:text-foreground"
                      >
                        <X size={14} />
                      </button>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>

              {isOffline && (
                <div className="shrink-0 border-b border-destructive/35 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                  You are offline. Reconnect to continue chatting.
                </div>
              )}

              <div
                ref={scrollContainerRef}
                className="flex-1 min-h-0 overflow-y-auto no-scrollbar px-3 py-4 sm:px-5 sm:py-5"
              >
                {messages.length === 0 ? (
                  <motion.div
                    variants={welcomeVariants}
                    initial="hidden"
                    animate="show"
                    className="h-full min-h-90 flex flex-col items-center justify-center text-center gap-4"
                  >
                    <motion.div
                      variants={welcomeItemVariants}
                      className="w-16 h-16 rounded-2xl gradient-bg flex items-center justify-center glow-blue"
                    >
                      <Bot size={28} className="text-white" />
                    </motion.div>

                    <motion.div
                      variants={welcomeItemVariants}
                      className="space-y-1"
                    >
                      <h2 className="text-xl sm:text-2xl font-semibold">
                        {greeting}, {user?.username || "there"}.
                      </h2>
                      <p className="text-sm text-muted-foreground max-w-xl">
                        Ask for explanations, upload materials, and generate
                        quizzes or flashcards from any response.
                      </p>
                    </motion.div>

                    <motion.div
                      variants={welcomeItemVariants}
                      className="flex flex-wrap justify-center gap-2 max-w-2xl"
                    >
                      {suggestedPrompts.map((prompt) => (
                        <button
                          key={prompt}
                          onClick={() => {
                            setEditingSourceId(null);
                            void streamAssistantResponse({
                              prompt,
                              includeUserMessage: true,
                            });
                          }}
                          className="px-3 py-1.5 rounded-full border border-border bg-background/55 text-xs hover:border-primary/50 hover:text-primary hover:bg-background/70 transition-colors"
                        >
                          {prompt}
                        </button>
                      ))}
                    </motion.div>
                  </motion.div>
                ) : (
                  <div className="space-y-5">
                    {displayMessages.map((message) => (
                      <MessageBubble
                        key={message.id}
                        message={message}
                        user={user}
                        userInitials={userInitials}
                        copiedId={copiedId}
                        isLoading={isLoading}
                        isMenuOpen={openActionMenuId === message.id}
                        isEditing={editingSourceId === message.id}
                        onCopy={handleCopy}
                        onRetry={handleRetry}
                        onRegenerate={handleRegenerate}
                        onQuickAction={handleQuickAction}
                        onEditResend={handleEditResend}
                        onToggleMenu={handleToggleMenu}
                        onRate={handleRate}
                      />
                    ))}

                    <div ref={messagesEndRef} />
                  </div>
                )}
              </div>

              <AnimatePresence>
                {showScrollButton && (
                  <motion.button
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 6 }}
                    transition={{ duration: 0.18, ease: "easeOut" }}
                    onClick={() =>
                      messagesEndRef.current?.scrollIntoView({
                        behavior: "smooth",
                      })
                    }
                    className="absolute bottom-[88px] left-1/2 -translate-x-1/2 z-20 flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-background/90 backdrop-blur-sm text-xs font-medium text-muted-foreground hover:text-foreground hover:border-primary/50 shadow-md transition-colors"
                    aria-label="Scroll to latest message"
                  >
                    <ChevronDown size={13} />
                    Latest
                  </motion.button>
                )}
              </AnimatePresence>

              <div className="shrink-0 px-3 py-3 sm:px-4 pb-[calc(env(safe-area-inset-bottom)+0.35rem)]">
                {editingSourceId && (
                  <div className="mb-2 flex items-center justify-between rounded-lg border border-primary/35 bg-primary/10 px-2.5 py-1.5 text-xs">
                    <span>Editing a previous user message</span>
                    <button
                      onClick={() => setEditingSourceId(null)}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      Cancel
                    </button>
                  </div>
                )}

                {stagedFiles.length > 0 && (
                  <div className="mb-2 flex flex-wrap gap-2">
                    {stagedFiles.map((sf) => (
                      <div
                        key={sf.id}
                        className={cn(
                          "flex items-center gap-2 pl-2.5 pr-1.5 py-1.5 rounded-lg border text-xs transition-colors",
                          isLoading
                            ? "border-primary/40 bg-primary/8 text-primary/80"
                            : "border-border bg-background/60 hover:border-primary/30",
                        )}
                      >
                        {isLoading ? (
                          <Loader2
                            size={12}
                            className="animate-spin shrink-0"
                          />
                        ) : (
                          <FileText
                            size={12}
                            className="shrink-0 text-primary/70"
                          />
                        )}
                        <div className="min-w-0">
                          <p className="max-w-[160px] truncate font-medium leading-tight">
                            {sf.file.name}
                          </p>
                          <p className="text-[10px] text-muted-foreground leading-tight">
                            {isLoading
                              ? "Processing..."
                              : `${formatFileSize(sf.file.size)} · Ready`}
                          </p>
                        </div>
                        {!isLoading && (
                          <button
                            onClick={() => handleRemoveStagedFile(sf.id)}
                            className="ml-0.5 h-5 w-5 rounded grid place-items-center hover:bg-destructive/10 hover:text-destructive transition-colors"
                            aria-label={`Remove ${sf.file.name}`}
                          >
                            <X size={10} />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                )}


                {fileError && (
                  <p className="mb-2 text-xs text-destructive">{fileError}</p>
                )}

                <div className="flex items-end gap-2 rounded-xl border border-border/70 bg-background/45 px-2 py-1.5">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    title="Attach file"
                    className="h-11 w-11 rounded-lg text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors grid place-items-center shrink-0"
                  >
                    <Paperclip size={18} />
                  </button>

                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.pptx,.txt"
                    className="hidden"
                    onChange={(event) =>
                      handleSelectFile(event.target.files?.[0] || null)
                    }
                  />

                  <div className="relative shrink-0" data-search-menu-root>
                    <button
                      onClick={() => setShowSearchMenu((prev) => !prev)}
                      title={searchModeLabels[searchMode]}
                      className={cn(
                        "h-11 w-11 rounded-lg border transition-colors grid place-items-center",
                        searchMode !== "disabled"
                          ? "border-primary/55 text-primary bg-primary/10"
                          : "border-border text-muted-foreground hover:bg-surface-hover",
                      )}
                    >
                      <Globe size={16} />
                    </button>
                    {showSearchMenu && (
                      <div className="absolute bottom-full left-0 mb-2 z-30 rounded-lg border border-border bg-background/95 backdrop-blur-xl shadow-xl py-1 min-w-[154px]">
                        {(Object.keys(searchModeLabels) as SearchMode[]).map(
                          (mode) => (
                            <button
                              key={mode}
                              onClick={() => {
                                setSearchMode(mode);
                                setShowSearchMenu(false);
                              }}
                              className={cn(
                                "w-full text-left px-3 py-2 text-xs transition-colors",
                                searchMode === mode
                                  ? "text-primary bg-primary/10"
                                  : "text-muted-foreground hover:bg-surface-hover",
                              )}
                            >
                              {searchModeLabels[mode]}
                            </button>
                          ),
                        )}
                      </div>
                    )}
                  </div>

                  <textarea
                    ref={textareaRef}
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    onKeyDown={handleKeyDown}
                    onInput={(event) => {
                      const target = event.currentTarget;
                      target.style.height = "0px";
                      target.style.height = `${Math.min(target.scrollHeight, 170)}px`;
                    }}
                    placeholder={
                      stagedFiles.length > 0
                        ? "Add a message or send to analyze the file..."
                        : "Ask me anything... (Shift+Enter for new line)"
                    }
                    rows={1}
                    className="flex-1 bg-transparent resize-none text-sm focus:outline-none max-h-[170px] overflow-y-auto no-scrollbar placeholder:text-muted-foreground leading-relaxed py-2"
                  />

                  <button
                    onClick={isLoading ? handleStopGenerating : handleSend}
                    disabled={isLoading ? false : !canSend}
                    className={cn(
                      "h-11 w-11 rounded-lg transition-all grid place-items-center shrink-0",
                      isLoading
                        ? "bg-destructive/10 text-destructive border border-destructive/25 hover:bg-destructive/20"
                        : "gradient-bg text-white hover:opacity-90 disabled:opacity-45",
                    )}
                  >
                    {isLoading ? <Square size={16} /> : <Send size={18} />}
                  </button>
                </div>

                <div className="mt-2 flex items-center justify-between gap-2 text-[11px] text-muted-foreground">
                  <span>
                    {stagedFiles.length > 0
                      ? `${stagedFiles.length} file${stagedFiles.length > 1 ? "s" : ""} staged · Send to analyze`
                      : "AI can make mistakes. Verify important details."}
                  </span>
                  <span className="hidden md:inline">
                    Shortcuts: `/` focus, `Ctrl/Cmd+Enter` send, `Esc` close
                    menu
                  </span>
                </div>
              </div>
            </div>

            <AnimatePresence>
              {showSessionSidebar && (
                <motion.div
                  className="md:hidden absolute inset-0 z-40"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.2, ease: "easeOut" }}
                >
                  <button
                    onClick={() => setShowSessionSidebar(false)}
                    className="absolute inset-0 bg-black/50 backdrop-blur-[1px]"
                    aria-label="Close sessions sidebar"
                  />
                  <motion.aside
                    className="absolute inset-y-0 left-0 w-[82%] max-w-[320px] glass border-r border-border/70 p-3 flex flex-col"
                    initial={{ x: -28 }}
                    animate={{ x: 0 }}
                    exit={{ x: -28 }}
                    transition={{ duration: 0.24, ease: "easeOut" }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold">Saved Sessions</p>
                      <button
                        onClick={() => setShowSessionSidebar(false)}
                        className="h-8 w-8 rounded-lg border border-border text-muted-foreground hover:text-foreground hover:bg-surface-hover grid place-items-center transition-colors"
                      >
                        <X size={14} />
                      </button>
                    </div>

                    <button
                      onClick={createNewSession}
                      className="mt-3 h-10 rounded-lg border border-border text-sm font-medium hover:bg-surface-hover transition-colors"
                    >
                      New Chat
                    </button>

                    <div className="mt-3 flex-1 min-h-0 overflow-y-auto no-scrollbar space-y-1.5 pr-1">
                      {sortedSessions.map((session) => (
                        <div
                          key={session.id}
                          className={cn(
                            "relative rounded-xl border transition-colors",
                            activeSessionId === session.id
                              ? "border-primary/55 bg-primary/12"
                              : "border-transparent hover:border-border/70 hover:bg-surface-hover/70",
                          )}
                        >
                          {renamingSessionId === session.id ? (
                            <input
                              autoFocus
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              onBlur={() =>
                                commitRename(session.id, renameValue)
                              }
                              onKeyDown={(e) => {
                                if (e.key === "Enter")
                                  commitRename(session.id, renameValue);
                                if (e.key === "Escape")
                                  setRenamingSessionId(null);
                              }}
                              className="w-full px-3 py-2 text-sm bg-transparent border-none outline-none focus:ring-1 focus:ring-primary/50 rounded-lg"
                              onClick={(e) => e.stopPropagation()}
                            />
                          ) : (
                            <button
                              onDoubleClick={(e) => {
                                e.stopPropagation();
                                setRenamingSessionId(session.id);
                                setRenameValue(session.title);
                              }}
                              onClick={() => openSession(session.id)}
                              className="w-full text-left px-3 py-2.5 pr-16"
                            >
                              <p className="text-sm font-medium line-clamp-2">
                                {session.title}
                              </p>
                              <p className="text-[11px] text-muted-foreground mt-1">
                                {formatSessionTime(session.updatedAt)}
                              </p>
                            </button>
                          )}
                          {renamingSessionId !== session.id && (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setRenamingSessionId(session.id);
                                setRenameValue(session.title);
                              }}
                              aria-label="Rename session"
                              className="absolute top-2 right-8 h-6 w-6 rounded-md grid place-items-center text-muted-foreground hover:text-foreground hover:bg-surface-hover transition-colors"
                            >
                              <Edit2 size={11} />
                            </button>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              deleteSession(session.id);
                            }}
                            aria-label="Delete session"
                            className="absolute top-2 right-2 h-6 w-6 rounded-md grid place-items-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
                          >
                            <Trash2 size={12} />
                          </button>
                        </div>
                      ))}
                    </div>

                    {isLoading && (
                      <button
                        onClick={handleStopGenerating}
                        className="mt-3 h-10 rounded-lg bg-destructive text-white text-sm font-semibold hover:bg-destructive/90 transition-colors inline-flex items-center justify-center gap-1.5"
                      >
                        <Square size={13} />
                        Stop
                      </button>
                    )}
                  </motion.aside>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
    </AppLayout>
  );
}
