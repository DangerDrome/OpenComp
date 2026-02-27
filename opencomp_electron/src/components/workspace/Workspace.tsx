import { useState, useCallback, useRef, useEffect } from 'react';
import './Workspace.css';

interface WorkspaceProps {
  leftSidebar?: React.ReactNode;
  rightSidebar?: React.ReactNode;
  children: React.ReactNode;
  ribbon?: React.ReactNode;
  bottomBar?: React.ReactNode;
}

const MIN_SIDEBAR_WIDTH = 180;
const MAX_SIDEBAR_WIDTH = 400;
const DEFAULT_LEFT_WIDTH = 220;
const DEFAULT_RIGHT_WIDTH = 220;

const Workspace = ({
  leftSidebar,
  rightSidebar,
  children,
  ribbon,
  bottomBar,
}: WorkspaceProps) => {
  const [leftWidth, setLeftWidth] = useState(DEFAULT_LEFT_WIDTH);
  const [rightWidth, setRightWidth] = useState(DEFAULT_RIGHT_WIDTH);
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [isResizingLeft, setIsResizingLeft] = useState(false);
  const [isResizingRight, setIsResizingRight] = useState(false);

  const workspaceRef = useRef<HTMLDivElement>(null);

  // Handle left sidebar resize
  const handleLeftResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingLeft(true);
  }, []);

  // Handle right sidebar resize
  const handleRightResizeStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizingRight(true);
  }, []);

  // Handle mouse move for resizing
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!workspaceRef.current) return;

      const rect = workspaceRef.current.getBoundingClientRect();

      if (isResizingLeft) {
        const newWidth = e.clientX - rect.left - (ribbon ? 44 : 0);
        setLeftWidth(Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, newWidth)));
      }

      if (isResizingRight) {
        const newWidth = rect.right - e.clientX;
        setRightWidth(Math.max(MIN_SIDEBAR_WIDTH, Math.min(MAX_SIDEBAR_WIDTH, newWidth)));
      }
    };

    const handleMouseUp = () => {
      setIsResizingLeft(false);
      setIsResizingRight(false);
    };

    if (isResizingLeft || isResizingRight) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizingLeft, isResizingRight, ribbon]);

  // Toggle sidebars
  const toggleLeftSidebar = useCallback(() => {
    setLeftCollapsed((prev) => !prev);
  }, []);

  const toggleRightSidebar = useCallback(() => {
    setRightCollapsed((prev) => !prev);
  }, []);

  return (
    <div className="workspace" ref={workspaceRef}>
      {/* Left ribbon (icon bar) */}
      {ribbon && (
        <div className={`workspace-ribbon mod-left ${leftCollapsed ? 'is-collapsed' : ''}`}>
          <div className="workspace-ribbon-content">
            {ribbon}
          </div>
          <button
            className="workspace-ribbon-collapse-btn"
            onClick={toggleLeftSidebar}
            title={leftCollapsed ? 'Expand' : 'Collapse'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {leftCollapsed ? (
                <path d="M9 18l6-6-6-6" />
              ) : (
                <path d="M15 18l-6-6 6-6" />
              )}
            </svg>
          </button>
        </div>
      )}

      {/* Left sidebar */}
      {leftSidebar && (
        <div
          className={`workspace-split mod-left-split ${leftCollapsed ? 'is-collapsed' : ''}`}
          style={{ width: leftCollapsed ? 0 : leftWidth }}
        >
          <div className="workspace-split-content">
            {leftSidebar}
          </div>
          {!leftCollapsed && (
            <div
              className="workspace-leaf-resize-handle"
              onMouseDown={handleLeftResizeStart}
            />
          )}
        </div>
      )}

      {/* Main content area */}
      <div className="workspace-split mod-root">
        <div className="workspace-split-content">
          {children}
        </div>
        {bottomBar && (
          <div className="workspace-bottom-bar">
            {bottomBar}
          </div>
        )}
      </div>

      {/* Right sidebar */}
      {rightSidebar && (
        <div
          className={`workspace-split mod-right-split ${rightCollapsed ? 'is-collapsed' : ''}`}
          style={{ width: rightCollapsed ? 0 : rightWidth }}
        >
          <div
            className="workspace-leaf-resize-handle mod-left"
            onMouseDown={handleRightResizeStart}
          />
          <div className="workspace-split-content">
            {rightSidebar}
          </div>
          <button
            className="workspace-ribbon-collapse-btn mod-right"
            onClick={toggleRightSidebar}
            title={rightCollapsed ? 'Expand' : 'Collapse'}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              {rightCollapsed ? (
                <path d="M15 18l-6-6 6-6" />
              ) : (
                <path d="M9 18l6-6-6-6" />
              )}
            </svg>
          </button>
        </div>
      )}
    </div>
  );
};

export default Workspace;
