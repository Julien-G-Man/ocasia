import React, { useState, useRef, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { FontAwesomeIcon } from '@fortawesome/react-fontawesome';
import { faPlus, faTimes, faSpinner, faEllipsisV, faTrash } from '@fortawesome/free-solid-svg-icons';
import './Sidebar.css'; 

/**
 * Sidebar component for chatbot session management.
 * Displays list of past chat sessions with ability to switch between them.
 * Provides "New Chat" button to start fresh conversations.
 */
const Sidebar = ({
  sessions,              // Array of session objects: {id, message_count, last_message, created_at}
  currentSessionId,      // ID of currently active session
  onNewChat,             // Callback when "New Chat" button clicked
  onSwitchSession,       // Callback with (sessionId) when session selected
  onDeleteSession,       // Callback with (sessionId) when delete is confirmed
  onRenameSession,       // Callback with (sessionId, title) when rename is confirmed
  isOpen,                // Sidebar visibility (controls both desktop collapse and mobile drawer)
  onToggleSidebar,       // Callback to toggle sidebar open/closed
  isLoading,             // Loading state for session list
  user,                  // User object (to check authentication)
  isAuthenticated,       // Whether the visitor is signed in
}) => {
  const [openMenuSessionId, setOpenMenuSessionId] = useState(null);
  const [renameModal, setRenameModal] = useState(null); // {sessionId, title}
  const [renameValue, setRenameValue] = useState('');
  const sidebarRef = useRef(null);
  const renameInputRef = useRef(null);

  // Hide sidebar on mobile when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      // Only applies to mobile
      if (window.innerWidth > 768) return;

      if (sidebarRef.current && !sidebarRef.current.contains(e.target)) {
        // Check if click was on the toggle button
        const toggleBtn = document.querySelector('.sidebar-toggle-mobile');
        if (toggleBtn && !toggleBtn.contains(e.target)) {
          onToggleSidebar?.();
        }
      }
    };

    if (isOpen) {
      document.addEventListener('click', handleClickOutside);
      return () => document.removeEventListener('click', handleClickOutside);
    }
  }, [isOpen, onToggleSidebar]);

  useEffect(() => {
    const handleClickOutsideMenu = (e) => {
      if (sidebarRef.current && !sidebarRef.current.contains(e.target)) {
        setOpenMenuSessionId(null);
      }
    };

    if (openMenuSessionId) {
      document.addEventListener('click', handleClickOutsideMenu);
      return () => document.removeEventListener('click', handleClickOutsideMenu);
    }
  }, [openMenuSessionId]);

  useEffect(() => {
    if (renameModal && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renameModal]);

  // Format timestamp to readable format (e.g., "Today 2:45 PM")
  const formatTimestamp = (isoString) => {
    try {
      const date = new Date(isoString);
      const now = new Date();
      const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const yesterday = new Date(today);
      yesterday.setDate(yesterday.getDate() - 1);

      const dateParam = new Date(date.getFullYear(), date.getMonth(), date.getDate());

      let dateStr;
      if (dateParam.getTime() === today.getTime()) {
        dateStr = 'Today';
      } else if (dateParam.getTime() === yesterday.getTime()) {
        dateStr = 'Yesterday';
      } else if (now.getTime() - date.getTime() < 7 * 24 * 60 * 60 * 1000) {
        dateStr = date.toLocaleDateString('en-US', { weekday: 'short' });
      } else {
        dateStr = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
      }

      const timeStr = date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
      return `${dateStr} ${timeStr}`;
    } catch {
      return 'Unknown';
    }
  };

  const handleSessionClick = (session) => {
    const sessionKey = session.session_id || session.id;
    if (sessionKey === currentSessionId) return;
    onSwitchSession?.(sessionKey);
    if (window.innerWidth <= 768) onToggleSidebar?.();
  };

  const handleToggleSessionMenu = (sessionId, e) => {
    e?.stopPropagation();
    setOpenMenuSessionId((current) => (current === sessionId ? null : sessionId));
  };

  const handleDeleteSession = (session) => {
    const sessionKey = session.session_id || session.id;
    if (!window.confirm('Delete this chat session? This cannot be undone.')) {
      return;
    }
    onDeleteSession?.(sessionKey);
    setOpenMenuSessionId(null);
  };

  const handleRenameSession = (session) => {
    const sessionKey = session.session_id || session.id;
    const currentTitle = session.title || session.last_message || 'Chat session';
    setRenameValue(currentTitle);
    setRenameModal({ sessionId: sessionKey, title: currentTitle });
    setOpenMenuSessionId(null);
  };

  const handleSubmitRename = (e) => {
    e.preventDefault();

    const trimmedTitle = renameValue.trim();
    if (!trimmedTitle) {
      alert('Session title cannot be empty.');
      return;
    }

    onRenameSession?.(renameModal.sessionId, trimmedTitle);
    setRenameModal(null);
    setRenameValue('');
  };

  const handleCancelRename = () => {
    setRenameModal(null);
    setRenameValue('');
  };

  return (
    <>
      {/* Mobile overlay backdrop */}
      {isOpen && window.innerWidth <= 768 && (
        <div
          className="sidebar-overlay open"
          onClick={() => onToggleSidebar?.()}
          aria-hidden="true"
        />
      )}

      {/* Sidebar */}
      <div
        ref={sidebarRef}
        className={`sidebar-wrapper ${isOpen ? 'open' : ''}`}
        role="navigation"
        aria-label="Chat sessions"
      >
        {/* Header */}
        <div className="sidebar-header">
          <h2 className="sidebar-title"> </h2>
          {/* Close button visible on mobile */}
          <button
            className="sidebar-close-btn"
            onClick={() => onToggleSidebar?.()}
            title="Close sidebar"
            aria-label="Close sidebar"
          >
            <FontAwesomeIcon icon={faTimes} />
          </button>
        </div>

        {/* New Chat Button */}
        <button
          className="new-chat-btn"
          onClick={() => {
            onNewChat?.();
            // Close sidebar on mobile after creating new chat
            if (window.innerWidth <= 768) {
              onToggleSidebar?.();
            }
          }}
          title="Start a new conversation"
        >
          <FontAwesomeIcon icon={faPlus} />
          New Chat
        </button>

        {/* Sessions List */}
        <div className="sidebar-sessions">
          {isLoading ? (
            <div className="sidebar-loading">
              <div className="sidebar-loading-spinner">
                <FontAwesomeIcon icon={faSpinner} spin /> Loading past messages...
              </div>
            </div>
          ) : sessions && sessions.length > 0 ? (
            <>
              <div className="sessions-label">Previous Conversations</div>
              {sessions.map((session) => (
                <div
                  key={session.session_id || session.id}
                  className={`session-item ${(session.session_id || session.id) === currentSessionId ? 'active' : ''}`}
                  onClick={() => handleSessionClick(session)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      handleSessionClick(session);
                    }
                  }}
                  title={session.last_message || 'No messages'}
                >
                  <div className="session-item-header">
                    <div className="session-item-header-left">
                      <div className="session-title-row">
                        <span className="session-title-text">{session.title || 'Untitled session'}</span>
                        <span className="session-badge">{session.message_count} msg</span>
                      </div>
                      <span className="session-timestamp">{formatTimestamp(session.created_at)}</span>
                    </div>
                    <button
                      type="button"
                      className="session-actions-btn"
                      onClick={(e) => handleToggleSessionMenu(session.session_id || session.id, e)}
                      aria-label="Session actions"
                      title="Session actions"
                    >
                      <FontAwesomeIcon icon={faEllipsisV} />
                    </button>
                  </div>
                  <div className="session-preview">
                    {session.last_message || '(Empty conversation)'}
                  </div>
                  {openMenuSessionId === (session.session_id || session.id) && (
                    <div className="session-actions-menu" onClick={(e) => e.stopPropagation()}>
                      <button
                        type="button"
                        className="session-actions-menu-item"
                        onClick={() => handleRenameSession(session)}
                      >
                        Rename
                      </button>
                      <button
                        type="button"
                        className="session-actions-menu-item danger"
                        onClick={() => handleDeleteSession(session)}
                      >
                        <FontAwesomeIcon icon={faTrash} />
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </>
          ) : (
            <div className="sidebar-empty">
              <div className="sidebar-empty-icon">💬</div>
              {isAuthenticated ? (
                <>
                  <div>No previous conversations yet.</div>
                  <div style={{ fontSize: '0.8rem', marginTop: '8px' }}>
                    Start chatting to create your first session!
                  </div>
                </>
              ) : (
                <>
                  <div>No previous conversations yet.</div>
                  <div className="sidebar-empty-copy">
                    Sign up to save your chats and come back to them later.
                  </div>
                  <Link to="/signup" className="sidebar-signup-btn sidebar-signup-empty-btn">
                    Sign up
                  </Link>
                </>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Rename modal */}
      {renameModal && (
        <div className="rename-modal-overlay" onClick={handleCancelRename}>
          <div className="rename-modal" onClick={(e) => e.stopPropagation()}>
            <h3 className="rename-modal-title">Rename conversation</h3>
            <form onSubmit={handleSubmitRename} className="rename-modal-form">
              <label className="rename-modal-label" htmlFor="session-title-input">
                Session name
              </label>
              <input
                id="session-title-input"
                ref={renameInputRef}
                className="rename-modal-input"
                type="text"
                value={renameValue}
                onChange={(e) => setRenameValue(e.target.value)}
                maxLength={120}
                placeholder="Give this conversation a name"
              />
              <div className="rename-modal-buttons">
                <button type="button" className="confirmation-modal-btn cancel" onClick={handleCancelRename}>
                  Cancel
                </button>
                <button type="submit" className="confirmation-modal-btn confirm">
                  Save name
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
};

export default Sidebar;
